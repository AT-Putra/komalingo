"""Erase the source text and continue the page underneath it. Phase 2c.

WHAT WAS WRONG. Until this module, inpaint filled every detected quad with flat
white. That is right for exactly one case -- dialogue inside an opaque white
bubble -- and a box-over for every other: an SFX laid across a character, a
caption on screentone, a bubble the artist drew half-transparent over the
panel, white text in a black bubble. The user saw it as big white rectangles
on the art, worst on SFX.

WHAT THIS DOES, per page:

  1. The ERASE MASK is the glyphs, not the quads. textmask.py's per-pixel text
     probability, cut to each kept part (grown a little, so an SFX outline
     that pokes out of its quad still goes), then grown by a few pixels to
     take the anti-aliased edge and the letter's own outline. Both growths
     scale with THAT PART's glyph size: a region's median glyph is pulled down
     by its furigana, and a 110px SFX grown by a furigana's margin keeps a
     white rim of outline that the inpainter then spreads into a halo. A part
     the text model barely covers -- it missed the text -- is erased whole
     instead: a detection the pipeline is about to typeset over must not keep
     its source glyphs. Dismissed regions are not in `regions` and are never
     erased.

  2. FLAT FILL where the page around a mask component is flat: a 2-6px ring
     outside it that is mostly one colour (FLAT_SHARE within FLAT_TOL of its
     median; the rest may be the bubble's border ink). The component takes
     the ring's median colour -- except page structure that runs out of it:
     a bubble outline a quad overlaps is dark against the fill and continues
     past the mask, so it is left as drawn, while a glyph ends inside it. That
     is the white-bubble case, and it is not only the fast path: LaMa over
     pure white leaves faint off-white ghosts where the glyphs were (measured
     in the Phase 2c spike), so a flat surround MUST NOT go to the model. A
     flat black bubble is flat too, and fills black.

  3. LaMa for everything else, at the model's fixed 512px, one component at a
     time: a crop of real page LAMA_SIZE square centred on it (larger, and
     downscaled, only for a component that does not fit with CONTEXT_MIN_PX
     around it). Crops are NOT merged -- the first version merged overlapping
     ones, and on a busy page the union outgrew 512, was downscaled, and came
     back visibly softer than the art. Every LaMa pixel inside a crop is
     masked on input, so a neighbour's glyphs are never read as context to
     copy, and a component whose box already lies inside an earlier crop
     rides along with it. Only the crop's own components are written back,
     feathered over FEATHER_PX inside them.

THE INVARIANT the erase gate holds this to: every pixel outside the erase
mask is byte-identical to the input. A white box is precisely a violation of
it, which makes it an assert that cannot pass for the failure it exists for.

Ceiling: a component wider or taller than LAMA_SIZE - 2 * CONTEXT_MIN_PX is
inpainted downscaled, so a very large SFX comes back softer than the art
around it. Upgrade path: tile the crop instead of scaling it.

Ceiling: glyph pixels the text model missed that are drawn ACROSS a bubble
outline join the outline's structure and are left with it, where a flat fill
applies. The pre-2c white fill left pieces there too. Upgrade path: let only
thin, line-like structure far from the text model's ink escape.

Ceiling: on the CPU provider the text model takes ~2.5s a page and LaMa ~1.5s
a crop, so an SFX-heavy page costs tens of seconds where the white fill cost
milliseconds. Upgrade path: a Settings switch for MT_INPAINTER.

`MT_INPAINTER=fill` keeps the pre-2c behaviour, byte for byte, for comparison
and for a machine that cannot hold the models. Unset means lama. An unknown
value is an error, never a quiet default -- the detect.py rule.
"""

from __future__ import annotations

import os

import numpy as np
from PIL import Image, ImageDraw

from . import textmask
from .textmask import EraseError

ENV_FLAG = "MT_INPAINTER"
LAMA = "lama"
FILL = "fill"
KNOWN = (LAMA, FILL)

