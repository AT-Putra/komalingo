#!/usr/bin/env python3
r"""Phase 8 -- AC-7 (directory batch and job queue). Offline, against the stub.

    uv run --project sidecar python tests/check_batch.py

Exit-code contract, uniform across every check here:
    0  pass
    1  fail
    2  inconclusive -- never here; nothing is timed against a floor
    3  skip         -- fixtures/archives/ or fixtures/pdf/ is absent

AC-7 in the spec's words: a folder mixing loose images, PDFs and archives
processes every supported item, skips unsupported ones with a per-item
reason, and never aborts the whole job on one bad file; progress streams per
item. Four things are asserted, and the fourth is the one the build order
moved here from a live endpoint:

  STATUSES. The folder holds two loose pages, a PDF, two archives, a corrupt
  archive, a hostile archive, an unsupported file and a dotfile. Every item
  ends with a terminal status; every skip and failure carries a reason; every
  OK item has its output on disk. "Never aborts" is asserted on the mixed
  folder, not on a folder of good files -- an aborted job and a finished one
  look the same when nothing in it could fail.

  PROGRESS. Captured stdout carries exactly one item_start and one item_done
  per item, skipped ones included, and the seven page stages for every page
  of every OK item. And the item events INTERLEAVE: some item_start arrives
  before an earlier item's item_done, which is the evidence the queue ran
  items concurrently rather than one after another with a queue in name only.

  THE CAP. Peak in-flight requests at the stub over the whole batch is at
  most 3. That alone cannot go red on a broken cap when the queue is narrow,
  so the load half follows: eight threads each translating a 41-region page
  (two requests each) at the same instant, the shape the queue's workers
  create, peak at most 3 -- and with the gate monkeypatched to 8, peak above
  3. The second half is the control; without it the first is vacuous. The
  stub owns the 200ms delay for the same reason (see stub_provider.py).

  CANCEL. A one-worker job cancelled right after start: the running item
  stops at its next page boundary (Phase 9), the rest come back CANCELLED
  with CANCELLED_REASON, and the job still reaches done. check_cancel holds
  the rest of AC-13 -- no partial file, and the resume.
"""

import asyncio
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from sidecar import atomic, cache, job, llm, pipeline, safety  # noqa: E402
from sidecar.llm import LLMClient, Region  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider, vision_capable  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")

# What the folder holds, and what each must become. `pages` is asserted for
# OK items; `reason` is a substring the item's reason must carry.
FOLDER = [
    # name              source fixture                 kind        status   pages/reason
    ("ch2.png",        "smoke/tategaki_01.png",        "image",    job.OK,      1),
    ("ch10.png",       "smoke/tategaki_02.png",        "image",    job.OK,      1),
    ("scan.pdf",       "pdf/scan.pdf",                 "pdf",      job.OK,      3),
    ("vol1.cbz",       "archives/benign.cbz",          "archive",  job.OK,      3),
    ("vol2.cb7",       "archives/benign.cb7",          "archive",  job.OK,      3),
    ("corrupt.cbz",    None,                           "archive",  None,        "corrupt"),
    ("slip.cbz",       "archives/slip.cbz",            "archive",  job.SKIPPED, safety.PARENT_TRAVERSAL),
    ("notes.txt",      None,                           "unsupported", job.SKIPPED, "unsupported file type .txt"),
]
NATURAL_ORDER = ["ch2.png", "ch10.png", "corrupt.cbz", "notes.txt", "scan.pdf",
                 "slip.cbz", "vol1.cbz", "vol2.cb7"]
DOTFILE = ".DS_Store"
TMPFILE = "half-written.tmp"


