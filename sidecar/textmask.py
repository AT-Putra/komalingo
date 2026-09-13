"""Which PIXELS are text: comic-text-detector's segmentation head.

WHY a second model when detect.py has already found the text. detect.py
answers "where is a line of text" with a quad, and a quad is a rectangle
around glyphs -- the art between and behind them included. Erasing the quad
is what the inpainter did until Phase 2c: every SFX laid over a character,
every caption on screentone, every bubble the artist drew half-transparent
came out as a white box with the English on it. What the eraser needs is the
glyphs themselves, and that is a per-pixel question a box detector cannot
answer and a threshold cannot either (outlined SFX are white letters with a
black edge; text on a black bubble is white). comic-text-detector was trained
to answer exactly it: its `seg` output is a text probability per pixel.

Only `seg` is used. Its `blk` and `det` heads find blocks and lines too, but
grouping, reading order and both OCR engines are tuned to detect.py's quads,
and the mask is intersected with those quads downstream -- so this model
decides nothing about WHAT is text, only which pixels of the text detect.py
kept are ink.

The input is letterboxed into the model's square with the page at the TOP
LEFT, so the valid part of the output is a plain crop with no offset to undo.
"""

from __future__ import annotations

import numpy as np

from . import models

WEIGHTS = "comic-text-detector"
SIZE = 1024  # the exported graph's fixed input side
THRESHOLD = 0.3  # seg is a sigmoid; manga text sits well above this, tone well below

_SESSION = None


class EraseError(RuntimeError):
    """The erase stage cannot run. Carries (reason, kind) like DetectError.

    Shared by this module and inpainter.py, so main.py's one "name the
    failure, let the UI branch on kind" handler covers the whole stage.
    """

    def __init__(self, reason: str, kind: str = "error"):
        self.reason = reason
        self.kind = kind  # network | checksum | space | weights | config | error
        super().__init__(reason)


def session(weights: str, progress=None):
    """An onnxruntime session for MANIFEST entry `weights`, with named failures.

    Not cached here: the caller owns the cache, because models.ensure re-hashes
    hundreds of megabytes on every call and a page must not pay that twice.
    """
    try:
        path = models.ensure(weights, progress)
    except models.FetchError as e:
        raise EraseError(f"{weights} weights unavailable: {e.reason}", e.kind) from None
    try:
        return models.onnx_session(path)
    except ImportError as e:
        raise EraseError(f"onnxruntime is not installed ({e.name}); cannot erase text", "config") from None
    except Exception as e:  # noqa: BLE001 -- onnxruntime raises its own untyped errors
        # A truncated or wrong-architecture file lands here, not in the
        # checksum branch, because the checksum already passed.
        raise EraseError(f"cannot load {weights} from {path}: {e}", "weights") from None


def _model():
    """The loaded detector, cached. Lock-free lazy global, as in detect.py:
    the pipeline calls it under _MODEL_LOCK."""
    global _SESSION
    if _SESSION is None:
        _SESSION = session(WEIGHTS)
    return _SESSION


def probability(rgb: np.ndarray) -> np.ndarray:
    """Text probability per pixel, float32 in [0, 1], the page's own (H, W)."""
    import cv2  # noqa: PLC0415 -- detect.py's dependency, loaded on first use

    h, w = rgb.shape[:2]
    scale = SIZE / max(h, w)
    nh, nw = max(1, round(h * scale)), max(1, round(w * scale))
    canvas = np.zeros((SIZE, SIZE, 3), np.uint8)
    canvas[:nh, :nw] = cv2.resize(rgb, (nw, nh),
                                  interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    x = canvas.transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    session = _model()
    try:
        seg = session.run(["seg"], {"images": x})[0][0, 0, :nh, :nw]
    except Exception as e:  # noqa: BLE001 -- onnxruntime raises its own untyped errors
        # Out of GPU memory, a provider fault: named, like detect.py's forward
        # pass, so the page fails with a reason instead of a bare 500.
        raise EraseError(f"text-mask forward pass failed: {e}", "error") from None
    return cv2.resize(seg, (w, h), interpolation=cv2.INTER_LINEAR)


def mask(rgb: np.ndarray, threshold: float = THRESHOLD) -> np.ndarray:
    """Boolean (H, W): True where the model reads text ink."""
    return probability(rgb) > threshold