WEIGHTS = "lama-manga"
LAMA_SIZE = 512  # the exported graph's fixed input side
# One crop per forward pass. The graph takes a batch, but onnxruntime's CUDA
# arena keeps what a batch grew it to: 8 crops held 5.8 GB of VRAM against 1.7
# GB for one, for 8% less time, in a process that also holds manga-ocr.

ALLOW_FRAC = 0.15  # a part grows by this many glyphs before the text mask is cut to it
GROW_FRAC = 0.12  # the cut mask grows by this many glyphs: anti-aliasing and outlines
GROW_MIN_PX = 3
GLYPH_CAP = 2.0  # a part's glyph is its short side, capped at this many region glyphs
MIN_COVER = 0.05  # a part the text mask covers less than this is erased whole
# A surround is flat when a SHARE of its pixels sit within FLAT_TOL of its
# median colour. A share, not a standard deviation: a column of text set close
# to its bubble's border has border ink in its ring, and the first version (std
# under 2/255) sent that bubble to LaMa, which painted the screentone from
# outside the bubble into it. The same test sent 8 of 9 bubbles on a JPEG scan
# to the model, because compression noise alone is more than 2/255.
#
# A component is judged by the ring just outside its (already grown) mask, and
# close: a small black bubble full of text has white page 10px out, and at
# 6-10px its ring read 0.70 flat, went to LaMa, and came back with the hatching
# from outside the bubble painted into it. Measured on the fixtures and two
# real scans at 2-6px: bubbles 0.82-1.00, text over art and hatching 0.55-0.65.
RING_INNER, RING_OUTER = 2, 6  # px outside a component's mask
FLAT_SHARE = 0.8
FLAT_TOL = 8  # /255, per channel
# A whole QUAD is erased flat only on stricter evidence -- its own non-glyph
# pixels and 10px around them, 90% one colour -- because a quad filled flat over
# art is a box, which is the one thing this module must not draw.
QUAD_RING_PX = 10
QUAD_FLAT_SHARE = 0.9
MIN_RING_PX = 32  # fewer surround pixels than this prove nothing flat
CONTEXT_MIN_PX = 48
FEATHER_PX = 2

_LAMA = None


def resolve(name: str | None = None) -> str:
    """The inpainter to use, from `name` or MT_INPAINTER. Unknown values raise."""
    value = (name if name is not None else os.environ.get(ENV_FLAG, "")).strip().lower()
    if not value:
        return LAMA
    if value in KNOWN:
        return value
    raise EraseError(f"unknown {ENV_FLAG}={value!r}; known inpainters are {', '.join(KNOWN)}",
                     "config")


def fill_white(img: Image.Image, regions: list[dict]) -> Image.Image:
    """The pre-2c inpainter: every part polygon flat white. MT_INPAINTER=fill."""
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for r in regions:
        for part in r.get("parts") or [r["polygon"]]:
            draw.polygon([tuple(p) for p in part], fill="white")
    return out


def erase(img: Image.Image, regions: list[dict], inpainter: str | None = None
          ) -> tuple[Image.Image, list[str]]:
    """The page with the regions' source text erased, and how each was erased.

    The second value is one entry per region, in order: "lama" if any of its
    mask went through the model, else "fill" if it was flat-filled, else
    "none" (no mask at all), or "white" under MT_INPAINTER=fill.
    """
    if resolve(inpainter) == FILL:
        return fill_white(img, regions), ["white"] * len(regions)
    rgb = np.asarray(img.convert("RGB"))
    if not regions:
        return Image.fromarray(rgb.copy()), []

    import cv2  # noqa: PLC0415 -- detect.py's dependency, loaded on first use

    ink = textmask.mask(rgb)
    windows = [region_mask(cv2, rgb, ink, r) for r in regions]
    erase_mask = np.zeros(ink.shape, np.uint8)
    for x0, y0, m in windows:
        erase_mask[y0:y0 + m.shape[0], x0:x0 + m.shape[1]] |= m

    out = rgb.copy()
    count, labels, stats, _ = cv2.connectedComponentsWithStats(erase_mask, connectivity=8)
    method = np.zeros(count, np.uint8)  # 0 none, 1 fill, 2 lama
    for i in range(1, count):
        colour = _flat_surround(cv2, rgb, labels, erase_mask, i, stats[i, :4])
        if colour is None:
            method[i] = 2
        else:
            _fill(cv2, rgb, ink, out, labels, i, stats[i, :4], colour)
            method[i] = 1

    lama = [i for i in range(1, count) if method[i] == 2]
    if lama:
        _inpaint(cv2, out, labels, stats, method, lama)

    methods = []
    for x0, y0, m in windows:
        seen = method[labels[y0:y0 + m.shape[0], x0:x0 + m.shape[1]][m > 0]]
        methods.append("lama" if (seen == 2).any() else "fill" if seen.size else "none")
    return Image.fromarray(out), methods


