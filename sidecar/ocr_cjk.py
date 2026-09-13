"""Chinese and Korean OCR: PP-OCRv5 text-line recognition through onnxruntime.

Owns AC-3's OCR half. Japanese never comes here -- manga-ocr owns it, whole
bubble in one pass, and this module refuses "ja" by name so the rule holds at
the engine and not only at the one caller that currently respects it.

WHY onnxruntime and not the paddleocr package. The build order names the
MODEL, PP-OCRv5, and the package is one way to run it: it pulls the whole
paddlepaddle runtime behind it for a recogniser, and downloads its weights
unpinned at run time -- the exact thing models.py exists to prevent (AC-14).
The weights themselves are PaddlePaddle's, Apache-2.0, and an ONNX export of
them is a fixed set of bytes a manifest can pin. models.select_provider had
been choosing an onnxruntime execution provider since Phase 0 for exactly
this eventuality.

WHY per LINE and not per bubble. PP-OCR's recogniser reads one text line; a
whole bubble handed to it is several lines read as one. Phase 2b's grouping
gives every region its member quads in `parts`, one per line as the detector
saw them, so recognition runs per part and the lines are joined in reading
order: columns right to left, rows top to bottom. The whole-block quads the
detector also returns -- one quad around all the columns -- are dropped
first, or the bubble would be read twice.

Vertical text follows PaddleOCR's own convention: a crop taller than 1.5x
its width is rotated a quarter turn counter-clockwise before recognition, so
the top glyph lands at the left. Measured, not assumed: the other rotation
read 快跑小心别担心 as 立描世シら鄙荘 at 0.24 confidence.
"""

from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image

from . import models
from .group import bbox
from .ocr_ja import _is_blank

LANGS = {"zh": "pp-ocrv5-rec-zh", "ko": "pp-ocrv5-rec-ko"}
SEPARATOR = {"zh": "", "ko": " "}  # between lines: Korean spaces its words, Chinese does not

# Chinese typesetting prints fullwidth punctuation and the recogniser answers
# the ASCII form about half the time -- '你在做什么?' for 你在做什么？ -- the
# same encoding drift ocr_ja.canonical folds for manga-ocr. Folded here, for
# zh only: Korean prints ASCII punctuation and the fold would be wrong there.
# Narrow on purpose: the five marks a bubble actually carries, nothing else.
_ZH_PUNCT = str.maketrans("?!,:;", "？！，：；")
CANONICAL = {"zh": lambda text: text.translate(_ZH_PUNCT), "ko": lambda text: text}

HEIGHT = 48  # the recogniser's input height; width follows the crop's aspect
ROTATE_RATIO = 1.5  # PaddleOCR's threshold: taller than this is a vertical line
CONF_FLOOR = 0.5  # PaddleOCR's drop_score: a line read below this is not a line
CONTAIN = 0.70  # a part holding this much of another part is a block quad, not a line


class OcrError(RuntimeError):
    """A recogniser that cannot run. Named, like every sidecar failure path."""


class _Recogniser:
    def __init__(self, lang: str):
        directory = models.ensure(LANGS[lang])
        names = os.listdir(directory)
        onnx = [n for n in names if n.endswith(".onnx")]
        dicts = [n for n in names if n.endswith(".txt")]
        if len(onnx) != 1 or len(dicts) != 1:
            raise OcrError(f"{LANGS[lang]} at {directory} should hold one .onnx and one .txt "
                           f"dictionary; found {sorted(names)}")
        with open(os.path.join(directory, dicts[0]), encoding="utf-8") as fh:
            self.chars = [line.rstrip("\r\n") for line in fh if line.rstrip("\r\n")]
        self.session = models.onnx_session(os.path.join(directory, onnx[0]))
        self.input = self.session.get_inputs()[0].name

    def read(self, crop: np.ndarray) -> tuple[str, float]:
        """One text line -> (text, mean character confidence)."""
        if crop.shape[0] / max(crop.shape[1], 1) >= ROTATE_RATIO:
            crop = np.rot90(crop)
        h, w = crop.shape[:2]
        width = max(1, math.ceil(HEIGHT * w / h))
        resized = np.asarray(Image.fromarray(crop).resize((width, HEIGHT), Image.BILINEAR),
                             dtype=np.float32)
        x = ((resized / 255.0 - 0.5) / 0.5).transpose(2, 0, 1)[None]
        probs = self.session.run(None, {self.input: x})[0][0]  # [T, len(chars) + 2]
        # CTC: argmax per step, collapse repeats, drop the blank at 0. Index
        # len(chars) + 1 is the space PaddleOCR appends past its dictionary.
        idx = probs.argmax(-1)
        keep = (idx != 0) & np.concatenate(([True], idx[1:] != idx[:-1]))
        picked = idx[keep]
        text = "".join(self.chars[i - 1] if i - 1 < len(self.chars) else " " for i in picked)
        conf = float(probs[keep].max(-1).mean()) if picked.size else 0.0
        return text, conf