def build_folder(root):
    src = os.path.join(root, "in")
    os.makedirs(src)
    for name, fixture, _kind, _status, _want in FOLDER:
        dest = os.path.join(src, name)
        if fixture:
            shutil.copy(os.path.join(FIXTURES, fixture), dest)
        elif name == "corrupt.cbz":
            # The first 900 bytes of a real archive: a zip signature with no
            # central directory. Dispatched by signature to the zip reader,
            # which cannot open it -- the corrupt file AC-7 names.
            with open(os.path.join(FIXTURES, "archives", "benign.cbz"), "rb") as fh:
                head = fh.read(900)
            with open(dest, "wb") as fh:
                fh.write(head)
        else:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("not an item\n")
    for name in (DOTFILE, TMPFILE):
        with open(os.path.join(src, name), "w", encoding="utf-8") as fh:
            fh.write("noise\n")
    os.makedirs(os.path.join(src, "subfolder"))
    shutil.copy(os.path.join(FIXTURES, "archives", "benign.cbz"),
                os.path.join(src, "subfolder", "nested.cbz"))
    return src


def events_of(text):
    out = []
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if isinstance(e, dict) and "stage" in e:
            out.append(e)
    return out


# --------------------------------------------------------------------------


def check_scan(c, src):
    listed = job.scan(src)
    names = [os.path.basename(p) for p in listed]
    c.check(names == NATURAL_ORDER,
            f"scan lists the top-level files in natural order (ch2 before ch10) "
            f"({names})")
    c.check(DOTFILE not in names and TMPFILE not in names,
            "and neither the dotfile nor the .tmp")
    c.check("nested.cbz" not in names and "subfolder" not in names,
            "and nothing from the subfolder: top level only")
    c.check(all(os.path.isabs(p) or p.startswith(src) for p in listed),
            "paths come back joined to the folder")
    try:
        job.scan(os.path.join(src, "missing"))
        c.check(False, "a missing folder raises NotADirectoryError")
    except NotADirectoryError as e:
        c.check("missing" in str(e), f"a missing folder raises NotADirectoryError naming it ({e})")
    try:
        job.scan(os.path.join(src, "notes.txt"))
        c.check(False, "a file is not a folder")
    except NotADirectoryError:
        c.check(True, "a file is not a folder: NotADirectoryError")


def check_statuses(c, src, out, stub):
    vision_capable(stub, "stub-model")  # this section is about statuses, not the probe
    client = LLMClient(stub.url, "", "stub-model")
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        batch = job.Job("check-batch", job.scan(src), out, client).start()
        # status() from another thread, mid-run, must never raise.
        snapshots = 0
        while not batch.wait(0.2):
            batch.status()
            snapshots += 1
        status = batch.status()
    c.check(status["done"] and status["pending"] == 0 and status["running"] == 0,
            f"the job reaches done with nothing pending or running "
            f"(done={status['done']}, pending={status['pending']}, running={status['running']})")
    c.check(snapshots > 0, f"status() was polled mid-run without raising ({snapshots} snapshots)")

    items = {i["item_id"]: i for i in status["items"]}
    c.check(sorted(items) == sorted(n for n, *_ in FOLDER),
            f"every file in the folder is an item ({sorted(items)})")
    c.check(all(i["status"] in (job.OK, job.SKIPPED, job.FAILED) for i in status["items"]),
            "every item has a terminal status -- the job did not abort")
    for name, _fixture, kind, want_status, want in FOLDER:
        item = items[name]
        c.check(item["kind"] == kind, f"{name}: kind {item['kind']} == {kind}")
        if want_status == job.OK:
            c.check(item["status"] == job.OK and item["pages"] == want,
                    f"{name}: OK with {want} pages ({item['status']}, {item['pages']}, "
                    f"{item['reason']!r})")
            c.check(bool(item["output"]) and os.path.isfile(item["output"]),
                    f"{name}: output on disk ({item['output']})")
        elif want_status is None:
            c.check(item["status"] in (job.SKIPPED, job.FAILED) and item["reason"],
                    f"{name}: reported with a reason, never raised "
                    f"({item['status']}: {item['reason']!r})")
        else:
            c.check(item["status"] == want_status and want in item["reason"],
                    f"{name}: {want_status} with {want!r} in the reason "
                    f"({item['status']}: {item['reason']!r})")
    ok = sum(1 for _n, _f, _k, s, _w in FOLDER if s == job.OK)
    c.check(status["ok"] == ok, f"ok count {status['ok']} == {ok}")
    c.check(status["ok"] + status["skipped"] + status["failed"] == len(FOLDER),
            f"ok + skipped + failed == {len(FOLDER)} "
            f"({status['ok']} + {status['skipped']} + {status['failed']})")

    # -- progress -----------------------------------------------------------
    events = events_of(captured.getvalue())
    starts = [e["item"] for e in events if e["stage"] == "item_start"]
    dones = [e["item"] for e in events if e["stage"] == "item_done"]
    c.check(sorted(starts) == sorted(items) and sorted(dones) == sorted(items),
            f"exactly one item_start and one item_done per item, skipped ones "
            f"included ({len(starts)} starts, {len(dones)} dones)")
    pages = sum(i["pages"] for i in status["items"] if i["status"] == job.OK)
    stage_counts = {s: sum(1 for e in events if e["stage"] == s) for s in pipeline.STAGES}
    c.check(all(n == pages for n in stage_counts.values()),
            f"each of the seven page stages was emitted once per page over "
            f"{pages} pages ({stage_counts})")
    # Interleaving: the position of every start and done in the stream.
    order = [(e["stage"], e["item"]) for e in events if e["stage"] in job.ITEM_STAGES]
    interleaved = False
    open_items: set[str] = set()
    for stage, item in order:
        if stage == "item_start":
            if open_items:
                interleaved = True
            open_items.add(item)
        else:
            open_items.discard(item)
    c.check(interleaved,
            "an item_start arrived while another item was still open -- the "
            "queue ran items concurrently")
    return status


