"""Text-region detection: a DB (differentiable-binarisation) net through cv2.dnn.

WHY a learned detector and not image processing. The obvious cheap answer --
threshold the page, take connected components, call the big white blobs
speech bubbles -- was tried in Phase 0a and is dead. A manga page is mostly
white, so the page background IS one connected component and the whole page
comes back as a single "bubble". No amount of morphology parameter tuning
moves that; the failure is structural, not tuned. So the detector has to be a
model that was trained to answer "is this text", and the cheapest such model
that ships inside OpenCV's own dnn module is DB.

WHY this checkpoint. PP-OCRv3's Chinese detection head IS a DB model -- same
probability-map-plus-unclip head cv2.dnn.TextDetectionModel_DB implements --
and it is trained on CJK, which is what a Japanese page is made of. It is
2.4 MB, so first launch does not cost the user a 100 MB download before the
app does anything. The pre-processing constants below are lifted verbatim
from opencv_zoo's own ppocr_det.py; they are not free parameters.

WHY two scales, BOTH run. DB detects at one input resolution and small
glyphs vanish when the page is downscaled to it. The first version ran the
fine scale only as a retry when the coarse one found nothing, on the theory
that a dialogue page has plenty of text at the coarse scale and only a cover
with a lone volume number needs the fine one. A real page (the stairwell,
006) refuted it: nine blocks found at 1408 and the tenth -- a caption of four
glyphs beside a character's black hair, ordinary 45px text -- found at 1984
with confidence 0.99 and at 1408 not at all. The retry never ran because the
page was not empty, and a bubble went untranslated. Recall is the product
here; the second forward pass costs well under a second on a CPU against
the seconds of OCR and provider round trip that follow it. Quads the two
scales agree on are the same text twice, and _dedupe keeps one.

Every failure path names its reason, the same contract models.py holds to:
"detection failed" tells the user nothing about whether to check their
network, their disk, or their settings.
"""

from __future__ import annotations

import os

import numpy as np

from . import group, models
from .region import Region

# The env flag. Unset means dbnet -- the flag exists so a future detector can
# be selected without a code change, not so the default can be guessed at.
ENV_FLAG = "MT_DETECTOR"
DBNET = "dbnet"
CTD = "ctd"

WEIGHTS = "text-detection-db"

# Verbatim from opencv_zoo models/text_detection_ppocr/ppocr_det.py. The mean
# is applied in the order the model was trained with, against the BGR array
# cv2 decodes -- copying the zoo's channel handling exactly, because a
# silently swapped R and B costs recall rather than raising.
_MEAN = (123.675, 116.28, 103.53)
_STD = np.array([0.229, 0.224, 0.225])
_BINARY_THRESHOLD = 0.3
_POLYGON_THRESHOLD = 0.5
_UNCLIP_RATIO = 2.0
_MAX_CANDIDATES = 200

# Long-side targets, coarse first. Both are multiples of 32 after the aspect
# fit below, which the backbone's five downsampling stages require.
_SCALES = (1408, 1984)

# A quad thinner than this in either axis cannot hold a glyph, and downstream
# an empty crop is an exception rather than an empty OCR result.
_MIN_SIDE = 4

# Two scales' quads over the same text, judged per axis rather than by IoU.
# Along the text's LONG axis -- the reading direction -- the two must cover
# the same span: SPAN of the longer extent. IoU could not tell this: a quad
# over the second word of a Korean line had IoU 0.69 with the whole line and
# a quad the coarse scale drew 1.5 glyphs wide had 0.64 with the fine one
# over the same column; the word is a PART, the wide quad a duplicate, and
# only the axis says which. On the SHORT axis the two must be the same
# line or column -- overlapping by SIDE of the smaller, and within WIDTH of
# each other in extent, so a whole-block quad is never "the same" as one of
# its columns (that pair is for grouping to nest and ocr_cjk.lines to sort
# out). Conservative on purpose: a missed duplicate costs one extra part
# that nesting absorbs, a wrong one costs the text it held.
_SAME_SPAN = 0.8
_SAME_SIDE = 0.7
_SAME_WIDTH = 0.6

# The ink guard group.py applies (see its docstring). Gray below INK is ink:
# outlines and panel borders are near black, screentone is lighter. Rays are
# cast across the gap between two adjacent quads, one per pixel of their
# shared extent widened by a glyph each side; a border or outline crosses
# every one, a stray glyph tail a few. BLOCKED is the share that means a
# line runs between them. The widening is what tells the two apart: a glyph
# is one glyph wide, a border keeps going.
_INK = 110
_BLOCKED = 0.5

_MODEL = None