_RECOGNISERS: dict[str, _Recogniser] = {}


def _recogniser(lang: str) -> _Recogniser:
    if lang == "ja":
        raise OcrError("ja is manga-ocr's; never Paddle")
    if lang not in LANGS:
        raise OcrError(f"no PP-OCRv5 recogniser for {lang!r}; have {sorted(LANGS)}")
    if lang not in _RECOGNISERS:
        _RECOGNISERS[lang] = _Recogniser(lang)
    return _RECOGNISERS[lang]


# A part holding smaller parts is a LINE over its words when it is no thicker
# than this many median part thicknesses, and a BLOCK over its lines beyond.
LINE_THICKNESS = 1.5


def lines(parts) -> list:
    """The parts that are text LINES, each read once.

    The detector answers per line and, at the same scale, once more per block
    around them; grouping keeps both as parts, and reading the block quad as
    a line would read the bubble twice. So a part holding most of another is
    resolved -- but which way depends on what the holder is:

      a BLOCK over its lines (thicker than LINE_THICKNESS lines) is dropped:
        the recogniser reads one line at a time, and a two-line crop is not
        a line;
      a LINE over its words (one line thick) is kept and the words dropped:
        the fine detector scale answers per word as often as per line, and a
        crop cut at a word boundary starts on the neighbouring glyph's stem
        -- "| 않을 거야" for 않을 거야 -- where the whole line, which the
        coarse scale drew and every gate was measured against, reads clean.

    Returned in reading order -- columns right to left, rows top to bottom,
    and along each -- decided by the majority orientation.
    """
    boxes = [bbox(p) for p in parts]
    if not boxes:
        return []

    def area(b):
        return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

    def inside(a, b) -> float:
        ov = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
        return ov / area(a) if area(a) else 0.0

    vertical = sum((b[3] - b[1]) > (b[2] - b[0]) for b in boxes) * 2 > len(boxes)

    def thickness(b) -> float:
        return (b[2] - b[0]) if vertical else (b[3] - b[1])

    sizes = sorted(thickness(b) for b in boxes)
    line = sizes[len(sizes) // 2]
    dropped: set[int] = set()
    for i, b in enumerate(boxes):
        held = [j for j, o in enumerate(boxes)
                if j != i and area(o) < area(b) and inside(o, b) >= CONTAIN]
        if not held:
            continue
        if thickness(b) <= LINE_THICKNESS * line:
            dropped.update(held)  # a line over its words: the line reads
        else:
            dropped.add(i)  # a block over its lines: the lines read
    kept = [i for i in range(len(boxes)) if i not in dropped]
    return [parts[i] for i in _reading_order(kept, boxes, vertical)]


def _reading_order(kept: list, boxes: list, vertical: bool) -> list:
    """Rows top to bottom (columns right to left), and WITHIN a row, left to
    right (within a column, top to bottom).

    The detector's fine scale answers per word as often as per line, so one
    line of Korean can arrive as two parts a pixel apart in y. Sorted on y
    alone they landed in whichever order that pixel fell -- "위험하니까 너무
    조심해" for a line that reads "너무 위험하니까 조심해" -- because the old
    key had no second axis: at the coarse scale a line was always one part.
    A row is the parts whose centres on the stacking axis lie within half a
    line of the row's first; the line is the median part thickness.
    """
    if not kept:
        return []

    def centre(i: int) -> float:
        b = boxes[i]
        return (b[0] + b[2]) / 2 if vertical else (b[1] + b[3]) / 2

    def thickness(i: int) -> float:
        b = boxes[i]
        return (b[2] - b[0]) if vertical else (b[3] - b[1])

    sizes = sorted(thickness(i) for i in kept)
    line = sizes[len(sizes) // 2]
    order = sorted(kept, key=lambda i: -centre(i) if vertical else centre(i))
    rows: list[tuple[float, list]] = []
    for i in order:
        if rows and abs(centre(i) - rows[-1][0]) <= 0.5 * line:
            rows[-1][1].append(i)
        else:
            rows.append((centre(i), [i]))
    out: list = []
    for _, row in rows:
        # Along the line: x for horizontal text, y for vertical.
        out.extend(sorted(row, key=lambda i: boxes[i][1] if vertical else boxes[i][0]))
    return out


def ocr(img, parts, lang: str) -> str:
    """Read one region: its line parts, recognised and joined in reading order."""
    rec = _recogniser(lang)
    page = np.asarray(img.convert("RGB"))
    out = []
    for part in lines(parts):
        x0, y0, x1, y1 = (int(round(v)) for v in bbox(part))
        crop = page[max(y0, 0):max(y1, 0), max(x0, 0):max(x1, 0)]
        if crop.size == 0 or _is_blank(Image.fromarray(crop)):
            continue
        text, conf = rec.read(crop)
        if text.strip() and conf >= CONF_FLOOR:
            out.append(text.strip())
    return CANONICAL[lang](SEPARATOR[lang].join(out))