def check_cap(c, stub):
    c.check(stub.peak_concurrency <= llm.MAX_CONCURRENT,
            f"peak in-flight at the stub over the whole batch: "
            f"{stub.peak_concurrency} <= {llm.MAX_CONCURRENT}")
    batch_peak = stub.peak_concurrency

    # The load half: the shape the queue's workers create, at full press.
    client = LLMClient(stub.url, "", "stub-model")

    def press(n_threads=8):
        go = threading.Barrier(n_threads)
        errors: list[str] = []

        def worker():
            try:
                go.wait()
                asyncio.run(client.translate_page(
                    [Region(id=i, text="x") for i in range(llm.MAX_REGIONS + 1)]))
            except Exception as e:  # noqa: BLE001 -- reported, not hidden
                errors.append(f"{type(e).__name__}: {e}")

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        stub.peak_concurrency = 0
        for t in threads:
            t.start()
        for t in threads:
            t.join(60)
        return stub.peak_concurrency, errors

    peak, errors = press()
    c.check(not errors, f"8 threads x 2 requests at once: no errors ({errors[:1]})")
    c.check(peak <= llm.MAX_CONCURRENT,
            f"8 threads x 2 requests at once peak at {peak} <= {llm.MAX_CONCURRENT}")
    gate = llm._GATE
    llm._GATE = threading.BoundedSemaphore(8)
    try:
        wide, _ = press()
    finally:
        llm._GATE = gate
    c.check(wide > llm.MAX_CONCURRENT,
            f"control: with the gate widened to 8 the same load peaks at {wide} > "
            f"{llm.MAX_CONCURRENT} -- the cap assert can go red")
    return batch_peak


def check_warning_once(c, src, out):
    """The cbr->cbz warning, once per job, with two workers racing for it.

    benign.cbr is absent on most machines (fixtures/README.md), so the
    warning is injected: pipeline.run_item is wrapped to stamp
    format_warning on two named archives. What is under test is job.py's
    "once per job" under concurrency, and that is exactly the code the wrap
    leaves alone.
    """
    original = pipeline.run_item

    def stamped(src_path, *args, **kwargs):
        record = original(src_path, *args, **kwargs)
        if os.path.basename(src_path).startswith("vol"):
            record["format_warning"] = "SIMULATED: written as .cbz"
        return record

    pipeline.run_item = stamped
    try:
        paths = [os.path.join(src, n) for n in ("vol1.cbz", "vol2.cb7")]
        with contextlib.redirect_stdout(io.StringIO()):
            status = job.run_job(paths, os.path.join(out, "warn"), "check-batch-warn",
                                 workers=2)
    finally:
        pipeline.run_item = original
    carried = [i for i in status["items"] if i["warning"]]
    # Both OK, on a COLD cache: vol1.cbz and vol2.cb7 are the same three
    # pages, so two workers miss on the same page hash together and write
    # the same cache files. Before pipeline's per-hash lock that was a
    # PermissionError [WinError 5] out of os.replace and a FAILED item that
    # this section did not look at (review). It looks now.
    c.check(all(i["status"] == job.OK for i in status["items"]),
            f"two identical archives on two workers both complete "
            f"({[(i['item_id'], i['status'], i['reason'][:60]) for i in status['items']]})")
    c.check(status["warnings"] == ["SIMULATED: written as .cbz"],
            f"two items raising the same warning on two workers yield ONE job "
            f"warning ({status['warnings']})")
    c.check(len(carried) == 1,
            f"and exactly one item carries it ({[i['item_id'] for i in carried]})")


