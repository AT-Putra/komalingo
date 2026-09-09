"""The shared Region type: detect.py's output, typeset.py's input.

Defined here (Phase 1) rather than in Phase 3 so two phases never invent it
twice. One definition, imported everywhere -- pipeline.py, detect.py, llm.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Region:
    id: int
    polygon: list = field(default_factory=list)
    text: str = ""  # source Japanese from ocr_ja.py
    translation: str = ""  # English from llm.py
    typeset: str = ""  # what typeset.py actually rendered (Phase 2a)
    confidence: float = 0.0  # detection confidence from detect.py
