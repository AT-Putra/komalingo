"""Group column-level detections into one region per bubble. Phase 2b.

WHY this exists, from the picture that forced it. The DB detector answers "is
this text" per text LINE, and a line of vertical Japanese is a column. A
bubble of tategaki therefore comes back as one quad per column, plus nested
quads (the whole text block AND its columns, at the same scale) and, on small
crops, glyph-sized fragments. Phase 2a's engine was then handed each column
alone: OCR'd alone, translated alone, typeset alone. On real page 010 one
sentence arrived as six regions and left the page as "don't / really / play /
it / in VR / hist game / sold on", with neighbouring columns painting over
each other and four fit_failed regions the ladder could do nothing about --
no rung fits an English sentence into a 34px column. AC-1 says the English
fits inside the BUBBLE, so the engine has to be handed the bubble.

It is also the granularity Phase 1 measured. check_tategaki's CER of 0.0022
was taken over bubble crops -- several columns per image -- and the pipeline
had been running OCR on single columns, which nothing had measured at all.

Three rules decide that two boxes belong together, on axis-aligned bboxes.
Distances are in units of the PAGE'S GLYPH -- the median short side over
every quad on the page, which is the column width for tategaki and the line
height for horizontal text -- never of a quad's own extent:

  nested       >= CONTAIN of the smaller box's area lies inside the larger.
  side by side y-overlap >= OVERLAP of the shorter, x-gap <= GAP glyphs.
  stacked      x-overlap >= OVERLAP of the narrower, y-gap <= GAP glyphs.

and for either of the last two the quads' own short sides must be within
RATIO of each other. The unit matters, and it took two tries. The first
version measured a stacked gap against the quads' HEIGHTS, and on page 012
that merged two bubbles: the columns of one stood 60px above the columns of
the other, less than a column's 200px height. The second used each quad's
own short side, and the same two bubbles merged again, because the net had
returned one 86px-wide quad for two columns and its short side was two
glyphs. The page's median short side is one glyph whatever any single quad
did: pieces of one column sit within a glyph or so of each other, and two
bubbles stand two or more apart, with a border and a gutter in between --
GAP sits at 1.5, between the two.

Two clauses keep art text out of bubbles, and page 010's box-art title --
a 275px quad rotated 14 degrees, beside a bubble on either side -- needed
both. RATIO: real columns of one bubble are within ~2x of each other in
glyph size, furigana fragments sit at about half, so 0.3 keeps them and
drops a title whose short side is four columns wide. TILT: a quad rotated
more than TILT_DEG off the axes is not a column or a line of dialogue, and
its bbox is inflated by the rotation -- the title's bbox stood 19px from
the next bubble's block while the title itself was 60px away -- so a tilted
quad joins a block only by being nested inside it, never by adjacency.

A quad's POLARITY -- dark glyphs on a light ground, or light glyphs on a
dark one -- is a third guard, and the caller supplies it because only the
caller has the pixels. Page 012's clock reads "23:45" in white on black one
glyph to the left of a bubble, and by geometry alone its digits are another
column of that bubble. Nothing in one bubble is set in both polarities.

INK between two boxes is the fourth guard, and like polarity the caller
supplies it because only the caller has the pixels. GAP measures distance
and a bubble border is thin: on a real page (the stairwell, 006) the last
column of one bubble stood 28px above the first column of the bubble in the
NEXT PANEL, same x, a glyph of 45px -- through a bubble outline, a panel
border, the gutter, another border and another outline -- and the stacked
rule read it as one column split in two. Two panels' dialogue became one
bubble's, and the second panel was left blank. Same page, other corner: a
line of narration 45px left of a bubble merged into the bubble through its
outline. No distance separates those cases from a genuine split column;
the ink does. `separated(i, j)` answers whether ink runs across the gap
between two adjacent boxes -- detect.py casts rays across it -- and a pair
it says yes to may nest, never neighbour.

Groups are the transitive closure -- union-find over every pair -- followed
by one absorb pass for a group whose bbox mostly sits inside another's, which
catches a fragment that failed every pairwise rule against its neighbours
but is plainly inside the bubble they form. The merged polygon is the CONVEX
HULL of the members' points, not their bbox: a bubble's columns differ in
height, and the hull follows the bubble's curve where a bbox would reach
past its border ink into the panel.
"""

from __future__ import annotations

import math

CONTAIN = 0.70  # nested: this much of the smaller box inside the larger
OVERLAP = 0.50  # neighbours: shared extent on the axis they line up on
GAP = 1.50  # neighbours: gap on the other axis, in page glyphs -- see glyph_unit
RATIO = 0.30  # neighbours: smaller/larger glyph size
ABSORB = 0.50  # second pass: a group mostly inside another group's bbox joins it
TILT_DEG = 12.0  # a quad rotated past this joins a block by nesting only