def _chats_with_image(stub):
    """(chat payloads, those carrying an image_url part). Three asserts ask this."""
    chats = [p for p in stub.payloads if p and p.get("messages")]
    with_image = [
        p for p in chats
        if any(part.get("type") == "image_url"
               for m in p["messages"]
               for part in (m.get("content") if isinstance(m.get("content"), list) else []))
    ]
    return chats, with_image


def check_probe_wiring(c, src, out, stub):
    """[probe] AC-9's other half: the JOB runs the vision probe, once.

    check_probe proves the latch against a live model. This proves the
    product reaches it -- which, until US-C-02, nothing did: probe_vision
    existed, translate_page honoured text_only, and no caller in the app ran
    the probe, so a text-only model was never detected and every page went
    out carrying an image the provider could not read.

    probe_vision is patched to count and to answer a scripted verdict, the
    same way check_cancel patches detect and ocr: the question is whether the
    job calls it, how many times, and what happens downstream -- not whether
    a stub can read a picture, which it cannot.
    """
    calls = []
    verdict = {"ok": False}
    original = LLMClient.probe_vision

    async def scripted(self, png, expect):
        calls.append(expect)
        if not verdict["ok"]:
            self.text_only = True
            self.text_only_reason = f"vision probe failed; expected {expect!r}, got 'SCRIPTED'"
        return verdict["ok"]

    LLMClient.probe_vision = scripted
    try:
        paths = [os.path.join(src, n) for n in ("vol1.cbz", "vol2.cb7")]

        # -- a text-only provider: one probe, one warning, no images -------
        stub.payloads.clear()
        client = LLMClient(stub.url, "", "probe-model-a")
        with contextlib.redirect_stdout(io.StringIO()):
            status = job.run_job(paths, os.path.join(out, "probe-a"),
                                 "check-batch-probe-a", client, workers=2)
        c.check(len(calls) == 1,
                f"[probe] a two-item, two-worker job probes exactly ONCE "
                f"(probed {len(calls)} times)")
        reasons = [w for w in status["warnings"] if "vision probe failed" in w]
        c.check(len(reasons) == 1 and "SCRIPTED" in reasons[0],
                f"[probe] the text-only reason surfaces as ONE job warning "
                f"({status['warnings']})")
        c.check(all(i["status"] == job.OK for i in status["items"]),
                f"[probe] and the job still completes text-only "
                f"({[(i['item_id'], i['status']) for i in status['items']]})")
        chats, with_image = _chats_with_image(stub)
        c.check(chats and not with_image,
                f"[probe] after the latch, NO translate request carried an image "
                f"({len(with_image)} of {len(chats)} did)")

        # -- a vision-capable provider: probe once, cache, images travel ---
        calls.clear()
        verdict["ok"] = True
        stub.payloads.clear()
        client = LLMClient(stub.url, "", "probe-model-b")
        with contextlib.redirect_stdout(io.StringIO()):
            status = job.run_job(paths, os.path.join(out, "probe-b"),
                                 "check-batch-probe-b", client, workers=2)
        c.check(len(calls) == 1,
                f"[probe] a vision-capable provider is probed once ({len(calls)})")
        c.check(not any("vision probe" in w for w in status["warnings"]),
                f"[probe] and raises no text-only warning ({status['warnings']})")
        chats, with_image = _chats_with_image(stub)
        c.check(chats and len(with_image) == len(chats),
                f"[probe] every translate request carried the page image "
                f"({len(with_image)} of {len(chats)})")

        # -- the per-(base_url, model) cache: same pair, no second probe ---
        calls.clear()
        client = LLMClient(stub.url, "", "probe-model-b")
        with contextlib.redirect_stdout(io.StringIO()):
            job.run_job(paths, os.path.join(out, "probe-b2"),
                        "check-batch-probe-b2", client, workers=2)
        c.check(len(calls) == 0,
                f"[probe] a second job on the same (base_url, model) does not "
                f"re-probe -- the success is cached ({len(calls)} calls)")

        # -- a different model is a different pair --------------------------
        calls.clear()
        client = LLMClient(stub.url, "", "probe-model-c")
        with contextlib.redirect_stdout(io.StringIO()):
            job.run_job(paths, os.path.join(out, "probe-c"),
                        "check-batch-probe-c", client, workers=2)
        c.check(len(calls) == 1,
                f"[probe] a different model on the same base_url is probed "
                f"afresh ({len(calls)} calls)")

        # -- a failure is NOT cached: the next job on that pair tries again --
        calls.clear()
        client = LLMClient(stub.url, "", "probe-model-a")
        with contextlib.redirect_stdout(io.StringIO()):
            job.run_job(paths, os.path.join(out, "probe-a2"),
                        "check-batch-probe-a2", client, workers=2)
        c.check(len(calls) == 1,
                f"[probe] a pair whose probe FAILED earlier is probed again by "
                f"the next job -- one hiccup is not text-only until restart "
                f"({len(calls)} calls)")

        # -- a probe that RAISES must not kill the worker -------------------
        # The architect's reproduction: _ensure_vision ran outside the
        # per-item boundary, a one-item job has one worker, and anything the
        # probe let escape left that job at done=false forever.
        async def exploding(self, png, expect):
            raise RuntimeError("proxy answered with a captive-portal page")

        LLMClient.probe_vision = exploding
        client = LLMClient(stub.url, "", "probe-model-x")
        with contextlib.redirect_stdout(io.StringIO()):
            batch = job.Job("check-batch-probe-x", paths[:1], os.path.join(out, "probe-x"),
                            client, workers=1).start()
            finished = batch.wait(15)
            status = batch.status()
        c.check(finished and status["done"],
                f"[probe] a one-item job whose probe RAISES still reaches done "
                f"(finished={finished}, done={status['done']})")
        c.check(any("vision probe error" in w and "RuntimeError" in w for w in status["warnings"]),
                f"[probe] and the job warns with the exception's name ({status['warnings']})")
        c.check(all(i["status"] in (job.OK, job.FAILED) for i in status["items"]),
                f"[probe] and the item reached a terminal status "
                f"({[(i['item_id'], i['status']) for i in status['items']]})")
    finally:
        LLMClient.probe_vision = original

    # -- the REAL probe against a base URL with no scheme -------------------
    # SettingsError out of _request, not ProviderError: the case that killed
    # the worker before probe_vision caught it. Real probe_vision, one item.
    client = LLMClient("localhost:1/v1", "", "probe-model-y")
    with contextlib.redirect_stdout(io.StringIO()):
        batch = job.Job("check-batch-probe-y", paths[:1], os.path.join(out, "probe-y"),
                        client, workers=1).start()
        finished = batch.wait(15)
        status = batch.status()
    c.check(finished and status["done"],
            f"[probe] a scheme-less base URL: the job still reaches done "
            f"(finished={finished})")
    c.check(not client.text_only and any("could not run" in w for w in status["warnings"]),
            f"[probe] and it did NOT latch text-only -- a probe that could not run "
            f"is not evidence about the model (text_only={client.text_only}, "
            f"warnings={status['warnings']})")

    # -- a 5xx on the probe does not latch either ---------------------------
    with StubProvider(status=500, delay=0) as down:
        client = LLMClient(down.url, "", "probe-model-z")
        with contextlib.redirect_stdout(io.StringIO()):
            status = job.run_job(paths[:1], os.path.join(out, "probe-z"),
                                 "check-batch-probe-z", client, workers=1)
    c.check(not client.text_only,
            f"[probe] HTTP 500 on the probe does not latch text-only "
            f"(text_only={client.text_only})")
    c.check(any("could not run (HTTP 500" in w for w in status["warnings"]),
            f"[probe] and the warning says the probe could not RUN, not that the "
            f"model is text-only ({status['warnings']})")
    c.check(all(i["status"] == job.FAILED for i in status["items"]),
            f"[probe] and the item fails with the provider's own error rather "
            f"than degrading silently ({[(i['status'], i['reason'][:50]) for i in status['items']]})")

    # -- the single-file routes probe too -----------------------------------
    # The image goes out on every route; only Job probed. /api/item is the
    # UI's primary flow. main._probed is what the two routes call.
    from sidecar import main as sidecar_main

    client = LLMClient(stub.url, "", "probe-model-r")   # a fresh pair, never probed
    reason = sidecar_main._probed(client)
    c.check(client.text_only and "vision probe failed" in reason,
            f"[probe] main._probed latches against the text-only stub and returns "
            f"the reason ({reason[:60]!r})")
    stub.payloads.clear()   # the probe's own request carried the image, by design
    with contextlib.redirect_stdout(io.StringIO()):
        record = pipeline.run_item(os.path.join(src, "vol1.cbz"), os.path.join(out, "probe-r"),
                                   "check-batch-probe-r", None, client)
    chats, with_image = _chats_with_image(stub)
    c.check(chats and not with_image and len(record["pages"]) == 3,
            f"[probe] and the item's pages then go out without an image "
            f"({len(with_image)} of {len(chats)} carried one)")