def region_mask(cv2, rgb: np.ndarray, ink: np.ndarray, r: dict) -> tuple[int, int, np.ndarray]:
    """(x0, y0, mask): region `r`'s pixels to erase, uint8 {0,1}, in a window
    whose top-left is (x0, y0) -- not page-sized, because a 300 DPI PDF page
    with sixty regions held 635 MB of page-sized masks.

    Per part: the whole quad when the quad and the page just outside it are
    flat, else the text model's glyph pixels inside it. A quad in a flat
    bubble holds glyphs and bubble, and erasing all of it with the bubble's
    colour is what erasing the glyphs would draw -- without trusting the text
    model to have caught every stroke. It had not: on the smoke page it left
    1.5% of a column's ink behind, and those strokes were the only thing still
    visible.
    """
    h, w = ink.shape
    pieces = []
    for part in r.get("parts") or [r["polygon"]]:
        pts = np.array(part, np.int32)
        glyph = max(1, int(np.ptp(pts, axis=0).min()))
        if r.get("glyph_px"):
            glyph = min(glyph, int(GLYPH_CAP * r["glyph_px"]))
        reach = round(ALLOW_FRAC * glyph)
        grow = max(GROW_MIN_PX, round(GROW_FRAC * glyph))
        margin = max(reach + grow, QUAD_RING_PX) + 1
        x0, y0 = (int(v) for v in np.maximum(pts.min(axis=0) - margin, 0))
        x1, y1 = (int(v) for v in np.minimum(pts.max(axis=0) + 1 + margin, (w, h)))
        if x1 <= x0 or y1 <= y0:
            continue
        one = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillPoly(one, [pts - (x0, y0)], 1)
        if not one.any():
            continue
        local = ink[y0:y1, x0:x1]
        if local[one > 0].mean() < MIN_COVER:
            pieces.append((x0, y0, one))  # the text model missed this part: erase all of it
            continue
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1,) * 2)
        glyphs = cv2.dilate(local.astype(np.uint8), kernel) > 0
        # Flat means the quad AND the page just outside it, glyphs aside: a
        # neighbouring column's text must not make a bubble look busy.
        around = cv2.dilate(one, np.ones((2 * QUAD_RING_PX + 1,) * 2, np.uint8))
        if _flat(rgb[y0:y1, x0:x1][(around > 0) & ~glyphs], QUAD_FLAT_SHARE) is not None:
            pieces.append((x0, y0, one))
            continue
        allowed = cv2.dilate(one, np.ones((2 * reach + 1,) * 2, np.uint8))
        pieces.append((x0, y0, cv2.dilate((local & (allowed > 0)).astype(np.uint8), kernel)))
    if not pieces:
        return 0, 0, np.zeros((0, 0), np.uint8)
    wx0 = min(x for x, _, _ in pieces)
    wy0 = min(y for _, y, _ in pieces)
    wx1 = max(x + p.shape[1] for x, _, p in pieces)
    wy1 = max(y + p.shape[0] for _, y, p in pieces)
    m = np.zeros((wy1 - wy0, wx1 - wx0), np.uint8)
    for x, y, p in pieces:
        m[y - wy0:y - wy0 + p.shape[0], x - wx0:x - wx0 + p.shape[1]] |= p
    return wx0, wy0, m


