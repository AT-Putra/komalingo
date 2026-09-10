"""Polygon-constrained typesetting: the five-rung fit ladder. Owns AC-1's fit half.

The contradiction this module exists to resolve, stated once: **a hard font
floor, zero overflow and zero clipping cannot all hold** when the translated
string does not fit inside the polygon at the floor size. One of the three must
yield. Choosing which, per region, in a defined order, is the ladder:

  1. Shrink toward the floor.
  2. At the floor, tighten leading to 0.92x and tracking to -0.02em. No further.
  3. Erode the inward inset to zero -- typeset into the full detected region.
  4. Overflow HORIZONTALLY only, <= 8% of polygon width in total (4% a side),
     never past the page raster edge. Flags `fit_compromised`. Skipped entirely
     -- not attempted and failed -- when the polygon already sits within 8% of
     its own width of the raster edge, because the bleed has nowhere to go.
  5. Terminal, ALWAYS applies: one length-capped re-translation, then
     truncation. Has no failure exit.

So the invariant is: font size >= floor AND clipping == 0 are absolute;
overflow is zero except on `fit_compromised` regions, where it is bounded at 8%
width and 0% height; text loss is zero except on `fit_failed` regions, which are
reported, never silent.

Five things here are load-bearing.

**Width is the polygon's CHORD, never the bounding box,** and the chord is
clipped to the page raster. Every line consults the NARROWEST chord its own box
spans, intersected with [0, page_w]. Clipping == 0 is therefore a property of
the layout by construction, not a number measured afterwards and hoped for.

**The line count EMERGES from the wrap; it is never chosen in advance.** An
earlier version tried each line count n and accepted only when all n lines were
non-empty. That made "does it fit" non-monotone in the text: adding one
character could push a word across a boundary so that no n worked, and the
measured predicate had six holes across one 169-character string. Both binary
searches below, and rung 5's character cap, silently depended on a monotonicity
that did not exist -- `_capacity` returned 116 for a string and 149 for a
longer string with that string as its prefix, on the same polygon. Now the wrap
is greedy from the top and a slot too narrow for the next word is simply left
empty. Greedy wrapping is prefix-stable -- the words of a prefix land in the
same slots whether or not more words follow -- so fit is monotone in length.
Vertical centring is a separate PLACEMENT step that only ever chooses among
layouts already known to fit, so it cannot reintroduce the holes.

**Overflow and clipping are measured from drawn ink, not from the layout
model.** Each region is rasterised into a scratch frame and compared against
its polygon mask and the page rectangle. The model-derived measure this
replaced reported 4px of overflow on a page with zero ink outside the polygon;
a self-report and the raster it describes are two different claims.

**The entry point is `typeset_page`, not a loop over one region.** Rung 5
batches its re-translation across every rung-5 region on the page, so a page of
hard bubbles costs one extra request rather than one per bubble. Phase one
ladders every region through rungs 1-4 and collects the candidates; phase two
issues the single request and re-typesets only those.

**`fit_compromised` and `fit_failed` are derived, never loaded.** Both are
recomputed on every pass and are output-only. `fit_compromised` means exactly
one thing -- the layout that was drawn needed rung 4's bleed -- and
`fit_failed` means exactly one other: text was lost. A region that was
re-translated and then fit cleanly is neither; it is reported as `retranslated`.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .region import as_points

# -- the constants the gate reads back ------------------------------------

# "12px at 300 DPI-equivalent, scaled by page height." Scaling only ever RAISES
# the floor: a page downscaled to thumbnail size cannot argue its way to 4px
# text, which would satisfy the floor arithmetically and defeat its purpose.
FLOOR_BASE_PX = 12
FLOOR_REF_PAGE_H = 2480  # A5 at 300 DPI -- the tankoubon page this baseline means

# Rung 3 erodes this to zero, recovering ~6% of the polygon's area on a typical
# bubble aspect. Expressed against min(w, h) so a wide bubble is not inset by a
# fraction of its long axis.
INSET_FRAC = 0.02

LEADING = 1.20
TIGHT_LEADING_FACTOR = 0.92  # rung 2, bounded -- no further
TIGHT_TRACKING_EM = -0.02  # rung 2, bounded -- no further

# Rung 4: 8% of polygon width IN TOTAL, split evenly, so 4% on each side. The
# gate asserts the per-side figure, which is the one the raster can violate.
BLEED_FRAC = 0.08
ELLIPSIS = "\u2026"

# The largest face rung 1 will try. Paired with a floor that scales with page
# height: on a very tall page the floor rises toward this ceiling, so the
# ceiling scales too rather than pinching rung 1's range to nothing.
MAX_FONT_PX = 96

FONT_CANDIDATES = ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"]

# Antialiased glyph edges are grey. A pixel counts as ink below this value --
# the same threshold check_inpaint uses for "dark", so the two gates agree on
# what a glyph pixel is.
INK_THRESHOLD = 128

# fit_failed reasons. Named, because "fit_failed" alone does not tell the user
# whether to shorten their text or complain that the provider sent nothing.
REASON_EMPTY = "empty translation"
REASON_TRUNCATED = "truncated at a word boundary"
REASON_NO_WORD = "no whole word fits"
REASON_TOKEN = "single token broken with an ellipsis"
# Informational, never fit_failed: the OCR blank gate emptied the source.
REASON_NO_SOURCE = "no source text (blank region)"


class TypesetError(RuntimeError):
    """A typeset pass that cannot proceed. Named, like every sidecar failure path."""


@dataclass
class Fit:
    """One region's typeset result. Every field is output-only.

    `rung` is the RUNG COUNTER check_typeset.py asserts against. It is recorded
    rather than inferred from the pixels, because two rungs can produce the
    same raster on an easy string and a gate that guesses from pixels cannot
    tell "rung 4 was not needed" from "rung 4 is not implemented". 0 means the
    region was never laddered, because there was nothing to typeset.
    """

    id: int = 0
    text: str = ""  # what was actually rendered
    font_px: int = 0
    rung: int = 1
    rung4_skipped: bool = False
    fit_compromised: bool = False
    fit_failed: bool = False
    reason: str = ""  # why fit_failed, or why nothing was drawn: a REASON_* constant
    retranslated: bool = False  # rung 5's reply was RENDERED (possibly truncated)
    reply_rejected: bool = False  # a reply arrived but exceeded the cap it was given
    capacity: int = 0  # rung 5's COMPUTED character cap, 0 when rung 5 was not reached
    bleed_px: float = 0.0  # per-side bleed the drawn layout was granted
    tracking: float = 0.0  # em fraction the LAYOUT used; the draw must match it
    # Measured from the RASTER, not the layout model:
    overflow_px_x: int = 0
    overflow_px_y: int = 0
    clipped_glyphs: int = 0
    offpage_ink_px: int = 0
    lines: list = field(default_factory=list)  # [(x, y, text)] in page coordinates


# -- geometry --------------------------------------------------------------


def floor_px(page_h: int) -> int:
    """The hard font floor for a page of this height. Never below FLOOR_BASE_PX."""
    return max(FLOOR_BASE_PX, round(FLOOR_BASE_PX * page_h / FLOOR_REF_PAGE_H))


def max_font_px(page_h: int) -> int:
    """Rung 1's ceiling. Scales with the floor so the search range never collapses."""
    return max(MAX_FONT_PX, 4 * floor_px(page_h))