def check_same_hash(c, src, out):
    """The same pages from two containers, four workers, cold cache, x3.

    The race B1 named is a timing: two workers must miss on one hash inside
    the same few milliseconds. Three rounds on a fresh cache each time make
    the window recur; every item must still come back OK. With the per-hash
    lock removed, the review measured one FAILED item per cold run.
    """
    paths = [os.path.join(src, n) for n in ("vol1.cbz", "vol2.cb7", "scan.pdf")]
    failures = []
    for round_ in range(3):
        cache_dir = os.path.join(out, f"cold-{round_}")
        os.environ["MT_CACHE_DIR"] = cache_dir
        with contextlib.redirect_stdout(io.StringIO()):
            status = job.run_job(paths, os.path.join(out, f"same-{round_}"),
                                 f"check-batch-same-{round_}", workers=4)
        failures += [(i["item_id"], i["status"], i["reason"][:80])
                     for i in status["items"] if i["status"] != job.OK]
    c.check(not failures,
            f"three cold-cache rounds of two identical archives on four workers: "
            f"every item OK ({failures or 'no failures'})")
    # The refcount at rest: nothing running, no marker left behind.
    c.check(not cache._running,
            f"no job is left marked running after the rounds ({cache._running})")


def check_same_hash_files(c):
    """The mechanism under B1, isolated and deterministic.

    Two threads, 300 write+read pairs each, on ONE page hash's translation
    file, bypassing the pipeline's page lock: the cache's own writer and
    reader must survive it. Then the control: with atomic's replace retry
    and open retry both removed, the same load fails -- 234 of 600 measured
    -- so the first assert is known to be able to go red.
    """
    def hammer():
        errors = []
        h = "ab" * 32

        def worker(n):
            for i in range(300):
                try:
                    cache.write_translation(h, "en", "m", {1: f"t{n}-{i}"})
                    cache.read_translation(h, "en", "m")
                except OSError as e:
                    errors.append(type(e).__name__)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return len(errors)

    clean = hammer()
    c.check(clean == 0,
            f"two threads x 300 write+read pairs on one page hash: {clean} OSErrors")
    replace, open_ = atomic._replace, atomic.open_retry
    atomic._replace = os.replace
    atomic.open_retry = lambda path, mode="r", encoding=None: open(path, mode, encoding=encoding)
    try:
        raw = hammer()
    finally:
        atomic._replace, atomic.open_retry = replace, open_
    c.check(raw > 0,
            f"control: with the replace and open retries removed the same load "
            f"fails ({raw} OSErrors) -- the assert above can go red")


