"""Japanese OCR with confidence and blank-crop gates.

Model output is canonicalised before it leaves this module, not inside the
test that grades it. manga-ocr spells the printed ellipsis glyph as three
fullwidth full stops and Latin runs as fullwidth letters; the page shows one
"…" and "VR". Folding those here means the gate measures what the pipeline
actually hands to translation, instead of a gate that quietly disagrees with
production about what the OCR said.

The fold is deliberately narrow -- ellipsis runs and fullwidth alphanumerics,
nothing else. A blanket NFKC would also rewrite the wave dash and the CJK
punctuation the artwork really does print.
"""

from __future__ import annotations

import re

import numpy as np
from PIL import Image

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from manga_ocr import MangaOcr

        from . import models

        # The PINNED directory, never the hub. MangaOcr's default argument is
        # the repo id, which resolves through the HuggingFace cache and then
        # the network -- so taking the default leaves the one model the app
        # cannot run without as the one model nothing pins, and a first launch
        # on a cold machine downloads whatever main holds that day.
        path = models.ensure("manga-ocr")

        # ponytail: the pipeline is single-threaded, so a lock-free lazy global is
        # sufficient. Upgrade path: add a lock if concurrent OCR is introduced.
        _MODEL = MangaOcr(pretrained_model_name_or_path=path, force_cpu=True)
    return _MODEL


def _as_image(img) -> Image.Image:
    if isinstance(img, Image.Image):
        return img
    if isinstance(img, np.ndarray):
        return Image.fromarray(img)
    with Image.open(img) as opened:
        return opened.copy()


def _is_blank(img) -> bool:
    """True when the crop carries no ink -- and true when that cannot be told.

    A crop with no pixels is the second case. np.std() of an empty array is
    nan, and EVERY comparison against nan is False, so the naive
    `std < 8.0` turned "cannot compute" into "definitely not blank" and let
    the model run on nothing: manga-ocr answered a 0x50 crop with 'それでも、',
    invented text, which is the exact hallucination this gate exists to stop.
    Reachable from production, not only from a test -- pipeline.ocr crops
    _bbox(polygon) straight from the detector, and a degenerate polygon gives
    a zero-area box.

    Third time this shape has been recorded (a swallowed decode, an empty
    tasklist parse, now a nan comparison): a failure to DETERMINE must never
    produce the same value as a negative determination. So the return is
    written as `not (std >= 8.0)` rather than `std < 8.0` -- with nan the
    first says blank and the second says not-blank, and blank is the safe
    answer, because a blank verdict costs an empty string and a not-blank
    verdict costs invented dialogue on the page.
    """
    gray = np.asarray(_as_image(img).convert("L"))
    if gray.size == 0:
        return True
    height, width = gray.shape
    inset_y, inset_x = int(height * 0.05), int(width * 0.05)
    interior = gray[inset_y : height - inset_y or None, inset_x : width - inset_x or None]
    return not (float(interior.std()) >= 8.0)


_ELLIPSIS = re.compile(r"(?:．|\.){3,}")
_FULLWIDTH = {c: c - 0xFEE0 for c in
              list(range(0xFF10, 0xFF1A)) + list(range(0xFF21, 0xFF3B))
              + list(range(0xFF41, 0xFF5B))}


def canonical(text: str) -> str:
    """Fold the two encodings manga-ocr picks that the page does not print."""
    return _ELLIPSIS.sub("…", text).translate(_FULLWIDTH)


def ocr(crop, confidence=1.0, conf_floor=0.0) -> str:
    if confidence < conf_floor:
        return ""
    image = _as_image(crop)
    if _is_blank(image):
        return ""
    return canonical(str(_get_model()(image)))


if __name__ == "__main__":
    from PIL import ImageDraw

    white = Image.new("L", (100, 100), 255)
    gray = Image.new("L", (100, 100), 128)
    bordered = white.copy()
    ImageDraw.Draw(bordered).rectangle((0, 0, 99, 99), outline=0, width=5)

    assert ocr(white) == ""
    assert ocr(gray) == ""
    assert ocr(bordered) == ""

    # Degenerate crops: no pixels means nothing can be read off them, so the
    # gate must answer "" rather than let the model invent a line.
    assert _is_blank(Image.new("L", (0, 50), 255))
    assert _is_blank(Image.new("L", (50, 0), 255))
    assert _is_blank(Image.new("L", (0, 0), 255))
    assert _is_blank(Image.new("L", (1, 1), 255))

    assert canonical("．．．") == "…"
    assert canonical("ＶＲで") == "VRで"
    assert canonical("こんにちは") == "こんにちは"