def bbox(points) -> tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def _inside(a, b) -> float:
    """Fraction of the SMALLER of a and b that lies inside the other."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ov_x = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    ov_y = max(0.0, min(ay1, by1) - max(ay0, by0))
    smaller = min((ax1 - ax0) * (ay1 - ay0), (bx1 - bx0) * (by1 - by0))
    return (ov_x * ov_y) / smaller if smaller > 0 else 0.0


def tilt(points) -> float:
    """Degrees the polygon's longest edge sits off the nearer axis, in [0, 45]."""
    best, best_len = 0.0, -1.0
    n = len(points)
    for i in range(n):
        (xa, ya), (xb, yb) = points[i], points[(i + 1) % n]
        length = math.hypot(xb - xa, yb - ya)
        if length > best_len:
            best_len = length
            best = abs(math.degrees(math.atan2(yb - ya, xb - xa))) % 90
    return min(best, 90 - best)


def glyph_unit(boxes) -> float:
    """The page's glyph: the median short side over its quads."""
    sides = sorted(min(x1 - x0, y1 - y0) for x0, y0, x1, y1 in boxes)
    if not sides:
        return 0.0
    mid = len(sides) // 2
    return sides[mid] if len(sides) % 2 else (sides[mid - 1] + sides[mid]) / 2


def neighbours(a, b, unit: float, apart: bool = False) -> bool:
    """Do two bboxes belong to the same text block?

    `unit` is the page's glyph (glyph_unit); `apart` says the pair may only
    nest, never neighbour -- one is tilted, or their polarities differ.
    """
    if _inside(a, b) >= CONTAIN:
        return True
    if apart:
        return False
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    wa, ha, wb, hb = ax1 - ax0, ay1 - ay0, bx1 - bx0, by1 - by0
    glyph_a, glyph_b = min(wa, ha), min(wb, hb)
    if min(glyph_a, glyph_b) < RATIO * max(glyph_a, glyph_b):
        return False
    reach = GAP * unit
    ov_y = min(ay1, by1) - max(ay0, by0)
    ov_x = min(ax1, bx1) - max(ax0, bx0)
    gap_x = max(ax0, bx0) - min(ax1, bx1)
    gap_y = max(ay0, by0) - min(ay1, by1)
    side_by_side = ov_y >= OVERLAP * min(ha, hb) and gap_x <= reach
    stacked = ov_x >= OVERLAP * min(wa, wb) and gap_y <= reach
    return side_by_side or stacked


def convex_hull(points) -> list[tuple[float, float]]:
    """Andrew's monotone chain. Counter-clockwise, no collinear points."""
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def group(polygons, inverse=None, separated=None) -> list[list[int]]:
    """Partition polygon indices into text blocks. Order: by first member index.

    `inverse[i]` is True for a quad of light glyphs on a dark ground; two
    quads of different polarity never neighbour (they may still nest). None
    means unknown for all, and polarity is not consulted.

    `separated(i, j)` is True when ink runs across the gap between two
    boxes -- a bubble outline, a panel border. Such a pair never neighbours
    either; it may still nest, because a quad inside another is inside it
    whatever is drawn around them. None means no pixels were consulted.

    Returns index lists rather than merged polygons so the caller can carry
    whatever else it holds per member -- detect.py keeps the strongest
    confidence -- and so the gate can assert WHICH quads were merged, not
    only how many groups remain.
    """
    boxes = [bbox(p) for p in polygons]
    tilted = [tilt(p) > TILT_DEG for p in polygons]
    unit = glyph_unit(boxes)
    n = len(boxes)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            apart = tilted[i] or tilted[j] or (inverse is not None and inverse[i] != inverse[j])
            if not neighbours(boxes[i], boxes[j], unit, apart):
                continue
            # Adjacent, not nested, and drawn apart: the ink guard. Consulted
            # last because it is the only rule that costs pixels.
            if (separated is not None and _inside(boxes[i], boxes[j]) < CONTAIN
                    and separated(i, j)):
                continue
            parent[find(i)] = find(j)

    members: dict[int, list[int]] = {}
    for i in range(n):
        members.setdefault(find(i), []).append(i)
    groups = sorted(members.values(), key=lambda g: g[0])

    # Absorb pass, on GROUP bboxes: a fragment that lined up with none of its
    # neighbours pairwise can still sit inside the block they form together.
    # Smallest first, so a fragment joins the block rather than a block
    # joining a fragment; one pass, because a block that absorbed a fragment
    # has not grown enough to change any other verdict.
    gboxes = [bbox([pt for i in g for pt in polygons[i]]) for g in groups]
    areas = [(x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in gboxes]
    order = sorted(range(len(groups)), key=areas.__getitem__)
    absorbed: set[int] = set()
    for k in order:
        for other in order:
            if other == k or other in absorbed:
                continue
            if areas[other] > areas[k] and _inside(gboxes[k], gboxes[other]) >= ABSORB:
                groups[other] = groups[other] + groups[k]
                absorbed.add(k)
                break
    return [sorted(g) for k, g in enumerate(groups) if k not in absorbed]


def merge(polygons, inverse=None, separated=None) -> list[tuple[list[tuple[float, float]], list[int]]]:
    """(hull polygon, member indices) per text block."""
    return [(convex_hull([pt for i in g for pt in polygons[i]]), g)
            for g in group(polygons, inverse, separated)]
