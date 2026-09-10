"""Phase 2a -- AC-1's erasure clause: original text ERASED, not boxed over. OFFLINE.

This gate was specified once before and was wrong in both directions, which is
worth stating because the shape of the mistake explains the shape of the fix.
Iteration 1 asserted "low variance inside the region" and "edge density drops
>= 60%". A detected region is the text area *inside* a speech bubble, so after
correct inpainting it is near-uniform -- meaning both asserts were MAXIMIZED by
pasting a white box over the bubble, the exact failure they existed to catch.
Its one discriminating assert, "no uniform-fill rectangle covers >70% of the
region", then REJECTED correct output. A false pass and a false fail in one
check.

The real signal is continuity with the surrounding bubble, not flatness.

  1. RING COMPARISON. A 6-10px ring just OUTSIDE the polygon -- inside the
     bubble, outside the text area -- against the ADJACENT INNER BAND 6-10px
     inside it. Correct inpainting continues the bubble's own interior, so the
     two match. A box over a toned or grey bubble does not.
  2. NO NEW STEP EDGE at the region's bounding-box perimeter. A pasted
     rectangle has four hard borders by construction; an inpaint has none.
     This is the box-over signature stated as something that can only be true
     of a box.
  3. INK REMOVED inside. Necessary, and explicitly NOT sufficient -- it never
     carries the gate alone, because a box satisfies it perfectly.

Two corrections keep assert 1 from false-failing on correct output. Ring pixels
darker than 0.45 of the page's dynamic range are masked out first, because a
6-10px ring crosses the bubble border on tight bubbles and a correct white fill
against a ring carrying border ink misses 4/255 by a wide margin. And the
comparison is against the adjacent inner band rather than the whole fill,
because on the very gradient bubble this assert exists for, a 6-10px offset
ALONG the gradient can exceed 4/255 before any inpainter is involved.

When fewer than 40% of a region's ring pixels survive the mask, assert 1 does
not run on that region. It is REPORTED, in the per-region line, in the summary
and in the METRICS record -- an unannounced skip is the same defect class as an
assert that cannot fail.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402
from sidecar import pipeline, typeset  # noqa: E402
from sidecar.llm import LLMClient  # noqa: E402

PAGE = os.path.join(ROOT, "fixtures", "smoke", "tategaki_01.png")

RING_INNER, RING_OUTER = 6, 10  # the band, in pixels, on both sides
DARK_FRAC_OF_RANGE = 0.45  # ring pixels darker than this are border ink
MIN_VALID_RING = 0.40  # below this, assert 1 does not run and says so
MEAN_TOL = 4.0  # /255
STD_RATIO = (0.5, 2.0)
UNIFORM_EPS = 1.0  # /255 -- below this both bands are flat, see _std_ratio_ok
INK_DROP = 0.80
EDGE_STEP = 32  # /255 -- a step this big across a bbox side is an edge
EDGE_TOL = 0.10  # new-edge fraction allowed over the input's own
STUB_TEXT = "HELLO"
NCC_FLOOR = 0.90
# Correlation on glyphs is shift-sensitive to the point of uselessness without
# an alignment search; see _best_ncc. Small on purpose.
SHIFT_SEARCH = 3


# -- masks -----------------------------------------------------------------


def _offset(points, d: float):
    """The polygon scaled about its centroid by d pixels (d<0 shrinks)."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    w, h = x1 - x0, y1 - y0
    if w + 2 * d <= 1 or h + 2 * d <= 1:
        return None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    sx, sy = (w + 2 * d) / w, (h + 2 * d) / h
    return [(cx + (px - cx) * sx, cy + (py - cy) * sy) for px, py in points]


def _mask(size, points) -> np.ndarray:
    m = Image.new("1", size, 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in points], fill=1)
    return np.array(m, dtype=bool)


def _band(size, points, near: float, far: float):
    """The annulus between two offsets of the polygon, as a boolean mask."""
    a, b = _offset(points, far), _offset(points, near)
    if a is None or b is None:
        return None
    return _mask(size, a) & ~_mask(size, b)


