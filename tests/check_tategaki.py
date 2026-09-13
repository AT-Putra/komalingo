"""Phase 1 -- OCR truth on real vertical Japanese (AC-2). OFFLINE.

Runs manga-ocr over the hand-transcribed tategaki panels and gates on two
thresholds, not one: the full set AND the furigana subset alone. Without the
split, every permitted full-set failure could be exactly a furigana panel
while AC-2's explicit furigana clause goes unmet.

AC-2 states the exact-match bars as 16/20 and 5/6. They are enforced here as
the RATIOS those fractions name, not as the absolute counts: with an absolute
floor of 16, growing the fixture set past 20 panels silently loosens the gate,
which is backwards -- more evidence must not mean a lower bar.

Ground truth is authored BY EYE into fixtures/tategaki/expected.json -- never
by running the OCR under test, which would make this gate circular. The blank
crops pin ocr_ja's hallucination gate: manga-ocr invents text on empty crops
('sooiebawa' class), so any non-empty output there is a hard fail.

Every panel also carries its own CER ceiling, not just the set mean. A single
panel read as something else entirely moves a 24-panel mean by 0.04 and stays
green; the per-panel assert is the one that goes red for it.
"""

import json
import os
import shutil
import subprocess
import sys

# CJK output dies on Windows under the ANSI code page (cp1252) without this.
# result.py print() hits the same wall -- see progress.txt Phase 1 US-P1-02.
getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # fetch_fixtures
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.asserts import assert_cer  # noqa: E402
from lib.result import Checks, broken_checkout, run, skip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TATEDIR = os.path.join(ROOT, "fixtures", "tategaki")
EXPECTED = os.path.join(TATEDIR, "expected.json")


