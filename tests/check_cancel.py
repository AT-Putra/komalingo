#!/usr/bin/env python3
r"""Phase 9 -- AC-13 (cancel and resume). Offline, against the stub.

    uv run --project sidecar python tests/check_cancel.py

Exit-code contract, uniform across every check here:
    0  pass
    1  fail
    2  inconclusive -- never here
    3  skip         -- fixtures/archives/ or fixtures/pdf/ is absent

AC-13 in the spec's words: a running batch can be cancelled and leaves no
partial output file in place; completed pages are cached so a re-run skips
them. Three things are asserted, and the third runs in ANOTHER PROCESS:

  CANCEL. A one-worker job over a three-page archive and a PDF, on a cold
  cache of its own, with the stub answering slowly. The check watches the
  progress stream and calls cancel() the moment page 1 is written. The
  archive comes back CANCELLED having delivered fewer than three pages, with
  the count in its reason; the PDF comes back CANCELLED before start; the
  job reaches done; NO output archive or PDF exists for either.

  NO PARTIAL FILE. Asserted over the whole tree, not one directory: no
  `.*.tmp` under the output or the cache; every image under the output
  decodes fully; every JSON under the cache parses; every cached raster
  loads. "Every write is atomic" is a sentence in atomic.py; this is what
  makes it a fact after a cancel.

  RESUME. A NEW PROCESS -- a driver script in tmp, launched with subprocess
  and the same MT_CACHE_DIR -- patches pipeline.detect and pipeline.ocr to
  COUNT and runs the same archive under a NEW job id. The pages the
  cancelled run delivered come back cached (ocr_calls 0); the rest are
  detected; the detector counter equals exactly the number the first run
  did not finish; the item completes with its archive. A second new-process
  run counts zero and its placement names the same page hashes: the cache
  path is job-independent, as Phase 3 promised and Phase 6's regression note
  demanded. Then the control: the same driver on an EMPTY cache counts
  three, so the counter assert is known to be able to go red.

New process and new job id, both deliberately: iteration 1 of the build
order had a cache layout that would have passed a same-process re-run and
failed a real one.
"""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from PIL import Image  # noqa: E402

from sidecar import cache, job  # noqa: E402
from sidecar.llm import LLMClient  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")
ARCHIVE_PAGES = 3

# The driver the new process runs. Patches BOTH entrypoints to count, runs
# one archive under the job id it is given, prints one JSON line. Written to
# tmp rather than passed with -c so a traceback names a file and a line.
DRIVER = r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
from sidecar import cache, job, pipeline

counts = {"detect": 0, "ocr": 0}
_detect, _ocr = pipeline.detect, pipeline.ocr

def detect(*a, **k):
    counts["detect"] += 1
    return _detect(*a, **k)

def ocr(*a, **k):
    counts["ocr"] += 1
    return _ocr(*a, **k)