def check_running_refcount(c, src, out):
    """B3: a .cbz that is not an archive must not leave the job marked running."""
    fake = os.path.join(out, "fake.cbz")
    with open(fake, "w", encoding="utf-8") as fh:
        fh.write("<html>not an archive</html>\n")
    with contextlib.redirect_stdout(io.StringIO()):
        status = job.run_job([fake, os.path.join(src, "vol1.cbz")],
                             os.path.join(out, "refcount"), "check-batch-refcount", workers=1)
    statuses = {i["item_id"]: i["status"] for i in status["items"]}
    c.check(statuses["fake.cbz"] == job.SKIPPED and statuses["vol1.cbz"] == job.OK,
            f"an HTML page named .cbz is skipped and the real archive completes ({statuses})")
    c.check("check-batch-refcount" not in cache._running
            and not os.path.exists(os.path.join(cache.job_dir("check-batch-refcount"), cache.RUNNING)),
            "and the job is not left marked running: the refcount reached zero "
            "and the marker file is gone")


def check_cancel(c, src, out):
    with contextlib.redirect_stdout(io.StringIO()):
        batch = job.Job("check-batch-cancel", job.scan(src), os.path.join(out, "cancel"),
                        workers=1).start()
        batch.cancel()
        finished = batch.wait(300)
        status = batch.status()
    c.check(finished and status["done"] and status["cancelled"],
            f"a cancelled one-worker job reaches done (done={status['done']})")
    cancelled = [i for i in status["items"] if i["reason"] == job.CANCELLED_REASON]
    c.check(len(cancelled) >= 1 and all(i["status"] == job.CANCELLED for i in cancelled),
            f"{len(cancelled)} items CANCELLED with {job.CANCELLED_REASON!r}")
    c.check(all(i["status"] != "pending" for i in status["items"]),
            "and nothing is left pending")
    # Phase 9: the item that was running when cancel() fired stops at its
    # next page boundary, so it is CANCELLED with a page count -- or OK if
    # it was already past its last page. Either way at most one item ran.
    ran = [i for i in status["items"]
           if i["status"] == job.OK or (i["status"] == job.CANCELLED
                                        and i["reason"] != job.CANCELLED_REASON)]
    c.check(len(ran) <= 1,
            f"at most the item that was already running got anywhere "
            f"({[(i['item_id'], i['status'], i['reason']) for i in ran]})")
    c.check(status["cancelled_items"] == len([i for i in status["items"]
                                              if i["status"] == job.CANCELLED]),
            f"status() counts the cancelled items ({status['cancelled_items']})")