class DetectError(RuntimeError):
    """Always carries a reason a user can act on.

    Mirrors models.FetchError deliberately: a caller that already knows how to
    show one of these does not need a second display path for the other. A
    FetchError raised underneath is re-raised as this with its kind intact.
    """

    def __init__(self, reason: str, kind: str = "error"):
        self.reason = reason
        self.kind = kind  # network | checksum | space | weights | config | error
        super().__init__(reason)


def selected(detector: str | None = None) -> str:
    """Resolve the detector name, or raise with the reason it cannot be used.

    An unknown or unavailable value fails here. It does NOT fall back to the
    default: a user who set MT_DETECTOR and got the default anyway has been
    told their setting worked when it did not.
    """
    name = (detector if detector is not None else os.environ.get(ENV_FLAG, "")).strip().lower()
    if not name:
        return DBNET
    if name == DBNET:
        return DBNET
    if name == CTD:
        raise DetectError(
            f"{ENV_FLAG}={CTD} is not available in this build: comic-text-detector "
            f"is not published on PyPI (Phase 0a finding), so its path was never "
            f"built. Unset {ENV_FLAG} to use {DBNET}.",
            "config",
        )
    raise DetectError(
        f"unknown {ENV_FLAG}={name!r}; known detectors are {DBNET!r} (and {CTD!r}, "
        f"which is not built)",
        "config",
    )


def weights(progress=None) -> str:
    """Path to the DB weights, downloading them on first use.

    Raises DetectError -- never a bare FetchError -- so one except clause
    covers everything this module can go wrong with.
    """
    try:
        return models.ensure(WEIGHTS, progress)
    except models.FetchError as e:
        raise DetectError(f"detector weights unavailable: {e.reason}", e.kind) from None