def _std_ratio_ok(s_ring: float, s_inner: float) -> tuple[bool, str]:
    """The std-dev ratio verdict, INCLUDING the case where both are flat.

    0/0 must not decide this gate by accident. Two uniform bands are the most
    continuous a bubble can be -- a flat white fill inside a flat white bubble
    is the correct answer, not a suspicious one -- so both below UNIFORM_EPS is
    an explicit PASS. One flat and one not is a real mismatch and is judged by
    the ratio, with a flat denominator reported as an infinite ratio rather
    than raising.
    """
    if s_ring < UNIFORM_EPS and s_inner < UNIFORM_EPS:
        return True, "both bands uniform"
    if s_ring < UNIFORM_EPS:
        return False, f"ring is flat ({s_ring:.2f}) but the fill is not ({s_inner:.2f})"
    ratio = s_inner / s_ring
    return STD_RATIO[0] <= ratio <= STD_RATIO[1], f"std ratio {ratio:.2f}"


# -- the three asserts -----------------------------------------------------


def _assert_ring(c, out_gray: np.ndarray, points, rid, skips: list) -> None:
    """Assert 1. Continuity with the surrounding bubble."""
    size = (out_gray.shape[1], out_gray.shape[0])
    ring = _band(size, points, RING_INNER, RING_OUTER)
    inner = _band(size, points, -RING_OUTER, -RING_INNER)
    if ring is None or inner is None or not ring.any() or not inner.any():
        skips.append(rid)
        print(f"  reduced coverage: assert 1 skipped on {rid}, valid ring 0%")
        return

    lo, hi = float(out_gray.min()), float(out_gray.max())
    cutoff = lo + DARK_FRAC_OF_RANGE * (hi - lo)
    valid = ring & (out_gray >= cutoff)
    coverage = valid.sum() / max(ring.sum(), 1)

    if coverage < MIN_VALID_RING:
        skips.append(rid)
        print(f"  reduced coverage: assert 1 skipped on {rid}, "
              f"valid ring {coverage * 100:.0f}%")
        return

    r, i = out_gray[valid], out_gray[inner]
    dmean = abs(float(r.mean()) - float(i.mean()))
    ok_std, why = _std_ratio_ok(float(r.std()), float(i.std()))
    c.check(dmean <= MEAN_TOL,
            f"[ring {rid}] mean difference {dmean:.2f} <= {MEAN_TOL}/255 "
            f"(valid ring {coverage * 100:.0f}%) -- the fill continues the bubble")
    c.check(ok_std, f"[ring {rid}] {why} -- a flat box over a toned bubble fails here")


def _side_edges(gray: np.ndarray, box) -> float:
    """Fraction of bbox-perimeter positions carrying an axis-aligned step.

    Measured ACROSS each side, one pixel either way, which is what a pasted
    rectangle's border looks like and what an inpaint's boundary does not.
    """
    x0, y0, x1, y1 = (int(round(v)) for v in box)
    h, w = gray.shape
    hits = total = 0
    for x in (x0, x1):
        if 1 <= x < w - 1:
            col = np.abs(gray[max(y0, 0):min(y1, h), x] - gray[max(y0, 0):min(y1, h), x - 1])
            hits += int((col > EDGE_STEP).sum())
            total += col.size
    for y in (y0, y1):
        if 1 <= y < h - 1:
            row = np.abs(gray[y, max(x0, 0):min(x1, w)] - gray[y - 1, max(x0, 0):min(x1, w)])
            hits += int((row > EDGE_STEP).sum())
            total += row.size
    return hits / max(total, 1)