def main():
    for sub in ("archives", "pdf", "smoke"):
        if not os.path.isdir(os.path.join(FIXTURES, sub)):
            return skip(f"fixtures/{sub}/ is absent -- run tests/gen_fixtures.py")

    c = Checks("check_batch")
    with tempfile.TemporaryDirectory() as tmp, StubProvider(delay=0.2) as stub:
        # A cache of this run's own, and COLD: every page misses, so the
        # queue's four workers really do detect, translate and write at
        # once. Against the developer's warm cache the batch is a series
        # of hits and half the code under test never runs (review).
        os.environ["MT_CACHE_DIR"] = os.path.join(tmp, "cache")
        src = build_folder(tmp)
        out = os.path.join(tmp, "out")
        check_scan(c, src)
        status = check_statuses(c, src, out, stub)
        batch_peak = check_cap(c, stub)
        check_warning_once(c, src, out)
        check_same_hash(c, src, out)
        check_same_hash_files(c)
        check_running_refcount(c, src, out)
        check_cancel(c, src, out)
        check_probe_wiring(c, src, out, stub)

    # Recorded, not ratcheted: the peak is a timing under a hard cap the
    # asserts above hold, and the item count is decided by the folder.
    print("METRICS " + json.dumps({
        "batch_peak_llm_concurrency": batch_peak,
        "batch_items_ok": status["ok"],
    }), flush=True)
    return c.finish()


if __name__ == "__main__":
    run(main)