def _model(progress=None):
    """The loaded net, cached.

    The cache also spares the weights check: models.fetch re-hashes the file
    on every call to prove it is the pinned one, and 2.4 MB of SHA-256 per
    page is a cost with nothing to buy -- the file cannot change under a
    running process.

    ponytail: a lock-free lazy global, matching ocr_ja.py -- the pipeline is
    single-threaded. Ceiling: two threads racing here would each build a net
    and one would be discarded. Upgrade path: a lock, if concurrent pages are
    introduced.
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    path = weights(progress)

    try:
        import cv2  # noqa: PLC0415 -- import cost is paid on first detect, not on import
    except ImportError as e:
        raise DetectError(f"opencv is not installed ({e.name}); cannot detect text", "config") from None

    try:
        net = cv2.dnn.TextDetectionModel_DB(cv2.dnn.readNet(path))
    except cv2.error as e:
        # A truncated or wrong-architecture file gets here, not to the
        # checksum branch, because the checksum already passed.
        raise DetectError(f"cannot load detector weights at {path}: {e}", "weights") from None

    net.setBinaryThreshold(_BINARY_THRESHOLD)
    net.setPolygonThreshold(_POLYGON_THRESHOLD)
    net.setUnclipRatio(_UNCLIP_RATIO)
    net.setMaxCandidates(_MAX_CANDIDATES)
    _MODEL = net
    return net


def _as_bgr(img) -> np.ndarray:
    """A cv2-shaped BGR array from a PIL image, an array, or a path."""
    import cv2  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    if isinstance(img, Image.Image):
        return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    if isinstance(img, np.ndarray):
        if img.ndim == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img
    # np.fromfile, not cv2.imread: imread cannot open a non-ASCII path on
    # Windows and returns None rather than raising, which reads as "no text".
    from . import atomic  # noqa: PLC0415

    data = np.fromfile(atomic.long_path(img), dtype=np.uint8)
    decoded = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if decoded is None:
        raise DetectError(f"cannot decode image at {img}", "error")
    return decoded


def _input_size(width: int, height: int, long_side: int) -> tuple[int, int]:
    """(w, h) for the net: aspect kept, both axes snapped to a multiple of 32."""
    scale = long_side / max(width, height)
    return (
        max(32, int(round(width * scale / 32)) * 32),
        max(32, int(round(height * scale / 32)) * 32),
    )


def _run(net, bgr: np.ndarray, size: tuple[int, int]):
    """One forward pass at one input size. Returns (quads, confidences).

    The mean and scale are re-set with every size because setInputSize resets
    the blob parameters underneath -- the zoo's own wrapper does the same.
    """
    import cv2  # noqa: PLC0415

    net.setInputSize(size)
    net.setInputMean(_MEAN)
    net.setInputScale(1.0 / 255.0 / _STD)
    try:
        return net.detect(cv2.resize(bgr, size))
    except cv2.error as e:
        raise DetectError(f"detector forward pass failed at {size}: {e}", "error") from None


def _quad_to_polygon(quad, sx: float, sy: float, width: int, height: int) -> list[list[int]]:
    """Net-space quad -> page-space polygon, clamped to the page.

    sx and sy are separate: snapping both axes to a multiple of 32 does not
    preserve the aspect ratio exactly, and one shared factor would skew every
    polygon by up to a percent.
    """
    return [
        [
            min(width - 1, max(0, int(round(float(x) * sx)))),
            min(height - 1, max(0, int(round(float(y) * sy)))),
        ]
        for x, y in quad
    ]


def _reading_order(polygon, band: int) -> tuple[int, int]:
    """Sort key: top band first, then right to left inside the band.

    The band exists because a bubble of vertical Japanese comes back as
    several columns that start at almost -- not exactly -- the same y. Sorting
    on raw y would interleave them by a few pixels of noise and destroy the
    right-to-left order the lines are actually read in.

    ponytail: a band heuristic, not reading order. Ceiling: it is right for a
    page whose panels stack in rows and wrong for a page with one tall panel
    beside two short ones, because it never sees the panels at all. Upgrade
    path: panel segmentation feeds real order in Phase 1b. It is here now
    because region ids have to be assigned in SOME stable order, and
    right-to-left top-to-bottom is the one a Japanese page is written in.
    """
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return (min(ys) // band, -max(xs))


def quads(img, detector: str | None = None, progress=None) -> list[tuple[list[list[int]], float]]:
    """The net's own answer: one (polygon, confidence) per text LINE, ungrouped.

    Public so a gate can measure what grouping changed against what the net
    said -- a grouping assert that cannot see the ungrouped quads cannot show
    that it discriminates.
    """
    selected(detector)  # raises before any download if the flag is unusable
    net = _model(progress)
    bgr = _as_bgr(img)
    height, width = bgr.shape[:2]

    found: list[tuple[list[list[int]], float]] = []
    for long_side in _SCALES:
        size = _input_size(width, height, long_side)
        raw, confidences = _run(net, bgr, size)
        sx, sy = width / size[0], height / size[1]
        for quad, confidence in zip(raw, confidences, strict=False):
            polygon = _quad_to_polygon(quad, sx, sy, width, height)
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            if max(xs) - min(xs) < _MIN_SIDE or max(ys) - min(ys) < _MIN_SIDE:
                continue
            found.append((polygon, float(confidence)))
    return _dedupe(found)


def _dedupe(found):
    """One quad per piece of text: of two that _same_text says are one line
    or column seen at both scales, keep the EARLIER -- the coarse scale's.

    Needed because both scales run: ocr_cjk reads a region's PARTS one by
    one, and a column seen at two scales would be read, and joined, twice.

    Coarse wins, not the more confident: the two scales' confidences differ
    in the second decimal and say nothing, while the coarse quad is the one
    every gate was measured against. Keeping it makes the fine scale purely
    additive -- what the coarse pass found reads exactly as before, and only
    what it missed is new. Preferring the fine quad moved a Korean crop's
    edge by a few pixels and turned 넌 into 년.
    """
    boxes = [group.bbox(polygon) for polygon, _ in found]
    keep = [True] * len(found)
    for i in range(len(found)):
        if not keep[i]:
            continue
        for j in range(i + 1, len(found)):
            if keep[j] and _same_text(boxes[i], boxes[j]):
                keep[j] = False
    return [entry for entry, k in zip(found, keep, strict=True) if k]


def _same_text(a, b) -> bool:
    """Do two bboxes cover the same line or column? See _SAME_SPAN."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    wa, ha, wb, hb = ax1 - ax0, ay1 - ay0, bx1 - bx0, by1 - by0
    ov_x = min(ax1, bx1) - max(ax0, bx0)
    ov_y = min(ay1, by1) - max(ay0, by0)
    if ov_x <= 0 or ov_y <= 0:
        return False
    # The longer box's orientation decides which axis reads.
    horizontal = max(wa, wb) >= max(ha, hb)
    span_ov, span_a, span_b = (ov_x, wa, wb) if horizontal else (ov_y, ha, hb)
    side_ov, side_a, side_b = (ov_y, ha, hb) if horizontal else (ov_x, wa, wb)
    return (span_ov >= _SAME_SPAN * max(span_a, span_b)
            and side_ov >= _SAME_SIDE * min(side_a, side_b)
            and min(side_a, side_b) >= _SAME_WIDTH * max(side_a, side_b))


