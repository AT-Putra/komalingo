#!/usr/bin/env python3
"""Generate every synthetic fixture the offline gates read.

    uv run --project sidecar python tests/gen_fixtures.py

Writes `fixtures/smoke/` and `fixtures/bubbles/` (Phase 0a); Phase 6 extends
this with `fixtures/archives/`. Exit 0 always, or a traceback -- there is no
partial-success mode: a generator that half-writes a fixture tree is worse
than one that fails.

Determinism is the whole point (Phase 0a gate: two regenerations from an empty
tree, byte-identical). Three sources of nondeterminism are closed here:

  - RNG: one seeded `default_rng` per fixture, never a global.
  - PNG timestamps: Pillow writes a tIME chunk from the wall clock unless
    told otherwise; `pnginfo` is passed with no tIME and `save(..., pnginfo=)`
    then omits it.
  - Dict/glob ordering: every loop iterates an explicit list, never a
    directory listing.

`fixtures/provider/` is deliberately NOT generated -- three hand-authored HTTP
bodies are Phase 0 deliverables (build order, section E).
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

# A JA-capable font is required: the smoke page's whole purpose is vertical
# Japanese glyphs, and Pillow's default bitmap font renders them as boxes.
JA_FONTS = ["C:/Windows/Fonts/msgothic.ttc", "C:/Windows/Fonts/YuGothR.ttc"]
LATIN_FONTS = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]


def load_font(candidates, size):
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(
        f"no usable font among {candidates} -- fixtures cannot be generated "
        f"deterministically without one"
    )


def save_png(img, path):
    """Write a PNG with no tIME chunk, so two runs are byte-identical."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG", pnginfo=PngInfo(), optimize=False, compress_level=6)


# --------------------------------------------------------------------------
# smoke/tategaki_01.png -- a full page, not a polygon on white.
# --------------------------------------------------------------------------

W, H = 1200, 1700

# Three bubbles of differing aspect. Bubble 0 is the screentone-gradient one and
# carries the clear ring assert 1 depends on; the crossing line art is placed
# against bubble 2, a DIFFERENT bubble, so bubble 0's ring stays valid.
# (x0, y0, x1, y1)
BUBBLES = [
    (150, 190, 470, 720),    # tall, aspect ~0.6 -- ring bubble
    (620, 240, 1060, 560),   # wide, aspect ~1.4
    (300, 980, 640, 1420),   # tall, aspect ~0.77 -- line art crosses this one
]
BUBBLE_TEXT = ["こんにちは", "元気ですか", "またあした"]


def screentone(size, rng, period=6):
    """A halftone-ish dot gradient. Density ramps top->bottom."""
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    ramp = yy / max(h - 1, 1)                       # 0 at top, 1 at bottom
    dots = ((xx % period == 0) & (yy % period == 0))
    jitter = rng.random((h, w)) < ramp * 0.35
    tone = np.full((h, w), 255, dtype=np.uint8)
    tone[dots | jitter] = 40
    return Image.fromarray(tone, "L").convert("RGB")


def draw_vertical(draw, text, box, font, fill="black"):
    """Tategaki: glyphs stacked top-to-bottom, columns right-to-left.

    One column here -- enough for the OCR path to have a real vertical run.
    """
    x0, y0, x1, y1 = box
    size = font.size
    cx = x1 - (x1 - x0) * 0.32          # right-ish, as tategaki reads
    cy = y0 + (y1 - y0) * 0.18
    for i, ch in enumerate(text):
        draw.text((cx, cy + i * size * 1.12), ch, font=font, fill=fill)


