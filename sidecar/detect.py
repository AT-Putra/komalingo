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

WHY a scale ladder. DB detects at one input resolution and small glyphs
vanish when the page is downscaled to it. A dialogue page has plenty of text
at the coarse scale, but a colour cover whose only text is a single volume
number needs the fine one. Running every page at the fine scale doubles the
cost of the common case to serve the rare one, so the fine scale is a RETRY,
entered only when the coarse scale found nothing.

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
        if found:
            break  # the coarse scale answered; the fine scale is the retry
    return found


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
    blocks = [
        ([[int(round(x)), int(round(y))] for x, y in hull],
         max(found[i][1] for i in members),
         _glyph_px([found[i][0] for i in members]),
         [found[i][0] for i in members])
        for hull, members in group.merge(polygons, _inverse(bgr, polygons))
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


def _glyph_px(members) -> int:
    """The source glyph size: the median short side of a block's quads.

    A tategaki column is one glyph wide, a line of horizontal text one glyph
    tall, and a glyph fragment is one glyph both ways -- so the short side of
    every quad is about the glyph, and the median is robust to the one
    whole-block quad the net also returns.
    """
    sides = sorted(min(x1 - x0, y1 - y0) for x0, y0, x1, y1 in map(group.bbox, members))
    return int(round(sides[len(sides) // 2])) if sides else 0
