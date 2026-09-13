"""Phase 2c -- the erase gate: text off the page, and NO box where it was. OFFLINE.

check_inpaint.py holds the eraser to account inside opaque white bubbles, and a
flat white fill passes it there, because inside a white bubble a white box and
a correct erase are the same pixels. This gate is the four cases where they are
not -- fixtures/erase/page_01.png -- and where the pre-2c inpainter drew the big
white rectangles the user reported:

  sfx          outlined katakana laid straight across hatched art
  translucent  a bubble drawn 60% opaque over the same hatching
  white        the control: an opaque white bubble (the fast path must hold)
  dark         white text in a black bubble

page_01_text.png is the ground truth of where glyph ink was drawn, so nothing
here trusts a model's idea of where the text is. Per item:

  [exact]     every pixel outside the eraser's own mask is byte-identical to
              the source. A box is a violation of this by construction.
  [covered]   the mask holds >= COVER of the ground-truth glyph pixels.
  [art]       art near the glyphs (outside the glyphs grown by a margin) that
              was dark in the source is not WHITE after the erase. This is the
              white-box failure measured directly, and the one a flat white
              fill fails on (sfx, translucent, dark).
  [continues] where the glyphs were, the erased page matches the band of page
              just outside them: mean within MEAN_TOL, and at least STD_RATIO
              of its texture -- a flat fill over hatching has none.
  [path]      sfx and translucent went through LaMa; white and dark were
              flat-filled with zero LaMa pixels.
  [ink]       typesetting on the erased page picks white ink for the dark
              bubble and plain black for the white one.
  [room]      the room room.py finds on the erased page stays inside its
              bubble, and over open art (the SFX) it is declined or stays
              near the text.

And the flag: MT_INPAINTER=fill reproduces the pre-2c inpainter byte for byte;
an unknown value raises a named error.

[red] run with MT_INPAINTER=fill set: [art], [continues] and [path] go red on
the items a box ruins. That run is the evidence this gate can fail.
"""

from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from lib.result import Checks, run, skip  # noqa: E402
from sidecar import inpainter, models, pipeline, textmask, typeset  # noqa: E402
from sidecar.textmask import EraseError  # noqa: E402

DIR = os.path.join(ROOT, "fixtures", "erase")
PAGE = os.path.join(DIR, "page_01.png")

COVER = 0.97  # of ground-truth glyph pixels inside the erase mask
MARGIN_FRAC = 0.2  # glyphs grown by this many glyph sizes before "near art" begins
# Source gray below this is art ink. Not lower: under the 60% veil the hatching
# is ~165, and a threshold of 160 found no art beside the translucent text at
# all -- an [art] assert over an empty zone, which fails for the wrong reason.
ART_DARK = 200
WHITE = 248  # erased gray at or above this is white; a box is 255
WHITENED_MAX = 0.05  # of near-art pixels allowed to turn white
MIN_ZONE_PX = 200
BAND_IN, BAND_OUT = 0.25, 0.6  # of glyph size: the band [continues] compares against
MEAN_TOL = 20.0  # /255
STD_RATIO = 0.35
KINDS_LAMA = ("sfx", "translucent")


def _poly_mask(size, points) -> np.ndarray:
    m = Image.new("1", size, 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in points], fill=1)
    return np.asarray(m, dtype=bool)


def _dilate(mask: np.ndarray, px: int) -> np.ndarray:
    import cv2  # noqa: PLC0415

    if px <= 0:
        return mask.copy()
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * px + 1, 2 * px + 1))
    return cv2.dilate(mask.astype(np.uint8), k) > 0