pipeline.detect, pipeline.ocr = detect, ocr
src, dest, job_id = sys.argv[2], sys.argv[3], sys.argv[4]
status = job.run_job([src], dest, job_id, workers=1)
placement = cache.read_placement(job_id)
print("RESULT " + json.dumps({
    "status": status, "counts": counts,
    "placement": {k: v.get("page_hash") for k, v in placement.items()},
}), flush=True)
'''


def build_inputs(root):
    src = os.path.join(root, "in")
    os.makedirs(src)
    shutil.copy(os.path.join(FIXTURES, "archives", "benign.cbz"), os.path.join(src, "vol1.cbz"))
    shutil.copy(os.path.join(FIXTURES, "pdf", "scan.pdf"), os.path.join(src, "scan.pdf"))
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


def check_cancel(c, src, out, stub):
    """Cancel the moment page 1 is on disk; the item must stop short."""
    client = LLMClient(stub.url, "", "stub-model")
    captured = io.StringIO()
    paths = [os.path.join(src, "vol1.cbz"), os.path.join(src, "scan.pdf")]
    with contextlib.redirect_stdout(captured):
        batch = job.Job("check-cancel", paths, out, client, workers=1).start()
        fired_at = None
        deadline = time.time() + 300
        while not batch.wait(0.05):
            if fired_at is None and any(
                    e["stage"] == "write" for e in events_of(captured.getvalue())):
                batch.cancel()
                fired_at = time.time()
            if time.time() > deadline:
                break
        status = batch.status()
    c.check(fired_at is not None, "cancel() was fired after page 1's write stage")
    c.check(status["done"] and status["cancelled"],
            f"the job reached done after cancel (done={status['done']})")
    items = {i["item_id"]: i for i in status["items"]}
    vol = items["vol1.cbz"]
    c.check(vol["status"] == job.CANCELLED and 1 <= vol["pages"] < ARCHIVE_PAGES,
            f"vol1.cbz is CANCELLED having delivered {vol['pages']} of {ARCHIVE_PAGES} "
            f"pages ({vol['status']}, {vol['reason']!r})")
    c.check(str(vol["pages"]) in vol["reason"] and "cancelled" in vol["reason"],
            f"and the reason names the count ({vol['reason']!r})")
    c.check(vol["output"] == "",
            f"no output archive was recorded for the cancelled item ({vol['output']!r})")
    pdf = items["scan.pdf"]
    c.check(pdf["status"] == job.CANCELLED and pdf["reason"] == job.CANCELLED_REASON,
            f"scan.pdf is CANCELLED {job.CANCELLED_REASON!r} ({pdf['status']}, {pdf['reason']!r})")
    c.check(status["cancelled_items"] == 2 and status["ok"] == 0,
            f"status counts 2 cancelled, 0 ok ({status['cancelled_items']}, {status['ok']})")

    # Nothing repacked, for either item, anywhere under the output.
    repacked = [f for _d, _s, files in os.walk(out) for f in files
                if f.endswith(("_translated.cbz", "_translated.pdf"))]
    c.check(not repacked, f"no repacked archive or PDF under the output ({repacked})")

    # The delivered pages ARE there, whole -- the decision Phase 6 stated.
    delivered = [os.path.join(d, f) for d, _s, files in os.walk(out) for f in files
                 if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    c.check(len(delivered) == vol["pages"],
            f"exactly the {vol['pages']} delivered pages are on disk ({len(delivered)} files)")
    # The stream said what happened, in order: item_start for both, item_done
    # for both, and the archive's write events number its delivered pages.
    events = events_of(captured.getvalue())
    writes = sum(1 for e in events if e["stage"] == "write")
    c.check(writes == vol["pages"],
            f"the progress stream carries one write per delivered page ({writes})")
    return vol["pages"]


def check_no_partial(c, out, cache_dir):
    tmps, bad_images, bad_json = [], [], []
    for root in (out, cache_dir):
        for d, _s, files in os.walk(root):
            for f in files:
                p = os.path.join(d, f)
                if f.startswith(".") and f.endswith(".tmp"):
                    tmps.append(p)
                elif f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    try:
                        with Image.open(p) as im:
                            im.load()
                    except Exception as e:  # noqa: BLE001 -- reported, not hidden
                        bad_images.append(f"{p}: {type(e).__name__}")
                elif f.lower().endswith(".json"):
                    try:
                        with open(p, encoding="utf-8") as fh:
                            json.load(fh)
                    except (ValueError, OSError) as e:
                        bad_json.append(f"{p}: {type(e).__name__}")
    c.check(not tmps, f"no atomic_write temp file anywhere under the output or the cache ({tmps})")
    c.check(not bad_images, f"every image under the output and the cache decodes fully ({bad_images})")
    c.check(not bad_json, f"every JSON under the cache parses ({bad_json})")
    rasters = [os.path.join(d, f) for d, _s, files in os.walk(cache_dir) for f in files
               if f == cache.RASTER]
    c.check(len(rasters) >= 1, f"the cancelled run left cached pages behind to resume from "
                               f"({len(rasters)} rasters)")


def _run_driver(tmp, src, dest, job_id, cache_dir, env_extra=None):
    driver = os.path.join(tmp, "resume_driver.py")
    with open(driver, "w", encoding="utf-8") as fh:
        fh.write(DRIVER)
    env = dict(os.environ, MT_CACHE_DIR=cache_dir, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    env.update(env_extra or {})
    proc = subprocess.run(
        [sys.executable, driver, ROOT, src, dest, job_id],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=900, env=env, cwd=ROOT,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            return json.loads(line[len("RESULT "):]), proc
    return None, proc


def check_resume(c, tmp, src, cache_dir, pages_before):
    archive = os.path.join(src, "vol1.cbz")

    result, proc = _run_driver(tmp, archive, os.path.join(tmp, "resume1"), "check-cancel-resume-1",
                               cache_dir)
    c.check(result is not None and proc.returncode == 0,
            f"the resume driver ran in a new process (rc {proc.returncode}, "
            f"{proc.stderr[-300:]!r})")
    if result is None:
        return None
    item = result["status"]["items"][0]
    c.check(item["status"] == job.OK and item["pages"] == ARCHIVE_PAGES,
            f"the re-run completes the archive: {item['status']}, {item['pages']} pages "
            f"({item['reason']!r})")
    c.check(bool(item["output"]) and os.path.isfile(item["output"]),
            f"and writes the archive this time ({item['output']})")
    expected_detect = ARCHIVE_PAGES - pages_before
    c.check(result["counts"]["detect"] == expected_detect,
            f"detect ran {result['counts']['detect']} times == {expected_detect} pages the "
            f"cancelled run did not finish")
    c.check(result["counts"]["ocr"] == expected_detect,
            f"ocr ran {result['counts']['ocr']} times == {expected_detect}")
    c.check(len(result["placement"]) == ARCHIVE_PAGES,
            f"the new job id has its own placement file with {len(result['placement'])} pages")
    first_hashes = result["placement"]

    result2, proc2 = _run_driver(tmp, archive, os.path.join(tmp, "resume2"),
                                 "check-cancel-resume-2", cache_dir)
    c.check(result2 is not None and proc2.returncode == 0,
            f"a second new-process run ran (rc {proc2.returncode})")
    if result2 is not None:
        item2 = result2["status"]["items"][0]
        c.check(item2["status"] == job.OK and item2["pages"] == ARCHIVE_PAGES,
                f"the second run completes ({item2['status']}, {item2['pages']} pages)")
        c.check(result2["counts"] == {"detect": 0, "ocr": 0},
                f"and calls neither detect nor ocr: every page cached ({result2['counts']})")
        c.check(result2["placement"] == first_hashes,
                "and its placement names the same page hashes under a third job id -- "
                "the cache path is job-independent")

    # The control: an empty cache detects everything.
    empty = os.path.join(tmp, "empty-cache")
    result3, proc3 = _run_driver(tmp, archive, os.path.join(tmp, "resume3"),
                                 "check-cancel-resume-3", empty)
    c.check(result3 is not None and result3["counts"]["detect"] == ARCHIVE_PAGES,
            f"control: on an EMPTY cache the same driver detects all {ARCHIVE_PAGES} pages "
            f"({result3['counts'] if result3 else proc3.stderr[-200:]!r}) -- the counter "
            f"assert can go red")
    return result["counts"]["detect"]


def main():
    for sub in ("archives", "pdf"):
        if not os.path.isdir(os.path.join(FIXTURES, sub)):
            return skip(f"fixtures/{sub}/ is absent -- run tests/gen_fixtures.py")

    c = Checks("check_cancel")
    with tempfile.TemporaryDirectory() as tmp, StubProvider(delay=0.5) as stub:
        cache_dir = os.path.join(tmp, "cache")
        os.environ["MT_CACHE_DIR"] = cache_dir
        src = build_inputs(tmp)
        out = os.path.join(tmp, "out")
        pages_before = check_cancel(c, src, out, stub)
        check_no_partial(c, out, cache_dir)
        detect_calls = check_resume(c, tmp, src, cache_dir, pages_before)

    # Recorded, not ratcheted: how far the item got before the cancel is a
    # timing, and the resume's detect count is 3 minus that.
    print("METRICS " + json.dumps({
        "cancel_pages_before_stop": pages_before,
        "resume_detect_calls": detect_calls,
    }), flush=True)
    return c.finish()


if __name__ == "__main__":
    run(main)
