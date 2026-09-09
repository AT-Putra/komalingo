"""The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode, write.

The stage names are a CONTRACT. check_ipc.py asserts against them by name and in
order, never by counting events, so renaming a stage here breaks the UI's
progress display and the check catches it. Each stage emits exactly one
line-flushed {stage, item, page, pct} object on stdout -- one, not one per
sub-step, because the UI draws one bar segment per stage.

This is writer number 1, not a special case: it encodes through imaging.py and
lands bytes through atomic.py like everything else. A pipeline that wrote its
own output directly would be the one path where a mid-write crash leaves a
half-page on disk.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict

from PIL import Image, ImageDraw

from . import atomic, imaging, ocr_ja
from . import detect as detector

STAGES = ("detect", "ocr", "translate", "inpaint", "render", "encode", "write")


def emit(stage: str, item: str, page: int, pct: int) -> None:
    """One progress line. flush=True is load-bearing.

    Tauri reads this pipe line by line. Without the flush, Python's block
    buffering holds every line until the process exits and the UI sits at 0%
    for the whole run, then jumps to 100%.
    """
    print(
        json.dumps({"stage": stage, "item": item, "page": page, "pct": pct}),
        flush=True,
    )


def _bbox(polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _changed_in_polygon(before: Image.Image, after: Image.Image, polygon) -> int:
    """Pixels that actually differ inside the polygon's bbox.

    The evidence check_package.py reads back. Measured CLEANED -> DRAWN, not
    ORIGINAL -> DRAWN: inpaint has already repainted the whole polygon white by
    then, so comparing against the original counts inpaint's work and reports a
    healthy number for a renderer that drew nothing at all. Only the narrower
    comparison can go red when render no-ops.
    """
    box = _bbox(polygon)
    a = before.convert("RGB").crop(box).tobytes()
    b = after.convert("RGB").crop(box).tobytes()
    return sum(1 for i in range(0, len(a), 3) if a[i : i + 3] != b[i : i + 3])


# -- stages ----------------------------------------------------------------


def detect(img: Image.Image, page: int) -> list[dict]:
    """Text regions from detect.py's DB model.

    Regions become plain dicts here rather than travelling as dataclasses,
    because every stage after this one mutates them in place and run_page
    json-serialises the same objects into regions.json. asdict carries
    confidence through to that file, which is the only place a reader can see
    whether a detection was marginal.
    """
    regions = [asdict(r) for r in detector.detect(img)]
    emit("detect", f"{len(regions)} regions", page, 10)
    return regions


def ocr(regions: list[dict], img: Image.Image, page: int) -> int:
    """Japanese text per region. Returns the number of OCR calls made."""
    rgb = img.convert("RGB")
    for r in regions:
        x0, y0, x1, y1 = _bbox(r["polygon"])
        r["text"] = ocr_ja.ocr(rgb.crop((x0, y0, x1, y1)))
    emit("ocr", f"{len(regions)} calls", page, 25)
    return len(regions)


def translate(regions: list[dict], page: int, client=None) -> None:
    """English per region. One LLM request for the whole page when configured.

    client is injected -- there is no default and no module-level base URL. The
    credentials come from the Settings UI at runtime, never from this file.
    """
    if client is None:
        # ponytail: offline placeholder so the skeleton runs with no provider.
        # Upgrade path: main.py builds an LLMClient from the settings payload.
        for r in regions:
            r["translation"] = "HELLO"
    else:
        import asyncio

        from .llm import Region

        out = asyncio.run(
            client.translate_page([Region(id=r["id"], text=r["text"]) for r in regions])
        )
        for r in regions:
            r["translation"] = out.get(r["id"], "")
    emit("translate", f"{len(regions)} regions", page, 50)


def inpaint(img: Image.Image, regions: list[dict], page: int) -> tuple[Image.Image, int]:
    """Erase the original text. Returns (image, call count).

    ponytail: fills each polygon with flat white. Ceiling: it destroys any
    screentone or art under the bubble, which is visible on a textured page.
    Upgrade path: Phase 1b replaces this with LaMa over a dilated text mask.
    """
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for r in regions:
        draw.polygon([tuple(p) for p in r["polygon"]], fill="white")
    emit("inpaint", f"{len(regions)} calls", page, 65)
    return out, len(regions)


def render(img: Image.Image, regions: list[dict], page: int) -> Image.Image:
    """Draw the translations back into the cleaned page.

    ponytail: upstream's naive renderer -- default font, top-left anchored,
    no wrapping. Ceiling: NO BUBBLE-FIT GUARANTEE. Long lines overflow the
    polygon and overlap the art, and that is expected in Phase 0. Upgrade
    path: Phase 2a replaces this call with the five-rung fit ladder
    (shrink -> wrap -> break -> compromise -> fail) that check_typeset.py
    already has fixtures for; the signature does not change.
    """
    out = img.copy()
    draw = ImageDraw.Draw(out)
    for r in regions:
        x0, y0, _, _ = _bbox(r["polygon"])
        draw.text((x0 + 4, y0 + 4), r.get("translation", ""), fill="black")
    emit("render", f"{len(regions)} regions", page, 80)
    return out


def encode_and_write(img: Image.Image, src_path, dest_dir, page: int) -> str:
    """The last two stages. Format and metadata come from the source image."""
    dest = imaging.output_path(src_path, dest_dir)
    emit("encode", os.path.basename(dest), page, 90)
    out = imaging.save(img, src_path, dest)
    emit("write", os.path.basename(dest), page, 100)
    return out


# -- the run ---------------------------------------------------------------


def run_page(src_path, dest_dir, page: int = 1, client=None) -> dict:
    """One page through all seven stages, in order. Returns the regions record."""
    with Image.open(atomic.long_path(src_path)) as src:
        src.load()
        original = src.convert("RGB").copy()

        regions = detect(src, page)
        ocr_calls = ocr(regions, src, page)
        translate(regions, page, client)
        cleaned, inpaint_calls = inpaint(original, regions, page)
        drawn = render(cleaned, regions, page)
        out_path = encode_and_write(drawn, src_path, dest_dir, page)

    changed = {r["id"]: _changed_in_polygon(cleaned, drawn, r["polygon"]) for r in regions}
    return {
        "page": page,
        "output": out_path,
        "detections": len(regions),
        "ocr_calls": ocr_calls,
        "inpaint_calls": inpaint_calls,
        "pixels_changed_in_polygon": changed,
        "regions": regions,
    }


def write_regions(record: dict, dest_dir) -> str:
    """The evidence file check_package.py reads back. Atomic like every write."""
    path = os.path.join(os.fspath(dest_dir), "regions.json")
    with atomic.atomic_write(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return atomic.long_path(path)
