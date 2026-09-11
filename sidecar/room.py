"""The room a bubble gives its English: the interior around the erased text.

WHY, from the picture. A block of tategaki is tall and narrow, so the region
the detector hands the ladder is tall and narrow -- and English set inside it
comes out as a stack of two-word lines at a size the bubble never asked for:
"What a / lovely / day it is / out / there / today." in five lines at 26px,
centred in a bubble 460px wide with white on both sides. A letterer uses the
bubble. This module finds it: starting from the erased text block on the
cleaned page, it floods outward over the bubble's interior until it meets
the border ink, and hands the ladder that shape instead.

Three things here are load-bearing.

**It can decline, and it does so more often than it accepts.** A flood on a
page with no border to stop at -- narration text on white, an open bubble, a
gate fixture that is a polygon on a blank page -- runs until it hits the
window this module allows itself, and a room that touched the window is not
a room. `room()` then returns None and the caller keeps the region it had.
Every check_typeset fixture takes that branch, which is why none of them
moved when this landed.

**Screentone is a wall.** A halftone is dots with white between them, and a
flood over "not ink" walks straight through the gaps. The ink mask is
dilated first so dots close ranks; the cost is that a border thinner than the
dilation on both sides is treated as a wall too, which is the right error.

**The room is eroded before it is traced, and the erosion is what removes
tails.** A speech bubble's tail is a thin spike of interior; eroding by a
few percent of the room's size cuts it off, and the largest component that
still meets the text block is the body. The same erosion keeps glyphs off the
border, so the ladder's own inset is redundant inside a room -- it is still
applied, and costs a percent.
"""

from __future__ import annotations

import numpy as np

from .group import bbox

# How far past the text block the flood may look, each side: the larger of a
# multiple of the block's own size and a fraction of the page. The multiple
# alone was wrong -- a tategaki column sits at the RIGHT of its bubble, so the
# interior runs three or four block-widths to the left of it and a window of
# three widths cut every smoke bubble off at the window edge.
REACH_X = 3.0  # block widths
REACH_Y = 1.0  # block heights
REACH_PAGE_X = 0.40  # of page width
REACH_PAGE_Y = 0.25  # of page height

WALL_THRESHOLD = 160  # gray below this is border ink or tone, and stops the flood
WALL_DILATE_PX = 2  # closes halftone gaps; a 5x5 kernel
MARGIN_FRAC = 0.05  # of the room's smaller side, eroded before tracing
MARGIN_MIN_PX = 4
CONTAIN_MIN = 0.80  # the traced room must still hold this much of the text block
SOLIDITY_MIN = 0.80  # body area over its convex hull's: a bubble is round, a leak is not
AREA_MAX = 20.0  # body area over the block's: past this the flood found a panel, not a bubble
SIMPLIFY_FRAC = 0.01  # approxPolyDP epsilon, of the contour's perimeter


def room(page, points, others=()) -> list[tuple[float, float]] | None:
    """The bubble interior around `points` on the CLEANED page, or None.

    `page` is the page after inpaint -- the text block is already white, so
    it seeds the flood. `others` are the page's other regions: their erased
    quads are white too, and on page 010 two of them bridged a bubble to the
    box art beside it, so they are walls here. Returns a polygon in page
    coordinates that contains (>= CONTAIN_MIN of) the block, sits inside the
    bubble's border with a margin, is round enough to be a bubble and not a
    panel the flood escaped into, and never reaches the window this function
    allows itself; or None, meaning "use the block as it is".
    """
    import cv2  # noqa: PLC0415 -- detect.py's dependency, loaded on first use

    x0, y0, x1, y1 = bbox(points)
    w, h = x1 - x0, y1 - y0
    if w <= 0 or h <= 0:
        return None
    page_w, page_h = page.size
    reach_x = max(REACH_X * w, REACH_PAGE_X * page_w)
    reach_y = max(REACH_Y * h, REACH_PAGE_Y * page_h)
    wx0 = max(0, int(x0 - reach_x))
    wy0 = max(0, int(y0 - reach_y))
    wx1 = min(page_w, int(x1 + reach_x) + 1)
    wy1 = min(page_h, int(y1 + reach_y) + 1)
    if wx1 - wx0 < 3 or wy1 - wy0 < 3:
        return None

    gray = np.asarray(page.convert("L").crop((wx0, wy0, wx1, wy1)))
    wall = (gray < WALL_THRESHOLD).astype(np.uint8)
    for other in others:
        cv2.fillPoly(wall, [np.array([(px - wx0, py - wy0) for px, py in other], np.int32)], 1)
    k = 2 * WALL_DILATE_PX + 1
    wall = cv2.dilate(wall, np.ones((k, k), np.uint8))

    block = np.zeros(gray.shape, np.uint8)
    cv2.fillPoly(block, [np.array([(px - wx0, py - wy0) for px, py in points], np.int32)], 1)
    # The block may carry residual ink the erase missed; the seed is its
    # free part, and a block with no free pixel has nothing to grow from.
    seed = (block == 1) & (wall == 0)
    if not seed.any():
        return None

    _, labels = cv2.connectedComponents((wall == 0).astype(np.uint8), connectivity=4)
    touched = set(np.unique(labels[seed])) - {0}
    flooded = np.isin(labels, list(touched))

    # A flood that reached the window found no border: not a room. A window
    # side that is also the page edge is treated the same way -- a bubble
    # interior that runs off the page is far more likely a missing border.
    if flooded[0, :].any() or flooded[-1, :].any() or flooded[:, 0].any() or flooded[:, -1].any():
        return None

    ys, xs = np.nonzero(flooded)
    rw, rh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    margin = max(MARGIN_MIN_PX, int(round(MARGIN_FRAC * min(rw, rh))))
    km = 2 * margin + 1
    eroded = cv2.erode(flooded.astype(np.uint8), np.ones((km, km), np.uint8))

    # Erosion severs tails and bridges; keep the body -- the largest piece
    # that still meets the text block.
    n, labels = cv2.connectedComponents(eroded, connectivity=4)
    best, best_area = 0, 0
    for label in range(1, n):
        piece = labels == label
        if (piece & (block == 1)).any() and piece.sum() > best_area:
            best, best_area = label, int(piece.sum())
    if not best:
        return None
    body = (labels == best).astype(np.uint8)
    block_area = int((block == 1).sum())
    if body[block == 1].sum() < CONTAIN_MIN * block_area:
        return None

    contours, _ = cv2.findContours(body, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    # A flood that slipped through an open side into the panel comes back as
    # an L or a T around the bubble: large, and hollow against its own hull.
    area = cv2.contourArea(contour)
    hull_area = cv2.contourArea(cv2.convexHull(contour))
    if area > AREA_MAX * block_area or hull_area <= 0 or area / hull_area < SOLIDITY_MIN:
        return None
    eps = SIMPLIFY_FRAC * cv2.arcLength(contour, True)
    poly = cv2.approxPolyDP(contour, eps, True).reshape(-1, 2)
    if len(poly) < 3:
        return None
    return [(float(px + wx0), float(py + wy0)) for px, py in poly]