def _bbox(points) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _chord(points, y: float) -> tuple[float, float] | None:
    """The WIDEST contiguous span of the polygon at scanline y, or None.

    Contiguous, not outermost. A row that crosses the polygon twice -- the arms
    of a U, the notch of an H -- has two inside runs with a gap between them,
    and the outermost pair of crossings hands the wrap a line straight across
    the gap. This function did exactly that until a review laid text across a
    U-shaped polygon and counted 1443 ink pixels outside it; its docstring then
    claimed the raster measure would catch it, and the raster measure -- which
    compared ink against the same outer extent -- did not. Crossings are sorted
    and paired even-odd, so each pair is one inside run; ties go leftmost.
    """
    xs = []
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if y1 == y2:
            continue
        if min(y1, y2) <= y < max(y1, y2):
            xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
    if len(xs) < 2:
        return None
    xs.sort()
    spans = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
    return max(spans, key=lambda span: span[1] - span[0])


def _inset_points(points, d: float) -> list[tuple[float, float]]:
    """Shrink the polygon toward its centroid by d pixels of its smaller axis.

    A true offset curve is not needed: the inset exists to keep glyphs off the
    bubble's ink border, and a centroid scale keeps the shape's proportions.
    """
    if d <= 0:
        return list(points)
    x0, y0, x1, y1 = _bbox(points)
    w, h = x1 - x0, y1 - y0
    if w <= 2 * d or h <= 2 * d:
        return list(points)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sx, sy = (w - 2 * d) / w, (h - 2 * d) / h
    return [(cx + (px - cx) * sx, cy + (py - cy) * sy) for px, py in points]


