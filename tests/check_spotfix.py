r"""Phase 3 -- the spot-fix editor and the page cache (AC-10). OFFLINE.

    uv run --project sidecar python tests\check_spotfix.py

Exit-code contract, all four reachable here:
    0 pass · 1 fail · 2 inconclusive (below the 3.0s gate's hardware floor)
    · 3 skip (the CBZ fixture is absent)

**Every assert carries a bracketed tag**, and the tags are the interface a
red-check keys on. Phase 2a lost a round to a red-check that looked for
`[overflow]` after the assert had been renamed `[page-overflow]`, reported a
miss, and was very nearly counted as a hole in the gate rather than as a
stale tag. Rename a tag here and the sabotage list in progress.txt goes with
it.

One ingest, then copies. Detection and OCR over eight pages cost about twenty
seconds, and nine of the eleven sections below need a cache that they then
mutate. So the archive is ingested ONCE into a pristine tree and each section
gets its own copy of it -- which also means no section can pass because of a
change another section made, and the order they run in does not matter.

The three timing-sensitive claims are measured, never assumed:
  * the 3.0s re-render budget, against a MEASURED hardware floor -- a
    page-sized raster pass timed at startup, not a clock speed read off
    WMI, which on a modern hybrid desktop reports a rated number well
    below what the machine does;
  * "zero LLM requests on the re-render path", counted at the stub SERVER, not
    at the client, because a client-side counter cannot see a request a second
    code path made;
  * "detection and OCR were never called", by patching both entrypoints to
    increment-and-raise, so an indirect call is caught as loudly as a direct
    one -- and a source-text assert would not have been.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import INCONCLUSIVE, PASS, Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402

CBZ = os.path.join(ROOT, "fixtures", "cbz", "sample.cbz")
EXPECTED = os.path.join(ROOT, "fixtures", "cbz", "expected.json")

# §E's floor for the 3.0s gate. Below it the measured time is printed and not
# asserted: a timing gate on an undeclared machine is flaky by construction,
# and a flaky gate gets disabled, which is worse than an honest inconclusive.
#
# The floor MEASURES the machine rather than reading its nameplate. It used to
# require 8 physical cores at >= 3000MHz: psutil takes cpu_freq().max from
# WMI's MaxClockSpeed on Windows, a static rated number, and a 24-core Arrow
# Lake desktop reports current == max == 2700MHz -- so a machine that
# re-renders in 0.03s, a hundredth of the budget, was ruled below the floor by
# a label. The rule was written when base clock still tracked performance; a
# nameplate is not a measurement, and this file asserts nothing else it has
# not measured.
FLOOR_RAM = 16 * 1024**3
BUDGET_S = 3.0

# One reference page's worth of raster work: the blur, resample and byte pass
# that dominate a re-render. On the box this was calibrated on it takes 0.091s
# against a real re-render of 0.03s, so the workload is about THREE
# re-renders' worth of pixels -- that ratio is what makes the allowance below
# derivable instead of picked.
CALIB_REPS = 3
CALIB_TO_RERENDER = 3.0   # measured: 0.091s calibration / 0.03s re-render
FLOOR_MARGIN = 3.0        # the expected re-render must be <= a third of the budget
CALIB_ALLOWANCE_S = BUDGET_S * CALIB_TO_RERENDER / FLOOR_MARGIN

# The measurements the METRICS line carries, filled by the calibration and the
# wallclock section. A module-level dict because sections return their own
# verdicts, not their timings.
MEASURED = {}

# The identical pair the fixture is built around. Read from expected.json
# rather than hard-coded, so regenerating the fixture with a different layout
# moves the asserts with it instead of silently testing the wrong pages.
JOB_A, JOB_B, JOB_DEAD = "job-a", "job-b", "job-killed"


def _reset(cache_dir: str):
    """Point the cache at `cache_dir` and clear every in-process remnant.

    The tier, the running set and the once-per-job warning set are module
    globals, and a section that inherited another section's warning set would
    read a suppressed warning as an absent one.
    """
    from sidecar import cache

    os.environ["MT_CACHE_DIR"] = cache_dir
    os.environ.pop("MT_CACHE_CAP_BYTES", None)
    os.environ.pop("MT_CACHE_TARGET_BYTES", None)
    cache.clear_tier()
    cache._running.clear()
    cache._warned.clear()
    return cache


def _quiet(fn, *a, **kw):
    """Run `fn` with stdout swallowed. The pipeline emits a progress line per
    stage, and eight pages of them bury the asserts this file prints."""
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        out = fn(*a, **kw)
    return out, buf.getvalue()


def _call(c: Checks, tag: str, fn, *a, **kw):
    """Run a pipeline entry point; an exception is a RED assert, not a dead run.

    Every section calls rerender or run_item, and each raises CacheMiss on a
    cache the section did not expect -- which is exactly what several
    sabotages produce. Left to propagate, the exception kills the check before
    the assert that would have named the defect, every later tag goes absent,
    and the red-check misreads a hole as a stale tag. Caught here, the call
    site gets None and its own assert goes red with the exception's text.
    """
    try:
        return _quiet(fn, *a, **kw)[0]
    except Exception as e:  # noqa: BLE001 -- the point is to report, not to filter
        c.check(False, f"{tag} {fn.__name__} raised {type(e).__name__}: {e}")
        return None


def _no_detect_or_ocr():
    """Patch both entrypoints to increment-and-RAISE. Returns (counter, undo).

    Increment *and* raise, not increment alone: a path that called detection
    and carried on would otherwise produce a plausible-looking record and only
    a number would object. Raising makes the failure land where it happened.
    """
    from sidecar import detect as detector
    from sidecar import ocr_ja

    calls = {"detect": 0, "ocr": 0}
    real = (detector.detect, ocr_ja.ocr)

    def boom_detect(*a, **kw):
        calls["detect"] += 1
        raise AssertionError("detect.detect was called on a cached path")

    def boom_ocr(*a, **kw):
        calls["ocr"] += 1
        raise AssertionError("ocr_ja.ocr was called on a cached path")

    detector.detect, ocr_ja.ocr = boom_detect, boom_ocr

    def undo():
        detector.detect, ocr_ja.ocr = real

    return calls, undo


def _calibrate():
    """Seconds for one reference page's worth of raster work. Best of N.

    Deterministic, offline, and built from the same primitives the re-render
    spends its time in -- a gaussian blur over a page-sized RGB buffer, a
    LANCZOS resample, a float pass and an encode. Best-of-N rather than a
    mean: the question is what the machine CAN do, and a scheduler hiccup
    during one repetition is not evidence that it cannot.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    h, w = 1400, 2048
    base = np.arange(h * w * 3, dtype=np.uint8).reshape(h, w, 3)
    best = float("inf")
    for _ in range(CALIB_REPS):
        t = time.perf_counter()
        img = Image.fromarray(base, "RGB").filter(ImageFilter.GaussianBlur(4))
        img = img.resize((w // 2, h // 2), Image.LANCZOS)
        arr = np.asarray(img, dtype=np.float32)
        arr = (arr * 0.5 + 8.0).clip(0, 255).astype(np.uint8)
        Image.fromarray(arr, "RGB").tobytes()
        best = min(best, time.perf_counter() - t)
    return best


def _above_floor():
    """(ok, description) for §E's hardware floor. Measured, not read off a label.

    MT_SPOTFIX_FLOOR_S can only make the allowance STRICTER -- it is how the
    red check proves the floor still refuses, and a knob that could loosen it
    would be a way to manufacture a green on a machine that cannot hold the
    budget.
    """
    try:
        import psutil
    except ImportError:
        return False, "psutil is not installed; the floor cannot be measured"

    ram = psutil.virtual_memory().total
    calib = _calibrate()
    MEASURED["spotfix_calib_s"] = round(calib, 4)

    allowance = CALIB_ALLOWANCE_S
    override = os.environ.get("MT_SPOTFIX_FLOOR_S", "").strip()
    if override:
        try:
            allowance = min(allowance, float(override))
        except ValueError:
            pass

    ok = calib <= allowance and ram >= FLOOR_RAM
    return ok, (f"{calib:.3f}s for a page of raster work (allowance "
                f"{allowance:.3f}s, {allowance / calib:.0f}x margin), "
                f"{ram / 1024**3:.1f}GB RAM")


def _sha(path):
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# -- sections --------------------------------------------------------------


def section_read_cbz(c: Checks, expected: dict):
    """[order] [skip-junk] [no-holes] [read-only]"""
    from sidecar.containers import read_cbz

    got = read_cbz.members(CBZ)
    c.check(
        got == expected["candidate_members"],
        f"[order] members come back in natural order of the FULL path -- ch2 "
        f"before ch10 and p9 before p10, in the same ordering: {got}",
    )
    c.check(
        expected["natural_order"] != expected["lexicographic_order"],
        "[order] the fixture's natural and lexicographic orders DIFFER, so a "
        "reader that sorted the wrong way cannot pass this section",
    )

    pages, _ = _quiet(lambda: list(read_cbz.pages(CBZ)))
    ordinals = [o for o, _n, _i in pages]
    c.check(
        ordinals == list(range(1, len(pages) + 1)),
        f"[no-holes] ordinals are 1-based and contiguous across skipped and "
        f"undecodable members: {ordinals}",
    )
    c.check(
        [n for _o, n, _i in pages] == expected["natural_order"],
        "[order] pages() yields the member NAME alongside the image, in the "
        "same order members() reports",
    )
    names = {n for _o, n, _i in pages}
    c.check(
        not (names & set(expected["skipped_members"])),
        f"[skip-junk] no junk or undecodable member is yielded as a page: "
        f"{sorted(names & set(expected['skipped_members']))}",
    )
    c.check(
        all(i.format for _o, _n, i in pages),
        "[order] each yielded image keeps its SOURCE format, so the delivered "
        "page is not silently re-encoded into another one",
    )

    # Read-only, asserted on the ARCHIVE rather than on the source text. The
    # first draft grepped read_cbz.py for write modes and for `zf.read(` -- and
    # one of those greps agreed with a false statement: pages() does read a
    # member whole on the non-seekable branch, spelled `stream.read()`, which
    # the grep did not look for. A byte-identical archive after enumeration is
    # what read-only means; a source pattern is what it looks like.
    before = _sha(CBZ)
    mtime = os.path.getmtime(CBZ)
    _quiet(lambda: list(read_cbz.pages(CBZ)))
    c.check(
        _sha(CBZ) == before and os.path.getmtime(CBZ) == mtime,
        "[read-only] enumerating every page leaves the archive byte-identical "
        "with its mtime untouched -- nothing repacked, nothing written",
    )
    junk = [f for f in os.listdir(os.path.dirname(CBZ)) if not f.endswith((".cbz", ".json"))]
    c.check(
        not junk,
        f"[read-only] and nothing was extracted beside it: {junk}",
    )


def section_key(c: Checks):
    """[key] the hash is over decoded pixels, and mode and size are in it."""
    import io as _io

    from PIL import Image

    from sidecar import cache

    img = Image.new("RGB", (40, 25), "white")
    img.putpixel((3, 3), (200, 10, 10))

    # Same pixels, two different containers and therefore two different files.
    # This is the case the cache exists for: a re-saved page, or the same page
    # arriving from a PDF rather than a CBZ.
    as_png, as_bmp = _io.BytesIO(), _io.BytesIO()
    img.save(as_png, "PNG")
    img.save(as_bmp, "BMP")
    c.check(
        as_png.getvalue() != as_bmp.getvalue(),
        "[key] the two encodings really are different FILES, so the next "
        "assert is not comparing a file with itself",
    )
    def _as_delivered(raw: bytes):
        """Decode exactly the way read_cbz hands a page to the cache.

        The `.format` restore matters, and this section was wrong without it.
        `convert()` drops format, so converting before hashing normalised the
        container away -- and a page_hash that let the container INTO the
        digest passed here while breaking the real pipeline, where read_cbz
        deliberately puts format back so the delivered page can be re-encoded
        in its source format. A check has to feed page_hash what the pipeline
        feeds it, not a tidier version of it. Caught by the red-check, which
        reported a hole rather than a stale tag and was right.
        """
        with Image.open(_io.BytesIO(raw)) as im:
            im.load()
            fmt = im.format
            out = im.convert("RGB")
        out.format = fmt
        return out

    a, b = _as_delivered(as_png.getvalue()), _as_delivered(as_bmp.getvalue())
    c.check(
        a.format != b.format,
        f"[key] and the two decoded images still REMEMBER which container they "
        f"came from ({a.format} vs {b.format}), so the next assert tests the "
        f"digest rather than a value convert() had already thrown away",
    )
    ha, hb = cache.page_hash(a), cache.page_hash(b)
    c.check(
        ha == hb,
        "[key] identical decoded pixels from two different containers hash "
        "EQUAL -- a file-byte hash would report a miss here",
    )

    other = img.copy()
    other.putpixel((3, 3), (10, 200, 10))
    c.check(
        cache.page_hash(other) != ha,
        "[key] one differing pixel changes the hash",
    )
    tall = Image.new("L", (25, 40), 0)
    wide = Image.new("L", (40, 25), 0)
    c.check(
        cache.page_hash(tall) != cache.page_hash(wide),
        "[key] two images with the same byte count and transposed dimensions "
        "hash differently -- mode and size are IN the digest, not assumed",
    )

    slug_a, slug_b = cache.model_slug("gpt-4o"), cache.model_slug("gpt/4o")
    c.check(
        slug_a != slug_b,
        f"[key] two model ids that sanitise to the same readable name still "
        f"get different slugs: {slug_a} vs {slug_b}",
    )


def section_layout(c: Checks, cache_dir: str, record: dict):
    """[layout] content-keyed page directories, job-keyed placement only."""
    cache = _reset(cache_dir)

    top = sorted(os.listdir(cache.root()))
    c.check(top == ["jobs", "pages"],
            f"[layout] the cache root holds exactly pages/ and jobs/: {top}")

    h = record["pages"][0]["page_hash"]
    # os.path.isdir first, not a bare listdir. A cache whose page directory is
    # not where this check expects it is exactly the defect [crossjob] below
    # exists to catch, and a section that raises FileNotFoundError instead of
    # failing an assert takes every later section down with it -- so the gate
    # reports "no page directory" and carries on to the asserts that name the
    # cause.
    d = cache.page_dir(h)
    files = sorted(os.listdir(d)) if os.path.isdir(d) else []
    c.check(
        "regions.json" in files and cache.RASTER in files and "refs.json" in files,
        f"[layout] a page directory holds regions.json, {cache.RASTER} and "
        f"refs.json: {files or f'no directory at {d}'}",
    )
    c.check(
        JOB_A not in cache.page_dir(h),
        "[layout] no job id appears anywhere in a page's PATH -- the whole "
        "basis of the cross-job assert below",
    )
    c.check(
        os.path.exists(os.path.join(cache.job_dir(JOB_A), "placement.json")),
        "[layout] the job directory holds placement.json and nothing a second "
        "job would need",
    )

    stored = cache.read_regions(h) or {"regions": []}
    keys = {"fit_compromised", "fit_failed", "typeset", "rung", "font_px"}
    c.check(
        bool(stored["regions"]) and all(keys <= set(r) for r in stored["regions"]),
        "[layout] regions.json round-trips the full typeset result the editor "
        "sorts on",
    )


def section_crossjob(c: Checks, cache_dir: str, out_dir: str):
    """[crossjob] a NEW job_id reads the same pages. The regression's own gate."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    calls, undo = _no_detect_or_ocr()
    try:
        record, _ = _quiet(pipeline.run_item, CBZ, out_dir, JOB_B)
    except AssertionError as e:
        undo()
        c.check(False, f"[crossjob] second job re-ran a stage: {e}")
        return None
    finally:
        undo()

    c.check(
        calls == {"detect": 0, "ocr": 0},
        f"[crossjob] a second job with a NEW job_id calls detection and OCR "
        f"ZERO times: {calls}",
    )
    c.check(
        all(p["cached"] for p in record["pages"]),
        "[crossjob] every page of the second job reports a cache hit",
    )
    c.check(
        all(p["ocr_calls"] == 0 and p["inpaint_calls"] == 0 for p in record["pages"]),
        "[crossjob] the second job's record says zero OCR and zero inpaint calls",
    )
    h = record["pages"][0]["page_hash"]
    c.check(
        sorted(cache.read_refs(h)) == sorted([JOB_A, JOB_B]),
        f"[refs] both jobs appear in the page's refs.json: {cache.read_refs(h)}",
    )
    return record


def section_placement(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[placement] two identical pages, one edit, one changed output."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    p3, p7 = record["pages"][2], record["pages"][6]
    c.check(
        p3["page_hash"] == p7["page_hash"],
        "[placement] ordinals 3 and 7 are byte-identical pages and DO share a "
        "page hash -- sharing the translation is correct; sharing the edit is "
        "the bug",
    )
    c.check(
        p3["output"] != p7["output"],
        f"[placement] they still deliver to two different files: "
        f"{os.path.basename(p3['output'])} vs {os.path.basename(p7['output'])}",
    )
    before7 = _sha(p7["output"])
    rid = record["pages"][2]["regions"][0]["id"]

    fresh = _call(c, "[placement]", pipeline.rerender, JOB_B, record["item_id"], 3, rid,
                  "ORDINAL THREE ONLY", out_dir) or {}
    after3, after7 = _sha(p3["output"]), _sha(p7["output"])
    c.check(
        after7 == before7,
        "[placement] editing ordinal 3 leaves ordinal 7's DELIVERED FILE "
        "byte-identical",
    )
    c.check(
        after3 != after7,
        "[placement] and ordinal 3's delivered file now differs from 7's",
    )

    # The RESPONSE must name the position that was edited, because the UI
    # posts back whatever it was handed. The review reproduced the failure:
    # the shared content record carried ordinal 7's page and member, rerender
    # returned them for an edit of ordinal 3, and the user's SECOND edit went
    # to page 7. Defect A fixed delivery; this is the same confusion one layer
    # up, and it is asserted by doing exactly what the UI does -- a second
    # edit addressed by the first response's own `page`.
    placed = cache.get_placement(JOB_B, record["item_id"], 3) or {}
    c.check(
        fresh.get("page") == 3 and fresh.get("member") == placed.get("member")
        and fresh.get("item_id") == record["item_id"],
        f"[placement] the response names ordinal 3 and its own member, not "
        f"the shared record's: page={fresh.get('page')} member={fresh.get('member')!r}",
    )
    before7 = _sha(p7["output"])
    if fresh.get("page") is not None:
        _call(c, "[placement]", pipeline.rerender, JOB_B, fresh.get("item_id"),
              fresh["page"], rid, "SECOND EDIT, ADDRESSED BY THE FIRST RESPONSE", out_dir)
    c.check(
        _sha(p7["output"]) == before7,
        "[placement] a second edit addressed by the first response's `page` "
        "still leaves ordinal 7's file byte-identical",
    )
    stored = cache.read_regions(p3["page_hash"]) or {}
    leaked = sorted(k for k in ("page", "member", "item_id", "output",
                                "edited_region", "edit_on_other_model")
                    if k in stored)
    c.check(
        not leaked,
        f"[placement] no per-POSITION field is persisted in the content-keyed "
        f"regions.json: {leaked or 'none'}",
    )
    placement = cache.read_placement(JOB_B)
    c.check(
        len(placement) == len(record["pages"]),
        f"[placement] placement holds one entry per ORDINAL, not per hash: "
        f"{len(placement)} entries for {len(record['pages'])} pages",
    )


def section_wallclock(c: Checks, cache_dir: str, out_dir: str, record: dict,
                      floor_ok: bool, floor_desc: str):
    """[wallclock] AC-10's 3.0s budget, with detection and OCR fenced off."""
    _reset(cache_dir)
    from sidecar import pipeline

    rid = record["pages"][0]["regions"][0]["id"]
    calls, undo = _no_detect_or_ocr()
    try:
        t = time.perf_counter()
        out, _ = _quiet(pipeline.rerender, JOB_B, record["item_id"], 1, rid,
                        "A SHORT FIX", out_dir)
        elapsed = time.perf_counter() - t
        MEASURED["spotfix_rerender_s"] = round(elapsed, 4)
    except AssertionError as e:
        undo()
        c.check(False, f"[wallclock] the re-render path ran a forbidden stage: {e}")
        return
    finally:
        undo()

    c.check(
        calls == {"detect": 0, "ocr": 0},
        f"[wallclock] the re-render called neither the detector nor OCR: {calls}",
    )
    if floor_ok:
        c.check(
            elapsed < BUDGET_S,
            f"[wallclock] one region edited and the page re-rendered in "
            f"{elapsed:.2f}s, under AC-10's {BUDGET_S}s budget ({floor_desc})",
        )
    else:
        print(
            f"  [--] INCONCLUSIVE: re-render took {elapsed:.2f}s but this "
            f"machine is below §E's floor ({floor_desc}); the 3.0s gate is "
            f"measured and not asserted",
            flush=True,
        )
    c.check(out["edited_region"] == rid,
            "[wallclock] the response names the region that was edited")


def section_flags(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[flag] the fit flags are RECOMPUTED, and regions.json is write-only for them."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    item, rid = record["item_id"], record["pages"][0]["regions"][0]["id"]
    h = record["pages"][0]["page_hash"]

    # Phase 2b hands the ladder the whole bubble interior, not the text block,
    # so "far too long" is measured against the BUBBLE: at the 12px floor a
    # fixture bubble holds well over a thousand characters, and the sentence
    # that once overflowed a column fits it. Fifteen copies do not.
    long_text = " ".join([
        "I told you already that we should never have opened that door because "
        "whatever waits behind it has been patient for a very long time indeed "
        "and it remembers every single one of us by name"
    ] * 15)
    out, _ = _quiet(pipeline.rerender, JOB_B, item, 1, rid, long_text, out_dir)
    flagged = next(r for r in out["regions"] if r["id"] == rid)
    c.check(
        flagged["fit_failed"] or flagged["fit_compromised"],
        f"[flag] an edit far too long for its bubble comes back flagged "
        f"(failed={flagged['fit_failed']}, compromised={flagged['fit_compromised']}, "
        f"reason={flagged.get('fit_reason')!r})",
    )

    # POISON the stored record: flags true, and a short text beside them. An
    # implementation that LOADED the flags would hand them straight back. This
    # is the assert that makes "derived, never read back" testable at all --
    # without it, a loader and a recomputer are indistinguishable whenever the
    # stored value happens to be right.
    stored = cache.read_regions(h)
    for r in stored["regions"]:
        if r["id"] == rid:
            r["fit_compromised"] = r["fit_failed"] = True
    cache.write_regions(h, stored)

    out2, _ = _quiet(pipeline.rerender, JOB_B, item, 1, rid, "OK", out_dir)
    cleared = next(r for r in out2["regions"] if r["id"] == rid)
    c.check(
        not cleared["fit_compromised"] and not cleared["fit_failed"],
        f"[flag] a short edit clears BOTH flags even though regions.json was "
        f"poisoned with them set -- the flags are recomputed from the geometry, "
        f"not loaded (failed={cleared['fit_failed']}, "
        f"compromised={cleared['fit_compromised']})",
    )
    c.check(
        rid not in out2["fit_summary"]["fit_failed"],
        "[flag] the job summary the editor sorts on agrees with the per-region "
        "flags after the re-render",
    )


def section_edits(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[edit] an edit is a translation, and a re-translation never overwrites it."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    item = record["item_id"]
    h = record["pages"][1]["page_hash"]
    regions = record["pages"][1]["regions"]
    rid, other = regions[0]["id"], regions[1]["id"]

    _quiet(pipeline.rerender, JOB_B, item, 2, rid, "MY OWN WORDS", out_dir)
    stored = cache.read_translation(h, "en", "offline")
    c.check(
        stored[str(rid)] == {"text": "MY OWN WORDS", "edited": True},
        f"[edit] the edit lands in the translation file as "
        f"{{text, edited: true}}: {stored.get(str(rid))}",
    )

    # A re-translation of the same page at the same (lang, model). The provider
    # both re-answers the edited region AND omits it, in two passes, because an
    # omission is the case where the stored text is all that is left.
    cache.write_translation(h, "en", "offline",
                            {rid: "PROVIDER OVERWRITE", other: "FRESH"})
    after = cache.read_translation(h, "en", "offline")
    c.check(
        after[str(rid)]["text"] == "MY OWN WORDS" and after[str(rid)]["edited"],
        f"[edit] a re-translation at the SAME (lang, model) leaves the edited "
        f"entry untouched: {after.get(str(rid))}",
    )
    c.check(
        after[str(other)]["text"] == "FRESH",
        "[edit] and it does update the regions that were not edited",
    )

    cache.write_translation(h, "en", "offline", {other: "ONLY THIS ONE"})
    after = cache.read_translation(h, "en", "offline")
    c.check(
        after[str(rid)]["text"] == "MY OWN WORDS",
        "[edit] an edited region the new translation OMITS entirely is still "
        "preserved -- a provider that drops an id must not erase the user's text",
    )

    other_lang = cache.read_translation(h, "id", "offline")
    c.check(
        str(rid) not in other_lang,
        "[edit] changing target language reads a DIFFERENT file: the edit does "
        "not leak across the pair it was made against",
    )
    c.check(
        cache.translation_name("en", "offline") != cache.translation_name("en", "other"),
        "[edit] and changing model does too",
    )
    c.check(
        not cache.has_edit_for_other_model(h, "en", "offline"),
        "[edit] has_edit_for_other_model is False for the pair the edit was "
        "made against",
    )
    c.check(
        cache.has_edit_for_other_model(h, "en", "another-model"),
        "[edit] and True from a different model, so the UI can say an edit "
        "exists elsewhere without importing it",
    )


def section_refs(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[refs] a list of ids, a survivable delete, and a repairable mid-run kill."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    h = record["pages"][0]["page_hash"]
    raw = json.load(open(os.path.join(cache.page_dir(h), "refs.json"), encoding="utf-8"))
    c.check(
        isinstance(raw, list) and all(isinstance(x, str) for x in raw),
        f"[refs] refs.json is a LIST of job id strings, never an integer "
        f"count: {raw!r}",
    )

    hashes = sorted(cache.placed_hashes(JOB_B))
    removed = cache.delete_job(JOB_A)
    c.check(
        removed == [],
        f"[refs] deleting job A removes no page directory, because job B still "
        f"holds every one: {removed}",
    )
    c.check(
        all(os.path.isdir(cache.page_dir(x)) for x in hashes),
        "[refs] the page directories survive the delete",
    )
    c.check(
        all(JOB_A not in cache.read_refs(x) for x in hashes),
        "[refs] and A's id is gone from every refs.json",
    )
    c.check(
        not os.path.isdir(cache.job_dir(JOB_A)),
        "[refs] A's placement file is gone with it",
    )

    calls, undo = _no_detect_or_ocr()
    try:
        again, _ = _quiet(pipeline.run_item, CBZ, out_dir, JOB_B)
    finally:
        undo()
    c.check(
        calls == {"detect": 0, "ocr": 0} and all(p["cached"] for p in again["pages"]),
        f"[refs] job B still resumes entirely from cache\\pages\\ after A was "
        f"deleted: {calls}",
    )

    # A job killed mid-run: its running marker is on disk and nothing cleared
    # it. Simulated by writing exactly what a live job writes and then NOT
    # clearing -- which is what a killed process leaves behind.
    cache.mark_running(JOB_DEAD)
    for x in hashes:
        cache.put_placement(JOB_DEAD, record["item_id"], hashes.index(x) + 1, x)
    cache._running.clear()  # the process went away; only the marker survives
    # ... and the marker names a pid that no longer exists. mark_running wrote
    # OUR pid, which is alive, and prune must not touch a job whose process is.
    cache._write_json(os.path.join(cache.job_dir(JOB_DEAD), cache.RUNNING),
                      {"pid": 999_999_999})
    c.check(
        all(JOB_DEAD in cache.read_refs(x) for x in hashes),
        "[refs] the killed job's id is in every page it touched -- the leak",
    )

    pruned = cache.prune_refs()
    c.check(
        pruned > 0,
        f"[refs] the startup prune reports the repair it made: {pruned} "
        f"references removed",
    )
    c.check(
        all(JOB_DEAD not in cache.read_refs(x) for x in hashes),
        "[refs] and the killed job's id is gone from every refs.json",
    )
    c.check(
        not os.path.isdir(cache.job_dir(JOB_DEAD)),
        "[refs] its job directory, running marker and all, is gone too",
    )
    c.check(
        all(os.path.isdir(cache.page_dir(x)) for x in hashes),
        "[refs] the pages themselves survive -- job B still holds them, and "
        "they are evictable again rather than pinned forever",
    )

    cache.mark_running(JOB_B)
    survivor = cache.prune_refs()
    c.check(
        survivor == 0 and os.path.isdir(cache.job_dir(JOB_B)),
        "[refs] a prune while a job is genuinely running in THIS process "
        "leaves it alone -- tidying up must not kill live jobs",
    )
    cache.clear_running(JOB_B)

    # Another INSTANCE's live job: its marker is on disk, its id is not in our
    # running set, and its pid is alive. The first draft would have deleted
    # it. Simulated with our own pid, which is as alive as a pid gets.
    cache._write_json(os.path.join(cache.job_dir("other-instance"), cache.RUNNING),
                      {"pid": os.getpid()})
    cache.put_placement("other-instance", record["item_id"], 1, hashes[0])
    cache.prune_refs()
    c.check(
        os.path.isdir(cache.job_dir("other-instance"))
        and "other-instance" in cache.read_refs(hashes[0]),
        "[refs] a marker whose pid is ALIVE belongs to another sidecar "
        "instance's live job, and prune leaves it alone -- the pid is written "
        "for this and the first draft never read it",
    )
    cache.delete_job("other-instance")

    # The sole holder dies. The plan says its pages become EVICTABLE AGAIN; the
    # first draft deleted them, which the review measured: a job that was the
    # only holder of its pages had every one removed at the next launch --
    # Phase 9's scenario, and the pages AC-13's re-run exists to reuse.
    cache.mark_running("solo")
    for x in hashes:
        cache.put_placement("solo", record["item_id"], hashes.index(x) + 1, x)
        # Make "solo" the ONLY holder. delete_job on the previous holder would
        # correctly have removed the pages (a page reaching zero references
        # is removed on explicit delete); the case here is a page whose one
        # remaining reference belongs to a job that then died.
        cache._write_json(os.path.join(cache.page_dir(x), cache.REFS), ["solo"])
    cache._running.clear()
    cache._write_json(os.path.join(cache.job_dir("solo"), cache.RUNNING),
                      {"pid": 999_999_999})
    cache.prune_refs()
    c.check(
        all(os.path.isdir(cache.page_dir(x)) for x in hashes)
        and all(cache.read_refs(x) == [] for x in hashes)
        and not os.path.isdir(cache.job_dir("solo")),
        "[refs] a dead job that was the SOLE holder of its pages loses its "
        "directory and its references -- and the pages survive with refs [], "
        "evictable rather than destroyed",
    )
    calls, undo = _no_detect_or_ocr()
    try:
        again, _ = _quiet(pipeline.run_item, CBZ, out_dir, "after-solo")
    finally:
        undo()
    c.check(
        calls == {"detect": 0, "ocr": 0} and all(p["cached"] for p in again["pages"]),
        f"[refs] and a re-run finds every one of them through its content hash "
        f"with zero detect/OCR: {calls}",
    )

    # Concurrency, measured rather than argued. The review ran six threads at
    # one page's refs.json and got 72 PermissionErrors out of 240 add_ref calls
    # -- atomic_write's temp name was keyed on the pid alone, so two threads in
    # one process opened the same temp file -- and on another run lost five of
    # six ids to interleaved read-modify-write. Both failures are on the
    # path two concurrent /api/item requests take today.
    import threading

    target = hashes[1]
    errors: list[str] = []

    def hammer(job):
        for _ in range(40):
            try:
                cache.add_ref(target, job)
            except Exception as e:  # noqa: BLE001 -- the assert is that none happen
                errors.append(f"{job}: {type(e).__name__}: {e}")

    workers = [threading.Thread(target=hammer, args=(f"thread-{i}",)) for i in range(6)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    got = sorted(r for r in cache.read_refs(target) if r.startswith("thread-"))
    c.check(
        not errors and got == [f"thread-{i}" for i in range(6)],
        f"[refs] six threads x forty add_ref calls on one page: every id "
        f"survives and nothing raises (errors={errors[:2]}, ids={got})",
    )


def section_cap(c: Checks, cache_dir: str, record: dict):
    """[cap] LRU by mtime, touched on read, two skips, and an honest overflow."""
    cache = _reset(cache_dir)

    hashes = sorted({p["page_hash"] for p in record["pages"]})
    old = time.time() - 10_000
    for h in hashes:
        os.utime(cache.page_dir(h), (old, old))

    hot = hashes[0]
    cache.read_regions(hot)
    c.check(
        os.path.getmtime(cache.page_dir(hot)) > old + 1,
        "[cap] a page directory is touched on READ, not only on write -- "
        "without this the cap evicts the hot set the content key exists to keep",
    )
    c.check(
        all(abs(os.path.getmtime(cache.page_dir(h)) - old) < 2
            for h in hashes if h != hot),
        "[cap] and reading one page does not touch the others",
    )

    total = cache.disk_bytes()
    os.environ["MT_CACHE_CAP_BYTES"] = str(int(total * 0.7))
    os.environ["MT_CACHE_TARGET_BYTES"] = str(int(total * 0.5))
    warning = cache.enforce_cap("cap-job")
    c.check(
        warning is None and cache.disk_bytes() <= int(total * 0.5),
        f"[cap] crossing the cap evicts LRU down to the target with no "
        f"warning: {cache.disk_bytes()} <= {int(total * 0.5)}, warning={warning!r}",
    )
    c.check(
        os.path.isdir(cache.page_dir(hot)),
        "[cap] the page that was READ survives while colder, later-WRITTEN "
        "pages are evicted -- the whole point of touching on read",
    )

    # Now pin everything left and force the overflow path.
    cache._warned.clear()
    left = [h for h in hashes if os.path.isdir(cache.page_dir(h))]
    c.check(bool(left), "[cap] pages remain to pin for the overflow case")
    cache.write_edit(left[0], "en", "offline", 1, "a correction")
    for h in left[1:]:
        cache.add_ref(h, "cap-running")
    cache.mark_running("cap-running")

    os.environ["MT_CACHE_CAP_BYTES"] = "1"
    os.environ["MT_CACHE_TARGET_BYTES"] = "1"
    before = cache.disk_bytes()
    warning = cache.enforce_cap("cap-job")
    c.check(
        cache.disk_bytes() == before,
        "[cap] with every page pinned by a user correction or a running job, "
        "nothing is evicted -- evicting either to honour a number is the worse "
        "failure",
    )
    c.check(
        bool(warning) and "over its" in (warning or ""),
        f"[cap] and the cache SAYS it is over its cap, naming the achieved "
        f"size and the reason: {warning!r}",
    )
    c.check(
        "correction" in (warning or "") or "running job" in (warning or ""),
        f"[cap] the warning names WHICH skip held the pages: {warning!r}",
    )
    c.check(
        cache.enforce_cap("cap-job") is None,
        "[cap] the warning is emitted at most ONCE per job, however many times "
        "eviction is attempted in it",
    )
    c.check(
        bool(cache.enforce_cap("a-different-job")),
        "[cap] and a different job gets told too, rather than inheriting the "
        "first job's silence",
    )
    cache.clear_running("cap-running")

    # "A user correction is not evictable WHILE ITS JOB EXISTS" -- the plan's
    # qualifier. Strip the edited page of every reference and it must become
    # evictable, or a page whose last job was deleted holds an edit nobody can
    # open and pins itself forever, warning on every job from then on.
    edited = left[0]
    cache._write_json(os.path.join(cache.page_dir(edited), cache.REFS), [])
    cache._warned.clear()
    cache.enforce_cap("cap-job-2")
    c.check(
        not os.path.isdir(cache.page_dir(edited)),
        "[cap] a page holding an edit but referenced by NO job is evictable -- "
        "the edit pin lasts exactly as long as a job that can show it",
    )


def section_cap_wiring(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[cap-wired] the cap is connected to the job, not only to the check."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    # The first draft asserted every clause of the cap by calling enforce_cap
    # itself. Delete the one line in run_item that calls it and every assert
    # stayed green while the cache grew to disk-full -- the review's uncovered
    # sabotage. So: a synthetic cold page that no job references, a cap set
    # just below the tree, and a job run. The JOB must evict it.
    cold = "0" * 64
    os.makedirs(cache.page_dir(cold), exist_ok=True)
    with open(os.path.join(cache.page_dir(cold), cache.RASTER), "wb") as fh:
        fh.write(b"\0" * 200_000)
    cache._write_json(os.path.join(cache.page_dir(cold), cache.REFS), [])
    old = time.time() - 10_000
    os.utime(cache.page_dir(cold), (old, old))

    total = cache.disk_bytes()
    os.environ["MT_CACHE_CAP_BYTES"] = str(total - 100_000)
    os.environ["MT_CACHE_TARGET_BYTES"] = str(total - 150_000)
    calls, undo = _no_detect_or_ocr()
    try:
        rec, _ = _quiet(pipeline.run_item, CBZ, out_dir, "cap-wired")
    finally:
        undo()
    c.check(
        not os.path.isdir(cache.page_dir(cold)) and rec["cache_warning"] is None,
        f"[cap-wired] running an item past the cap evicts the cold unreferenced "
        f"page and reports no warning: evicted={not os.path.isdir(cache.page_dir(cold))}, "
        f"warning={rec['cache_warning']!r}",
    )
    c.check(
        all(os.path.isdir(cache.page_dir(p["page_hash"])) for p in rec["pages"]),
        "[cap-wired] and none of the running job's own pages went with it",
    )

    # Every page pinned by the job itself: the warning must arrive in the
    # JOB'S OWN RECORD, which is what US-P3-05 says and the first draft did
    # not assert -- it read enforce_cap's return value directly.
    os.environ["MT_CACHE_CAP_BYTES"] = "1"
    os.environ["MT_CACHE_TARGET_BYTES"] = "1"
    calls, undo = _no_detect_or_ocr()
    try:
        rec, _ = _quiet(pipeline.run_item, CBZ, out_dir, "cap-wired-2")
    finally:
        undo()
    c.check(
        bool(rec["cache_warning"]) and "over its" in rec["cache_warning"],
        f"[cap-wired] with every page held by the running job the JOB SUMMARY "
        f"carries the overflow warning: {rec['cache_warning']!r}",
    )
    c.check(
        all(os.path.isdir(cache.page_dir(p["page_hash"])) for p in rec["pages"]),
        "[cap-wired] and the job's pages were not evicted to honour the number",
    )


def section_tier(c: Checks, cache_dir: str, record: dict):
    """[tier] LRU bounded by count OR bytes, and it never touches the disk."""
    cache = _reset(cache_dir)
    from PIL import Image

    # Many threads on one tiny LRU, on overlapping keys: the shape of three
    # pages per item inside four job workers. The GIL hides the race at the
    # default switch interval, so the interval is forced down for the run:
    # unlocked, 15 of 16 threads then died with KeyError from move_to_end.

    hammer = cache._Tier()
    tiles = [Image.new("L", (64, 64)) for _ in range(40)]
    errors = []

    def churn(seed):
        try:
            for i in range(20000):
                k = f"k{(seed * 7 + i) % 40}"
                if i % 5 == 0:
                    hammer.discard(k)  # enforce_cap's path
                elif i % 3:
                    hammer.put(k, tiles[(seed + i) % 40])
                else:
                    hammer.get(k)
                hammer.total_bytes()
        except Exception as e:  # noqa: BLE001 -- the assert reports it
            errors.append(f"{type(e).__name__}: {e}")

    workers = [threading.Thread(target=churn, args=(s,)) for s in range(16)]
    switch = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        for w in workers:
            w.start()
        for w in workers:
            w.join()
    finally:
        sys.setswitchinterval(switch)
    c.check(not errors and len(hammer._items) <= cache.MAX_RASTERS,
            f"[tier] sixteen threads churning one LRU raise nothing and keep the bound: "
            f"{errors[:2]} ({len(hammer._items)} resident)")

    hashes = [p["page_hash"] for p in record["pages"]][:4]
    for h in hashes:
        cache.read_raster(h)
    c.check(
        len(cache._tier._items) == cache.MAX_RASTERS,
        f"[tier] a fourth insert evicts the least-recently-used: "
        f"{len(cache._tier._items)} resident, bound is {cache.MAX_RASTERS}",
    )
    c.check(
        all(os.path.isdir(cache.page_dir(h)) for h in hashes),
        "[tier] evicting from the memory tier deletes NOTHING on disk",
    )
    c.check(
        cache.tier_bytes() > 0,
        f"[tier] tier_bytes reports the resident decoded total Phase 6's RSS "
        f"gate samples: {cache.tier_bytes()}",
    )

    cache.clear_tier()
    big = cache.MAX_TIER_BYTES // 3 + 1024
    side = int((big / 3) ** 0.5) + 1
    for i in range(3):
        cache._tier.put(f"big-{i}", Image.new("RGB", (side, side)))
    c.check(
        cache.tier_bytes() <= cache.MAX_TIER_BYTES
        and len(cache._tier._items) < 3,
        f"[tier] the BYTE bound binds before the count bound when rasters are "
        f"large: {len(cache._tier._items)} resident, {cache.tier_bytes()} bytes "
        f"<= {cache.MAX_TIER_BYTES}",
    )

    cache.clear_tier()
    huge = Image.new("RGB", (8000, 7000))  # 168MB decoded, over the 150MB bound
    cache._tier.put("huge", huge)
    c.check(
        "huge" not in cache._tier._items and cache.tier_bytes() <= cache.MAX_TIER_BYTES,
        f"[tier] a single raster over the byte bound is NOT held -- served from "
        f"disk instead -- so tier_bytes never exceeds the bound Phase 6 counts "
        f"inside AC-12: resident={'huge' in cache._tier._items}, "
        f"bytes={cache.tier_bytes()}",
    )
    del huge

    cache.clear_tier()
    h = hashes[0]
    from_disk = cache.read_raster(h)
    from_tier = cache.read_raster(h)
    c.check(
        cache.page_hash(from_disk) == cache.page_hash(from_tier),
        "[tier] a tier miss loads from disk and returns the same pixels a tier "
        "hit does -- compared by hash, not by size",
    )


def section_zero_llm(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[zero-llm] rung 5 must not fire on the spot-fix path."""
    cache = _reset(cache_dir)
    from sidecar import pipeline
    from sidecar.llm import LLMClient

    item = record["item_id"]
    rid = record["pages"][3]["regions"][0]["id"]
    # Fifteen copies: see section_flags -- the ladder now has the bubble's
    # room, and one copy fits it at the floor.
    too_long = " ".join([
        "I told you already that we should never have opened that door because "
        "whatever waits behind it has been patient for a very long time indeed "
        "and it remembers every single one of us by name and it will not forget"
    ] * 15)

    # The page must already be translated under (en, stub-model), or rerender
    # refuses with kind "translation" -- the mixed-language guard. Seeded from
    # the offline run's text rather than by a provider round trip, so the
    # request counter below starts from a known zero.
    h4 = record["pages"][3]["page_hash"]
    cache.write_translation(h4, "en", "stub-model",
                            {r["id"]: r["translation"] for r in record["pages"][3]["regions"]})

    with StubProvider(delay=0) as stub:
        client = LLMClient(stub.url, "", "stub-model")
        out, _ = _quiet(pipeline.rerender, JOB_B, item, 4, rid, too_long,
                        out_dir, client)
        counted = stub.chat_requests
        region = next(r for r in out["regions"] if r["id"] == rid)

        c.check(
            counted == 0,
            f"[zero-llm] an edit long enough to exhaust rungs 1-4 issues ZERO "
            f"LLM requests on the re-render path: the stub server counted "
            f"{counted}",
        )
        c.check(
            region["fit_failed"] and not region["retranslated"],
            f"[zero-llm] and the region reports fit_failed rather than a "
            f"retranslation: failed={region['fit_failed']}, "
            f"retranslated={region['retranslated']}",
        )

        # The counter has to be able to MOVE, or the zero above is agreeing
        # with nothing -- the defect Phase 2a carried forward in as many words.
        # Same text, same region, same client; the only difference is the flag
        # the re-render path pins to False.
        page = cache.read_raster(record["pages"][3]["page_hash"])
        regions = [dict(r) for r in out["regions"]]
        for r in regions:
            if r["id"] == rid:
                r["translation"] = too_long
        _quiet(pipeline.render, page, regions, 4, client, allow_retranslate=True)
        c.check(
            stub.chat_requests > counted,
            f"[zero-llm] the same edit WITH retranslation allowed does reach "
            f"the provider ({stub.chat_requests} requests), so the zero above "
            f"is a measurement and not a dead counter",
        )

    edited = cache.read_translation(record["pages"][3]["page_hash"], "en", "stub-model")
    c.check(
        edited[str(rid)]["edited"] is True,
        "[zero-llm] the edit is persisted under the CURRENT model's key before "
        "the response returns",
    )


def section_ingest_llm(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[ingest-llm] the translation cache is counted at the provider."""
    _reset(cache_dir)
    from sidecar import pipeline
    from sidecar.llm import LLMClient

    # The review's uncovered sabotage: delete cache.write_translation from
    # run_item and every assert stayed green -- [crossjob] counts detect and
    # OCR only -- while against a real provider every re-run silently
    # re-translated every page and billed for it. So the requests are counted
    # at the stub SERVER across three runs: a first run at (en, stub-model)
    # that must translate, a second job at the same pair that must not, and a
    # language switch that must translate again without re-detecting -- the
    # locked "second pass re-translates and re-renders without re-detecting".
    with StubProvider(delay=0) as stub:
        client = LLMClient(stub.url, "", "stub-model")
        calls, undo = _no_detect_or_ocr()
        try:
            _quiet(pipeline.run_item, CBZ, out_dir, "llm-1", None, client)
            first = stub.chat_requests
            _quiet(pipeline.run_item, CBZ, out_dir, "llm-2", None, client)
            second = stub.chat_requests
            rec3, _ = _quiet(pipeline.run_item, CBZ, out_dir, "llm-3", None, client, "id")
            third = stub.chat_requests
        finally:
            undo()

    c.check(
        first > 0,
        f"[ingest-llm] the first run at a new (lang, model) reaches the "
        f"provider: {first} requests",
    )
    c.check(
        second == first,
        f"[ingest-llm] a second job at the SAME (lang, model) makes ZERO "
        f"further requests -- the translation cache is real: {second - first}",
    )
    c.check(
        third > second and calls == {"detect": 0, "ocr": 0},
        f"[ingest-llm] switching target language re-translates ({third - second} "
        f"requests) WITHOUT re-detecting: {calls}",
    )
    c.check(
        all(p["cached"] for p in rec3["pages"]),
        "[ingest-llm] and the language switch still served every raster from "
        "the page cache",
    )


def section_rendered_edit(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[edit-rendered] the edit survives on the PAGE, not only in the file."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    h = record["pages"][1]["page_hash"]
    regions = record["pages"][1]["regions"]
    rid, other = regions[0]["id"], regions[1]["id"]
    cache.write_edit(h, "en", "offline", rid, "MY WORDS")

    # Partial coverage forces the re-translate branch, which is the only path
    # where the file and the in-memory regions can disagree. Delete the
    # second sabotage the review named -- run_item's read-back after
    # write_translation -- and every [edit] assert stays green (they read the
    # FILE) while the delivered page shows the provider's text over the
    # user's correction.
    stored = cache.read_translation(h, "en", "offline")
    stored.pop(str(other), None)
    cache._write_json(os.path.join(cache.page_dir(h), cache.translation_name("en", "offline")),
                      stored)

    calls, undo = _no_detect_or_ocr()
    try:
        rec, _ = _quiet(pipeline.run_item, CBZ, out_dir, "edit-rendered")
    finally:
        undo()
    region = next(r for r in rec["pages"][1]["regions"] if r["id"] == rid)
    c.check(
        region["typeset"] == "MY WORDS" and region.get("edited") is True,
        f"[edit-rendered] after a re-run that had to re-translate the page, "
        f"the edited region's TYPESET text is the user's edit: "
        f"{region['typeset']!r}, edited={region.get('edited')}",
    )
    peer = next(r for r in rec["pages"][1]["regions"] if r["id"] == other)
    c.check(
        peer["typeset"] == "HELLO" and not peer.get("edited"),
        f"[edit-rendered] and the region that was NOT edited carries the fresh "
        f"translation: {peer['typeset']!r}",
    )


def section_archive(c: Checks, cache_dir: str, out_dir: str):
    """[archive] an edit reaches the delivered ARCHIVE, not only the loose page.

    The re-render writes one loose page and answers inside AC-10's budget; the
    volume next to it is rebuilt on a worker once the edits go quiet. This
    section holds three things: the response says the archive is behind and
    a repack is pending, the archive on disk then carries the edited page
    byte-for-byte, and two edits inside REPACK_DELAY cost one repack.
    """
    import zipfile

    cache = _reset(cache_dir)
    from sidecar import main, pipeline

    job = "archive-job"
    calls, undo = _no_detect_or_ocr()
    try:
        rec, _ = _quiet(pipeline.run_item, CBZ, out_dir, job)
    finally:
        undo()
    archive_path = rec["archive"]
    item = rec["item_id"]
    c.check(
        os.path.exists(archive_path),
        f"[archive] the run delivered an archive beside the loose pages: {archive_path}",
    )
    before = _sha(archive_path)
    with zipfile.ZipFile(archive_path) as zf:
        members_before = zf.namelist()
    c.check(
        cache.get_placement(job, item, 1).get("src_path") == os.fspath(CBZ),
        "[archive] the placement remembers the item's input, which is what the "
        "repack reads ComicInfo and extras from",
    )

    first, second = rec["pages"][1], rec["pages"][2]
    rid1, rid2 = first["regions"][0]["id"], second["regions"][0]["id"]

    # The "two edits, one repack" assert below needs both re-renders inside
    # the debounce. Measured at 0.03s each against 1.0s, but a loaded run_all
    # is not a quiet machine; widened for this section and restored after.
    saved_delay, pipeline.REPACK_DELAY = pipeline.REPACK_DELAY, 3.0
    try:
        _archive_edits(c, pipeline, main, job, item, archive_path, before,
                       members_before, first, second, rid1, rid2, out_dir)
    finally:
        pipeline.REPACK_DELAY = saved_delay


def _archive_edits(c, pipeline, main, job, item, archive_path, before,
                   members_before, first, second, rid1, rid2, out_dir):
    import zipfile

    from fastapi.testclient import TestClient

    t0 = time.perf_counter()
    out1 = _call(c, "[archive]", pipeline.rerender, job, item, first["page"], rid1,
                 "INTO THE ZIP", out_dir)
    elapsed = time.perf_counter() - t0
    if out1 is None:
        return
    repack = out1.get("repack") or {}
    c.check(
        out1.get("archive_stale") is True and repack.get("status") == "pending",
        f"[archive] the re-render answers with archive_stale and a PENDING "
        f"repack, not a finished one: stale={out1.get('archive_stale')} "
        f"repack={repack}",
    )
    c.check(
        elapsed < BUDGET_S,
        f"[archive] and it did not wait on the archive: {elapsed:.2f}s",
    )
    out2 = _call(c, "[archive]", pipeline.rerender, job, item, second["page"], rid2,
                 "ALSO IN", out_dir)
    if out2 is None:
        return

    with TestClient(main.app) as client:
        r = client.get("/api/repack", params={"job_id": job, "item_id": item})
        c.check(
            r.status_code == 200 and r.json().get("status") in ("pending", "running"),
            f"[archive] /api/repack serves the worker's status while it is under "
            f"way: {r.status_code} {r.text[:120]}",
        )
        deadline = time.time() + 30
        status = r.json()
        # idle is terminal too: a sidecar that never scheduled the repack
        # answers idle forever, and waiting the full 30s on it tells nothing.
        while status.get("status") not in ("done", "failed", "idle") and time.time() < deadline:
            time.sleep(0.1)
            status = client.get("/api/repack", params={"job_id": job, "item_id": item}).json()
    c.check(
        status.get("status") == "done" and not status.get("error"),
        f"[archive] the background repack finished: {status}",
    )
    c.check(
        status.get("repacks") == 1,
        f"[archive] two edits inside REPACK_DELAY cost ONE repack, not two: "
        f"{status.get('repacks')}",
    )
    c.check(
        os.path.normcase(status.get("archive", "")) == os.path.normcase(archive_path),
        f"[archive] and it rewrote the SAME archive the run delivered: "
        f"{status.get('archive')!r}",
    )
    c.check(
        _sha(archive_path) != before,
        "[archive] the archive on disk is a different file from before the edits",
    )
    with zipfile.ZipFile(archive_path) as zf:
        members_after = zf.namelist()
        in_zip1, in_zip2 = zf.read(first["member"]), zf.read(second["member"])
    with open(out1["output"], "rb") as fh:
        loose1 = fh.read()
    with open(out2["output"], "rb") as fh:
        loose2 = fh.read()
    c.check(
        in_zip1 == loose1 and in_zip2 == loose2,
        "[archive] both edited pages inside the archive are byte-identical to "
        "the re-rendered loose pages -- the volume shows what the editor shows",
    )
    c.check(
        members_after == members_before,
        f"[archive] and the member set round-trips unchanged: "
        f"{len(members_after)} of {len(members_before)}",
    )

    # The exit paths. The app quits by closing the sidecar's stdin, and a
    # timer armed a second ago does not fire across os._exit -- so both exit
    # paths call flush_repacks first. Here: an edit, then the flush at once,
    # and the archive has it before the timer would have fired.
    out3 = _call(c, "[archive]", pipeline.rerender, job, item, first["page"], rid1,
                 "BEFORE QUIT", out_dir)
    if out3 is None:
        return
    t0 = time.perf_counter()
    pipeline.flush_repacks()
    flushed = pipeline.repack_status(job, item)
    c.check(
        flushed["status"] == "done" and flushed["repacks"] == 2,
        f"[archive] flush_repacks runs the pending repack inline, which is what "
        f"the exit paths call so an edit made just before quitting reaches the "
        f"volume: {flushed} in {time.perf_counter() - t0:.2f}s",
    )
    with zipfile.ZipFile(archive_path) as zf:
        in_zip3 = zf.read(first["member"])
    with open(out3["output"], "rb") as fh:
        loose3 = fh.read()
    c.check(
        in_zip3 == loose3 and in_zip3 != in_zip1,
        "[archive] and the archive carries the edit made before the flush",
    )
    time.sleep(pipeline.REPACK_DELAY + 0.3)
    c.check(
        pipeline.repack_status(job, item)["repacks"] == 2,
        "[archive] the timer the flush cancelled did not run a further pass",
    )

    # Coalescing. An edit that lands while a pass is running is not lost:
    # the worker goes again, once -- and the mid-pass edit's own timer,
    # still armed, is cancelled rather than left to run a third pass over
    # inputs the second already covered. The first pass is held on an
    # Event so the mid-pass edit lands deterministically.
    real_repack, saved_delay = pipeline.repack_item, pipeline.REPACK_DELAY
    started, release = threading.Event(), threading.Event()
    passes = [0]

    def held_first(*a, **kw):
        passes[0] += 1
        if passes[0] == 1:
            started.set()
            release.wait(10)
        return real_repack(*a, **kw)

    pipeline.repack_item = held_first
    try:
        pipeline.REPACK_DELAY = 0.05
        out4 = _call(c, "[archive]", pipeline.rerender, job, item, second["page"], rid2,
                     "MID PASS ONE", out_dir)
        c.check(
            out4 is not None and started.wait(5),
            "[archive] the first pass is under way and held",
        )
        pipeline.REPACK_DELAY = 0.4
        out5 = _call(c, "[archive]", pipeline.rerender, job, item, second["page"], rid2,
                     "MID PASS TWO", out_dir)
        c.check(
            pipeline.repack_status(job, item)["status"] == "running",
            "[archive] an edit that lands mid-pass leaves the status running, "
            "not pending: the worker owns it now",
        )
        release.set()
        deadline = time.time() + 30
        status = pipeline.repack_status(job, item)
        while status["status"] not in ("done", "failed") and time.time() < deadline:
            time.sleep(0.05)
            status = pipeline.repack_status(job, item)
        settled = time.perf_counter()
        c.check(
            status["status"] == "done" and status["repacks"] == 4,
            f"[archive] the worker went again ONCE for the mid-pass edit: {status}",
        )
        time.sleep(max(0.0, 0.4 - (time.perf_counter() - settled)) + 0.3)
        after = pipeline.repack_status(job, item)
        c.check(
            after["repacks"] == 4 and after["status"] == "done",
            f"[archive] and the mid-pass edit's own timer was cancelled -- no third "
            f"pass over inputs the second already covered: {after}",
        )
        if out5 is not None:
            with zipfile.ZipFile(archive_path) as zf:
                in_zip5 = zf.read(second["member"])
            with open(out5["output"], "rb") as fh:
                loose5 = fh.read()
            c.check(
                in_zip5 == loose5 and in_zip5 != in_zip2,
                "[archive] and the archive carries the LAST edit, the one that "
                "landed mid-pass",
            )
    finally:
        release.set()
        pipeline.repack_item, pipeline.REPACK_DELAY = real_repack, saved_delay

    # The failure path. A loose page gone before the pass runs is a pass that
    # cannot be honest about the volume, so it says so: status failed, the
    # error naming the page, and the archive on disk untouched -- the last
    # good one, not an empty or partial one.
    with zipfile.ZipFile(archive_path) as zf:
        in_zip_before = zf.read(second["member"])
    good = _sha(archive_path)
    pipeline.REPACK_DELAY = 0.05
    try:
        out6 = _call(c, "[archive]", pipeline.rerender, job, item, second["page"], rid2,
                     "GONE", out_dir)
        if out6 is None:
            return
        gone = out6["output"]
        os.remove(gone)
        deadline = time.time() + 30
        status = pipeline.repack_status(job, item)
        while status["status"] not in ("done", "failed") and time.time() < deadline:
            time.sleep(0.05)
            status = pipeline.repack_status(job, item)
    finally:
        pipeline.REPACK_DELAY = saved_delay
    c.check(
        status["status"] == "failed" and os.path.basename(gone) in status["error"],
        f"[archive] a loose page missing when the pass runs is a FAILED status "
        f"naming the page, not a done: {status}",
    )
    with zipfile.ZipFile(archive_path) as zf:
        in_zip_after = zf.read(second["member"])
    c.check(
        _sha(archive_path) == good and in_zip_after == in_zip_before,
        "[archive] and the archive on disk is the last good one, byte for byte",
    )


def section_persistence(c: Checks, cache_dir: str, record: dict):
    """[persist] the cache survives process exit, and every write is atomic."""
    cache = _reset(cache_dir)
    h = record["pages"][0]["page_hash"]
    expected_ids = sorted(r["id"] for r in cache.read_regions(h)["regions"])

    driver = (
        "import json,os,sys\n"
        "from sidecar import cache\n"
        "rec = cache.read_regions(sys.argv[1])\n"
        "print(json.dumps(sorted(r['id'] for r in rec['regions'])))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver, h],
        capture_output=True, encoding="utf-8", errors="replace",
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=ROOT, MT_CACHE_DIR=cache_dir,
                 PYTHONIOENCODING="utf-8"),
    )
    c.check(
        proc.returncode == 0,
        f"[persist] a FRESH process reads the cache (stderr: {proc.stderr[-200:]})",
    )
    got = json.loads(proc.stdout.strip() or "[]") if proc.returncode == 0 else []
    c.check(
        got == expected_ids,
        f"[persist] and gets the same regions back after the writer exited: "
        f"{got} vs {expected_ids}",
    )

    # Atomicity, by CRASHING a write rather than by grepping for the word
    # atomic. The first draft asserted "every write goes through atomic_write"
    # from the source text, which cannot see a non-atomic write spelled
    # Image.save(path). atomic.crash_hook exists for exactly this case and
    # check_package already uses it: park between the temp write and the
    # os.replace, blow up, and look at what is on disk.
    from sidecar import atomic

    before = _sha(os.path.join(cache.page_dir(h), "regions.json"))

    def crash(tmp, dest):
        raise RuntimeError("simulated crash between temp write and os.replace")

    atomic.crash_hook = crash
    try:
        try:
            cache.write_regions(h, {"regions": [], "poisoned": True})
            crashed = False
        except RuntimeError:
            crashed = True
    finally:
        atomic.crash_hook = None
    strays = [f for f in os.listdir(cache.page_dir(h)) if f.startswith(".")]
    c.check(
        crashed and not strays,
        f"[persist] a crash between the temp write and os.replace leaves no "
        f".tmp behind: crashed={crashed}, strays={strays}",
    )
    c.check(
        _sha(os.path.join(cache.page_dir(h), "regions.json")) == before,
        "[persist] and the previous regions.json is byte-identical -- the "
        "half-written record never became the record",
    )


def section_torn(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[torn] a page directory that lost its raster is a MISS, not a crash."""
    cache = _reset(cache_dir)
    from sidecar import pipeline

    h = record["pages"][0]["page_hash"]
    os.remove(os.path.join(cache.page_dir(h), cache.RASTER))
    cache.clear_tier()

    # has_page is FORCED true for the duration, and that is the whole point of
    # this section. Deleting the raster and leaving has_page alone reproduces
    # nothing: has_page checks for the raster too, so it returns False and the
    # ordinary miss path handles it -- the assert would pass with the guard
    # removed, which the red-check reported as a hole and was right to. The
    # race being guarded is the one has_page CANNOT see: it answered yes, and
    # the file went away before read_raster was reached.
    real_has_page = cache.has_page
    cache.has_page = lambda _h: True

    # Reachable without anyone doing anything strange: another job's
    # enforce_cap can evict between has_page and read_raster, and across
    # PROCESSES the reference writes are still last-writer-wins, so the
    # in-process lock does not close it entirely. A cache is allowed to lose an
    # entry. It is not allowed to hand the renderer a None and call it a page.
    #
    # The exception is CAUGHT rather than left to propagate, so that a
    # regression turns this assert red instead of killing the run before it --
    # a dead check reports its tag as absent, and an absent tag is how a hole
    # gets misread as a stale tag.
    detail = ""
    try:
        again, _ = _quiet(pipeline.run_item, CBZ, out_dir, "job-torn")
        ok = again["pages"][0]["cached"] is False
        detail = f"cached={again['pages'][0]['cached']}"
    except Exception as e:  # noqa: BLE001 -- any failure here is the defect
        ok, detail = False, f"{type(e).__name__}: {e}"
    finally:
        cache.has_page = real_has_page

    c.check(
        ok,
        f"[torn] a page whose raster was evicted between has_page and "
        f"read_raster is re-derived rather than crashing the run: {detail}",
    )
    if ok:
        c.check(
            all(p["cached"] for p in again["pages"][1:]),
            "[torn] and only that page pays -- the rest of the archive is still "
            "served from cache",
        )


def section_parallel(c: Checks, cache_dir: str, out_dir: str):
    """[parallel] concurrent jobs on an EMPTY cache do not fall over the models."""
    # In a SUBPROCESS, and that is the point. The route is a sync def, so
    # FastAPI runs concurrent POSTs in threads; the round-2 review ran three
    # run_item calls on an empty cache and saw DetectError out of OpenCV's
    # forward pass. Reproduced here without the model lock, the outcome was
    # worse: no exception at all -- the interpreter died mid-forward-pass. A
    # native crash cannot be caught by _guarded, and a dead check reports
    # every later tag as absent. So the three jobs run in a child; the child
    # dying is a red assert in the parent, with the exit code in the message.
    driver = (
        "import contextlib, io, os, sys, threading\n"
        "from sidecar import pipeline\n"
        "cbz, out = sys.argv[1], sys.argv[2]\n"
        "errors, pages = [], []\n"
        "def job(i):\n"
        "    try:\n"
        "        with contextlib.redirect_stdout(io.StringIO()):\n"
        "            rec = pipeline.run_item(cbz, os.path.join(out, str(i)), f'par-{i}')\n"
        "        pages.append(len(rec['pages']))\n"
        "    except Exception as e:\n"
        "        errors.append(f'{type(e).__name__}: {e}'[:160])\n"
        "ts = [threading.Thread(target=job, args=(i,)) for i in range(3)]\n"
        "[t.start() for t in ts]; [t.join() for t in ts]\n"
        # sys.__stdout__, not sys.stdout: three threads each swapping the
        # process-global stdout leave it pointing at one of their StringIOs,
        # and the result line vanished into it on the first run.
        "print('RESULT', sorted(pages), errors, file=sys.__stdout__, flush=True)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", driver, CBZ, out_dir],
        capture_output=True, encoding="utf-8", errors="replace", cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=ROOT, MT_CACHE_DIR=cache_dir,
                 PYTHONIOENCODING="utf-8"),
    )
    result = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT")), "")
    c.check(
        proc.returncode == 0 and result == "RESULT [8, 8, 8] []",
        f"[parallel] three jobs run at once on an EMPTY cache all complete every "
        f"page, and the process survives: exit={proc.returncode}, "
        f"{result or 'no result line -- the interpreter died'} "
        f"(stderr tail: {proc.stderr[-160:].strip()!r})",
    )


def section_safe_paths(c: Checks, out_dir: str):
    """[safe-path] a member name is untrusted input on the WRITE side."""
    from sidecar.pipeline import _member_dest

    os.makedirs(out_dir, exist_ok=True)

    # The colon is the one that loses data silently. `page.png:hidden.png` is a
    # valid NTFS alternate data stream reference: the write SUCCEEDS, the
    # directory listing shows only `page.png`, and the translated page is
    # nowhere the user can find it. Measured below rather than argued.
    dest = _member_dest(out_dir, "page.png:hidden.png")
    c.check(
        ":" not in os.path.splitdrive(dest)[1],
        f"[safe-path] a member carrying a colon cannot address an alternate "
        f"data stream: {dest}",
    )
    with open(dest, "wb") as fh:
        fh.write(b"page")
    c.check(
        os.path.basename(dest) in os.listdir(os.path.dirname(dest)),
        f"[safe-path] and the delivered page is VISIBLE in its directory, not "
        f"hidden in a stream: {os.listdir(os.path.dirname(dest))}",
    )

    escaped = _member_dest(out_dir, "../../../escaped.png")
    c.check(
        os.path.commonpath([os.path.abspath(escaped), os.path.abspath(out_dir)])
        == os.path.abspath(out_dir),
        f"[safe-path] no member name escapes the destination directory: {escaped}",
    )
    c.check(
        _member_dest(out_dir, "ch1/p1.png") != _member_dest(out_dir, "ch10/p1.png"),
        "[safe-path] two members with the same basename in different chapters "
        "deliver to two different files, rather than one overwriting the other",
    )

    # Substitution alone is many-to-one. The review measured `a<b.png` and
    # `a_b.png` both landing on a_b_translated.png, the second silently over
    # the first. An altered name carries a digest; an unaltered one does not.
    c.check(
        _member_dest(out_dir, "a<b.png") != _member_dest(out_dir, "a_b.png"),
        f"[safe-path] a name that had to be altered cannot collide with one "
        f"that did not: {os.path.basename(_member_dest(out_dir, 'a<b.png'))} vs "
        f"{os.path.basename(_member_dest(out_dir, 'a_b.png'))}",
    )
    c.check(
        _member_dest(out_dir, "ch1/p1.png").endswith(os.path.join("ch1", "p1_translated.png")),
        "[safe-path] and an ordinary name is delivered under exactly the name "
        "the user knows -- no digest where none was needed",
    )
    # The first draft ran os.path.splitdrive over the WHOLE member path, so
    # `a:b.png` lost its first segment as if `a:` were a drive. The colon is
    # handled per segment now, and the `a` survives in the delivered name.
    ab = os.path.basename(_member_dest(out_dir, "a:b.png"))
    c.check(
        ab.startswith("a_b") and ":" not in ab,
        f"[safe-path] `a:b.png` keeps its first segment rather than losing it "
        f"to a drive-letter parse: {ab}",
    )
    dotspace = os.path.basename(_member_dest(out_dir, "page. .png"))
    c.check(
        " _" not in dotspace and ". _" not in dotspace,
        f"[safe-path] trailing dots and spaces are stripped from the STEM, so "
        f"the _translated suffix never lands after an interior space: {dotspace}",
    )

    # job_id is a path segment too, and it arrives from the UI. The review
    # reproduced job_dir("../../../../escaped-job") writing running.json into
    # %LOCALAPPDATA% itself; with a delete route that is an rmtree primitive.
    from sidecar import cache

    jroot = os.path.abspath(cache.jobs_root()) + os.sep
    evil = "../../../../escaped-job"
    cache.mark_running(evil)
    landed = os.path.abspath(cache.job_dir(evil))
    c.check(
        landed.startswith(jroot) and os.path.exists(os.path.join(landed, cache.RUNNING)),
        f"[safe-path] a traversing job_id lands under the cache's jobs root, "
        f"not outside it: {os.path.relpath(landed, cache.root())}",
    )
    cache.clear_running(evil)
    c.check(
        cache._job_key("job-a") == "job-a" and cache._job_key("../x") != cache._job_key("..\\x"),
        "[safe-path] an ordinary job id is unchanged and two different unsafe "
        "ids do not collapse onto one directory",
    )


def section_routes(c: Checks, cache_dir: str, out_dir: str, record: dict):
    """[route] the HTTP surface: one success over the wire, and named errors."""
    from fastapi.testclient import TestClient

    from sidecar import main

    _reset(cache_dir)
    paths = {r.path for r in main.app.routes if hasattr(r, "path")}
    c.check(
        "/api/rerender" in paths and "/api/item" in paths,
        f"[route] the re-render and item routes are registered: "
        f"{sorted(p for p in paths if p.startswith('/api'))}",
    )

    with TestClient(main.app) as client:
        # The SUCCESS path, over the wire. Everything above called
        # pipeline.rerender directly, and one property is only observable
        # through the route: typeset_page refuses to run inside a live event
        # loop, because rung 5 uses asyncio.run. A route declared `async` would
        # raise TypesetError here and pass every in-process assert in this file.
        rid = record["pages"][4]["regions"][0]["id"]
        r = client.post("/api/rerender", json={
            "job_id": JOB_B, "item_id": record["item_id"], "ordinal": 5,
            "region_id": rid, "text": "OVER THE WIRE", "dest_dir": out_dir,
        })
        c.check(
            r.status_code == 200,
            f"[route] a re-render over HTTP succeeds -- the typesetter's "
            f"event-loop guard is satisfied by a sync route: {r.status_code} "
            f"{r.text[:200]}",
        )
        if r.status_code == 200:
            body = r.json()
            edited = next(x for x in body["regions"] if x["id"] == rid)
            c.check(
                edited["typeset"] == "OVER THE WIRE" and body["edited_region"] == rid,
                f"[route] and the response carries the RE-TYPESET text, not the "
                f"text that was posted back unchanged: {edited['typeset']!r}",
            )
            c.check(
                {"fit_summary", "regions", "output"} <= set(body),
                "[route] in the same record shape /api/translate returns, so "
                "the UI has one renderer for both",
            )

        r = client.post("/api/rerender", json={
            "job_id": JOB_B, "item_id": record["item_id"], "ordinal": 5,
            "region_id": 99999, "text": "x", "dest_dir": out_dir,
        })
        c.check(
            r.status_code == 404 and r.json().get("kind") == "region",
            f"[route] a region that is not on the page is a 404 kinded "
            f"'region', distinct from a missing placement: {r.status_code} "
            f"{r.text[:120]}",
        )

        r = client.post("/api/rerender", json={
            "job_id": "no-such-job", "item_id": "x", "ordinal": 1,
            "region_id": 1, "text": "hi", "dest_dir": tempfile.gettempdir(),
        })
        c.check(
            r.status_code == 404,
            f"[route] a re-render against a job that never ran is a 404, not "
            f"an unhandled 500: {r.status_code}",
        )
        body = r.json()
        c.check(
            body.get("kind") == "placement" and body.get("error"),
            f"[route] and it names a KIND the UI can branch on: {body}",
        )
        r = client.post("/api/rerender", json={
            "job_id": "x", "item_id": "y", "ordinal": 1, "region_id": 1,
            "text": "hi", "dest_dir": tempfile.gettempdir(),
            "settings": {"base_url": "", "api_key": "", "model": ""},
        })
        c.check(
            r.status_code == 400,
            f"[route] empty settings are a 400 about the settings, not a 500 "
            f"and not a silent offline run: {r.status_code}",
        )

        # The item route, over the wire, at least once. The first draft only
        # asserted it was registered; it shipped untested.
        calls, undo = _no_detect_or_ocr()
        try:
            r = client.post("/api/item", json={
                "src_path": CBZ, "dest_dir": out_dir, "job_id": "http-job",
            })
        finally:
            undo()
        c.check(
            r.status_code == 200 and len(r.json().get("pages", [])) == len(record["pages"])
            and calls == {"detect": 0, "ocr": 0},
            f"[route] POST /api/item runs the archive over HTTP and, against a "
            f"warm cache, calls neither detect nor OCR: {r.status_code}, "
            f"{len(r.json().get('pages', [])) if r.status_code == 200 else r.text[:120]} "
            f"pages, {calls}",
        )

        # A re-render at a language this page was never translated into is an
        # error, not a page with one bubble in the new language and the rest
        # in the old one -- the review called it a mixed-language page.
        r = client.post("/api/rerender", json={
            "job_id": JOB_B, "item_id": record["item_id"], "ordinal": 5,
            "region_id": rid, "text": "SELAMAT", "dest_dir": out_dir, "lang": "id",
        })
        c.check(
            r.status_code == 404 and r.json().get("kind") == "translation",
            f"[route] a re-render at an untranslated (lang, model) is a 404 "
            f"kinded 'translation', never a mixed-language page: {r.status_code} "
            f"{r.text[:140]}",
        )


# -- the run ---------------------------------------------------------------


def _guarded(c: Checks, tag: str, fn, *a, **kw):
    """Run one section; a crash inside it is ONE red assert, not a dead run.

    Every section is dispatched through here. A section that raises -- a
    CacheMiss a sabotage produced, a KeyError on a field a sabotage removed --
    would otherwise kill the check before its assert could go red, every later
    tag would go absent, and the red-check would misread the hole as a stale
    tag. Reported under the section's own tag so the red-check can key on it.
    """
    try:
        return fn(c, *a, **kw)
    except Exception as e:  # noqa: BLE001 -- the point is to report, not to filter
        c.check(False, f"{tag} section crashed with {type(e).__name__}: {e}")
        return None


def main():
    c = Checks("check_spotfix")

    # redcheck_spotfix.py deliberately breaks the source tree between runs, and
    # anything else running the suite meanwhile sees that broken tree. Without
    # this the reader gets a red assert naming a defect nobody introduced --
    # three consecutive runs failing three DIFFERENT sections, which reads
    # exactly like a flaky gate and is not one. MT_REDCHECK is set only by the
    # red-check's own child, which must see the sabotage.
    marker = os.path.join(ROOT, "tests", ".sabotage-active")
    if os.path.exists(marker) and not os.environ.get("MT_REDCHECK"):
        detail = open(marker, encoding="utf-8").read().strip().replace("\n", " / ")
        print(f"check_spotfix: INCONCLUSIVE -- the working tree is currently "
              f"SABOTAGED by redcheck_spotfix.py ({detail}). Nothing here is a "
              f"real failure; re-run when it finishes.", flush=True)
        return INCONCLUSIVE

    if not os.path.exists(CBZ) or not os.path.exists(EXPECTED):
        return skip(f"fixture missing: {CBZ} -- run tests/gen_fixtures.py")
    expected = json.load(open(EXPECTED, encoding="utf-8"))["sample.cbz"]

    floor_ok, floor_desc = _above_floor()
    print(f"  hardware: {floor_desc} -- 3.0s gate "
          f"{'ASSERTED' if floor_ok else 'measured only'}", flush=True)

    with tempfile.TemporaryDirectory(prefix="mt-spotfix-") as tmp:
        base_cache = os.path.join(tmp, "base-cache")
        base_out = os.path.join(tmp, "base-out")
        _reset(base_cache)

        from sidecar import pipeline

        record, _ = _quiet(pipeline.run_item, CBZ, base_out, JOB_A)
        c.check(
            len(record["pages"]) == len(expected["natural_order"]),
            f"[order] the ingest ran every page of the archive: "
            f"{len(record['pages'])} of {len(expected['natural_order'])}",
        )

        def fork(name):
            """A private copy of the ingested cache, so sections cannot collide."""
            d = os.path.join(tmp, name)
            shutil.copytree(base_cache, d)
            return d, os.path.join(tmp, f"{name}-out")

        _guarded(c, "[order]", section_read_cbz, expected)
        _guarded(c, "[key]", section_key)
        _guarded(c, "[layout]", section_layout, fork("layout")[0], record)

        cross_cache, cross_out = fork("crossjob")
        cross = _guarded(c, "[crossjob]", section_crossjob, cross_cache, cross_out)
        if cross is not None:
            _guarded(c, "[placement]", section_placement, cross_cache, cross_out, cross)
            wcache, wout = fork("wall")
            _seed(wcache, wout, cross)
            _guarded(c, "[wallclock]", section_wallclock, wcache, wout, cross, floor_ok, floor_desc)

            fcache, fout = fork("flags")
            _seed(fcache, fout, cross)
            _guarded(c, "[flag]", section_flags, fcache, fout, cross)

            ecache, eout = fork("edits")
            _seed(ecache, eout, cross)
            _guarded(c, "[edit]", section_edits, ecache, eout, cross)

            rcache, rout = fork("refs")
            _seed(rcache, rout, cross)
            _guarded(c, "[refs]", section_refs, rcache, rout, cross)

            zcache, zout = fork("zerollm")
            _seed(zcache, zout, cross)
            _guarded(c, "[zero-llm]", section_zero_llm, zcache, zout, cross)

            tcache, tout = fork("torn")
            _seed(tcache, tout, cross)
            _guarded(c, "[torn]", section_torn, tcache, tout, cross)

            rcache2, rout2 = fork("routes")
            _seed(rcache2, rout2, cross)
            _guarded(c, "[route]", section_routes, rcache2, rout2, cross)

            _guarded(c, "[ingest-llm]", section_ingest_llm, *fork("ingest-llm"), cross)
            _guarded(c, "[edit-rendered]", section_rendered_edit, *fork("edit-rendered"), cross)
            _guarded(c, "[archive]", section_archive, *fork("archive"))
            _guarded(c, "[cap-wired]", section_cap_wiring, *fork("cap-wired"), cross)

        _guarded(c, "[safe-path]", section_safe_paths, os.path.join(tmp, "safe-paths"))
        _guarded(c, "[parallel]", section_parallel, os.path.join(tmp, "par-cache"),
                 os.path.join(tmp, "par-out"))
        _guarded(c, "[cap]", section_cap, fork("cap")[0], record)
        _guarded(c, "[tier]", section_tier, fork("tier")[0], record)
        _guarded(c, "[persist]", section_persistence, fork("persist")[0], record)

    print("METRICS " + json.dumps(MEASURED), flush=True)

    result = c.finish()
    if result == PASS and not floor_ok:
        print("check_spotfix: INCONCLUSIVE -- every assert passed, but the "
              "3.0s gate was not asserted on this machine", flush=True)
        return INCONCLUSIVE
    return result


def _seed(cache_dir, out_dir, record):
    """Give a forked cache job B's placement, so its sections can re-render.

    Each fork carries the pages and job A's placement; job B's placement was
    written into the crossjob fork alone. Replaying it costs four file writes
    and is clearer than re-ingesting the archive once per section.
    """
    cache = _reset(cache_dir)
    for p in record["pages"]:
        cache.put_placement(JOB_B, record["item_id"], p["page"], p["page_hash"],
                            p["member"])
    os.makedirs(out_dir, exist_ok=True)


run(main)
