#!/usr/bin/env python3
"""Phase 0a spike: can we import the CV components in-process on the pinned stack?

Retires dep #5 (comic-text-detector, stale since 2023, vs opencv-python 5.0 /
torch 2.14 / numpy 2.x) and bounds dep #2's blast radius (in-process vs
subprocess for manga-image-translator).

    uv run python spikes/imports.py

Exit 0 all three loaded and ran, 1 at least one failed. A failure here selects
the Section C row 2 ladder rung (a) -- import the internal detector/OCR/inpainter
modules and skip the orchestrator -- or row 5's DBNet swap, in writing, before
Phase 0 starts. Section C row 2 time box: 1 day on rung (a).

Section C row 2's real risks, each probed below rather than assumed:
  - argparse at import time (a module that calls parse_args() on import dies here)
  - global config singletons
  - asyncio loop ownership: imported UNDER a running loop, because the sidecar
    is FastAPI and every import will happen inside one
  - CUDA init in module scope (we assert the CPU path works with CUDA hidden)
"""

import asyncio
import importlib
import os
import sys
import traceback

import numpy as np

# The sidecar runs CPU-first; every check must pass on the CPU path (Section E).
# Hiding CUDA here turns "CUDA init in module scope" from a silent success on
# this machine into a visible failure on a machine without a GPU.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

CROP = (np.random.default_rng(0).random((256, 256, 3)) * 255).astype(np.uint8)

TARGETS = [
    # (label, module, what a success proves)
    ("detector", "comic_text_detector", "dep #5: weight-load path + cv2 5.0 API"),
    ("ocr_ja", "manga_ocr", "dep #6: manga-ocr on torch 2.14 / numpy 2.x"),
    ("inpaint", "manga_translator.inpainting", "dep #2: MIT internals importable"),
]


async def load(label, modname, why):
    """Import under a RUNNING event loop -- the condition the sidecar imposes."""
    print(f"--- {label}: {modname}")
    print(f"    proves: {why}")
    try:
        mod = importlib.import_module(modname)
    except BaseException:
        # BaseException, not Exception: a module calling parse_args() on import
        # raises SystemExit, which is exactly the failure mode we are probing.
        traceback.print_exc(limit=3)
        return False
    print(f"    imported from {getattr(mod, '__file__', '?')}")
    return True


async def main():
    print(f"python {sys.version.split()[0]}  numpy {np.__version__}")
    for label, mod in (("cv2", "cv2"), ("torch", "torch"), ("PIL", "PIL")):
        try:
            m = importlib.import_module(mod)
            print(f"{label} {getattr(m, '__version__', '?')}")
        except ImportError as e:
            print(f"{label} MISSING: {e}")

    results = {}
    for label, modname, why in TARGETS:
        results[label] = await load(label, modname, why)

    print("\n--- summary")
    for label, ok in results.items():
        print(f"{label:10s} {'ok' if ok else 'FAILED'}")
    if all(results.values()):
        print("PASS: all three import in-process under a running loop")
        return 0
    failed = [k for k, v in results.items() if not v]
    print(f"FAIL: {', '.join(failed)} -- select the Section C fallback in writing "
          f"before Phase 0 starts (row 2 ladder rung (a), or row 5 DBNet swap)")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