def _narrowest(points, y_top: float, y_bot: float, page_w: int, samples: int = 5):
    """The tightest chord the line's own box spans, clipped to the page raster.

    A line box two thirds of the way down an ellipse is narrower at its bottom
    edge than at its middle; measuring the middle and drawing the whole box is
    how text ends up outside a bubble it was reported to fit. Clipping to
    [0, page_w] here is what makes clipping == 0 a property of every layout
    rather than a number checked afterwards.
    """
    spans = []
    for i in range(samples):
        y = y_top + (y_bot - y_top) * i / max(samples - 1, 1)
        c = _chord(points, y)
        if c is None:
            return None
        spans.append(c)
    lo = max(max(s[0] for s in spans), 0.0)
    hi = min(min(s[1] for s in spans), float(page_w))
    return (lo, hi) if hi > lo else None


# -- text measurement ------------------------------------------------------


_FONT_CACHE: dict[int, ImageFont.FreeTypeFont] = {}


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """One truetype face, cached per size. MT_TYPESET_FONT overrides the search."""
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]
    candidates = [os.environ["MT_TYPESET_FONT"]] if os.environ.get("MT_TYPESET_FONT") else []
    candidates += FONT_CANDIDATES
    for path in candidates:
        if os.path.exists(path):
            _FONT_CACHE[size] = ImageFont.truetype(path, size)
            return _FONT_CACHE[size]
    raise TypesetError(
        f"no usable Latin font among {candidates} -- typesetting cannot proceed; "
        f"set MT_TYPESET_FONT to a .ttf path"
    )


def text_width(font, s: str, tracking_em: float) -> float:
    """Advance width including tracking, which PIL does not model.

    Tracking is applied between glyphs, so a string of n glyphs carries n-1
    gaps. Charging n gaps over-measures every string by one em-fraction.
    """
    if not s:
        return 0.0
    return font.getlength(s) + tracking_em * font.size * (len(s) - 1)


# -- layout ----------------------------------------------------------------


def _wrap_from(poly, words, font, line_h, tracking, bleed, top, bottom, page_w):
    """Greedy wrap of `words` in slots starting at `top`. None if words remain.

    A slot too narrow for the next word is left EMPTY and the word tries the
    next slot. That single rule is what makes the fit predicate monotone:
    greedy filling is prefix-stable, so the words of a shorter string occupy
    exactly the slots they would occupy inside a longer one, and "the last word
    landed before `bottom`" can only get harder as words are added.
    """
    out = []
    wi = 0
    slot = 0
    while wi < len(words):
        ly = top + slot * line_h
        if ly + line_h > bottom + 1e-6:
            return None
        slot += 1
        span = _narrowest(poly, ly, ly + line_h, page_w)
        if span is None:
            continue
        lo, hi = span
        centre = (lo + hi) / 2
        # Bleed widens the line symmetrically, and never past the raster edge.
        avail = min((hi - lo) + 2 * bleed, 2 * min(centre, page_w - centre))
        line = ""
        while wi < len(words):
            trial = f"{line} {words[wi]}" if line else words[wi]
            if text_width(font, trial, tracking) <= avail:
                line = trial
                wi += 1
            else:
                break
        if line:
            out.append((centre - text_width(font, line, tracking) / 2, ly, line))
    return out