def _assert_step_edge(c, src_gray, out_gray, points, rid) -> None:
    """Assert 2. No axis-aligned edge in the output that was absent from the input."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    box = (min(xs), min(ys), max(xs), max(ys))
    before, after = _side_edges(src_gray, box), _side_edges(out_gray, box)
    c.check(after <= before + EDGE_TOL,
            f"[edge {rid}] new step-edge fraction at the bbox perimeter "
            f"{after:.3f} <= input {before:.3f} + {EDGE_TOL} -- a pasted "
            f"rectangle has four hard borders by construction")


def _assert_ink(c, src_gray, out_gray, points, rid, label="ink") -> float:
    """Assert 3. Dark-pixel fraction inside the polygon drops by >= 80%.

    NECESSARY, NOT SUFFICIENT, and deliberately never the only assert on a
    region: a white box over the whole bubble satisfies it perfectly. It is
    here to catch the opposite failure -- an inpainter that ran and changed
    nothing.
    """
    size = (src_gray.shape[1], src_gray.shape[0])
    inside = _mask(size, points)
    before = float((src_gray[inside] < 128).mean())
    after = float((out_gray[inside] < 128).mean())
    drop = 1.0 if before == 0 else 1.0 - after / before
    c.check(before == 0 or drop >= INK_DROP,
            f"[{label} {rid}] dark-pixel fraction {before:.3f} -> {after:.3f} "
            f"(down {drop * 100:.0f}%, need {INK_DROP * 100:.0f}%) -- necessary, not sufficient")
    return drop


# -- the composite gate ----------------------------------------------------


def _chord_x(points, y: float):
    """Widest CONTIGUOUS span of the polygon at scanline y. This file's own scanline code.

    Independent of the engine by design -- the reference must not be derived
    from the code it checks -- but it has to agree with the engine on what a
    row's usable width MEANS. Both take the widest contiguous run, so a row
    that crosses the polygon twice is read the same way here as there. It took
    the outermost crossings until a review pointed out the mismatch: identical
    on every convex region that reaches this gate today, and a false failure on
    the first concave one.
    """
    xs = []
    n = len(points)
    for i in range(n):
        (xa, ya), (xb, yb) = points[i], points[(i + 1) % n]
        if ya == yb:
            continue
        if min(ya, yb) <= y < max(ya, yb):
            xs.append(xa + (y - ya) * (xb - xa) / (yb - ya))
    if len(xs) < 2:
        return None
    xs.sort()
    spans = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
    return max(spans, key=lambda span: span[1] - span[0])


def _expected_font_px(points, text: str, page_w: int, page_h: int) -> int:
    """The size a single-word line MUST be set at, derived from the polygon.

    What is independent and what is not, stated exactly, because the first
    version overstated it. INDEPENDENT: the engine's reported font size is never
    read, and the geometry -- the inset polygon, its chords, the slot grid -- is
    computed by this file's own code. SHARED: the RULE CONSTANTS (INSET_FRAC,
    LEADING, the floor and ceiling) -- a reference cannot predict an exact size
    without knowing the rule it is predicting.

    That split is the point. A uniformly mis-scaled render still fails, because
    the size comes from geometry, not from the engine's self-report. And the
    inset is applied as the rule states it, INSET_FRAC of min(w, h): the first
    version used a fraction of the width alone, which agreed with the engine
    only on regions taller than wide -- all three smoke regions happen to be --
    and would have false-failed the first wide bubble, at a 1px size difference
    that NCC scores at 0.3-0.5. _selftest_reference runs this against wide,
    tall and flat regions so that cannot recur unseen.
    """
    from PIL import ImageFont

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    inner = _offset(points, -typeset.INSET_FRAC * min(w, h)) or list(points)
    top = max(min(p[1] for p in inner), 0.0)
    bottom = min(max(p[1] for p in inner), float(page_h))
    floor = typeset.floor_px(page_h)
    ceiling = max(floor, min(typeset.max_font_px(page_h), int(h)))

    for size in range(ceiling, floor - 1, -1):
        line_h = size * typeset.LEADING
        need = ImageFont.truetype(typeset.FONT_CANDIDATES[0], size).getlength(text)
        k = 0
        while top + (k + 1) * line_h <= bottom + 1e-6:
            y = top + k * line_h
            k += 1
            spans = [_chord_x(inner, y + line_h * t / 4) for t in range(5)]
            if any(sp is None for sp in spans):
                continue
            lo = max(max(sp[0] for sp in spans), 0.0)
            hi = min(min(sp[1] for sp in spans), float(page_w))
            if hi - lo >= need:
                return size
    return floor


def _reference(text: str, size: int) -> np.ndarray:
    """The reference render of `text` at `size`, cropped to its own INK box.

    Cropped to ink, not to font.getbbox(). getbbox reports the layout box, which
    carries the first glyph's left side bearing as blank margin -- so the
    reference's glyphs sat several pixels right of the canvas origin, while the
    page's ink box starts exactly at the first stem. The bearing scales with the
    font: about 1px at the smoke page's 15px, which hid inside the +/-3px
    alignment search, and 7px at 90px, which did not -- measured, a correct
    wide-bubble render correlated 1.000 at offset -7 and 0.593 inside the window.
    Both sides of the comparison are now anchored at ink, so the search window
    stays small enough to mean "this bubble" rather than "anywhere nearby".
    """
    from PIL import ImageFont

    font = ImageFont.truetype(typeset.FONT_CANDIDATES[0], size)
    gx0, gy0, gx1, gy1 = font.getbbox(text)
    pad = 4
    canvas = Image.new("L", (gx1 - gx0 + 2 * pad, gy1 - gy0 + 2 * pad), 255)
    ImageDraw.Draw(canvas).text((pad - gx0, pad - gy0), text, font=font, fill=0)
    arr = np.array(canvas, dtype=np.float64)
    ys, xs = np.nonzero(arr < typeset.INK_THRESHOLD)
    return arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.astype(np.float64) - a.mean()
    b = b.astype(np.float64) - b.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom else 0.0


def _best_ncc(page: np.ndarray, ref: np.ndarray, at, search: int = SHIFT_SEARCH) -> float:
    """The best correlation of `ref` against `page` within a few pixels of `at`.

    Correlation on glyphs is brutally shift-sensitive: two renders of the same
    string at the same size, one pixel apart, score near ZERO because a 2px
    stroke lands entirely in the other's background. Measured here at 0.06 for
    a pair a human reads as identical. So the match searches a small
    neighbourhood and takes the best, which is what makes the score a question
    about SCALE AND IDENTITY -- is this that string at that size -- rather than
    a question about sub-pixel placement, which no part of AC-1 constrains.

    The window stays small on purpose. A large one would let a glyph found
    anywhere on the page satisfy an assert about a specific bubble.
    """
    h, w = ref.shape
    x, y = at
    best = -1.0
    for dy in range(-search, search + 1):
        for dx in range(-search, search + 1):
            y0, x0 = y + dy, x + dx
            if y0 < 0 or x0 < 0 or y0 + h > page.shape[0] or x0 + w > page.shape[1]:
                continue
            best = max(best, _ncc(page[y0:y0 + h, x0:x0 + w], ref))
    return best


def _ink_bbox(gray: np.ndarray, mask: np.ndarray):
    dark = mask & (gray < 128)
    if not dark.any():
        return None
    ys, xs = np.nonzero(dark)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _composite(c) -> None:
    """The gate nothing else provides: translated text landing on a real page.

    check_typeset runs on synthetic polygons and check_probe only asserts that
    in-polygon pixels changed, which boxing over satisfies. This runs the whole
    pipeline over the smoke page with the provider stubbed to one fixed English
    string, and then asks three separate questions of the raster.
    """
    with Image.open(PAGE) as im:
        src = im.convert("RGB").copy()
    src_gray = np.array(src.convert("L"), dtype=np.float64)
    page_w, page_h = src.size

    # The cleaned page, reproduced by calling the same two stages on the same
    # input. run_page does not surface its intermediate, and assert (a) is a
    # claim about the ERASURE -- measuring it on the final page would measure
    # the English text drawn on top of it instead.
    regions = pipeline.detect(src, 1)
    cleaned, _ = pipeline.inpaint(src, regions, 1)
    cleaned_gray = np.array(cleaned.convert("L"), dtype=np.float64)
    for r in regions:
        _assert_ink(c, src_gray, cleaned_gray, r["polygon"], r["id"], label="composite-a")

    replies = {r["id"]: STUB_TEXT for r in regions}
    with tempfile.TemporaryDirectory() as dest, StubProvider(replies=replies, delay=0) as stub:
        client = LLMClient(stub.url, "k", "stub-model")
        record = pipeline.run_page(PAGE, dest, 1, client)
        with Image.open(record["output"]) as im:
            out = im.convert("RGB").copy()

    out_gray = np.array(out.convert("L"), dtype=np.float64)

    # (b) the stub's exact string, at a scale derived from the geometry.
    for r in record["regions"]:
        rid, points = r["id"], r["polygon"]
        c.check(r["typeset"] == STUB_TEXT,
                f"[composite-b {rid}] the stub's string reached the page record "
                f"({r['typeset']!r} == {STUB_TEXT!r})")
        inside = _mask((page_w, page_h), points)
        box = _ink_bbox(out_gray, inside)
        if not c.check(box is not None,
                       f"[composite-b {rid}] the rendered string leaves ink inside the "
                       f"polygon -- text composited BEHIND the inpaint layer leaves none"):
            continue
        assert box is not None  # narrowed by the check above

        # The reference is rendered at the size the POLYGON implies, at its own
        # natural extent -- never cropped to the measured ink box, which would
        # hand the mis-scale case the very freedom this assert exists to deny.
        # A page rendered at half scale leaves a half-height ink box, the
        # full-height reference cannot align with it at any shift, and the
        # correlation collapses.
        size = _expected_font_px(points, STUB_TEXT, page_w, page_h)
        score = _best_ncc(out_gray, _reference(STUB_TEXT, size), (box[0], box[1]))
        c.check(score >= NCC_FLOOR,
                f"[composite-b {rid}] rendered text correlates {score:.3f} >= {NCC_FLOOR} "
                f"with a {size}px reference derived from the POLYGON, not from the "
                f"engine's own reported metrics")

    # (c) everything outside the dilated bboxes is untouched.
    touched = np.zeros((page_h, page_w), dtype=bool)
    for r in record["regions"]:
        xs = [p[0] for p in r["polygon"]]
        ys = [p[1] for p in r["polygon"]]
        bleed = typeset.BLEED_FRAC * (max(xs) - min(xs))
        x0 = max(int(min(xs) - bleed), 0)
        x1 = min(int(max(xs) + bleed) + 1, page_w)
        y0, y1 = max(int(min(ys)), 0), min(int(max(ys)) + 1, page_h)
        touched[y0:y1, x0:x1] = True
        c.check(r["rung"] < 4,
                f"[composite-c {r['id']}] took rung {r['rung']} < 4 under the stub "
                f"string -- the bleed allowance dilating this gate is provably unused, "
                f"and a later change that pushes a smoke region to rung 4 says so here "
                f"rather than hiding inside the tolerance")

    diff = (np.array(out, dtype=np.int16) != np.array(src, dtype=np.int16)).any(axis=2)
    outside = int((diff & ~touched).sum())
    c.check(outside == 0,
            f"[composite-c] {outside} pixels changed outside every region bbox dilated "
            f"by rung 4's {typeset.BLEED_FRAC:.0%} allowance -- no box-over-the-page "
            f"shortcut survives this")


# -- self-tests: branches the smoke page cannot reach ----------------------


class _Verdicts:
    """A Checks stand-in that RECORDS verdicts instead of failing the run.

    The self-tests feed assert 1 inputs it SHOULD fail, then assert that it did.
    Routing those through the real Checks would report a correct red as a check
    failure.
    """

    def __init__(self):
        self.results = []

    def check(self, ok, description):
        self.results.append((bool(ok), description))
        return ok


def _selftest_ring(c) -> None:
    """Make assert 1's discriminating branches EXECUTE, and assert their verdicts.

    On the smoke page every bubble interior is opaque white, so assert 1 only
    ever compared white to white: the mean-difference miss, the std-ratio leg
    and the reduced-coverage skip had never run in CI. A branch that has never
    run is an assert nobody has seen go red. These synthetic pages drive each.
    """
    size = (300, 300)
    box = [(100, 100), (200, 100), (200, 200), (100, 200)]
    yy, xx = np.mgrid[0:size[1], 0:size[0]]
    # A mid-grey checker tone, ABOVE the 0.45-of-range ink cutoff so the mask
    # keeps it -- a black-dot tone is masked out as ink and reads as flat white.
    tone = np.where(((xx % 4) < 2) ^ ((yy % 4) < 2), 150.0, 230.0)
    tone[:4, :] = 0.0  # a strip of true black, as line art gives every real page
    inside = _mask(size, box)

    # A flat white box over a toned bubble: both legs must go red.
    boxed = tone.copy()
    boxed[inside] = 255.0
    v, skips = _Verdicts(), []
    _assert_ring(v, boxed, box, "selftest-box", skips)
    c.check(len(v.results) == 2 and not any(ok for ok, _ in v.results),
            f"[selftest ring] a flat box over a toned bubble fails BOTH the mean and "
            f"the std-ratio legs ({[ok for ok, _ in v.results]})")

    # The tone continued through the region: both legs must stay green.
    v, skips = _Verdicts(), []
    _assert_ring(v, tone, box, "selftest-continued", skips)
    c.check(len(v.results) == 2 and all(ok for ok, _ in v.results),
            f"[selftest ring] a fill that continues the tone passes both legs, "
            f"including the std RATIO branch ({[d for _, d in v.results]})")

    # A ring that is all border ink: assert 1 must not run, and must say so.
    inked = np.full((size[1], size[0]), 255.0)
    inked[:4, :] = 0.0
    inked[86:215, 86:215] = 0.0
    inked[97:204, 97:204] = 255.0
    v, skips = _Verdicts(), []
    _assert_ring(v, inked, box, "selftest-inked", skips)
    c.check(not v.results and skips == ["selftest-inked"],
            f"[selftest ring] a ring that is all border ink SKIPS assert 1 and "
            f"records the skip (verdicts {len(v.results)}, skipped {skips})")


def _selftest_reference(c) -> None:
    """Composite (b)'s reference against every aspect ratio, not just the smoke page's.

    The smoke regions are all taller than wide -- the one shape the first
    reference happened to get right. This typesets the stub string into tall,
    wide and flat regions and requires the geometry-derived reference to match
    the raster on each, so the gate cannot quietly false-fail a wide bubble.
    """
    page_w, page_h = 700, 420
    shapes = {
        "tall": (20, 20, 80, 270),
        "wide": (120, 20, 420, 140),
        "flatter": (120, 170, 520, 260),
        "flattest": (120, 300, 620, 360),
    }
    regions = [
        {"id": i, "translation": STUB_TEXT,
         "polygon": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}
        for i, (x0, y0, x1, y1) in enumerate(shapes.values(), 1)
    ]
    out, fits = typeset.typeset_page(regions, Image.new("RGB", (page_w, page_h), "white"))
    gray = np.array(out.convert("L"), dtype=np.float64)

    for label, r, fit in zip(shapes, regions, fits):
        points = r["polygon"]
        box = _ink_bbox(gray, _mask((page_w, page_h), points))
        if not c.check(box is not None, f"[selftest reference {label}] ink was drawn"):
            continue
        assert box is not None
        size = _expected_font_px(points, STUB_TEXT, page_w, page_h)
        score = _best_ncc(gray, _reference(STUB_TEXT, size), (box[0], box[1]))
        c.check(score >= NCC_FLOOR,
                f"[selftest reference {label}] {size}px reference from geometry "
                f"correlates {score:.3f} >= {NCC_FLOOR} with the raster "
                f"(engine reported {fit.font_px}px -- diagnostic only, never compared)")


# -- the run ---------------------------------------------------------------


def main():
    c = Checks("check_inpaint")

    if not os.path.exists(PAGE):
        return skip(f"no smoke page at {PAGE} -- run tests/gen_fixtures.py")

    with Image.open(PAGE) as im:
        src = im.convert("RGB").copy()
    src_gray = np.array(src.convert("L"), dtype=np.float64)

    regions = pipeline.detect(src, 1)
    if not c.check(bool(regions), "the smoke page yields at least one region to erase"):
        return c.finish()

    out, _ = pipeline.inpaint(src, regions, 1)
    out_gray = np.array(out.convert("L"), dtype=np.float64)

    skips: list = []
    for r in regions:
        points, rid = r["polygon"], r["id"]
        _assert_ring(c, out_gray, points, rid, skips)
        _assert_step_edge(c, src_gray, out_gray, points, rid)
        _assert_ink(c, src_gray, out_gray, points, rid)

    _selftest_ring(c)
    _selftest_reference(c)
    _composite(c)

    if skips:
        print(f"  summary: assert 1 skipped on {len(skips)} region(s) for reduced "
              f"ring coverage: {skips}")
    print("METRICS " + json.dumps({"ring_assert_skipped": len(skips)}))
    return c.finish()


run(main)
