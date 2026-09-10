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

from . import atomic, imaging, ocr_ja, typeset
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

    Fills each detected polygon with flat white. That is CORRECT, not a
    placeholder, for the case this pipeline actually meets: a detected region is
    the text area *inside* a speech bubble, and a manga bubble's interior is
    white, so filling it white continues the bubble's own interior. Phase 2a's
    check_inpaint.py is what holds that claim to account -- it compares the
    filled area against the ring of bubble just outside it, and a flat fill
    passes only where the surrounding bubble is flat too.

    Ceiling: a bubble whose interior carries screentone or a gradient. There,
    flat white is a box-over and check_inpaint.py's ring assert says so.
    Upgrade path: a texture-continuing inpainter behind this same call. It is
    NOT a Phase 2a deliverable -- the build order lists no inpainter module in
    2a, and there is no "Phase 1b" despite what this docstring used to claim.
    """
    out = img.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for r in regions:
        draw.polygon([tuple(p) for p in r["polygon"]], fill="white")
    emit("inpaint", f"{len(regions)} calls", page, 65)
    return out, len(regions)


def render(
    img: Image.Image,
    regions: list[dict],
    page: int,
    client=None,
    *,
    allow_retranslate: bool = True,
) -> tuple[Image.Image, dict]:
    """Draw the translations back into the cleaned page. Returns (image, summary).

    Phase 2a: this is typeset.py's five-rung ladder, replacing the Phase 0
    placeholder that anchored every string top-left with the default font and
    no wrapping at all.

    The fit metrics are written back onto the region dicts here rather than
    returned alongside them, because run_page json-serialises those same
    objects into regions.json -- which is where a reader, and the spot-fix
    editor, look to find out which bubbles came out compromised. They are
    DERIVED on every pass and never read back as input: typeset_page recomputes
    both flags from the geometry each time, so a user shortening an edit clears
    the flag by re-running rather than by anyone remembering to clear it.

    `client` is threaded through for rung 5's one length-capped retry, so that
    request acquires llm.py's Semaphore(3) like every other call.
    `allow_retranslate=False` is the spot-fix re-render path.
    """
    out, fits = typeset.typeset_page(
        regions, img, allow_retranslate=allow_retranslate, client=client
    )
    by_id = {f.id: f for f in fits}
    for r in regions:
        f = by_id.get(r["id"])
        if f is None:
            continue
        r["typeset"] = f.text
        r["font_px"] = f.font_px
        r["rung"] = f.rung
        r["rung4_skipped"] = f.rung4_skipped
        r["fit_compromised"] = f.fit_compromised
        r["fit_failed"] = f.fit_failed
        # Why it failed, and whether the text on the page is the provider's
        # shortened reply rather than the original translation. Without these
        # the editor can highlight a bubble but cannot tell the user what to do.
        r["fit_reason"] = f.reason
        r["retranslated"] = f.retranslated
    emit("render", f"{len(regions)} regions", page, 80)
    return out, typeset.summary(fits)


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
        drawn, fit_summary = render(cleaned, regions, page, client)
        out_path = encode_and_write(drawn, src_path, dest_dir, page)

    changed = {r["id"]: _changed_in_polygon(cleaned, drawn, r["polygon"]) for r in regions}
    return {
        "page": page,
        "output": out_path,
        "detections": len(regions),
        "ocr_calls": ocr_calls,
        "inpaint_calls": inpaint_calls,
        "pixels_changed_in_polygon": changed,
        # AC-1's reporting half. Region IDS, not counts alone: "3 regions did
        # not fit" tells the user the page is incomplete without telling them
        # where to look, and the spot-fix editor sorts on exactly this list.
        "fit_summary": fit_summary,
        "regions": regions,
    }


def write_regions(record: dict, dest_dir) -> str:
    """The evidence file check_package.py reads back. Atomic like every write."""
    path = os.path.join(os.fspath(dest_dir), "regions.json")
    with atomic.atomic_write(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return atomic.long_path(path)