def _layout(points, text: str, font_px: int, *, tight: bool, inset: float, bleed: float,
            page_w: int, page_h: int):
    """Lay `text` out at this size and state, or return None if it does not fit.

    FIT is decided by one greedy wrap from the top of the usable region, which
    is monotone in the length of `text`. PLACEMENT then tries to centre the
    block vertically, and only ever swaps in a centred wrap that ALSO consumes
    every word -- so centring can improve how a fitting layout looks, but it
    can never decide whether something fits.
    """
    words = text.split()
    if not words:
        return None
    font = load_font(font_px)
    leading = LEADING * (TIGHT_LEADING_FACTOR if tight else 1.0)
    tracking = TIGHT_TRACKING_EM if tight else 0.0
    line_h = font_px * leading
    poly = _inset_points(points, inset)
    _, y0, _, y1 = _bbox(poly)
    top, bottom = max(y0, 0.0), min(y1, float(page_h))
    if bottom - top < line_h:
        return None

    lines = _wrap_from(poly, words, font, line_h, tracking, bleed, top, bottom, page_w)
    if lines is None:
        return None

    centre = (top + bottom) / 2
    best = lines
    for _ in range(3):
        block_top, block_bot = best[0][1], best[-1][1] + line_h
        offset = centre - (block_top + block_bot) / 2
        if abs(offset) < 0.5:
            break
        start = min(max(top + offset, top), bottom - line_h)
        cand = _wrap_from(poly, words, font, line_h, tracking, bleed, start, bottom, page_w)
        if cand is None:
            break
        cand_centre = (cand[0][1] + cand[-1][1] + line_h) / 2
        if abs(cand_centre - centre) >= abs((block_top + block_bot) / 2 - centre):
            break
        best = cand

    return {"lines": best, "font_px": font_px, "line_h": line_h,
            "tracking": tracking, "bleed": bleed}


def _longest(n_max: int, fits) -> int:
    """The largest n in [0, n_max] for which fits(n) holds, given fits is monotone.

    One search, used at three granularities -- characters for rung 5's cap,
    whole words and token characters for truncation. It is only correct
    because `_layout` is monotone in text length; see the module docstring for
    what it returned before that was true.
    """
    lo, hi, best = 1, n_max, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        if fits(mid):
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return best


# -- raster measurement ----------------------------------------------------


def _raster_metrics(points, placed, page_w: int, page_h: int) -> tuple[int, int, int, int]:
    """(overflow_x, overflow_y, clipped_glyphs, offpage_ink_px), read off drawn ink.

    The region is drawn into a scratch frame that covers both the polygon and
    every glyph box and is deliberately NOT clipped to the page, so ink that
    would leave the raster is still visible to count. Overflow is then measured
    per row against the rasterised polygon: horizontal where the row crosses the
    polygon, vertical where ink sits on a row the polygon does not reach.
    """
    lines = placed["lines"]
    if not lines:
        return 0, 0, 0, 0
    font_px, line_h, tracking = placed["font_px"], placed["line_h"], placed["tracking"]
    font = load_font(font_px)

    px0, py0, px1, py1 = _bbox(points)
    xs, ys = [px0, px1], [py0, py1]
    for x, y, line in lines:
        xs += [x - font_px, x + text_width(font, line, tracking) + font_px]
        ys += [y - font_px, y + line_h + font_px]
    fx0, fy0 = math.floor(min(xs)) - 2, math.floor(min(ys)) - 2
    fw, fh = math.ceil(max(xs)) + 2 - fx0, math.ceil(max(ys)) + 2 - fy0

    ink_img = Image.new("L", (fw, fh), 255)
    draw = ImageDraw.Draw(ink_img)
    for x, y, line in lines:
        _draw_line(draw, x - fx0, y - fy0, line, font_px, tracking)
    mask_img = Image.new("1", (fw, fh), 0)
    ImageDraw.Draw(mask_img).polygon([(px - fx0, py - fy0) for px, py in points], fill=1)

    ink = np.asarray(ink_img) < INK_THRESHOLD
    mask = np.asarray(mask_img, dtype=bool)
    mask_rows = np.nonzero(mask.any(axis=1))[0]

    # Every ink pixel OUTSIDE the mask, measured to the nearest polygon pixel --
    # in its own row when that row crosses the polygon (horizontal), else to the
    # nearest row that does (vertical). Against the mask itself, never against a
    # row's outer extent: the outer extent cannot see a gap between two inside
    # runs, which is precisely where a concave polygon's overflow lands.
    outside = ink & ~mask
    ox = oy = 0
    for r in np.nonzero(outside.any(axis=1))[0]:
        cols = np.nonzero(outside[r])[0]
        poly_cols = np.nonzero(mask[r])[0]
        if poly_cols.size == 0:
            if mask_rows.size:
                oy = max(oy, int(np.abs(mask_rows - r).min()))
            continue
        idx = np.searchsorted(poly_cols, cols)
        left = poly_cols[np.clip(idx - 1, 0, poly_cols.size - 1)]
        right = poly_cols[np.clip(idx, 0, poly_cols.size - 1)]
        ox = max(ox, int(np.minimum(np.abs(cols - left), np.abs(right - cols)).max()))

    col_abs = np.arange(fw) + fx0
    row_abs = np.arange(fh) + fy0
    on_page = ((row_abs >= 0) & (row_abs < page_h))[:, None] & ((col_abs >= 0) & (col_abs < page_w))[None, :]
    offpage = int((ink & ~on_page).sum())

    clipped = 0
    for x, y, line in lines:
        cx = x
        for ch in line:
            gx0, gy0, gx1, gy1 = font.getbbox(ch)
            if cx + gx0 < 0 or cx + gx1 > page_w or y + gy0 < 0 or y + gy1 > page_h:
                clipped += 1
            cx += font.getlength(ch) + tracking * font_px

    return max(0, ox), max(0, oy), clipped, offpage


