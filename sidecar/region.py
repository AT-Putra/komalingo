"""The shared Region type: detect.py's output, typeset.py's input.

Defined here (Phase 1) rather than in Phase 3 so two phases never invent it
twice. One definition, imported everywhere -- pipeline.py, detect.py, llm.py.

Phase 2a adds the two polygon helpers that more than one module needs. They
live beside the type they describe rather than inside typeset.py, because the
fixture generator needs `ellipse_points` too, and a generator that imports the
engine it generates fixtures FOR has its dependency pointing the wrong way.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

# How finely a bubble ellipse is polygonised. Pinned rather than passed,
# because the fixture generator and the gate must agree on the same point
# list -- see ellipse_points.
ELLIPSE_POINTS = 64


@dataclass
class Region:
    """One detected text region, as it travels through the pipeline.

    `text` defaults to None, and the distinction is load-bearing rather than
    stylistic: None means OCR has not run on this region yet, and "" means it
    HAS run and found nothing -- ocr_ja's blank gate returns an empty string
    for a crop with no text in it. typeset.py reads exactly that difference. A
    region whose source is known-blank has no text to lose, so nothing is
    flagged; a region whose source is unknown, or non-empty, and whose
    translation came back empty has lost text and says so.

    It defaulted to "" until Phase 3 came into view. That default is the
    safest-LOOKING one and the wrong one: it makes every freshly constructed
    Region claim its source was checked and empty. Harmless while the pipeline
    passes dicts built by `asdict`, and a silent false negative the moment
    Phase 3 starts passing dataclasses through the spot-fix path.
    """

    id: int
    polygon: list = field(default_factory=list)
    text: str | None = None  # source Japanese from ocr_ja.py; None = not yet OCR'd
    translation: str = ""  # English from llm.py
    typeset: str = ""  # what typeset.py actually rendered (Phase 2a)
    confidence: float = 0.0  # detection confidence from detect.py


def as_points(polygon) -> list[tuple[float, float]]:
    """Accept both shapes a region can carry: a point list or an (x0,y0,x1,y1) box.

    detect.py emits point lists; a caller holding a box should not have to
    convert it first, because a conversion done in four places is a conversion
    done three ways.
    """
    if len(polygon) == 4 and all(isinstance(v, (int, float)) for v in polygon):
        x0, y0, x1, y1 = polygon
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [(float(p[0]), float(p[1])) for p in polygon]


def ellipse_points(box, n: int = ELLIPSE_POINTS) -> list[tuple[float, float]]:
    """The n-gon inscribed in an (x0,y0,x1,y1) ellipse, as a region polygon.

    gen_fixtures.py DRAWS each bubble from this point list and check_typeset.py
    hands the same list to the ladder. A bubble drawn as a true ellipse but
    measured as a 64-gon differs by under a pixel at the waist and by more at
    the poles -- small, and exactly the disagreement that makes a boundary
    fixture flip between runs. Drawing and measuring one point list removes it.
    """
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    a, b = (x1 - x0) / 2, (y1 - y0) / 2
    return [
        (cx + a * math.cos(2 * math.pi * i / n), cy + b * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]
