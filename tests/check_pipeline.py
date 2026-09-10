"""Phase 0 -- the seven-stage pipeline and its progress contract (US-006). OFFLINE.

Runs the real page from fixtures/smoke through the real pipeline in a
subprocess, because the emission contract is only observable from outside: an
in-process call could read the return value and never notice that nothing was
ever flushed to stdout.

The stages are asserted BY NAME and IN ORDER. Counting seven lines would pass
against a pipeline that emitted "detect" seven times.
"""

import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import Checks, run  # noqa: E402
from sidecar import pipeline  # noqa: E402

PAGE = os.path.join(ROOT, "fixtures", "smoke", "tategaki_01.png")

# Runs the pipeline in a child process so stdout is a real pipe, not a
# StringIO -- block buffering only manifests when the stream is not a tty.
DRIVER = """
import json, sys
from sidecar import pipeline
record = pipeline.run_page(sys.argv[1], sys.argv[2])
pipeline.write_regions(record, sys.argv[2])
"""


def main():
    c = Checks("check_pipeline")

    if not os.path.exists(PAGE):
        from lib.result import skip

        return skip(f"fixture missing: {PAGE}")

    with tempfile.TemporaryDirectory() as out:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=ROOT)
        proc = subprocess.run(
            [sys.executable, "-c", DRIVER, PAGE, out],
            capture_output=True,
            encoding="utf-8", errors="replace",
            env=env,
            cwd=ROOT,
        )
        c.check(proc.returncode == 0, f"pipeline exits 0 (stderr: {proc.stderr[-300:]})")

        lines = [ln for ln in proc.stdout.splitlines() if ln.strip()]
        events = []
        for ln in lines:
            try:
                events.append(json.loads(ln))
            except ValueError:
                c.check(False, f"every stdout line is JSON, got: {ln[:80]}")

        # -- the contract --------------------------------------------------
        names = [e.get("stage") for e in events]
        c.check(
            names == list(pipeline.STAGES),
            f"seven named stages in order, got {names}",
        )
        c.check(
            len(events) == len(set(names)),
            "each stage emits EXACTLY ONE line, no duplicates",
        )
        c.check(
            all({"stage", "item", "page", "pct"} <= set(e) for e in events),
            "every event carries stage, item, page, pct",
        )
        pcts = [e["pct"] for e in events]
        c.check(pcts == sorted(pcts) and pcts[-1] == 100, f"pct is monotonic to 100: {pcts}")

        # -- the output ----------------------------------------------------
        produced = [f for f in os.listdir(out) if f.endswith(".png")]
        c.check(len(produced) == 1, f"one translated page written: {produced}")

        regions_path = os.path.join(out, "regions.json")
        c.check(os.path.exists(regions_path), "regions.json exists for check_package to read")

        with open(regions_path, encoding="utf-8") as fh:
            record = json.load(fh)
        c.check(record.get("detections", 0) > 0, f"detection count recorded: {record.get('detections')}")
        c.check(
            record.get("ocr_calls") == record.get("detections"),
            f"one OCR call per detection: {record.get('ocr_calls')}",
        )
        c.check(
            record.get("inpaint_calls") == record.get("detections"),
            f"inpaint call count recorded: {record.get('inpaint_calls')}",
        )

        # -- Phase 2a: the fit result reaches the file the editor reads ----
        # Written by pipeline.render, and until this assert NO check read any
        # of it back out of regions.json -- the flags could have been dropped
        # at serialisation and every gate would still be green.
        regs = record.get("regions", [])
        fit_keys = {"typeset", "font_px", "rung", "fit_compromised", "fit_failed",
                    "fit_reason", "retranslated"}
        c.check(
            bool(regs) and all(fit_keys <= set(r) for r in regs),
            f"every region in regions.json carries the typeset result "
            f"(missing: {sorted(fit_keys - set(regs[0])) if regs else 'no regions'})",
        )
        summary = record.get("fit_summary") or {}
        lists = ("fit_compromised", "fit_failed", "retranslated")
        c.check(
            all(isinstance(summary.get(k), list) for k in lists),
            f"regions.json carries a job summary listing region IDS: {summary}",
        )
        c.check(
            set(summary.get("fit_failed", [])) == {r["id"] for r in regs if r.get("fit_failed")},
            "the summary's fit_failed ids agree with the per-region flags",
        )
        changed = record.get("pixels_changed_in_polygon", {})
        c.check(
            bool(changed) and all(v > 0 for v in changed.values()),
            f"pixels actually changed inside every polygon: {changed}",
        )

    # -- the write path is shared, not special -----------------------------
    src = open(os.path.join(ROOT, "sidecar", "pipeline.py"), encoding="utf-8").read()
    c.check("imaging.save" in src, "the pipeline encodes through imaging.py")
    c.check("atomic.atomic_write" in src, "the pipeline lands bytes through atomic.py")
    # Phase 2a retired the placeholder renderer. Until this revision the assert
    # here read `"ponytail:" in src` and was described as "the placeholder
    # renderer names its ceiling" -- which kept passing after the renderer was
    # replaced, because translate()'s own offline placeholder still carries the
    # marker. An assert that survives the removal of the thing it describes is
    # measuring the file, not the claim.
    c.check("typeset.typeset_page" in src,
            "the render stage is typeset.py's fit ladder, not the top-left placeholder")
    c.check("draw.text((x0 + 4, y0 + 4)" not in src,
            "the Phase 0 top-left anchored draw.text is gone from the render stage")
    for marker in ("ponytail:",):
        if marker in src:
            c.check("Ceiling:" in src and "Upgrade path:" in src,
                    f"every remaining {marker!r} placeholder still names its "
                    f"ceiling and its upgrade path")
    c.check("TODO" not in src, "no TODO placeholders left behind")

    return c.finish()


run(main)