# -- the ladder ------------------------------------------------------------


def _edge_adjacent(points, page_w: int) -> bool:
    """Is rung 4's bleed physically available?

    Rung 4 is skipped, not attempted and failed, when it is not -- the
    difference is visible in the rung counter and is what tells a reader that
    the ladder made a decision rather than that an attempt silently no-opped.
    """
    x0, _, x1, _ = _bbox(points)
    margin = BLEED_FRAC * (x1 - x0)
    return x0 < margin or (page_w - x1) < margin


def _floor_fits(points, page_w, page_h):
    """The rung-3 state -- floor, tightened, no inset, no bleed -- as a predicate."""
    floor = floor_px(page_h)

    def fits(text):
        return _layout(points, text, floor, tight=True, inset=0.0, bleed=0.0,
                       page_w=page_w, page_h=page_h)

    return fits


def _capacity(points, text: str, page_w: int, page_h: int) -> int:
    """The largest character count of `text` that fits at the floor, tightened.

    COMPUTED against this actual string rather than estimated from an area:
    capacity in characters depends on which characters, and a cap derived from
    a mean glyph width is wrong by a third on a run of capitals or of i's.
    """
    fits = _floor_fits(points, page_w, page_h)
    return _longest(len(text), lambda n: bool(fits(text[:n])))


def _ladder(points, text: str, page_w: int, page_h: int):
    """Rungs 1-4. Returns (placed, rung, rung4_skipped). placed None on a miss.

    On a miss the caller escalates to rung 5, the only rung that cannot miss.
    """
    floor = floor_px(page_h)
    x0, y0, x1, y1 = _bbox(points)
    inset = INSET_FRAC * min(x1 - x0, y1 - y0)
    kw = {"page_w": page_w, "page_h": page_h}

    # Rung 1 -- the largest size at or above the floor that fits. A binary
    # search, and its correctness does NOT rest on fit being monotone in font
    # size, which a slot grid only approximately is: every failed probe moves
    # the search DOWN, so the floor is always tested whenever nothing larger
    # was found. A hole in the size predicate can therefore cost a font size,
    # but can never escalate a region that fits at the floor into rung 2.
    start = max(floor, min(max_font_px(page_h), int(y1 - y0)))
    lo, hi, best = floor, start, None
    while lo <= hi:
        mid = (lo + hi) // 2
        placed = _layout(points, text, mid, tight=False, inset=inset, bleed=0.0, **kw)
        if placed:
            best, lo = placed, mid + 1
        else:
            hi = mid - 1
    if best:
        return best, 1, False

    # Rung 2 -- at the floor, tightened. Bounded: no further tightening exists.
    placed = _layout(points, text, floor, tight=True, inset=inset, bleed=0.0, **kw)
    if placed:
        return placed, 2, False

    # Rung 3 -- erode the inset to zero.
    placed = _layout(points, text, floor, tight=True, inset=0.0, bleed=0.0, **kw)
    if placed:
        return placed, 3, False

    # Rung 4 -- bounded horizontal bleed, or a recorded skip.
    if _edge_adjacent(points, page_w):
        return None, 5, True
    placed = _layout(points, text, floor, tight=True, inset=0.0,
                     bleed=BLEED_FRAC * (x1 - x0) / 2, **kw)
    if placed:
        return placed, 4, False

    return None, 5, False