def gen_smoke():
    rng = np.random.default_rng(0xC0FFEE)
    page = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(page)

    # Panel borders: three panels, thick black strokes.
    panels = [(60, 60, 1140, 800), (60, 850, 640, 1560), (700, 850, 1140, 1560)]
    for p in panels:
        draw.rectangle(p, outline="black", width=7)

    # Screentone fill inside panel 0, so bubble 0 sits ON tone rather than white.
    px0, py0, px1, py1 = panels[0]
    tone = screentone((px1 - px0 - 14, py1 - py0 - 14), rng)
    page.paste(tone, (px0 + 7, py0 + 7))

    # Some line art in panel 1, crossing bubble 2's edge (assert 1's "different
    # bubble" guarantee: this must NOT touch bubble 0).
    for x0, y0, x1, y1 in [(120, 1180, 700, 1090), (140, 1300, 690, 1240),
                           (200, 900, 260, 1520)]:
        draw.line((x0, y0, x1, y1), fill="black", width=5)

    # Bubbles: white ellipse + black outline. Painted AFTER the tone and line
    # art, so bubble 0's interior is clean white -- that clean band inside its
    # own border is the ring check_inpaint.py evaluates.
    ja = load_font(JA_FONTS, 44)
    for box, text in zip(BUBBLES, BUBBLE_TEXT):
        draw.ellipse(box, fill="white", outline="black", width=5)
        draw_vertical(draw, text, box, ja)

    save_png(page, FIXTURES / "smoke" / "tategaki_01.png")

    return {
        "tategaki_01.png": {
            "size": [W, H],
            "panels": panels,
            "bubbles": [
                {"box": list(BUBBLES[0]), "text": BUBBLE_TEXT[0],
                 "aspect": round((BUBBLES[0][2] - BUBBLES[0][0])
                                 / (BUBBLES[0][3] - BUBBLES[0][1]), 3),
                 "on_screentone": True, "clean_ring_px_min": 6, "line_art_crosses": False},
                {"box": list(BUBBLES[1]), "text": BUBBLE_TEXT[1],
                 "aspect": round((BUBBLES[1][2] - BUBBLES[1][0])
                                 / (BUBBLES[1][3] - BUBBLES[1][1]), 3),
                 "on_screentone": True, "clean_ring_px_min": 6, "line_art_crosses": False},
                {"box": list(BUBBLES[2]), "text": BUBBLE_TEXT[2],
                 "aspect": round((BUBBLES[2][2] - BUBBLES[2][0])
                                 / (BUBBLES[2][3] - BUBBLES[2][1]), 3),
                 "on_screentone": False, "clean_ring_px_min": None, "line_art_crosses": True},
            ],
            "notes": "Ring guarantee: bubble 0 sits on screentone with a clean "
                     "6-10px band inside its border; line art crosses bubble 2 only.",
        }
    }


# --------------------------------------------------------------------------
# bubbles/ -- the six forcing fixtures Phase 2a's five-rung ladder needs.
# --------------------------------------------------------------------------
# Each is one bubble on white with a source string and a translation the
# typesetter will be handed. The fixture forces a rung by geometry (how much
# room) crossed with string length. `expected.json` states which rung and what
# the ladder must report -- the gate reads that, not this docstring.

FORCING = [
    # (name, W, H, ellipse, ja source, english the typesetter receives, rung, expect)
    ("rung4", 420, 300, (30, 30, 390, 270), "たすけて",
     "Help me right now please",
     4, {"fit_compromised": False, "fit_failed": False,
         "why": "fits after shrink-to-fit above the font floor"}),

    ("rung5-length", 300, 200, (20, 20, 280, 180), "せつめい",
     "This explanation is far too long to ever fit inside this small bubble at "
     "any font size above the floor",
     5, {"fit_compromised": True, "fit_failed": False, "retranslate": True,
         "why": "length forces one capped re-translation"}),

    ("rung5-geometry", 260, 460, (6, 6, 254, 454), "ほそい",
     "A sentence in a sliver",
     5, {"fit_compromised": True, "fit_failed": False,
         "why": "polygon at the raster edge; geometry, not length, forces rung 5"}),

    ("rung5-success", 340, 240, (20, 20, 320, 220), "みじかく",
     "Shortened on retry",
     5, {"fit_compromised": True, "fit_failed": False, "retranslate": True,
         "rendered_text": "Shortened on retry",
         "why": "the retry's reply MUST be rendered; discarding it must fail"}),

    ("rung5-nowordfits", 150, 120, (8, 8, 142, 112), "むり",
     "Incomprehensibilities notwithstanding",
     5, {"fit_compromised": True, "fit_failed": True, "rendered_text": "",
         "why": "no whole word fits: renders empty, fit_failed surfaced"}),

    ("rung5-midtoken", 130, 110, (8, 8, 122, 102), "ながい",
     "Pneumonoultramicroscopicsilicovolcanoconiosis",
     5, {"fit_compromised": True, "fit_failed": True, "ellipsis": True,
         "why": "first token exceeds capacity: mid-token break with an ellipsis"}),
]


def gen_bubbles():
    ja = load_font(JA_FONTS, 26)
    index = {}
    for name, w, h, ell, src, english, rung, expect in FORCING:
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        draw.ellipse(ell, fill="white", outline="black", width=4)
        draw_vertical(draw, src, ell, ja)
        save_png(img, FIXTURES / "bubbles" / f"{name}.png")
        index[f"{name}.png"] = {
            "polygon": list(ell),
            "source_ja": src,
            "translation_in": english,
            "forces_rung": rung,
            "expect": expect,
        }
    return index


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + fixed separators + trailing newline: byte-identical across runs.
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main():
    for sub in ("smoke", "bubbles"):
        shutil.rmtree(FIXTURES / sub, ignore_errors=True)

    smoke = gen_smoke()
    bubbles = gen_bubbles()

    write_json(FIXTURES / "smoke" / "expected.json", smoke)
    write_json(FIXTURES / "bubbles" / "expected.json", bubbles)

    n = len(smoke) + len(bubbles)
    print(f"generated {n} fixtures + 2 expected.json under {FIXTURES}")
    for name in sorted(smoke):
        print(f"  smoke/{name}")
    for name in sorted(bubbles):
        print(f"  bubbles/{name}  rung {bubbles[name]['forces_rung']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