def _flat_surround(cv2, rgb, labels, erase_mask, i, box):
    """The ring's median colour if the page around component `i` is flat, else None."""
    x, y, bw, bh = (int(v) for v in box)
    h, w = labels.shape
    x0, y0 = max(0, x - RING_OUTER), max(0, y - RING_OUTER)
    x1, y1 = min(w, x + bw + RING_OUTER), min(h, y + bh + RING_OUTER)
    comp = (labels[y0:y1, x0:x1] == i).astype(np.uint8)
    outer = cv2.dilate(comp, np.ones((2 * RING_OUTER + 1,) * 2, np.uint8))
    inner = cv2.dilate(comp, np.ones((2 * RING_INNER + 1,) * 2, np.uint8))
    ring = (outer > 0) & (inner == 0) & (erase_mask[y0:y1, x0:x1] == 0)
    return _flat(rgb[y0:y1, x0:x1][ring])


def _flat(px: np.ndarray, share: float = FLAT_SHARE):
    """The median colour of (N, 3) pixels if `share` of them match it, else None."""
    if len(px) < MIN_RING_PX:
        return None
    px = px.astype(np.int16)
    median = np.median(px, axis=0).round().astype(np.int16)
    if (np.abs(px - median).max(axis=1) <= FLAT_TOL).mean() < share:
        return None
    return median.astype(np.uint8)


def _fill(cv2, rgb, ink, out, labels, i, box, colour) -> None:
    """Fill component `i` with `colour`, in place -- all of it but page
    structure that runs out of it.

    A quad erased whole can overlap its bubble's outline, and the ring around
    the component meets that outline only at the quad's ends, so it still
    reads flat. Filling the component would cut the outline where the quad
    crossed it (a 3px border through a 66x300 quad lost 903 of 903 pixels in
    review). What differs from the fill colour and continues past the
    component is the page's, not the text's: a glyph sits inside its grown
    mask. The text model's own ink is erased regardless, so a stroke that
    touches the quad edge is not saved by this.
    """
    x, y, bw, bh = (int(v) for v in box)
    h, w = labels.shape
    reach = RING_OUTER + 1
    x0, y0 = max(0, x - reach), max(0, y - reach)
    x1, y1 = min(w, x + bw + reach), min(h, y + bh + reach)
    comp = (labels[y0:y1, x0:x1] == i).astype(np.uint8)
    foreign = (np.abs(rgb[y0:y1, x0:x1].astype(np.int16) - colour.astype(np.int16)).max(axis=2)
               > FLAT_TOL) & ~ink[y0:y1, x0:x1]
    sel = comp > 0
    if foreign.any():
        # Escaping means reaching more than RING_OUTER px past the component,
        # not merely touching its edge: a detector quad can end tight on a
        # column, and the anti-aliased edge of its last glyph poking a pixel
        # or two out of it is still text (the smoke page's bubble kept its
        # strokes, and check_inpaint's ring went red, when touching counted).
        near = cv2.dilate(comp, np.ones((2 * RING_OUTER + 1,) * 2, np.uint8)) > 0
        _, structure = cv2.connectedComponents(foreign.astype(np.uint8), connectivity=8)
        escapes = np.unique(structure[foreign & ~near])
        sel &= ~np.isin(structure, escapes[escapes > 0])
    out[y0:y1, x0:x1][sel] = colour


def _lama():
    """The loaded model, cached (see textmask._model for the locking rule)."""
    global _LAMA
    if _LAMA is None:
        _LAMA = textmask.session(WEIGHTS)
    return _LAMA