def _truncate(points, text: str, page_w: int, page_h: int):
    """Rung 5's terminal branch. Returns (placed or None, rendered, reason).

    Cannot fail: truncation is a decision, not an accident. Two sub-cases below
    one word, separated by whether the string has a boundary to stop at:

      * it has a space and no whole word fits -> render EMPTY, fit_failed set.
        Empty is a reported state, never a silent one.
      * it is a single token that exceeds capacity -- an SFX, a URL, a compound
        -- so there is no boundary -> break mid-token with a trailing ellipsis.
    """
    fits = _floor_fits(points, page_w, page_h)
    words = text.split()

    n = _longest(len(words), lambda k: bool(fits(" ".join(words[:k]))))
    if n:
        cand = " ".join(words[:n])
        return fits(cand), cand, REASON_TRUNCATED
    if len(words) != 1:
        return None, "", REASON_NO_WORD

    token = words[0]
    n = _longest(len(token) - 1, lambda k: bool(fits(token[:k] + ELLIPSIS)))
    if n:
        cand = token[:n] + ELLIPSIS
        return fits(cand), cand, REASON_TOKEN
    return None, "", REASON_TOKEN


# -- the entry point -------------------------------------------------------


def typeset_page(regions, page: Image.Image, *, allow_retranslate: bool = True, client=None):
    """Typeset every region of one page. Returns (image, [Fit]).

    Two-phase by construction. `allow_retranslate=False` is what Phase 3's
    re-render route passes: on the spot-fix path the user's text is
    authoritative, re-translating it would overwrite an `edited: true` entry,
    and the round trip would not fit inside AC-10's 3.0s budget. Rung 5 then
    falls straight to truncation with fit_failed shown.

    SYNCHRONOUS, and must not be called from inside a running event loop: rung
    5's retry uses asyncio.run. From async code, call it via asyncio.to_thread.
    Doing otherwise raises TypesetError naming the fix, rather than asyncio's
    RuntimeError from somewhere inside a page run.
    """
    _refuse_running_loop()
    page_w, page_h = page.size
    out = page.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    floor = floor_px(page_h)

    fits: list[Fit] = []
    pending: list[tuple[int, list, str]] = []  # (index, points, original text)

    # -- phase one: rungs 1-4 for every region, collecting rung-5 candidates.
    for r in regions:
        points = as_points(r["polygon"] if isinstance(r, dict) else r.polygon)
        text = (r.get("translation", "") if isinstance(r, dict) else r.translation) or ""
        rid = r.get("id", 0) if isinstance(r, dict) else r.id
        fit = Fit(id=rid, font_px=floor)

        if not text.strip():
            # Nothing will be drawn. Whether that is text LOSS depends on the
            # SOURCE, not the translation. A region the OCR blank gate emptied
            # (ocr_ja returns "" for a crop with no text in it) had nothing to
            # lose, and flagging it would report every false-positive detection
            # as an incomplete page and sort it to the top of the spot-fix editor
            # -- a false alarm on the one signal AC-1 exists to make trustworthy.
            # A non-empty source, or none supplied, is lost text and is flagged:
            # a provider that omitted this id must not yield a bubble that looks
            # deliberately blank. Both carriers can express the difference:
            # region.Region defaults text to None (not yet OCR'd) rather than ""
            # (OCR ran, found nothing), and the pipeline's dicts carry whatever
            # ocr_ja returned.
            source = r.get("text") if isinstance(r, dict) else getattr(r, "text", None)
            fit.rung = 0
            if source is not None and not str(source).strip():
                fit.reason = REASON_NO_SOURCE
            else:
                fit.fit_failed, fit.reason = True, REASON_EMPTY
            fits.append(fit)
            continue

        placed, rung, skipped = _ladder(points, text, page_w, page_h)
        fit.rung, fit.rung4_skipped = rung, skipped
        if placed:
            _commit(fit, points, placed, text, page_w, page_h)
        else:
            fit.capacity = _capacity(points, text, page_w, page_h)
            pending.append((len(fits), points, text))
        fits.append(fit)

    # -- phase two: ONE batched re-translation for every rung-5 candidate.
    # A region whose capacity is zero is left out: nothing can fit it, so a
    # request asking for "at most 0 characters" is a round trip with no answer.
    shortened: dict[int, str] = {}
    askable = [(fits[i].id, text, fits[i].capacity) for i, _, text in pending if fits[i].capacity]
    if askable and allow_retranslate and client is not None:
        shortened = _retranslate(client, askable)

    for i, points, text in pending:
        fit = fits[i]
        fit.rung = 5
        source = text
        cand = shortened.get(fit.id, "")
        if cand and len(cand) > fit.capacity:
            # The spec names this case: the provider replied longer than the cap
            # it was given. Its reply is not trusted over the original.
            fit.reply_rejected = True
        elif cand:
            fit.retranslated = True
            source = cand
            placed, rung, _ = _ladder(points, cand, page_w, page_h)
            if placed:
                # The retry's reply is RENDERED, not merely requested. An
                # implementation that issues the call and truncates the original
                # anyway passes every request-count assert and fails here.
                _commit(fit, points, placed, cand, page_w, page_h)
                continue

        placed, rendered, reason = _truncate(points, source, page_w, page_h)
        fit.fit_failed, fit.reason = True, reason
        if placed:
            _commit(fit, points, placed, rendered, page_w, page_h)

    for fit in fits:
        for x, y, line in fit.lines:
            _draw_line(draw, x, y, line, fit.font_px, fit.tracking)

    return out, fits


