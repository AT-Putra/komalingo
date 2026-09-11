#!/usr/bin/env python3
"""Generate every synthetic fixture the offline gates read.

    uv run --project sidecar python tests/gen_fixtures.py

Writes `fixtures/smoke/` and `fixtures/bubbles/` (Phase 0a) and
`fixtures/cbz/` (Phase 3); Phase 6 extends this with `fixtures/archives/`. Exit 0 always, or a traceback -- there is no
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
  - Zip metadata: a ZipInfo's date_time defaults to the wall clock and its
    external_attr to the process umask, so an archive written twice differs
    twice over. Both are pinned in gen_cbz.

`fixtures/provider/` is deliberately NOT generated -- three hand-authored HTTP
bodies are Phase 0 deliverables (build order, section E).
"""

import io
import json
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"

sys.path.insert(0, str(ROOT))

from sidecar.containers.read_cbz import _natural_key  # noqa: E402
from sidecar.region import ellipse_points  # noqa: E402

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
SMOKE_GLYPH_PX = 44  # the JA face size on both smoke pages; Phase 2b's gates read it

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
    ja = load_font(JA_FONTS, SMOKE_GLYPH_PX)
    for box, text in zip(BUBBLES, BUBBLE_TEXT):
        draw.ellipse(box, fill="white", outline="black", width=5)
        draw_vertical(draw, text, box, ja)

    save_png(page, FIXTURES / "smoke" / "tategaki_01.png")

    return {
        "tategaki_01.png": {
            "size": [W, H],
            "panels": panels,
            "glyph_px": SMOKE_GLYPH_PX,
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
# smoke/tategaki_02.png -- multi-column bubbles, for Phase 2b's grouping gate.
# --------------------------------------------------------------------------
# tategaki_01 has one column per bubble, so it never showed the defect Phase
# 2b exists to fix: the detector returns one quad per COLUMN and each column
# was typeset alone. Three bubbles of 2, 3 and 4 columns, plus a rotated Latin
# title on a dark block hard against bubble 2 -- page 010's box-art case,
# where a wide rotated quad's bbox overlaps the neighbouring columns in y and
# must still stay a separate region.

# (x0, y0, x1, y1), and the columns each carries, right to left as read.
COLUMN_BUBBLES = [
    ((640, 110, 1100, 470), ["今日はいい", "天気だね"]),
    ((110, 150, 520, 690), ["史実が売りの", "歴史ゲームを", "やるもんじゃ", "ないな"]),
    ((240, 940, 700, 1500), ["反撃なしじゃ", "みんな", "死ぬぞ"]),
]
ART_BLOCK = (720, 1000, 1150, 1440)  # dark rectangle; its title is rotated
ART_TEXT = "DEUS EX MACHINA"
ART_ANGLE = -14
# Two words stacked on the art with dark art between them -- page 012's
# "Storage Magic" laid down a character's body. They group into one block,
# and the erase must take the two words and leave the art between them.
ART_STACK = [("収納", (740, 1016)), ("魔法", (740, 1092))]
ART_STACK_GAP = (740, 1066, 830, 1090)  # (x0, y0, x1, y1) of dark art between the words


def draw_columns(draw, columns, box, font, pitch=1.35, leading=1.12):
    """Tategaki in several columns: right to left, glyphs top to bottom.

    The block is centred in the bubble. Column pitch and leading are what a
    typeset tankoubon page uses, near enough that the detector sees columns
    at the spacing it will meet on real pages.
    """
    x0, y0, x1, y1 = box
    size = font.size
    step = size * pitch
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    tallest = max(len(c) for c in columns) * size * leading
    top = cy - tallest / 2
    right = cx + (len(columns) - 1) * step / 2 - size / 2
    for ci, column in enumerate(columns):
        x = right - ci * step
        for gi, ch in enumerate(column):
            draw.text((x, top + gi * size * leading), ch, font=font, fill="black")


def gen_smoke_columns():
    page = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(page)
    for p in [(60, 60, 1140, 800), (60, 850, 1140, 1560)]:
        draw.rectangle(p, outline="black", width=7)

    # The art block first, so the bubble beside it is painted over its edge
    # the way a bubble overlaps panel art; then the rotated title on top.
    draw.rectangle(ART_BLOCK, fill=(40, 40, 40))
    latin = load_font(LATIN_FONTS, 54)
    tw = int(latin.getlength(ART_TEXT)) + 20
    title = Image.new("RGBA", (tw, 80), (0, 0, 0, 0))
    ImageDraw.Draw(title).text((10, 8), ART_TEXT, font=latin, fill="white")
    title = title.rotate(ART_ANGLE, expand=True, resample=Image.BICUBIC)
    ax0, ay0, ax1, ay1 = ART_BLOCK
    page.paste(title, ((ax0 + ax1 - title.width) // 2, (ay0 + ay1 - title.height) // 2), title)

    ja = load_font(JA_FONTS, SMOKE_GLYPH_PX)
    for word, at in ART_STACK:
        draw.text(at, word, font=ja, fill="white")
    for box, columns in COLUMN_BUBBLES:
        draw.ellipse(box, fill="white", outline="black", width=5)
        draw_columns(draw, columns, box, ja)

    save_png(page, FIXTURES / "smoke" / "tategaki_02.png")
    return {
        "tategaki_02.png": {
            "size": [W, H],
            "glyph_px": SMOKE_GLYPH_PX,
            "bubbles": [
                {"box": list(box), "columns": columns, "text": "".join(columns)}
                for box, columns in COLUMN_BUBBLES
            ],
            "art": {"box": list(ART_BLOCK), "text": ART_TEXT, "angle": ART_ANGLE,
                    "stack": [w for w, _ in ART_STACK], "stack_gap": list(ART_STACK_GAP)},
            "notes": "One region per bubble is the claim; the art block beside "
                     "bubble 2 must remain its own region, and the art between "
                     "the two stacked words on it must survive the erase.",
        }
    }


# --------------------------------------------------------------------------
# bubbles/ -- the six forcing fixtures Phase 2a's five-rung ladder needs.
# --------------------------------------------------------------------------
# Each is one bubble on white with a source string and a translation the
# typesetter will be handed. The fixture forces a rung by geometry (how much
# room) crossed with string length. `expected.json` states which rung and what
# the ladder must report -- the gate reads that, not this docstring.
#
# EVERY NUMBER BELOW IS MEASURED, NOT CHOSEN. The first version of this table
# was written before the ladder existed, and when the ladder arrived FIVE of
# the six fixtures landed on rung 1: `rung5-geometry`'s "sliver" was a 248px
# ellipse that fitted its 116px string at full size, and `rung5-nowordfits`'
# longest word fitted its 133px centre chord with room to spare. Six fixtures
# that cannot reach the rungs they are named for are six asserts that cannot
# go red -- the exact defect class this suite exists to remove. The geometry
# here was found by bisecting the ladder's own rung boundaries; see the rung
# assert in check_typeset.py, which fails if any fixture stops forcing.
#
# Widths are measured against the ELLIPSE CHORD, never the bounding box: a
# bubble's bbox is far wider than the chord any line may actually use, and
# tuning against the bbox is how the first version came to be so far out.

# One sentence, sliced at measured word counts. The large fixtures share it so
# that the ONLY difference between them is the variable each isolates.
_LONG = (
    "I told you already that we should never have opened that door because "
    "whatever waits behind it has been patient for a very long time indeed and "
    "it remembers every single one of us by name and it will not forget"
).split()

# Re-measured after the Phase 2a review rewrote the ladder's fit predicate to
# be monotone -- the first set of numbers was bisected against a predicate with
# holes in it, and moved when the holes were removed. On the 110x150 bubble
# below, at the 12px floor:
#
#     words 20-23 -> rung 2    24-25 -> rung 3    26-28 -> rung 4    29+ -> rung 5
#
# and rung 5's computed capacity is 138 characters for every string past it.
# Each fixture sits in the MIDDLE of its window, so a small change in the
# engine's metrics moves a boundary before it moves a fixture off its rung.
_S27 = " ".join(_LONG[:27])   # 143 chars -- centre of rung 4's 26-28 window
_S31 = " ".join(_LONG[:31])   # 169 chars -- rung 5 by length
_S32 = " ".join(_LONG[:32])   # 173 chars -- likewise, distinct for stub keying

# The shared bubble: 110x150, and the page around it is what decides whether
# rung 4's bleed has anywhere to go.
_BIG = (15, 10, 125, 160)
_SMALL = (10, 10, 70, 50)

# A reply LONGER than the cap it was sent with. The spec names this case: rung 5
# must not trust it over the original, so it is rejected and the ORIGINAL is
# what gets truncated.
_TOO_LONG_REPLY = "Still far too long to fit " + _S27

# A reply WITHIN its cap that still does not fit: 121 characters against a cap
# of 138, but in capitals, which run far wider than the lowercase prefix the cap
# was measured on. The spec names this case separately from a reply that is too
# long. This reply is ACCEPTED and rendered, then truncated -- the reply, at a
# word boundary of the reply -- with retranslated and fit_failed both set.
_WITHIN_CAP_REPLY = (
    "WE MUST NEVER OPEN THAT DOOR AGAIN BECAUSE WHATEVER WAITS BEHIND IT "
    "REMEMBERS EVERY ONE OF US BY NAME AND WILL NOT FORGET"
)

FORCING = [
    # (name, W, H, ellipse, ja source, english the typesetter receives, rung,
    #  expect, retry_reply)
    #
    # Rung 4: the string exhausts rungs 1-3 and fits only once bounded
    # horizontal bleed is allowed. Both margins (15px) exceed the 8.8px the
    # bleed needs, so rung 4 is genuinely available here.
    ("rung4", 140, 170, _BIG, "たすけて", _S27,
     4, {"fit_compromised": True, "fit_failed": False, "rung4_skipped": False,
         "retranslated": False,
         "why": "exhausts rungs 1-3; fits only with bounded horizontal bleed"},
     None),

    # Rung 5 by LENGTH, reply REJECTED: past rung 4's ceiling on the same
    # polygon and margins, and the retry comes back LONGER than its cap. The
    # reply is not trusted over the original; the original is truncated.
    ("rung5-length", 140, 170, _BIG, "せつめい", _S31,
     5, {"fit_compromised": False, "fit_failed": True, "rung4_skipped": False,
         "retranslate": True, "reply_rejected": True, "retranslated": False,
         "word_boundary": True, "reason": "truncated at a word boundary",
         "why": "length forces rung 5; the capped retry comes back longer than its cap"},
     _TOO_LONG_REPLY),

    # Rung 5 by GEOMETRY, reply ACCEPTED but still too big: the SAME polygon and
    # the SAME string as the rung-4 fixture, on a page 15px narrower so the
    # bubble's right edge sits on the raster edge -- rung 4 is SKIPPED rather
    # than attempted. The retry is within its cap and does not fit, which is
    # the spec's "the shortened string still does not fit" branch: rendered,
    # then truncated at a boundary of the REPLY. Paired with rung5-length, the
    # two cover both ways a retry can fail to rescue a region.
    ("rung5-geometry", 125, 170, _BIG, "ほそい", _S27,
     5, {"fit_compromised": False, "fit_failed": True, "rung4_skipped": True,
         "retranslate": True, "reply_rejected": False, "retranslated": True,
         "word_boundary": True, "reason": "truncated at a word boundary",
         "why": "raster edge skips rung 4; the accepted reply still does not fit"},
     _WITHIN_CAP_REPLY),

    # Rung 5's SUCCESS branch. The stub's reply is within its cap and FITS.
    # Without this fixture an implementation that issues the retry, discards
    # the reply and truncates passes every other rung-5 assert including the
    # request count. A retried region that fits cleanly is neither compromised
    # nor failed; it is reported as retranslated.
    ("rung5-success", 140, 170, _BIG, "みじかく", _S32,
     5, {"fit_compromised": False, "fit_failed": False, "rung4_skipped": False,
         "retranslate": True, "reply_rejected": False, "retranslated": True,
         "rendered_text": "Shortened on retry",
         "why": "the retry's reply MUST be rendered; discarding it must fail"},
     "Shortened on retry"),

    # Rung 5, no whole word fits: a 60px-wide bubble against a string whose
    # SHORTEST word is 87px at the floor. Renders empty, fit_failed surfaced.
    ("rung5-nowordfits", 80, 60, _SMALL, "むり",
     "Incomprehensibilities notwithstanding",
     5, {"fit_compromised": False, "fit_failed": True, "retranslate": True,
         "reply_rejected": True, "retranslated": False, "rendered_text": "",
         "reason": "no whole word fits",
         "why": "no whole word fits: renders empty, fit_failed surfaced"},
     "Incomprehensibilities notwithstanding"),

    # Rung 5, first token exceeds capacity: the same bubble against a single
    # 44-character token. There is no boundary to stop at, so the break is
    # mid-token with a trailing ellipsis.
    ("rung5-midtoken", 80, 60, _SMALL, "ながい",
     "Pneumonoultramicroscopicsilicovolcanoconiosis",
     5, {"fit_compromised": False, "fit_failed": True, "retranslate": True,
         "reply_rejected": True, "retranslated": False, "ellipsis": True,
         "reason": "single token broken with an ellipsis",
         "why": "first token exceeds capacity: mid-token break with an ellipsis"},
     "Pneumonoultramicroscopicsilicovolcanoconiosis"),
]

def gen_bubbles():
    """One bubble per fixture, DRAWN from the same point list the gate measures.

    The bubble is drawn with `draw.polygon` over region.ellipse_points rather
    than with `draw.ellipse`, so the shape on the raster and the polygon in
    expected.json are the same object. Drawing a true ellipse and measuring an
    inscribed 64-gon differs by under a pixel at the waist and by more at the
    poles -- harmless on an easy string, and enough to flip a boundary fixture
    between runs, which is precisely what these fixtures are.
    """
    ja = load_font(JA_FONTS, 22)
    index = {}
    for name, w, h, ell, src, english, rung, expect, retry in FORCING:
        points = ellipse_points(ell)
        img = Image.new("RGB", (w, h), "white")
        draw = ImageDraw.Draw(img)
        draw.polygon(points, fill="white", outline="black")
        draw_vertical(draw, src, ell, ja)
        save_png(img, FIXTURES / "bubbles" / f"{name}.png")
        entry = {
            "page_size": [w, h],
            # The BOX, not the 64 derived points. Both the drawing above and
            # the gate rebuild the polygon with region.ellipse_points(box), so
            # writing the points here would add 30x the file size and no
            # information -- and would introduce a second copy that can drift
            # from the function that made it.
            "box": list(ell),
            "shape": "ellipse",
            "source_ja": src,
            "translation_in": english,
            "forces_rung": rung,
            "expect": expect,
        }
        # The stubbed retry reply lives WITH the fixture, not in the check: the
        # fixture is what decides whether rung 5's retry is rescued or survived,
        # and a reply held in the check drifts from the geometry it was chosen
        # against.
        if retry is not None:
            entry["retry_reply"] = retry
        index[f"{name}.png"] = entry
    return index


# --------------------------------------------------------------------------
# cbz/sample.cbz -- Phase 3's one real multi-page item.
# --------------------------------------------------------------------------
# Phase 3 freezes the page-cache contract, and two clauses of it are only
# testable against a real archive:
#
#   * PLACEMENT. Two byte-identical pages share a page hash, so they share a
#     page directory and a translation -- which is correct and wanted. Editing
#     one and silently editing the other is the bug placement exists to
#     prevent, and a directory of loose files cannot exhibit it.
#   * ORDER. Members are natural-sorted on the FULL path. The layout below has
#     a lexicographic order that differs from its natural order in both
#     directions that matter: ch10 after ch2 (a directory segment), and p10
#     after p9 (a filename segment). A reader that sorted lexicographically
#     would produce a visibly different page order against this file and an
#     identical one against any tidily zero-padded archive.
#
# Ordinals 3 and 7 are the identical pair. They are deliberately NOT adjacent
# and NOT in the same chapter directory, so a placement bug cannot pass by
# accidentally treating neighbours alike.
#
# Junk members and one undecodable member are included because skipping them
# is part of the contract and because ordinals must stay contiguous across
# them: a hole would mean "page 7" naming different pages before and after a
# corrupt member was repaired.

CBZ_W, CBZ_H = 620, 880

# (member path, page index). Page index repeats for the identical pair.
# Written to the archive in REVERSE natural order, so a reader that trusted
# the zip's central directory order would produce the exactly wrong sequence.
CBZ_MEMBERS = [
    ("ch1/p1.png", 0),
    ("ch1/p2.png", 1),
    ("ch1/p9.png", 2),    # ordinal 3  -- identical to ordinal 7
    ("ch1/p10.png", 3),
    ("ch2/p1.png", 4),
    ("ch2/p2.png", 5),
    ("ch10/p1.png", 2),   # ordinal 7  -- identical to ordinal 3
    ("ch10/p2.png", 6),
]
CBZ_JUNK = {
    "ComicInfo.xml": b"<?xml version=\"1.0\"?><ComicInfo><Title>sample</Title></ComicInfo>",
    "Thumbs.db": b"\x00\x01not a page",
    "__MACOSX/._ch1/p1.png": b"\x00\x05\x16\x07resource fork",
    "notes.txt": b"credits\n",
    # Named .png and not a PNG: the decode-failure path, which must skip with a
    # warning rather than abort the enumeration. It sorts FIRST inside ch1
    # (text before digits under the natural key), so if a skipped member left a
    # hole every ordinal after it would shift.
    "ch1/broken.png": b"not an image at all",
}

# The zip's own timestamp and external attributes are wall-clock and umask
# derived unless pinned. Without this the archive differs on every
# regeneration and check_fixtures_deterministic goes red on a fixture that
# changed in no way that matters.
CBZ_DATE = (1980, 1, 1, 0, 0, 0)


def _cbz_page(i: int) -> bytes:
    """One page: two bubbles with Latin text, on a panel border. Deterministic."""
    img = Image.new("RGB", (CBZ_W, CBZ_H), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, CBZ_W - 20, CBZ_H - 20), outline="black", width=5)
    font = load_font(LATIN_FONTS, 22)
    boxes = [(70, 90, 400, 330), (200, 470, 550, 760)]
    for j, box in enumerate(boxes):
        draw.ellipse(box, fill="white", outline="black", width=4)
        draw.text((box[0] + 40, box[1] + 60), f"PAGE {i}\nBUBBLE {j}",
                  font=font, fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG", pnginfo=PngInfo(), optimize=False, compress_level=6)
    return buf.getvalue()


def gen_cbz():
    pages = {i: _cbz_page(i) for i in sorted({idx for _n, idx in CBZ_MEMBERS})}
    path = FIXTURES / "cbz" / "sample.cbz"
    path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in list(CBZ_JUNK.items()) + [
            (n, pages[i]) for n, i in reversed(CBZ_MEMBERS)
        ]:
            info = zipfile.ZipInfo(name, date_time=CBZ_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, payload)

    order = [n for n, _i in CBZ_MEMBERS]
    # What members() reports: every member selected by EXTENSION, before
    # anything is decoded. ch1/broken.png is named .png and is not one, so it
    # is a candidate and not a page -- the two lists differ by exactly that
    # file, which is what makes "a skipped member leaves no ordinal hole"
    # testable.
    candidates = sorted(order + ["ch1/broken.png"], key=_natural_key)
    identical = [o + 1 for o, (_n, i) in enumerate(CBZ_MEMBERS)
                 if [x for _y, x in CBZ_MEMBERS].count(i) > 1]
    return {
        "sample.cbz": {
            "page_size": [CBZ_W, CBZ_H],
            "natural_order": order,
            "candidate_members": candidates,
            "lexicographic_order": sorted(order),
            "identical_ordinals": identical,
            "skipped_members": sorted(CBZ_JUNK),
            "notes": "Ordinals 3 and 7 are byte-identical pages in different "
                     "chapter directories. Natural and lexicographic order "
                     "differ, so a reader that sorted the wrong way is visible.",
        }
    }


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    # sort_keys + fixed separators + trailing newline: byte-identical across runs.
    # newline="\n": write_text defaults to os.linesep (CRLF on Windows), which
    # would dirty every fixture on each regeneration vs the LF blobs in git.
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main():
    for sub in ("smoke", "bubbles", "cbz"):
        shutil.rmtree(FIXTURES / sub, ignore_errors=True)

    smoke = gen_smoke()
    smoke.update(gen_smoke_columns())
    bubbles = gen_bubbles()
    cbz = gen_cbz()

    write_json(FIXTURES / "smoke" / "expected.json", smoke)
    write_json(FIXTURES / "bubbles" / "expected.json", bubbles)
    write_json(FIXTURES / "cbz" / "expected.json", cbz)

    n = len(smoke) + len(bubbles) + len(cbz)
    print(f"generated {n} fixtures + 3 expected.json under {FIXTURES}")
    for name in sorted(smoke):
        print(f"  smoke/{name}")
    for name in sorted(bubbles):
        print(f"  bubbles/{name}  rung {bubbles[name]['forces_rung']}")
    for name in sorted(cbz):
        print(f"  cbz/{name}  {len(CBZ_MEMBERS)} pages, "
              f"identical ordinals {cbz[name]['identical_ordinals']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