def detect(img, detector: str | None = None, progress=None) -> list[Region]:
    """Text regions on one page, as Regions carrying polygon and confidence.

    ids are 1-based and assigned after sorting, so the same page always gets
    the same ids. text and translation are left empty: filling them is ocr.py
    and llm.py's job, and a detector that guessed at them would be lying.

    Phase 2b: one region per BUBBLE, not per column. DB answers per text
    line, and a line of tategaki is a column, so a bubble arrived here as
    several quads -- each then OCR'd, translated and typeset on its own.
    group.py merges them; the polygon becomes the members' convex hull and
    the confidence the strongest member's. See group.py for the picture that
    forced this.
    """
    bgr = _as_bgr(img)  # once; quads() accepts the array as-is
    found = quads(bgr, detector, progress)
    polygons = [polygon for polygon, _ in found]
    inverse = _inverse(bgr, polygons)
    blocks = [
        ([[int(round(x)), int(round(y))] for x, y in hull],
         max(found[i][1] for i in members),
         _glyph_px([found[i][0] for i in members]),
         [found[i][0] for i in members])
        for hull, members in group.merge(polygons, inverse, _separator(bgr, polygons, inverse))
    ]

    band = max(1, bgr.shape[0] // 24)  # about one line of dialogue on a manga page
    blocks.sort(key=lambda entry: _reading_order(entry[0], band))
    return [
        Region(id=i, polygon=polygon, confidence=confidence, glyph_px=glyph, parts=parts)
        for i, (polygon, confidence, glyph, parts) in enumerate(blocks, start=1)
    ]


def _inverse(bgr: np.ndarray, polygons) -> list[bool]:
    """Per quad: light glyphs on a dark ground? (mean gray inside under 128)

    The polarity guard group.py applies: a clock reading "23:45" in white on
    black one glyph from a bubble is, by geometry, another column of it.
    """
    import cv2  # noqa: PLC0415

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    out = []
    for polygon in polygons:
        mask = np.zeros(gray.shape, np.uint8)
        cv2.fillPoly(mask, [np.array(polygon, np.int32)], 1)
        inside = gray[mask == 1]
        out.append(bool(inside.size) and float(inside.mean()) < 128)
    return out


def _separator(bgr: np.ndarray, polygons, inverse) -> "callable":
    """separated(i, j): does ink run across the gap between two adjacent quads?

    The ink guard group.py applies -- see its docstring for the page that
    needed it. Rays are cast from one bbox to the other across the gap that
    separates them, along the axis of that gap, one ray per pixel of their
    shared extent on the other axis widened by a page glyph each side. A
    bubble outline or a panel border crosses every ray; a glyph tail poking
    into the gap crosses a few; the widening keeps a glyph-wide mark -- a
    dash between two pieces of one column -- under _BLOCKED, because a glyph
    is one glyph wide and a border keeps going.

    Two quads of light-on-dark text sit on ink by definition, so the guard
    stands aside for them: polarity already keeps them from joining anything
    of the other kind, and between two of the same kind there is nothing a
    ray could tell.
    """
    import cv2  # noqa: PLC0415

    ink = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) < _INK
    height, width = ink.shape
    boxes = [group.bbox(p) for p in polygons]
    widen = int(round(group.glyph_unit(boxes)))

    def separated(i: int, j: int) -> bool:
        if inverse[i] or inverse[j]:
            return False
        ax0, ay0, ax1, ay1 = boxes[i]
        bx0, by0, bx1, by1 = boxes[j]
        gap_x = max(ax0, bx0) - min(ax1, bx1)
        gap_y = max(ay0, by0) - min(ay1, by1)
        if gap_x <= 0 and gap_y <= 0:
            return False  # overlapping: nothing lies between them
        if gap_x >= gap_y:
            # Side by side: rays run left-right across the x gap, one per row.
            x0, x1 = int(min(ax1, bx1)), int(max(ax0, bx0))
            y0, y1 = int(max(ay0, by0)) - widen, int(min(ay1, by1)) + widen
            band = ink[max(0, y0):min(height, y1), max(0, x0):min(width, x1)]
            hit = band.any(axis=1)
        else:
            # Stacked: rays run top-bottom across the y gap, one per column.
            y0, y1 = int(min(ay1, by1)), int(max(ay0, by0))
            x0, x1 = int(max(ax0, bx0)) - widen, int(min(ax1, bx1)) + widen
            band = ink[max(0, y0):min(height, y1), max(0, x0):min(width, x1)]
            hit = band.any(axis=0)
        return bool(hit.size) and float(hit.mean()) >= _BLOCKED

    return separated


def _glyph_px(members) -> int:
    """The source glyph size: the median short side of a block's quads.

    A tategaki column is one glyph wide, a line of horizontal text one glyph
    tall, and a glyph fragment is one glyph both ways -- so the short side of
    every quad is about the glyph, and the median is robust to the one
    whole-block quad the net also returns.
    """
    sides = sorted(min(x1 - x0, y1 - y0) for x0, y0, x1, y1 in map(group.bbox, members))
    return int(round(sides[len(sides) // 2])) if sides else 0