def _crops(labels, stats, lama):
    """[(box, [component ids])]: one crop per component, largest first; a
    component whose box already lies inside a crop joins it.

    A crop is LAMA_SIZE square of real page centred on its component, slid
    inward at the page edge -- so a tall narrow column is not mirrored out to
    512 while the page beside it goes unread -- and larger only when the
    component does not fit with CONTEXT_MIN_PX around it.
    """
    h, w = labels.shape
    crops = []
    for i in sorted(lama, key=lambda c: -int(stats[c, 4])):
        x, y, bw, bh = (int(v) for v in stats[i, :4])
        # Only a crop at the model's own size takes riders: one grown for a
        # large component is downscaled, and a small one sharing it would be too.
        home = next((c for c in crops if c[2] and c[0][0] <= x and c[0][1] <= y
                     and x + bw <= c[0][2] and y + bh <= c[0][3]), None)
        if home is not None:
            home[1].append(i)
            continue
        side = max(LAMA_SIZE, max(bw, bh) + 2 * CONTEXT_MIN_PX)
        x0 = min(max(0, x + bw // 2 - side // 2), max(0, w - side))
        y0 = min(max(0, y + bh // 2 - side // 2), max(0, h - side))
        crops.append(((x0, y0, min(w, x0 + side), min(h, y0 + side)), [i], side == LAMA_SIZE))
    return [(box, ids) for box, ids, _ in crops]


def _inpaint(cv2, out: np.ndarray, labels, stats, method, lama) -> None:
    """Run LaMa over one crop per component and write back its pixels, in place.

    Crops run and are written one at a time. Every LaMa pixel is masked on
    every crop's input, so what an earlier crop wrote is never read by a later
    one: the order changes nothing.
    """
    lama_px = (method[labels] == 2).astype(np.uint8)
    session = _lama()
    for (x0, y0, x1, y1), ids in _crops(labels, stats, lama):
        crop, mask = out[y0:y1, x0:x1], lama_px[y0:y1, x0:x1]
        ch, cw = mask.shape
        side = max(LAMA_SIZE, ch, cw)
        # Padding (a page smaller than the crop) is a REFLECTION, of the image
        # and of the mask alike: the model reads padding as context, so black
        # padding is a black border it continues, and a reflected image under
        # an unreflected mask shows it mirror copies of the very glyphs it is
        # erasing -- which it drew back in, as a grey ghost of the text, in a
        # small black bubble.
        img = cv2.copyMakeBorder(crop, 0, side - ch, 0, side - cw, cv2.BORDER_REFLECT_101)
        m = cv2.copyMakeBorder(mask, 0, side - ch, 0, side - cw, cv2.BORDER_REFLECT_101)
        if side > LAMA_SIZE:
            img = cv2.resize(img, (LAMA_SIZE, LAMA_SIZE), interpolation=cv2.INTER_AREA)
            # AREA then > 0: a thin stroke downscaled must stay masked.
            m = (cv2.resize(m.astype(np.float32), (LAMA_SIZE, LAMA_SIZE),
                            interpolation=cv2.INTER_AREA) > 0).astype(np.uint8)
        mf = m[None, None].astype(np.float32)
        x = img.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
        try:
            filled = session.run(["output"], {"image": x * (1.0 - mf), "mask": mf})[0][0]
        except Exception as e:  # noqa: BLE001 -- onnxruntime raises its own untyped errors
            raise EraseError(f"LaMa forward pass failed: {e}", "error") from None
        filled = np.clip(filled.transpose(1, 2, 0) * 255.0 + 0.5, 0, 255).astype(np.uint8)
        if side > LAMA_SIZE:
            filled = cv2.resize(filled, (side, side), interpolation=cv2.INTER_CUBIC)
        filled = filled[:ch, :cw]
        own = np.isin(labels[y0:y1, x0:x1], ids).astype(np.uint8)
        # Feathered INSIDE the components only, so nothing outside them changes.
        dist = cv2.distanceTransform(own, cv2.DIST_L2, 3)
        alpha = np.clip(dist / FEATHER_PX, 0.0, 1.0)[..., None]
        blended = (alpha * filled + (1.0 - alpha) * crop + 0.5).astype(np.uint8)
        sel = own > 0
        crop[sel] = blended[sel]