def main():
    c = Checks("check_tategaki")

    if not os.path.exists(EXPECTED):
        # Local-only, like the panels: it transcribes the volume's dialogue,
        # which is not ours to publish. Absent is a skip, not a broken checkout.
        return skip(f"ground truth absent: {EXPECTED} -- kept locally with the "
                    f"scans, see fixtures/README.md")

    with open(EXPECTED, encoding="utf-8") as fh:
        entries = json.load(fh)

    # -- [manifest] these are the pixels the ground truth was read off ------
    # Absent panels are a skip: artwork this box is not allowed to have.
    # Present-but-different panels are a FAIL: a second developer's scan of
    # the same volume crops to the right filenames with other pixels, and a
    # CER graded against transcriptions authored for the maintainer's pixels
    # is not a measurement of the OCR. The hashes live in MANIFEST.json,
    # which is committed, so its absence is a broken checkout, not a skip --
    # and it is checked BEFORE the panels, so that on a box without the
    # artwork a missing manifest does not hide behind the skip.
    # The verifier is fetch_fixtures.verify(), not a copy of it.
    from fetch_fixtures import MANIFEST, load_manifest, verify
    from gen_tategaki_panels import scan_dirs

    if not os.path.exists(MANIFEST):
        return broken_checkout(f"manifest absent: {MANIFEST} -- committed, "
                               f"see fixtures/README.md")

    missing = [e["file"] for e in entries
               if not os.path.exists(os.path.join(TATEDIR, e["file"]))]
    if missing:
        return skip(f"tategaki panels absent ({len(missing)}/{len(entries)} "
                    f"missing, e.g. {missing[0]}) -- see fixtures/README.md")

    # With the scans present the verifier can say WHICH of wrong-scan and
    # wrong-crop a mismatch is; without them it says it cannot. Look, rather
    # than assume the scans are absent because this is a check and not the
    # fetch tool -- on the box that authored the manifest they are here, and
    # a message that says "absent" while they sit on disk is a wrong message.
    dirs = scan_dirs()
    rep = verify(load_manifest(), dirs[0] if len(dirs) == 1 else None)
    c.check(rep.expected is None,
            "[manifest] expected.json sha256 matches the one MANIFEST.json was "
            "written against" + (f" ({rep.expected})" if rep.expected else ""))
    c.check(not rep.panels,
            f"[manifest] all {len(entries)} panels match MANIFEST.json"
            + (f" -- {len(rep.panels)} do not: " + "; ".join(rep.panels)
               if rep.panels else ""))
    # The source pages, when this box has them. rep.ok is false on a page
    # mismatch, and without an assert here that case returned c.finish()
    # green with nothing graded -- a PASS (2/2) with no CER and no METRICS,
    # on a box holding a different rip of the volume (review, G1).
    c.check(not rep.pages,
            "[manifest] every source page this box holds matches MANIFEST.json"
            + (f" -- {len(rep.pages)} do not: " + "; ".join(rep.pages)
               if rep.pages else ""))
    if not rep.ok:
        # Stop here rather than grade on. The numbers below would be printed
        # as METRICS and recorded by run_all as this box's baseline, and a
        # baseline measured on the wrong pixels is worse than none.
        return c.finish()

    c.check(len(entries) >= 20,
            f">= 20 ground-truth panels, have {len(entries)}")
    furi = [e for e in entries if e.get("has_furigana")]
    if not c.check(len(furi) >= 6, f">= 6 furigana panels, have {len(furi)}"):
        # The subset thresholds below divide by this count. Stop at the red
        # assert rather than crash past it into a ZeroDivisionError.
        return c.finish()

    from PIL import Image

    from sidecar import ocr_ja

    # Loose enough for the real recognition errors this set contains (worst
    # 0.053, a single mora), tight enough that a panel read as a different
    # sentence is red.
    panel_ceiling = 0.35

    exact_all, cers_all = 0, []
    exact_furi, cers_furi = 0, []
    for e in entries:
        with Image.open(os.path.join(TATEDIR, e["file"])) as im:
            im.load()
            got = ocr_ja.ocr(im.convert("RGB"))
        want = e["text"]
        rate = assert_cer(c, got, want, panel_ceiling, e["file"])
        cers_all.append(rate)
        if got == want:
            exact_all += 1
        if e.get("has_furigana"):
            cers_furi.append(rate)
            if got == want:
                exact_furi += 1

    mean_all = sum(cers_all) / len(cers_all)
    floor_all = -(-16 * len(entries) // 20)  # ceil: 16/20 of the set, never fewer
    c.check(exact_all >= floor_all,
            f"full-set exact match {exact_all}/{len(entries)} >= {floor_all} (16/20)")
    c.check(mean_all <= 0.10, f"full-set mean CER {mean_all:.3f} <= 0.10")

    mean_furi = sum(cers_furi) / len(cers_furi)
    floor_furi = -(-5 * len(furi) // 6)
    c.check(exact_furi >= floor_furi,
            f"furigana exact match {exact_furi}/{len(furi)} >= {floor_furi} (5/6)")
    c.check(mean_furi <= 0.12, f"furigana mean CER {mean_furi:.3f} <= 0.12")

    # One machine-readable line for run_all's baseline record. Prose asserts
    # are for a reader; the ratchet must not have to parse them.
    print("METRICS " + json.dumps({"mean_cer": round(mean_all, 4),
                                   "exact_match": round(exact_all / len(entries), 4)}),
          flush=True)

    # -- the hallucination gate: three blank crops, zero non-empty output ----
    from PIL import ImageDraw

    bordered = Image.new("RGB", (300, 300), "white")
    ImageDraw.Draw(bordered).rectangle([10, 10, 290, 290], outline="black", width=4)
    # The degenerate sizes are here because the gate used to be green on a
    # boundary it never tested. Every blank above is 300x300, and _is_blank
    # took std() of an empty array on a zero-area crop: nan, and nan < 8.0 is
    # False, so "cannot compute" read as "not blank" and manga-ocr answered a
    # 0x50 crop with 'それでも、'. pipeline.ocr reaches this from production --
    # it crops _bbox(polygon) straight from the detector, and a degenerate
    # polygon gives a zero-area box. A hallucination gate that only ever sees
    # well-formed input is not a gate.
    blanks = {
        "white": Image.new("RGB", (300, 300), "white"),
        "gray": Image.new("RGB", (300, 300), (200, 200, 200)),
        "bordered": bordered,
        "zero-width": Image.new("RGB", (0, 50), "white"),
        "zero-height": Image.new("RGB", (50, 0), "white"),
        "zero-area": Image.new("RGB", (0, 0), "white"),
        "one-pixel": Image.new("RGB", (1, 1), "white"),
    }
    for name, img in blanks.items():
        # Once, not once per use: the assert and the message it prints must
        # report the same call, not two.
        got = ocr_ja.ocr(img)
        c.check(got == "", f"blank {name} crop returns '' (got {got!r:.30})")

    # -- the OFFLINE property, asserted rather than assumed ----------------
    # US-P1-07 moved manga-ocr onto a pinned local directory so the app cannot
    # silently fetch from the HuggingFace Hub. That property lives in
    # transformers' behaviour, not in our code: from_pretrained takes a local
    # branch only because os.path.isdir() is true of what we hand it. A
    # dependency bump that changed that branch would regress this in the worst
    # possible way -- still working on every developer machine with a warm HF
    # cache, and reaching the network again on cold ones. Nobody would see it.
    #
    # A SUBPROCESS because the model is a module-level singleton already loaded
    # above, and the block has to be in place before the first load.
    #
    # HF_HOME is redirected at an empty directory too, and that is the part
    # that makes this assert able to fail at all. Blocking sockets alone is not
    # enough: the first version of this check stayed GREEN when ocr_ja was
    # sabotaged back to MangaOcr(force_cpu=True), because this machine's
    # HuggingFace cache is warm and the repo id resolved out of it without a
    # single packet. That is a check that cannot fail on the machine of anyone
    # who has ever run the app -- which is precisely the regression being
    # guarded against, wearing the disguise of a passing test. With no network
    # AND no cache, only the pinned directory can satisfy the load.
    hf_empty = os.path.join(ROOT, "build", "work", "tategaki-empty-hf")
    shutil.rmtree(hf_empty, ignore_errors=True)
    os.makedirs(hf_empty, exist_ok=True)
    r = subprocess.run(
        [sys.executable, "-c", OFFLINE_DRIVER, os.path.join(TATEDIR, entries[0]["file"])],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONPATH": ROOT, "PYTHONIOENCODING": "utf-8",
             "HF_HOME": hf_empty, "HF_HUB_CACHE": os.path.join(hf_empty, "hub"),
             "TRANSFORMERS_CACHE": hf_empty},
    )
    got = (r.stdout or "").strip().splitlines()[-1:] or [""]
    c.check(r.returncode == 0 and got[0] == entries[0]["text"],
            f"OCR loads and reads with every socket refused and the HF cache empty "
            f"(rc={r.returncode}, got {got[0]!r}, want {entries[0]['text']!r}"
            f"{'; stderr: ' + (r.stderr or '').strip()[-200:] if r.returncode else ''})")

    return c.finish()


# Every outbound socket refused -- not HF_HUB_OFFLINE, which asks the library
# to behave rather than proving it never asks.
OFFLINE_DRIVER = """
import socket, sys

def _refuse(*a, **k):
    raise OSError("offline assert: no network")

socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
socket.create_connection = _refuse

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
from sidecar import ocr_ja

with Image.open(sys.argv[1]) as im:
    im.load()
    print(ocr_ja.ocr(im.convert("RGB")))
"""


run(main)
