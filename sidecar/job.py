r"""The Item model and the per-item error boundary.

Moved here from Phase 8 on the architect's row 4: Phase 6 is the first phase
that can fail HALFWAY through a job -- one hostile archive among five benign
ones -- so it is the first phase that needs somewhere to put "this item was
skipped, and here is why". Inventing that here and replacing it in Phase 8
would mean two error models across three phases, so Phase 8 inherits this one
and adds only the queue, the scheduling and `Job.tsx` on top.

**Phase 8 adds the queue on top of that boundary, unchanged.** `scan` turns a
folder into the ordered list of things in it; `Job` runs those things on a
few worker threads, one item at a time each, every item through `run_item`
exactly as before; `run_job` is now `Job(...).start().wait()` and its callers
did not change. The queue is WIDER than the LLM cap on purpose -- see
WORKERS -- because the cap is llm.py's job and the queue's job is to keep the
models and the provider both busy. Cancellation is a plumbing point here:
`Job.cancel` stops items that have not started. Interrupting an item that is
mid-page, and leaving no partial output behind when it does, is Phase 9's
(AC-13), and this file says so rather than half-doing it.

**The boundary is total.** `run_item` returns an Item for every input, in every
case: a rejected archive, a file that is not an archive at all, a corrupt one,
a provider outage, an unexpected `KeyError` out of a library. One bad file in a
two-hundred-item job must not take the other hundred and ninety-nine with it,
and the only way to promise that is to catch `Exception` and say so out loud
rather than to enumerate the exceptions we happen to have seen.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import threading
import traceback
from collections import deque
from dataclasses import dataclass, field

from . import atomic, pipeline, safety
from .containers import archive, pdf
from .containers.read_cbz import _natural_key

# How many items run at once. One more than llm.MAX_CONCURRENT, and that is
# the reasoning rather than a coincidence: the provider cap lives in llm.py
# and is the ONLY thing allowed to bound provider load, so the queue must be
# able to offer the gate more than it will take -- otherwise a broken gate
# would be hidden by a narrow queue, and check_batch's "the stub could have
# seen more than 3" control would be vacuous. Wider than 4 buys nothing: the
# detector, the OCR and the eraser's models are serialised behind
# pipeline._MODEL_LOCK, so the fourth worker is already mostly waiting for a model.
WORKERS = 4

CANCELLED_REASON = "cancelled before start"

# The lock run_item's warning dedupe takes when the caller has no Job to
# lend one: module-level so two lockless callers are still serialised,
# rather than a throwaway Lock() per call that serialises nothing.
_WARN_LOCK = threading.Lock()

# The item-level progress contract, the way STAGES is the page-level one.
# check_archives asserts against these names rather than counting events: a
# renamed stage silently stops the UI's item list updating, and a count cannot
# tell that from three of the right events.
ITEM_STAGES = ("item_start", "item_done")

OK, SKIPPED, FAILED, CANCELLED = "ok", "skipped", "failed", "cancelled"

# Loose images are items too -- AC-7's folder mixes them with archives -- and
# Phase 0's run_page already handles one. Listed here so `classify` has one
# place that decides what an item IS.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


@dataclass
class Item:
    """One input file and what became of it.

    `status` is the machine-readable outcome and `reason` is why, in the user's
    words. An Item with status SKIPPED, FAILED or CANCELLED always carries a
    non-empty reason -- a skipped item with no reason is a file that vanished
    from the user's job with no explanation, which is the failure mode AC-7's
    "per-item reason" clause exists to forbid. CANCELLED (Phase 9) is its own
    status because "skipped" means the product declined the item and
    "cancelled" means the user did; the reason says how far it got.
    """

    path: str
    item_id: str
    kind: str = "unsupported"
    status: str = "pending"
    reason: str = ""
    warning: str = ""
    output: str = ""
    pages: int = 0
    record: dict = field(default_factory=dict, repr=False)

    def as_dict(self) -> dict:
        # The public fields by name, not dataclasses.asdict: that deep-copies
        # `record` -- every page's polygons -- and then throws it away, on
        # every item on every 500ms poll of the queue view.
        return {
            "path": self.path, "item_id": self.item_id, "kind": self.kind,
            "status": self.status, "reason": self.reason, "warning": self.warning,
            "output": self.output, "pages": self.pages,
        }


def classify(path) -> Item:
    """What kind of item `path` is, by NAME alone.

    By name, because classification runs over a directory listing and opening
    every file on the user's disk to find out is the cost AC-7's batch cannot
    pay. The signature is read later, by `archive.detect_format`, on the items
    this admits -- so a `.cbz` that is really a 7z is classified as an archive
    here and read as a 7z there, which is the division that makes both cheap.
    """
    name = os.path.basename(os.fspath(path))
    ext = os.path.splitext(name)[1].lower()
    if archive.is_archive(path):
        return Item(path=os.fspath(path), item_id=name, kind="archive")
    if pdf.is_pdf(path):
        # Phase 7. A container like an archive -- pipeline.run_item reads it
        # page by page through the same budget and repacks it -- and it is
        # its own kind because the UI's item list says what a thing is.
        return Item(path=os.fspath(path), item_id=name, kind="pdf")
    if ext in IMAGE_SUFFIXES:
        return Item(path=os.fspath(path), item_id=name, kind="image")
    return Item(path=os.fspath(path), item_id=name, kind="unsupported",
                status=SKIPPED, reason=f"unsupported file type {ext or '(none)'}")


def _discard_output(item: Item, dest_dir) -> None:
    """Remove what a REFUSED item already wrote. Best effort, never raises.

    The three byte rules can only fire mid-stream -- a bomb is only a bomb once
    it has expanded -- so by the time an archive is refused, pages 1..k have
    been delivered and cached. Reporting the item "skipped" while leaving its
    translated pages in the output directory hands the user pages from an
    archive the product refused, mixed in with legitimate output. The per-item
    directory is what makes the cleanup safe: there is nothing else in it.
    """
    if item.kind not in ("archive", "pdf"):
        return
    out = pipeline.item_dir(dest_dir, item.item_id)
    try:
        shutil.rmtree(atomic.long_path(out), ignore_errors=True)
    except OSError:
        pass


def run_item(item: Item, dest_dir, job_id, client=None,
             lang: str = pipeline.DEFAULT_LANG,
             source: str = pipeline.DEFAULT_SOURCE,
             warned: set | None = None,
             warned_lock: threading.Lock | None = None,
             cancel: threading.Event | None = None) -> Item:
    """Process one item. Never raises.

    `cancel` (Phase 9) is the job's token, handed down to the pipeline, which
    checks it at page boundaries. A cancelled item comes back CANCELLED with
    its delivered page count and no output archive; its finished pages are
    left in place -- complete files, and the cache the next run reads.

    `warned` is the per-JOB warning set. AC-6 says the cbr->cbz warning is
    surfaced "once", and once means once per job: a job of thirty `.cbr` items
    that showed thirty identical dialogs would satisfy a naive count and annoy
    the user thirty times. The set is owned by the caller because the scope the
    word "once" refers to is the job, and this function only sees one item.
    `warned_lock` is the Job's lock (Phase 8): with four workers the
    check-then-add on the set is a race, and a race here is exactly the
    "twice" the word "once" forbids.
    """
    pipeline.emit("item_start", item.item_id, 0, 0)
    try:
        if item.status == SKIPPED:
            # Classified out before it got here -- an unsupported extension.
            # Still emitted and still reported, because a file the user put in
            # the folder and never heard about again is the complaint.
            return item

        if item.kind == "image":
            record = pipeline.run_page(item.path, dest_dir, 1, client, source, lang, item_id=item.item_id,
                                       cancel=cancel)
            item.output = record.get("output", "")
            item.pages = 1
            item.record = record
            item.status = OK
            return item

        # An archive or a PDF: both are "every page through the cache, then
        # repack", and pipeline.run_item tells them apart by signature.
        record = pipeline.run_item(
            item.path, dest_dir, job_id, item.item_id, client, lang, source,
            cancel=cancel,
        )
        item.record = record
        item.pages = len(record.get("pages", []))
        item.output = record.get("archive", "")
        warning = record.get("format_warning")
        if warning:
            seen = warned if warned is not None else set()
            with warned_lock or _WARN_LOCK:
                if warning not in seen:
                    seen.add(warning)
                    item.warning = warning
        item.status = OK
        return item

    # Reason BEFORE status in every branch below: a poll between the two
    # assignments must not see SKIPPED with an empty reason, the state the
    # Item docstring forbids.
    except pipeline.Cancelled as e:
        item.pages = e.pages_done
        # An item that stopped before its first page landed is, to the user,
        # one that never started; the count only helps once it is non-zero.
        item.reason = (CANCELLED_REASON if e.pages_done == 0 else
                       f"cancelled after {e.pages_done} page{'s' if e.pages_done != 1 else ''}")
        item.status = CANCELLED
        return item
    except safety.UnsafeArchive as e:
        # The one failure with a machine-readable reason. The UI shows
        # e.reason's rule name; the detail stays in the message.
        item.reason = f"unsafe archive ({e.reason}): {e.member}"
        item.status = SKIPPED
        _discard_output(item, dest_dir)
        return item
    except archive.UnsupportedArchive as e:
        item.reason = e.reason
        item.status = SKIPPED
        return item
    except archive.LibarchiveMissing as e:
        item.reason = e.reason
        item.status = SKIPPED
        return item
    except Exception as e:  # noqa: BLE001 -- the boundary; see module docstring
        # Deliberately broad, and deliberately loud on stderr. A library we do
        # not own raising something we did not predict is the case this
        # boundary exists for; narrowing it to the exceptions seen so far means
        # the first unseen one takes the whole job down.
        item.reason = f"{type(e).__name__}: {e}"
        item.status = FAILED
        traceback.print_exc()
        return item
    finally:
        pipeline.emit("item_done", item.item_id, item.pages, 100)


def disambiguate(items: list[Item]) -> list[Item]:
    """Give every item in a job a DISTINCT item_id. Mutates and returns them.

    `item_id` is the per-item output directory name and half of the cache's
    placement key, so two items sharing one is not a cosmetic clash: the second
    volume's pages overwrite the first's on disk, and the placement records the
    first job wrote go on pointing at files the second rewrote, which corrupts
    AC-13's resume as well as the output. A folder holding `art/vol1.cbz` and
    `text/vol1.cbz` is the ordinary case, not a contrived one.

    Both colliding items are renamed, not just the second: leaving one holding
    the plain name would make which volume kept it depend on listing order,
    which is the kind of difference that shows up as "it worked yesterday". The
    suffix is a digest of the ABSOLUTE path, so the same file resolves to the
    same id on every run and a resumed job finds its own pages.
    """
    counts: dict[str, int] = {}
    for item in items:
        counts[item.item_id] = counts.get(item.item_id, 0) + 1
    for item in items:
        if counts[item.item_id] > 1:
            stem, ext = os.path.splitext(item.item_id)
            digest = hashlib.sha256(
                os.path.abspath(item.path).encode("utf-8")).hexdigest()[:8]
            item.item_id = f"{stem}-{digest}{ext}"
    return items


def scan(directory) -> list[str]:
    """The files in `directory`, top level only, in natural order.

    Top level only: a folder of volumes is what AC-7 describes, and a
    recursive walk would pick up whatever an earlier job left in a
    subfolder -- including the per-item output directories this very
    program writes. Dotfiles and `*.tmp` are skipped for the same reason:
    `.DS_Store` is not an item, and a `.tmp` is atomic_write's in-flight
    file. Natural order, shared with the page readers, so `ch10.cbz` sorts
    after `ch2.cbz` the way the user's file manager shows them.
    """
    directory = os.fspath(directory)
    if not os.path.isdir(atomic.long_path(directory)):
        raise NotADirectoryError(f"not a directory: {directory}")
    names = []
    for name in os.listdir(atomic.long_path(directory)):
        if name.startswith(".") or name.lower().endswith(".tmp"):
            continue
        if os.path.isfile(atomic.long_path(os.path.join(directory, name))):
            names.append(name)
    return [os.path.join(directory, n) for n in sorted(names, key=_natural_key)]


class Job:
    """Every item, through the boundary, on `workers` threads. Never raises.

    Construct, `start()`, then either `wait()` or poll `status()` -- the
    status is a snapshot taken under the job's lock, safe from any thread
    while the workers run, and is the dict `run_job` always returned plus
    `pending`, `running` and `done`. The Item objects are the workers'; the
    snapshot copies them.

    Items are claimed from one queue in the order `scan` gave them, so a
    four-worker job over ten volumes translates volumes 1-4 first, not a
    random four. The cbr->cbz warning stays "once per job" under
    concurrency because the shared `warned` set is guarded here: two workers
    finishing two `.cbr` items in the same millisecond would otherwise both
    see an empty set and both surface the warning.

    `cancel()` sets the token every worker hands to the pipeline (Phase 9,
    AC-13). Items that have not started come back CANCELLED with
    CANCELLED_REASON; an item mid-run stops at its next page boundary and
    comes back CANCELLED with the pages it delivered; the job runs to `done`.
    Nothing partial is left behind: every write is atomic and the repack of
    a cancelled item never starts.
    """

    def __init__(self, job_id, paths, dest_dir, client=None,
                 lang: str = pipeline.DEFAULT_LANG,
                 source: str = pipeline.DEFAULT_SOURCE,
                 workers: int = WORKERS):
        self.job_id = str(job_id)
        self.dest_dir = os.fspath(dest_dir)
        self.client = client
        self.lang = lang
        self.source = source
        self.workers = max(1, int(workers))
        self.items = disambiguate([classify(p) for p in paths])
        self.warned: set[str] = set()
        self._lock = threading.Lock()
        # A deque under the job's own lock, not a queue.Queue: every claim
        # already runs under _lock (see _worker), so a second lock inside the
        # queue would guard nothing.
        self._pending: deque[Item] = deque()
        self._running: set[str] = set()
        self._cancel = threading.Event()
        # The vision probe runs once per job, on whichever worker starts
        # first; the others block on this lock until it has, so no page
        # goes out before the client knows whether an image can go with it.
        self._vision_lock = threading.Lock()
        self._vision_done = False
        self._done = threading.Event()
        self._threads: list[threading.Thread] = []
        self._started = False

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> "Job":
        with self._lock:
            if self._started:
                return self
            self._started = True
            self._pending.extend(self.items)
            if not self.items:
                self._done.set()
                return self
            self._threads = [
                threading.Thread(target=self._worker, name=f"job-{self.job_id}-{n}",
                                 daemon=True)
                for n in range(min(self.workers, len(self.items)))
            ]
        for t in self._threads:
            t.start()
        return self

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def done(self) -> bool:
        return self._done.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until every item has a terminal status. False on timeout."""
        return self._done.wait(timeout)

    # -- the workers -------------------------------------------------------

    def _ensure_vision(self) -> None:
        """AC-9, the half the product had never wired: probe once per job.

        Before this, LLMClient.probe_vision existed, translate_page honoured
        text_only, and check_probe proved the latch -- and nothing in the app
        called the probe, so a text-only model was never detected and every
        page went out with an image it could not read. The result is per job
        and surfaces ONCE, through the same `warned` set the cbr->cbz notice
        uses: D.4 asks for one UI notice per job, not one per page.

        Not in start(): POST /api/job answers with the first status snapshot
        immediately, and a probe is a provider round trip.
        """
        if self.client is None or self._cancel.is_set():
            return
        with self._vision_lock:
            if self._vision_done:
                return
            self._vision_done = True
            try:
                ok, reason = self.client.ensure_vision()
            except Exception as e:  # noqa: BLE001 -- the boundary; see below
                # This runs on a worker thread OUTSIDE the per-item boundary
                # in _worker, and before this except existed anything the
                # probe let escape killed the thread before it claimed an
                # item. A one-item job has one worker: it never set _done,
                # GET /api/job reported done=false forever, and a retry
                # under the same job_id got 409. The probe now catches its
                # own known failures (llm.probe_vision), so this is for the
                # ones nobody predicted -- and the item's own translate will
                # raise the same error inside a boundary that names it.
                ok, reason = False, f"vision probe error ({type(e).__name__}: {str(e)[:200]})"[:400]
        if not ok:
            with self._lock:
                self.warned.add(reason)

    def _worker(self) -> None:
        self._ensure_vision()
        while True:
            # Claim and register under ONE lock. A claim outside the lock
            # leaves a moment where the queue is empty and the item is in
            # nobody's hands, and a sibling draining at that moment would
            # declare the job done with this item still pending.
            with self._lock:
                if not self._pending:
                    finished = not self._running
                    break
                item = self._pending.popleft()
                self._running.add(item.item_id)
            try:
                if self._cancel.is_set() and item.status == "pending":
                    item.reason = CANCELLED_REASON
                    item.status = CANCELLED
                    # Still emitted, still reported: a cancelled item is an
                    # item the user asked about and did not get, and the
                    # queue view has to say why.
                    pipeline.emit("item_start", item.item_id, 0, 0)
                    pipeline.emit("item_done", item.item_id, 0, 100)
                else:
                    run_item(item, self.dest_dir, self.job_id, self.client,
                             self.lang, self.source, self.warned, self._lock,
                             cancel=self._cancel)
            except BaseException as e:  # noqa: BLE001 -- see below
                # run_item's boundary is total for the pipeline, but not for
                # its own `finally: emit(...)` on a broken stdout, nor for
                # the emits above. A worker that died here with the item
                # still "pending" and nobody left to set done would leave
                # wait() blocking and GET /api/job reporting a job that
                # never finishes (review, S4). Report the item, keep going.
                if item.status == "pending":
                    item.reason = f"worker error: {type(e).__name__}: {e}"
                    item.status = FAILED
                try:
                    traceback.print_exc()
                except OSError:
                    pass  # the realistic trigger is a closed pipe: stderr is gone too
            finally:
                with self._lock:
                    self._running.discard(item.item_id)
        # The last worker out -- the one that found the queue empty with
        # nobody still running -- sets done.
        if finished:
            self._done.set()

    # -- reporting ---------------------------------------------------------

    def status(self) -> dict:
        with self._lock:
            items = [i.as_dict() for i in self.items]
            warnings = sorted(self.warned)
            running = len(self._running)
        return {
            "job_id": self.job_id,
            "items": items,
            "warnings": warnings,
            "ok": sum(1 for i in items if i["status"] == OK),
            "skipped": sum(1 for i in items if i["status"] == SKIPPED),
            "failed": sum(1 for i in items if i["status"] == FAILED),
            "cancelled_items": sum(1 for i in items if i["status"] == CANCELLED),
            # Not yet claimed. An item mid-run still carries status
            # "pending" -- the boundary only writes a terminal status --
            # so it is subtracted here rather than counted twice.
            # Clamped: a worker writes the terminal status outside the lock
            # and discards itself from _running inside it, so a snapshot
            # between the two would otherwise read -1 for an instant.
            "pending": max(0, sum(1 for i in items if i["status"] == "pending") - running),
            "running": running,
            "done": self._done.is_set(),
            "cancelled": self._cancel.is_set(),
        }


def run_job(paths, dest_dir, job_id, client=None,
            lang: str = pipeline.DEFAULT_LANG,
            source: str = pipeline.DEFAULT_SOURCE,
            workers: int = WORKERS) -> dict:
    """Every path through the boundary, and the record when all are done.

    The blocking form of `Job`, kept because it is the shape every check
    since Phase 6 calls. Same workers, same queue, same "once per job"
    warning scope.
    """
    job = Job(job_id, paths, dest_dir, client, lang, source, workers).start()
    job.wait()
    return job.status()