def _commit(fit: Fit, points, placed, text: str, page_w: int, page_h: int) -> None:
    """Record one drawn layout onto its Fit. The only writer of the metrics."""
    fit.text = text
    fit.font_px = placed["font_px"]
    fit.tracking = placed["tracking"]
    fit.bleed_px = placed["bleed"]
    fit.lines = placed["lines"]
    fit.fit_compromised = placed["bleed"] > 0
    (fit.overflow_px_x, fit.overflow_px_y,
     fit.clipped_glyphs, fit.offpage_ink_px) = _raster_metrics(points, placed, page_w, page_h)


def _draw_line(draw, x: float, y: float, line: str, font_px: int, tracking: float) -> None:
    """Draw one line glyph by glyph, because PIL has no tracking parameter.

    `tracking` is the value the LAYOUT used, not a constant. Drawing with
    TIGHT_TRACKING_EM unconditionally -- as this did until check_inpaint's
    composite gate caught it -- squeezed rung-1 lines measured at zero tracking,
    and the raster drifted off the geometry the engine reported for it.
    """
    font = load_font(font_px)
    cx = x
    for ch in line:
        draw.text((cx, y), ch, font=font, fill="black")
        cx += font.getlength(ch) + tracking * font_px


def _refuse_running_loop() -> None:
    """Raise a named error if called inside a running event loop, on EVERY page.

    The guard used to sit inside _retranslate, so an async caller passed on
    every easy page and broke only on the first page hard enough to reach rung
    5 -- in production, on real content, never in a quick test. Checking at the
    entry makes the constraint fail on the first call, whatever the page.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise TypesetError(
        "typeset_page is synchronous and was called from a running event loop; "
        "call it via asyncio.to_thread from async code"
    )


def _retranslate(client, items) -> dict:
    """One request for every rung-5 region on the page, through llm.py's semaphore.

    The `except` is NARROW on purpose. Rung 5 has no failure exit, so a provider
    that 401s or times out must degrade to truncation rather than kill the page
    -- but "the provider misbehaved" is the only thing that may be absorbed. A
    bare `except Exception` would also swallow a TypeError in the capacity
    computation or a KeyError in the reply mapping, turning our own bugs into
    silently truncated pages that look like hard bubbles.
    """
    import asyncio

    from .llm import ProviderError, SettingsError

    try:
        return asyncio.run(client.retranslate_capped(items))
    except (ProviderError, SettingsError, OSError, TimeoutError):
        return {}


def summary(fits) -> dict:
    """The job summary AC-1 requires: which regions were compromised, which failed.

    Region ids, not counts alone. "3 regions failed to fit" tells a user the
    page is incomplete; it does not tell them where to look, and the spot-fix
    editor sorts on exactly these lists.
    """
    return {
        "fit_compromised": [f.id for f in fits if f.fit_compromised],
        "fit_failed": [f.id for f in fits if f.fit_failed],
        "retranslated": [f.id for f in fits if f.retranslated],
        "fit_compromised_count": sum(1 for f in fits if f.fit_compromised),
        "fit_failed_count": sum(1 for f in fits if f.fit_failed),
        "min_font_px": min([f.font_px for f in fits], default=0),
        "clipped_glyph_count": sum(f.clipped_glyphs for f in fits),
    }
