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
import sys

# CJK output dies on Windows under the ANSI code page (cp1252) without this.
# result.py print() hits the same wall -- see progress.txt Phase 1 US-P1-02.
getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.asserts import assert_cer  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TATEDIR = os.path.join(ROOT, "fixtures", "tategaki")
EXPECTED = os.path.join(TATEDIR, "expected.json")


def main():
    c = Checks("check_tategaki")

    if not os.path.exists(EXPECTED):
        return skip(f"ground truth absent: {EXPECTED} -- see fixtures/README.md")

    with open(EXPECTED, encoding="utf-8") as fh:
        entries = json.load(fh)

    missing = [e["file"] for e in entries
               if not os.path.exists(os.path.join(TATEDIR, e["file"]))]
    if missing:
        return skip(f"tategaki panels absent ({len(missing)}/{len(entries)} "
                    f"missing, e.g. {missing[0]}) -- see fixtures/README.md")

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
    blanks = {
        "white": Image.new("RGB", (300, 300), "white"),
        "gray": Image.new("RGB", (300, 300), (200, 200, 200)),
        "bordered": bordered,
    }
    for name, img in blanks.items():
        # Once, not once per use: the assert and the message it prints must
        # report the same call, not two.
        got = ocr_ja.ocr(img)
        c.check(got == "", f"blank {name} crop returns '' (got {got!r:.30})")

    return c.finish()


run(main)
