r"""The Item model and the per-item error boundary.

Moved here from Phase 8 on the architect's row 4: Phase 6 is the first phase
that can fail HALFWAY through a job -- one hostile archive among five benign
ones -- so it is the first phase that needs somewhere to put "this item was
skipped, and here is why". Inventing that here and replacing it in Phase 8
would mean two error models across three phases, so Phase 8 inherits this one
and adds only the queue, the scheduling and `Job.tsx` on top.

**AC-7 is still Phase 8's.** What lives here is the boundary, not the queue:
items are processed in the order given, one at a time, with no concurrency
decisions of any kind. `run_job` exists so the boundary has a caller in this
phase and so `check_archives` can assert the boundary holds over a real mixed
list; it is not the batch runner AC-7 asks for.

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
import traceback
from dataclasses import asdict, dataclass, field

from . import atomic, pipeline, safety
from .containers import archive, pdf

# The item-level progress contract, the way STAGES is the page-level one.
# check_archives asserts against these names rather than counting events: a
# renamed stage silently stops the UI's item list updating, and a count cannot
# tell that from three of the right events.
ITEM_STAGES = ("item_start", "item_done")

OK, SKIPPED, FAILED = "ok", "skipped", "failed"

# Loose images are items too -- AC-7's folder mixes them with archives -- and
# Phase 0's run_page already handles one. Listed here so `classify` has one
# place that decides what an item IS.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")


@dataclass
class Item:
    """One input file and what became of it.

    `status` is the machine-readable outcome and `reason` is why, in the user's
    words. An Item with status SKIPPED or FAILED always carries a non-empty
    reason -- a skipped item with no reason is a file that vanished from the
    user's job with no explanation, which is the failure mode AC-7's "per-item
    reason" clause exists to forbid.
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
        d = asdict(self)
        d.pop("record", None)
        return d


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
             warned: set | None = None) -> Item:
    """Process one item. Never raises.

    `warned` is the per-JOB warning set. AC-6 says the cbr->cbz warning is
    surfaced "once", and once means once per job: a job of thirty `.cbr` items
    that showed thirty identical dialogs would satisfy a naive count and annoy
    the user thirty times. The set is owned by the caller because the scope the
    word "once" refers to is the job, and this function only sees one item.
    """
    pipeline.emit("item_start", item.item_id, 0, 0)
    try:
        if item.status == SKIPPED:
            # Classified out before it got here -- an unsupported extension.
            # Still emitted and still reported, because a file the user put in
            # the folder and never heard about again is the complaint.
            return item

        if item.kind == "image":
            record = pipeline.run_page(item.path, dest_dir, 1, client, source, lang)
            item.output = record.get("output", "")
            item.pages = 1
            item.record = record
            item.status = OK
            return item

        # An archive or a PDF: both are "every page through the cache, then
        # repack", and pipeline.run_item tells them apart by signature.
        record = pipeline.run_item(
            item.path, dest_dir, job_id, item.item_id, client, lang, source,
        )
        item.record = record
        item.pages = len(record.get("pages", []))
        item.output = record.get("archive", "")
        warning = record.get("format_warning")
        if warning:
            seen = warned if warned is not None else set()
            if warning not in seen:
                seen.add(warning)
                item.warning = warning
        item.status = OK
        return item

    except safety.UnsafeArchive as e:
        # The one failure with a machine-readable reason. The UI shows
        # e.reason's rule name; the detail stays in the message.
        item.status = SKIPPED
        item.reason = f"unsafe archive ({e.reason}): {e.member}"
        _discard_output(item, dest_dir)
        return item
    except archive.UnsupportedArchive as e:
        item.status = SKIPPED
        item.reason = e.reason
        return item
    except archive.LibarchiveMissing as e:
        item.status = SKIPPED
        item.reason = e.reason
        return item
    except Exception as e:  # noqa: BLE001 -- the boundary; see module docstring
        # Deliberately broad, and deliberately loud on stderr. A library we do
        # not own raising something we did not predict is the case this
        # boundary exists for; narrowing it to the exceptions seen so far means
        # the first unseen one takes the whole job down.
        item.status = FAILED
        item.reason = f"{type(e).__name__}: {e}"
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


def run_job(paths, dest_dir, job_id, client=None,
            lang: str = pipeline.DEFAULT_LANG,
            source: str = pipeline.DEFAULT_SOURCE) -> dict:
    """Every path, in order, through the boundary. Returns the job record.

    No queue, no concurrency, no cancellation -- those are Phase 8's and naming
    them here would be the same forward-dependency this file was moved to
    avoid. What it does provide is the scope the cbr->cbz warning is "once"
    within, and a shape `Job.tsx` can render without being rewritten.
    """
    warned: set[str] = set()
    items = [run_item(item, dest_dir, job_id, client, lang, source, warned)
             for item in disambiguate([classify(p) for p in paths])]
    return {
        "job_id": str(job_id),
        "items": [i.as_dict() for i in items],
        "warnings": sorted(warned),
        "ok": sum(1 for i in items if i.status == OK),
        "skipped": sum(1 for i in items if i.status == SKIPPED),
        "failed": sum(1 for i in items if i.status == FAILED),
    }