def _in_box(region, box) -> bool:
    xs = [p[0] for p in region["polygon"]]
    ys = [p[1] for p in region["polygon"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _pre_2c_fill(img, regions):
    """The inpainter as it was before Phase 2c, copied here so the flag is
    compared against the old code and not against itself."""
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for r in regions:
        for part in r.get("parts") or [r["polygon"]]:
            draw.polygon([tuple(p) for p in part], fill="white")
    return out


def _flag(c, src, regions):
    saved = os.environ.get(inpainter.ENV_FLAG)
    try:
        os.environ[inpainter.ENV_FLAG] = "fill"
        got, _ = pipeline.inpaint(src, regions, 1)
        c.check(np.array_equal(np.asarray(got), np.asarray(_pre_2c_fill(src, regions))),
                f"[flag] {inpainter.ENV_FLAG}=fill reproduces the pre-2c inpainter byte for byte")
        os.environ[inpainter.ENV_FLAG] = "watercolour"
        try:
            pipeline.inpaint(src, regions, 1)
            c.check(False, f"[flag] an unknown {inpainter.ENV_FLAG} raises (it returned)")
        except EraseError as e:
            c.check(e.kind == "config" and "lama" in e.reason and "fill" in e.reason,
                    f"[flag] an unknown {inpainter.ENV_FLAG} raises a named config error "
                    f"listing the known values: {e.reason!r}")
    finally:
        if saved is None:
            os.environ.pop(inpainter.ENV_FLAG, None)
        else:
            os.environ[inpainter.ENV_FLAG] = saved


def main():
    if not os.path.exists(PAGE):
        return skip(f"no erase page at {PAGE} -- run tests/gen_fixtures.py")
    c = Checks("check_erase")
    with open(os.path.join(DIR, "expected.json"), encoding="utf-8") as fh:
        entry = json.load(fh)["page_01.png"]
    with Image.open(PAGE) as im:
        src = im.convert("RGB").copy()
    with Image.open(os.path.join(DIR, entry["truth"])) as im:
        truth = np.asarray(im.convert("L")) > 127
    provider, reason = models.select_provider()
    print(f"  provider: {provider} {reason}".rstrip(), flush=True)

    regions = pipeline.detect(src, 1)
    erased, methods = inpainter.erase(src, regions)
    rgb, out = np.asarray(src), np.asarray(erased)
    src_gray = np.asarray(src.convert("L")).astype(np.float64)
    out_gray = np.asarray(erased.convert("L")).astype(np.float64)

    import cv2  # noqa: PLC0415

    ink = textmask.mask(rgb)
    mask = np.zeros(truth.shape, bool)
    for x0, y0, m in (inpainter.region_mask(cv2, rgb, ink, r) for r in regions):
        mask[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] |= m > 0
    changed = (rgb != out).any(axis=2)
    c.check(not (changed & ~mask).any(),
            f"[exact] {int((changed & ~mask).sum())} pixels changed outside the erase mask == 0")

    kinds = {}  # region index -> fixture item kind
    for item in entry["items"]:
        kind, box, glyph = item["kind"], item["box"], item["glyph_px"]
        hits = [i for i, r in enumerate(regions) if _in_box(r, box)]
        if not c.check(len(hits) >= 1, f"[detect {kind}] the detector found the text ({len(hits)} regions)"):
            continue
        in_box = np.zeros(truth.shape, bool)
        in_box[box[1]:box[3], box[0]:box[2]] = True
        glyphs = truth & in_box
        quads = np.zeros(truth.shape, bool)
        for i in hits:
            for part in regions[i].get("parts") or [regions[i]["polygon"]]:
                quads |= _poly_mask(src.size, part)

        cover = (glyphs & mask).sum() / max(1, glyphs.sum())
        c.check(cover >= COVER, f"[covered {kind}] the mask holds {cover:.3f} of the glyph pixels >= {COVER}")

        near = _dilate(quads, 12) & ~_dilate(glyphs, round(MARGIN_FRAC * glyph)) & (src_gray < ART_DARK)
        if kind == "white":
            print(f"  [art white] no dark art near the glyphs ({int(near.sum())} px): the control "
                  f"has nothing a box could whiten, so [art] is not asserted on it", flush=True)
        else:
            whitened = float((out_gray[near] >= WHITE).mean()) if near.any() else 1.0
            c.check(near.sum() >= MIN_ZONE_PX and whitened <= WHITENED_MAX,
                    f"[art {kind}] {whitened:.3f} of {int(near.sum())} dark art pixels beside the "
                    f"glyphs turned white <= {WHITENED_MAX} -- a white box turns them all")

        rebuilt = _dilate(glyphs, 2) & mask
        # The bubbles are ellipses drawn in their box: the band stays inside,
        # clear of the border, or the dark bubble is compared with white page.
        within = in_box
        if kind != "sfx":
            ellipse = Image.new("1", src.size, 0)
            ImageDraw.Draw(ellipse).ellipse(box, fill=1)
            within = ~_dilate(~np.asarray(ellipse, dtype=bool), 8)
        band = (_dilate(glyphs, round(BAND_OUT * glyph)) & ~_dilate(glyphs, round(BAND_IN * glyph))
                & within & ~mask & ~truth)
        mean_diff = abs(out_gray[rebuilt].mean() - out_gray[band].mean())
        s_in, s_out = out_gray[rebuilt].std(), out_gray[band].std()
        textured = s_out < 2.0 or s_in >= STD_RATIO * s_out
        c.check(band.sum() >= MIN_ZONE_PX and mean_diff <= MEAN_TOL and textured,
                f"[continues {kind}] erased glyphs vs the page around them: mean diff "
                f"{mean_diff:.1f} <= {MEAN_TOL}, std {s_in:.1f} vs {s_out:.1f} (ratio >= {STD_RATIO} "
                f"unless the page is flat)")

        if kind != "sfx":
            # The bubble's own outline survives the erase, wherever the
            # detector's quad reached over it.
            ellipse = Image.new("1", src.size, 0)
            ImageDraw.Draw(ellipse).ellipse(box, fill=1)
            e = np.asarray(ellipse, dtype=bool)
            # The rim: dark pixels within 6px inside the ellipse's edge, clear of the glyphs.
            outline = e & _dilate(~e, 6) & (src_gray < 128) & ~_dilate(truth, 2)
            cut = int((outline & changed).sum())
            c.check(outline.any() and cut == 0,
                    f"[outline {kind}] {cut} of {int(outline.sum())} outline pixels changed == 0 "
                    f"({int((outline & quads).sum())} of them inside the detector's quads)")

        got = {methods[i] for i in hits}
        want = "lama" if kind in KINDS_LAMA else "fill"
        if kind == "tight":
            want = None  # its surround holds the outline; either path is correct if [outline] holds
        c.check(want is None or got == {want},
                f"[path {kind}] erased by {sorted(got)}, expected {want or 'either'!r}")
        kinds.update((i, kind) for i in hits)

    # [ink]: typeset a sentence into every region on the erased page.
    for r in regions:
        r["translation"] = "WAIT UP"
    drawn, fits = typeset.typeset_page(regions, erased)
    by_id = {f.id: f for f in fits}
    for i, kind in sorted(kinds.items()):
        fit = by_id[regions[i]["id"]]
        # room.py floods the ERASED page from the erased block. On a page the
        # eraser now rebuilds rather than whitens, a room must still stop at
        # the bubble's border -- or, over open art, not be found at all.
        box = next(item["box"] for item in entry["items"] if item["kind"] == kind)
        if kind == "sfx":
            hull = _poly_mask(src.size, regions[i]["polygon"]).sum()
            area = _poly_mask(src.size, fit.room).sum() if fit.room else 0
            c.check(area <= 3 * hull, f"[room sfx] over open art the room is declined or stays near "
                                      f"the text ({area} px vs hull {hull})")
        else:
            # Every bubble gets its interior, whatever its colour: the first
            # 2c eraser left room.py no seed in the translucent and black
            # bubbles, and their English was set in the bare column.
            ellipse = Image.new("1", src.size, 0)
            ImageDraw.Draw(ellipse).ellipse(box, fill=1)
            room = _poly_mask(src.size, fit.room) if fit.room else np.zeros(truth.shape, bool)
            leak = int((room & ~_dilate(np.asarray(ellipse, dtype=bool), 2)).sum())
            share = room.sum() / max(1, np.asarray(ellipse, dtype=bool).sum())
            c.check(fit.room is not None and leak == 0 and share >= 0.25,
                    f"[room {kind}] the room found on the erased page is the bubble's interior: "
                    f"{share:.2f} of the bubble, {leak} px outside it")
        if kind == "dark":
            poly = _poly_mask(src.size, fit.room or regions[i]["polygon"])
            white_px = int((np.asarray(drawn.convert("L"))[poly] > 200).sum())
            c.check(fit.ink == typeset.INK_DARK and white_px > 0,
                    f"[ink dark] the black bubble is inked {fit.ink!r} and {white_px} white text pixels "
                    f"were drawn in it")
        elif kind in ("white", "tight"):
            c.check(fit.ink == typeset.INK_PLAIN, f"[ink {kind}] the white bubble is inked {fit.ink!r}")
        else:
            c.check(fit.ink != typeset.INK_PLAIN,
                    f"[ink {kind}] text over art is inked {fit.ink!r}, not plain black on nothing")

    _outline_through_quad(c)
    _flag(c, src, regions)
    return c.finish()


def _outline_through_quad(c):
    """The review's counterexample, pinned: a flat quad erased whole with a
    bubble outline running through it. The text model is stood in for by the
    glyph mask itself, so the case is exact and needs no weights: the quad and
    its surround read flat (the outline is a few percent of them), the whole
    quad is the mask, and the flat fill must leave the outline as drawn while
    taking the glyphs."""
    import cv2  # noqa: PLC0415

    page = Image.new("RGB", (300, 400), "white")
    d = ImageDraw.Draw(page)
    d.line((175, 0, 175, 399), fill="black", width=3)
    glyphs = [(120, 100, 150, 140), (120, 180, 150, 220), (120, 260, 150, 300)]
    for g in glyphs:
        d.rectangle(g, fill="black")
    gray = np.asarray(page.convert("L"))
    ink = np.zeros(gray.shape, bool)
    for x0, y0, x1, y1 in glyphs:
        ink[y0:y1 + 1, x0:x1 + 1] = True
    region = {"id": 1, "polygon": [[105, 80], [185, 80], [185, 320], [105, 320]], "glyph_px": 30}
    region["parts"] = [region["polygon"]]
    line = (gray < 128) & ~ink
    saved = textmask.mask
    textmask.mask = lambda rgb, threshold=textmask.THRESHOLD: ink
    try:
        out, methods = inpainter.erase(page, [region], inpainter.LAMA)
    finally:
        textmask.mask = saved
    o = np.asarray(out.convert("L"))
    _, _, m = inpainter.region_mask(cv2, np.asarray(page), ink, region)
    c.check(methods == ["fill"] and m.sum() >= 0.95 * 81 * 241,
            f"[outline quad] the flat quad took the fill path as a whole quad ({methods}, "
            f"{int(m.sum())} mask px)")
    c.check(int((o[line] != gray[line]).sum()) == 0 and int((o[ink] < 128).sum()) == 0,
            f"[outline quad] {int((o[line] != gray[line]).sum())} of {int(line.sum())} outline pixels "
            f"through the quad changed == 0, and {int((o[ink] < 128).sum())} glyph pixels left dark == 0")


run(main)
