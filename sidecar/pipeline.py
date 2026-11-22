"""The seven-stage pipeline: detect, ocr, translate, inpaint, render, encode, write.

The stage names are a CONTRACT. check_ipc.py asserts against them by name and in
order, never by counting events, so renaming a stage here breaks the UI's
progress display and the check catches it. Each stage emits exactly one
line-flushed {stage, item, page, pct} object on stdout -- one, not one per
sub-step, because the UI draws one bar segment per stage -- plus `total`, the
item's page count, when it is known (see emit and expecting).

This is writer number 1, not a special case: it encodes through imaging.py and
lands bytes through atomic.py like everything else. A pipeline that wrote its
own output directly would be the one path where a mid-write crash leaves a
half-page on disk.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import sys
import threading
import time
from dataclasses import asdict

from PIL import Image

from . import atomic, cache, imaging, inpainter, models, ocr_cjk, ocr_ja, safety, typeset
from . import detect as detector
from .containers import archive, folder, pdf
from .llm import MAX_CONCURRENT, is_null_word

STAGES = ("detect", "ocr", "translate", "inpaint", "render", "encode", "write")


def emit(stage: str, item: str, page: int, pct: int) -> None:
    """One progress line. flush=True is load-bearing.

    Tauri reads this pipe line by line. Without the flush, Python's block
    buffering holds every line until the process exits and the UI sits at 0%
    for the whole run, then jumps to 100%.

    `total` rides along when the item running on THIS thread knows its page
    count (see expecting): `pct` is one page's progress, and without a total
    the UI can only count pages up from nothing -- a chapter's bar had no end
    to run to. Optional by construction: a compressed tar cannot be counted
    cheaply, and the field is then absent rather than a guess.

    Under a lock since Phase 8: four workers emit at once, and Tauri parses
    one JSON object per line. CPython happens to write the line and its
    newline without releasing the GIL between them; the lock makes what was
    an implementation accident a guarantee.
    """
    line = {"stage": stage, "item": item, "page": page, "pct": pct}
    total = getattr(_EXPECTED, "total", None)
    if total:
        line["total"] = total
    # `item` on a page stage is that stage's detail ("5 regions", the output
    # file name), not the item. With an item's pages interleaved, the UI needs
    # to know which item and page a line belongs to, so the id rides along.
    item_id = getattr(_EXPECTED, "item_id", None)
    if item_id:
        line["item_id"] = item_id
    with _EMIT_LOCK:
        print(json.dumps(line), flush=True)


_EMIT_LOCK = threading.Lock()
# Per THREAD, not per process: the job runs four items at once (job.WORKERS)
# and each is a different length. A worker publishes its own count here and
# every emit under it carries that one.
_EXPECTED = threading.local()


def _log(msg: str) -> None:
    """One line to stderr, which Tauri reads into the log pane. Not stdout:
    that pipe carries emit()'s progress JSON, one object per line."""
    print(msg, file=sys.stderr, flush=True)


# A page whose provider request failed for a reason that can pass -- a
# stalled reply, a cut-off one, a 5xx -- is asked ONCE more before the item
# fails. One, not a loop: the second request already costs up to llm.TIMEOUT,
# and a provider that fails twice in a row is the user's to look at, in the
# log pane, where both attempts are named. Module-level so a check can zero
# the pause.
TRANSLATE_RETRIES = 1
RETRY_DELAY = 2.0


@contextlib.contextmanager
def expecting(total: int | None, item_id: str | None = None):
    """Publish the page count and id of the item this thread is about to run."""
    previous = (getattr(_EXPECTED, "total", None), getattr(_EXPECTED, "item_id", None))
    _EXPECTED.total, _EXPECTED.item_id = total, item_id
    try:
        yield
    finally:
        _EXPECTED.total, _EXPECTED.item_id = previous


def _bbox(polygon):
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _changed_in_polygon(before: Image.Image, after: Image.Image, polygon) -> int:
    """Pixels that actually differ inside the polygon's bbox.

    The evidence check_package.py reads back. Measured CLEANED -> DRAWN, not
    ORIGINAL -> DRAWN: inpaint has already erased the source glyphs by then, so
    comparing against the original counts inpaint's work and reports a
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


# The source languages the pipeline reads, and which engine reads each. ja is
# manga-ocr's -- whole bubble, one pass, furigana and all -- and NEVER
# PaddleOCR's: PP-OCRv5 reads Japanese at 60% (spec, component table). zh and
# ko are PP-OCRv5's, per text line. Phase 4, AC-3.
SOURCES = ("ja", "zh", "ko")
DEFAULT_SOURCE = "ja"
DEFAULT_LANG = "en"


# Characters a region can be made of and still hold nothing to translate.
# Ellipses, dots, dashes, brackets, exclamation and question marks, in their
# ASCII and fullwidth forms, and whitespace.
_PUNCTUATION = re.compile(
    "^[\\s\u2026\u2025\u30fb\u3002\u3001\uff0c,.\u2022!?\uff01\uff1f"
    "\u30fc\u2014\u2015\u2500~\uff5e\u301c\\-\u2212\u300c\u300d\u300e\u300f()\uff08\uff09"
    ":;\uff1a\uff1b\u3000'\"\u201c\u201d\u2018\u2019*\uff0a]+$"
)


def punctuation_only(text: str | None) -> bool:
    """Is there anything here a translator could change?

    A region that reads as nothing but punctuation -- 「…」, 「・」, 「！！」 --
    has no translation that differs from itself, so it stays as drawn. That
    is the whole of the rule, and it is deliberately blind to why the OCR
    read punctuation: a real beat-bubble of 「…」 loses nothing by keeping its
    own dots, and a speck, a rivet, a skirt tag or a hand that manga-ocr read
    as 「…」 (page 4 of the stairwell chapter, at detector confidence 0.97)
    is left as the art it is instead of being painted white and given
    "...". The vision model's null (llm.NOT_TEXT_INSTRUCTION) covers the
    hand that read 「いや…」; this covers what needs no model at all, and
    does not depend on one answering the same way twice.
    """
    return bool(text) and bool(_PUNCTUATION.match(text))


def ocr(regions: list[dict], img: Image.Image, page: int, source: str = DEFAULT_SOURCE) -> int:
    """Source text per region. Returns the number of OCR calls made.

    One call per region on both paths. manga-ocr takes the whole region
    (its hull) in one pass; PP-OCRv5 takes the region's PARTS -- one per text
    line as the detector saw them -- and ocr_cjk joins them in reading order,
    which is still one call here and one entry in regions.json.

    A region that read as punctuation only is flagged `not_text` here, with
    its reason; translate() then does not send it, and dismiss() takes it
    off the page before the inpainter. See punctuation_only.
    """
    if source not in SOURCES:
        raise ValueError(f"source {source!r} is not one of {SOURCES}")
    rgb = img.convert("RGB")
    for r in regions:
        if source == "ja":
            x0, y0, x1, y1 = _bbox(r["polygon"])
            r["text"] = ocr_ja.ocr(rgb.crop((x0, y0, x1, y1)))
        else:
            r["text"] = ocr_cjk.ocr(rgb, r.get("parts") or [r["polygon"]], source)
        if punctuation_only(r["text"]):
            r["not_text"] = True
            r["dismiss_reason"] = "punctuation only"
    emit("ocr", f"{len(regions)} calls", page, 25)
    return len(regions)


# The page image the provider sees for context, bounded. A raw scan is
# 1500-2500px on the long edge and a few MB; base64 in a JSON body on every
# page of a 200-page volume is a payload the request timeout was never sized
# for. Both numbers are MEASURED, on three real pages (010-012) against a
# gateway vision model, two interleaved rounds each:
#
#   PNG  1280 px       1215 KB/page   median 21.9 s
#   JPEG 1280 px q85    294 KB/page   median 20.3 s
#   JPEG 1024 px q85    203 KB/page   median 16.3 s
#
# Translations agreed with the PNG run's as closely as two PNG runs agreed
# with each other (text similarity 0.65 vs 0.70, null decisions 26 vs 22
# mismatches over the same regions): the model's own run-to-run variation,
# not a cost of the smaller image. Bubbles stay legible at 1024 px, and the
# regions' text travels as text anyway -- the image is context.
PAGE_CONTEXT_LONG_EDGE = 1024
PAGE_CONTEXT_QUALITY = 85


def page_context_image(img: Image.Image) -> bytes:
    """The page, downscaled to PAGE_CONTEXT_LONG_EDGE, as JPEG bytes.

    JPEG, not PNG: a PNG of a screentoned scan does not compress -- page 012
    of the real volume was 1.2 MB at 1280 px, where the comment this replaced
    promised "well under 500KB" for a mostly-white page, and screentone is
    exactly what a manga page is not mostly-white about.
    """
    # Convert BEFORE resizing: on a palette or 1-bit source PIL silently
    # downgrades LANCZOS to NEAREST, and a nearest-neighbour downscale of a
    # screentoned page is moire the model has to read through.
    rgb = img.convert("RGB")
    w, h = rgb.size
    scale = PAGE_CONTEXT_LONG_EDGE / max(w, h)
    small = rgb if scale >= 1 else rgb.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=PAGE_CONTEXT_QUALITY, optimize=True)
    return buf.getvalue()


def _ask_with_retry(ask, where: str, cancel=None) -> dict:
    """`ask()` once, and once more if the provider's failure was transient.

    `where` names the file and the page, and every outcome that involves a
    retry is logged with it: the first failure and the reason, then whether
    the second request succeeded or failed too. A user reading the log pane
    after a failed job must be able to see WHICH page stalled, and a user
    whose job finished must be able to see that a page needed two tries --
    that is the difference between "the gateway is fine" and "it is about
    to fail for good".

    A cancel set between the attempts is honoured: the retry is a whole new
    provider request, up to llm.TIMEOUT long, and a cancelled job does not
    get to spend it.
    """
    from .llm import ProviderError

    for attempt in range(1, TRANSLATE_RETRIES + 2):
        try:
            out = ask()
        except ProviderError as e:
            why = str(e)[:300]
            if attempt > TRANSLATE_RETRIES:
                _log(f"translate: {where}: retry {attempt - 1} of {TRANSLATE_RETRIES} "
                     f"failed too ({why}); giving up on this page")
                raise
            if not e.transient or (cancel is not None and cancel.is_set()):
                raise
            _log(f"translate: {where}: attempt {attempt} failed ({why}); "
                 f"retrying in {RETRY_DELAY:g}s")
            time.sleep(RETRY_DELAY)
            continue
        if attempt > 1:
            _log(f"translate: {where}: retry {attempt - 1} succeeded")
        return out
    raise AssertionError("unreachable: the loop returns or raises")


def translate(regions: list[dict], page: int, client=None, lang: str = DEFAULT_LANG,
              source: str = DEFAULT_SOURCE, img: Image.Image | None = None,
              where: str = "", cancel=None) -> None:
    """Target-language text per region. One LLM request for the whole page.

    `img` is the page the regions came from, and it TRAVELS with the request
    when the client has vision -- that is the page context AC-9 is about, and
    what makes a vision-capable model worth probing for. Until US-C-02 this
    function never passed it: the client accepted page_image, honoured
    text_only, and check_provider proved both against a direct call, while
    the pipeline sent text alone on every page. A vision model saw nothing.
    The client drops the image itself when text_only is latched, so this
    passes it unconditionally and the latch stays the single point of
    decision.

    client is injected -- there is no default and no module-level base URL. The
    credentials come from the Settings UI at runtime, never from this file.
    Phase 5: `lang` and `source` reach the prompt. Until then the job's lang
    was a cache key and nothing else, and the prompt said English regardless.

    `where` is the file and page for the log, "vol1.cbz, page 3 (003.png)";
    it defaults to the page number alone, which is all this function knows.
    See _ask_with_retry for the one retry a transient provider failure gets.
    """
    # Regions ocr() already set aside are not sent: nothing to translate,
    # and no tokens spent finding that out.
    asked = [r for r in regions if not r.get("not_text")]
    if client is None:
        # ponytail: offline placeholder so the skeleton runs with no provider.
        # Ceiling: every region reads HELLO; nothing is translated.
        # Upgrade path: main.py builds an LLMClient from the settings payload.
        for r in asked:
            r["translation"] = "HELLO"
    else:
        import asyncio

        from .llm import Region

        # Built once, sent up to twice: the region list and the page context
        # are the same request both times, so a retry is the SAME question.
        sent = [Region(id=r["id"], text=r["text"], box=_box(r, img)) for r in asked]
        context = page_context_image(img) if img is not None else None

        def ask():
            return asyncio.run(client.translate_page(sent, page_image=context,
                                                     lang=lang, source=source))

        out = _ask_with_retry(ask, where or f"page {page}", cancel) if asked else {}
        for r in asked:
            text = out.get(r["id"], "")
            # None is the vision model's "nothing is written there" -- see
            # llm.NOT_TEXT_INSTRUCTION. Flagged here, removed by dismiss()
            # before the inpainter runs, and stored as null in the
            # translation cache so a cache hit makes the same call.
            if text is None:
                r["not_text"] = True
                r["dismiss_reason"] = VISION_REASON
            r["translation"] = text or ""
    for r in regions:
        r.setdefault("translation", "")
    emit("translate", f"{len(regions)} regions", page, 50)


def _box(region: dict, img: Image.Image | None) -> list[int] | None:
    """The region's bounding box in thousandths of the page, for the vision model.

    Thousandths of the SOURCE page, which is the frame the polygon is in; the
    context image is a scaled copy of the same page, so the fractions hold for
    it too.
    """
    if img is None or not region.get("polygon"):
        return None
    w, h = img.size
    x0, y0, x1, y1 = _bbox(region["polygon"])
    return [round(1000 * x0 / w), round(1000 * y0 / h), round(1000 * x1 / w), round(1000 * y1 / h)]


# Why a region the vision model answered null for is off the page. A DECISION,
# per (lang, model), not a property of the page: _content_region strips it
# before the record is cached, and the translation file puts it back.
VISION_REASON = "not on the page (vision model)"


def dismiss(regions: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept, dismissed): the regions the vision model said hold no text.

    Called after translate and before inpaint, on the fresh path and the
    cached one alike. A dismissed region is not inpainted, not typeset, not
    in the page's fit summary and not in its regions -- the art under it
    stays as drawn. It is kept on the record under `dismissed`, with what the
    OCR read there, so a page that lost a real bubble to a wrong null can be
    seen to have lost it rather than never having found it.

    `editable` marks the model's dismissals, which the editor lists and lets
    the user translate by hand: a wrong null is the model's call, and the
    user overrules it. OCR's punctuation-only set-asides are not editable --
    there is nothing there a translation could change.
    """
    kept = [r for r in regions if not r.get("not_text")]
    gone = [{"id": r["id"], "polygon": r["polygon"], "text": r.get("text"),
             "reason": r.get("dismiss_reason", ""),
             "editable": r.get("dismiss_reason") == VISION_REASON}
            for r in regions if r.get("not_text")]
    return kept, gone


def inpaint(img: Image.Image, regions: list[dict], page: int) -> tuple[Image.Image, int]:
    """Erase the original text. Returns (image, call count).

    Phase 2c: inpainter.py. Only the glyph pixels of the regions' parts are
    erased, and what was under them is continued -- a flat fill where the
    surround is flat (the white bubble), manga-finetuned LaMa everywhere else
    (SFX over art, screentone, translucent bubbles). Until 2c this filled every
    part polygon flat white, which was right inside an opaque white bubble and
    a white box over the art everywhere else; MT_INPAINTER=fill still does.

    Under _MODEL_LOCK like detect and OCR: the text-mask and LaMa sessions are
    lazy globals, and four workers reaching the first page at once would each
    build them.
    """
    with _MODEL_LOCK:
        out, _ = inpainter.erase(img, regions)
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
        # Phase 2b: the polygon the English was actually laid into -- the
        # bubble interior room.py found, or null when it declined. The editor
        # hit-tests on it, because that is where the English now is.
        r["room"] = [[x, y] for x, y in f.room] if f.room else None
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


def run_page(src_path, dest_dir, page: int = 1, client=None, source: str = DEFAULT_SOURCE,
             lang: str = DEFAULT_LANG, cancel=None, item_id: str | None = None) -> dict:
    """One page through all seven stages, in order. Returns the regions record.

    `cancel` (Phase 9) is checked before the first stage: a loose image is one
    page, and one page is delivered whole or not at all -- a check between
    stages would stop after detect with nothing on disk to show for it, which
    is the same outcome as not starting. "Before the first stage" means after
    the page slot, too: that wait lasts as long as other items' translations,
    and a cancel that lands during it must not run the image anyway (review).

    `item_id` is the job's id for the image, which job.py disambiguates when
    two files share a name; the basename otherwise.
    """
    item_id = item_id or os.path.basename(os.fspath(src_path))
    _check_cancel(cancel, item_id, 0)
    # One loose image is one page, and its lines say so: the UI's chapter bar
    # reads `total` and a page run that omitted it would look like an item
    # whose length is unknown.
    # A page slot like every item page (see PAGE_WINDOW): a folder of loose
    # images runs beside archives on the same four workers, and their decoded
    # pages count against the same bound.
    with _page_slots():
        _check_cancel(cancel, item_id, 0)
        return _run_page_in_slot(src_path, dest_dir, page, client, source, lang, item_id)


def _run_page_in_slot(src_path, dest_dir, page, client, source, lang, item_id) -> dict:
    with expecting(1, item_id), Image.open(atomic.long_path(src_path)) as src:
        src.load()
        original = src.convert("RGB").copy()

        # Under the same lock as run_item's pages, since Phase 8: a folder of
        # loose images runs on four workers, and two of them in detect at
        # once is the DetectError run_item's comment records -- plus a raced
        # lazy load in ocr_ja that built the OCR model twice (review,
        # measured: "Loading OCR model" logged twice in one millisecond).
        with _MODEL_LOCK:
            regions = detect(src, page)
            ocr_calls = ocr(regions, src, page, source)
        translate(regions, page, client, lang, source, img=original,
                  where=item_id or os.path.basename(os.fspath(src_path)))
        regions, dismissed = dismiss(regions)
        cleaned, inpaint_calls = inpaint(original, regions, page)
        drawn, fit_summary = render(cleaned, regions, page, client)
        out_path = encode_and_write(drawn, src_path, dest_dir, page)

    changed = {r["id"]: _changed_in_polygon(cleaned, drawn, r["polygon"]) for r in regions}
    return {
        "page": page,
        "source": source,
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
        "dismissed": dismissed,
    }


def write_regions(record: dict, dest_dir) -> str:
    """The evidence file check_package.py reads back. Atomic like every write."""
    path = os.path.join(os.fspath(dest_dir), "regions.json")
    with atomic.atomic_write(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, ensure_ascii=False, indent=2, sort_keys=True)
    return atomic.long_path(path)


# -- the cached paths (Phase 3) -------------------------------------------
#
# run_page above is untouched: one loose image, no cache, no job. It is what
# check_pipeline asserts the seven-stage contract against, and threading a
# cache through it would have made that contract conditional on a cache state.
# The cache enters here instead, where an ITEM -- an archive with an id and page
# ordinals -- is the thing being run.


# Serialises the models -- detector, OCR, and since Phase 2c the text-mask and
# LaMa sessions inpaint() runs -- across concurrent jobs. See run_item.
_MODEL_LOCK = threading.Lock()

# Set by Tauri, and only by Tauri, like MT_EXIT_ON_STDIN_EOF: the app's own
# sidecar warms its models at launch, while a check that starts a sidecar or
# a TestClient does not load a GPU model it never asked for.
WARMUP_ENV = "MT_WARMUP"


def warm_models(log=None) -> list[str]:
    """Load the models every page needs, before the first page asks. Returns what loaded.

    Measured on a real page that needs all of them: 19.1 s for the first page
    of a fresh process against 3.3 s once loaded -- manga-ocr, the text-mask
    session and the LaMa session are the difference, and without this the
    user pays it on the first page of every launch.

    Each model loads under _MODEL_LOCK through the same lazy global the
    pipeline uses, so a page that arrives mid-warm-up waits for the model
    rather than building a second copy. A model not yet on disk -- or on disk
    but failing its checksum -- is skipped, never fetched: a download at
    launch would hold the model lock with nothing on screen to say why pages
    wait. A failure is logged and skipped; the page that needs the model
    fetches or raises exactly as it did before.
    """
    log = log or (lambda msg: print(msg, file=sys.stderr, flush=True))
    steps = [
        ("detector", [detector.WEIGHTS], detector._model),
        ("manga-ocr", ["manga-ocr"], ocr_ja._get_model),
    ]
    try:
        erasing = inpainter.resolve() != inpainter.FILL
    except inpainter.EraseError as e:
        log(f"warm-up: erase models skipped ({e.reason})")
        erasing = False
    if erasing:
        steps += [
            ("text-mask", [inpainter.textmask.WEIGHTS], inpainter.textmask._model),
            ("lama", [inpainter.WEIGHTS], inpainter._lama),
        ]
    loaded = []
    for name, weights, load in steps:
        if not all(models.on_disk(w) for w in weights):
            log(f"warm-up: {name} not downloaded yet; the first page fetches it")
            continue
        try:
            # no_download: on_disk checks sizes only, so a file of the right
            # size that fails its checksum reaches fetch -- which would
            # re-download hundreds of MB here, silently, at launch, with every
            # page waiting behind _MODEL_LOCK. Refused instead; the page that
            # needs the model downloads it.
            with _MODEL_LOCK, models.no_download():
                load()
            loaded.append(name)
        except Exception as e:  # noqa: BLE001 -- logged; the page raises it properly
            log(f"warm-up: {name} failed to load ({type(e).__name__}: {e})")
    return loaded


class Cancelled(Exception):
    """AC-13: the job's cancel token was set and this item stopped at a page
    boundary. `pages_done` is how many pages were DELIVERED -- complete files
    on disk, cached pages in the store -- before the stop.

    Raised, not returned, because the item did not finish: the repack must
    not run, and the Item boundary in job.py is what turns it into the
    CANCELLED status with this count in the reason.
    """

    def __init__(self, item_id: str, pages_done: int):
        super().__init__(f"cancelled after {pages_done} pages of {item_id!r}")
        self.item_id, self.pages_done = item_id, pages_done


class Paused(Cancelled):
    """The job paused: an account-level failure, or STREAK pages in a row
    that failed. Every page past this point stops at its boundary exactly as
    for a cancel -- nothing partial, the delivered pages kept -- and the
    job's resume picks the item up again. A Cancelled subclass so every
    boundary that already stops for a cancel stops for this too; the Item
    boundary in job.py catches it FIRST, because the status differs.
    """

    def __init__(self, item_id: str, pages_done: int, reason: str = ""):
        super().__init__(item_id, pages_done)
        self.reason = reason


class Control:
    """A job's stop signals, handed to every page in place of a bare Event.

    `is_set()` is True once the user cancelled OR the job paused, so the
    boundaries that already stop for a cancel (`_check_cancel`, the page
    reader in `_run_pages`, the retry gap) stop for a pause with no second
    check to forget. `paused` says which -- a cancel always wins.

    It also keeps the job-wide count of pages that failed in a row, in the
    order they FINISHED: pages of four items run in one process-wide window,
    so a per-item count would never reach the threshold on a job where one
    refused scene is spread across items. `carried` holds the
    (item_id, ordinal) pages skipped before a pause; on resume they are
    asked again but do not count, or a scene the model refuses would pause
    the resumed job straight away, every time.
    """

    STREAK = 3

    def __init__(self, cancel: threading.Event | None = None, streak: bool = True):
        # `streak=False` pauses on account failures only: /api/item has no
        # resume, so a streak pause there could never be got past (review M2).
        self.streak = streak
        self._cancel = cancel or threading.Event()
        self._pause = threading.Event()
        self._lock = threading.Lock()
        self._streak = 0
        self.pause_reason = ""
        self.carried: set[tuple[str, int]] = set()

    def is_set(self) -> bool:
        return self._cancel.is_set() or self._pause.is_set()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    @property
    def paused(self) -> bool:
        return self._pause.is_set() and not self._cancel.is_set()

    def pause(self, reason: str) -> None:
        with self._lock:
            if not self._pause.is_set():
                self.pause_reason = reason
                self._pause.set()

    def page_result(self, item_id: str, ordinal: int, failed: bool) -> None:
        """Count a finished page: a success resets the streak, a failure adds
        to it unless the page was already skipped before a resume."""
        with self._lock:
            if not failed:
                self._streak = 0
                return
            if not self.streak or (item_id, ordinal) in self.carried:
                return
            self._streak += 1
            if self._streak >= self.STREAK and not self._pause.is_set():
                self.pause_reason = (
                    f"{self.STREAK} pages in a row could not be translated. The provider "
                    f"may be down, or refusing this series; check the skipped pages, "
                    f"then resume or change the model.")
                self._pause.set()


def _check_cancel(cancel, item_id: str, pages_done: int) -> None:
    """Raise Cancelled (or Paused) if the token is set. `cancel` is anything
    with is_set() -- a Control from job.Job, a bare Event from a check -- or
    None for the routes that have no job to be cancelled from."""
    if cancel is not None and cancel.is_set():
        if getattr(cancel, "paused", False):
            raise Paused(item_id, pages_done, cancel.pause_reason)
        raise Cancelled(item_id, pages_done)


def _pause_job(cancel, item_id: str, pages_done: int, reason: str) -> bool:
    """Pause the job behind `cancel` and raise Paused; False when there is
    no job that can pause (a bare Event, None) -- the caller then raises the
    original error, as before pausing existed."""
    if cancel is None or not hasattr(cancel, "pause"):
        return False
    cancel.pause(reason)
    _check_cancel(cancel, item_id, pages_done)
    return True  # unreachable when a cancel raced it to Cancelled; kept for the type


def refusal_key(client, with_image: bool) -> str:
    """What a refusal is remembered under: endpoint, model, image or not."""
    raw = f"{getattr(client, 'base_url', '')}\n{_model_id(client)}\n{int(bool(with_image))}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _describe_skip(e) -> str:
    """The one line the Queue and the review panel show for a skipped page."""
    from .llm import BAD_REPLY, OUTAGE, REFUSED, REJECTED  # noqa: PLC0415

    return {
        REFUSED: "The model refused to translate this page.",
        BAD_REPLY: "The model did not answer with a translation (often a refusal in words).",
        OUTAGE: "The provider did not answer in time, or was busy.",
        REJECTED: "The provider rejected the request for this page.",
    }.get(getattr(e, "kind", ""), "The page could not be translated.")


class CacheMiss(Exception):
    """A page or region the re-render route was asked for is not cached.

    Carries (reason, kind) like FetchError and DetectError, so main.py's
    existing "name the failure, let the UI branch on kind" handling extends to
    it rather than growing a fourth display path.
    """

    def __init__(self, reason: str, kind: str = "cache"):
        super().__init__(reason)
        self.reason, self.kind = reason, kind


# What cache.write_regions persists. Keyed on CONTENT, so nothing about a
# position or a run may live in it: two identical pages share this record, and
# whichever ordinal wrote it last would own any per-position field. The first
# draft persisted `page`, `member`, `item_id` and `output` here, and rerender
# handed them back -- so the UI, which posts the ordinal it was handed, edited
# page 7 when the user was looking at page 3. Defect A fixed the delivery path
# and the review found the same confusion alive in the response envelope.
# `source` is content: the OCR text in `regions` was read by the engine for
# that language, and a page cached under ja and re-run under zh must not hand
# the zh run manga-ocr's reading of Chinese. run_item treats a mismatch as a
# miss. Phase 4.
CONTENT_KEYS = ("page_hash", "src_format", "source", "detections", "fit_summary", "regions")


def _persist(h: str, record: dict, detected: list[dict], complete: bool = True,
             redetect_failed: bool = False) -> None:
    """Write the page's content record: EVERY detected region, not the kept ones.

    Until this, the record held only the regions the run's model kept, so a
    null from one model removed the region for every model and language that
    read the page later -- the translation file of the next (lang, model) had
    no chance to disagree, because the region was gone from the page (124 of
    165 cached pages on the developer's box carried such nulls). Now the
    regions are stored as detected, vision decisions stripped, and each run's
    own translation file dismisses what that model dismissed.

    Which regions the raster erased is not recorded here: each erased set has
    its own raster file, named by the set (cache.raster_name), so a record
    cannot disagree with the pixels.
    `complete` is False for a legacy record re-cached without re-detection:
    its regions are still the old kept set, and all_regions must not claim
    otherwise. `redetect_failed` marks a legacy record re-detection did not
    reproduce, so it is not re-detected on every run (review).
    """
    content = {k: record[k] for k in CONTENT_KEYS if k in record}
    content["regions"] = [_content_region(r) for r in detected]
    content["all_regions"] = complete
    if redetect_failed:
        content["redetect_failed"] = True
    cache.write_regions(h, content)


def _content_region(region: dict) -> dict:
    """The region as the page holds it: a vision model's null is not content."""
    if region.get("dismiss_reason") != VISION_REASON:
        return region
    return {k: v for k, v in region.items() if k not in ("not_text", "dismiss_reason")}


def _model_id(client) -> str:
    """What the translation file is keyed on. 'offline' is a real key, not a hole.

    The placeholder translator produces text, that text gets cached, and a run
    with a real provider must not pick it up. Naming the offline path keeps the
    two in separate files for the same reason two providers are.
    """
    return getattr(client, "model", None) or "offline"


def _load_translations(regions: list[dict], h: str, lang: str, model: str) -> bool:
    """Fill translations from the cache. True only if EVERY region was covered."""
    return not _apply_translations(regions, h, lang, model)


def _apply_translations(regions: list[dict], h: str, lang: str, model: str,
                        recheck: bool = False) -> set:
    """Fill translations from the cache. Returns the ids still to translate.

    A stored null dismisses its region, as the model decided -- unless
    `recheck` is set (the client can see the page) and the null carries no
    `boxed` mark: it was decided before regions carried their boxes, blind to
    where the region was (measured: 13-15 of 47 regions flipped between runs
    that way), and it is asked once more. A null on a region OCR already set
    aside (punctuation only) is content, not a decision, and is never re-asked.
    A stored translation lifts a vision dismissal left on the region by an
    earlier pass over the same dicts. A stored "null" STRING that the user did
    not type is a null (llm.is_null_word): files written before the parser
    knew that hold it as text, and reading it as text painted "null" onto the
    page. It is not re-asked -- the model already answered.

    The caller translates only the returned ids, and writes only those back:
    a page with one gap is re-asked for the gap, with every stored translation
    and every edit left exactly as it was.
    """
    stored = cache.read_translation(h, lang, model)
    missing = set()
    for r in regions:
        # A vision dismissal already on the region belongs to whichever pass
        # put it there -- an earlier read of the same dicts, or a record saved
        # before decisions were stripped from it. Only this (lang, model)'s
        # stored entry decides.
        if r.get("dismiss_reason") == VISION_REASON:
            r.pop("not_text", None)
            r.pop("dismiss_reason", None)
        entry = stored.get(str(r["id"]))
        if entry is None:
            missing.add(r["id"])
            continue
        text = entry.get("text", "")
        worded = not entry.get("edited") and is_null_word(text)
        if worded:
            text = None
        if text is None:
            if recheck and not entry.get("boxed") and not worded and not r.get("not_text"):
                missing.add(r["id"])
                continue
            r["not_text"] = True
            r.setdefault("dismiss_reason", VISION_REASON)
        r["translation"] = text or ""
        r["edited"] = bool(entry.get("edited"))
    return missing


_UNSAFE_SEGMENT = re.compile(r'[<>:"|?*\x00-\x1f]')


def _safe_segment(seg: str) -> str:
    r"""One path segment, made safe to CREATE on Windows.

    The colon is the one that actually loses data, and it does so silently: a
    member named `page.png:hidden.png` is a valid NTFS alternate data stream
    reference, so the write SUCCEEDS, the directory listing shows only
    `page.png`, and the translated page is nowhere the user can find it. Not
    hypothetical -- verified by writing one. `\\?\` does not help, because an
    ADS is an NTFS feature rather than a Win32 path-parsing one.

    Trailing dots and spaces are stripped for the same class of reason: Windows
    silently drops them when creating a file, so `page .png` and `page.png`
    become the same file and the second archive member overwrites the first.

    A segment that HAD to be altered carries a short digest of its original
    name. Substitution alone is many-to-one -- `a<b.png` and `a_b.png` both
    became `a_b.png`, and the second silently overwrote the first, which the
    review measured. model_slug in cache.py appends a digest for exactly this
    reason; the first draft of this function did not, one file over.
    Unaltered names stay exactly as they were, so the ordinary archive is
    delivered under the names the user knows.

    The strip of trailing dots and spaces runs on the STEM. Run on the whole
    segment it never fired for `page. .png` (the segment ends in `g`), and the
    `_translated` suffix then landed after an interior trailing space -- a name
    Explorer cannot open, kept alive by the \\?\ prefix.

    Device names (CON, NUL, COM1) are deliberately NOT special-cased, and the
    reason is construction rather than measurement: imaging.output_path appends
    `_translated` to the stem, so `CON.png` is delivered as `CON_translated.png`
    and a bare device name can never be the file created. (Win32 does resolve
    `CON.png` to the console device in some APIs -- the first draft's claim
    that the extension made it ordinary was the wrong reason for the right
    conclusion.)
    """
    stem, ext = os.path.splitext(seg)
    clean_stem = _UNSAFE_SEGMENT.sub("_", stem).rstrip(". ")
    clean_ext = _UNSAFE_SEGMENT.sub("_", ext).rstrip(". ")
    if clean_stem == stem and clean_ext == ext and clean_stem:
        return seg
    digest = hashlib.sha256(seg.encode("utf-8")).hexdigest()[:8]
    return f"{clean_stem or '_'}-{digest}{clean_ext}"


_LANG_RE = re.compile(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{1,8})*")


def _check_lang(lang: str) -> None:
    """Reject a target language that is not a language tag.

    `lang` is substituted into the user's ComicInfo.xml as raw bytes, because
    AC-6 requires every other byte of that file back verbatim and no XML
    library preserves an input it has parsed. Raw substitution means a `lang`
    carrying `<`, `&` or a quote writes malformed XML into a file the AC
    promises is otherwise untouched. `source` was validated here from Phase 4
    and `lang` never was; it is the one that reaches a file.
    """
    if not _LANG_RE.fullmatch(str(lang)):
        raise ValueError(f"lang {lang!r} is not a language tag")


def item_dir(dest_dir, item_id) -> str:
    r"""The per-ITEM output directory. Every file an item produces lands here.

    AC-7's batch puts several items into one `dest_dir`, and both output names
    were keyed on the input's basename and the member's name alone -- so two
    volumes called `vol1.cbz` from different folders wrote the same
    `vol1_translated.cbz`, and any two archives carrying `ch1/p1.png` (which is
    most of them) wrote the same `ch1/p1_translated.png`. The second item
    silently destroyed the first, and the cache's placement records went on
    pointing at files another item had rewritten, which corrupts AC-13's resume
    as well as the output. Measured, not theorised.

    `_safe_segment` because `item_id` is a FILENAME from the user's disk and
    this is the one place it becomes a directory name.
    """
    return os.path.join(os.fspath(dest_dir), _safe_segment(str(item_id)))


def _member_dest(dest_dir, member: str) -> str:
    r"""Where one archive member's translated page lands, under `dest_dir`.

    `dest_dir` here is the ITEM's directory, not the job's -- see `item_dir`.

    The member's DIRECTORY structure is preserved, and it has to be: an archive
    with `ch1/p1.png` and `ch10/p1.png` -- which the CBZ fixture has, because
    real archives have it -- flattens to one `p1_translated.png`, and the
    second page silently overwrites the first. A collision that loses a page of
    the user's output is worse than a long path.

    Every member name is also SANITISED here, and this is the one place in the
    codebase that needs it. read_cbz is read-only and says so; the moment a
    member name is used to build a path being WRITTEN to, `..\..\startup` is a
    write outside dest_dir. Leading separators and every dot segment are
    dropped rather than rejected, because a page with an odd name should still
    be delivered somewhere sane. A colon is handled by _safe_segment, per
    segment -- NOT by os.path.splitdrive on the whole path, which the first
    draft used and which silently discarded the first segment of `a:b.png`
    as if it were a drive letter.

    Phase 6 owns traversal enforcement on INGEST, where a rejected archive is
    the right answer. Here the archive is already the user's and the page is
    already being translated, so the right answer is a safe path.
    """
    parts = []
    for seg in member.replace("\\", "/").split("/"):
        if seg in ("", ".", ".."):
            continue
        parts.append(_safe_segment(seg))
    safe = os.path.join(*parts) if parts else "page.png"
    return imaging.output_path(
        os.path.basename(safe), os.path.join(os.fspath(dest_dir), os.path.dirname(safe))
    )


def _deliver(img: Image.Image, dest_dir, member: str, fmt: str,
             src: Image.Image, page: int) -> str:
    """Encode and write one page of an ITEM. The last two stages, for archives.

    encode_and_write cannot serve this path: it re-opens the source FILE to
    learn the format, and an archive member lives inside a zip nobody re-opens
    here. Format comes from `fmt`, recorded at ingest, and the icc_profile and
    exif ride in on `src` -- which for a cached page is the cached raster,
    because cache.write_raster carried them there for exactly this call.
    """
    dest = _member_dest(dest_dir, member)
    emit("encode", os.path.basename(dest), page, 90)
    payload = imaging.encode(img, fmt, src)
    with atomic.atomic_write(dest) as fh:
        fh.write(payload)
    emit("write", os.path.basename(dest), page, 100)
    return atomic.long_path(dest)


def _container(src_path) -> str:
    """The container family of `src_path`, by signature: an archive family
    or `pdf.PDF`. Archives first, because `%PDF-` inside the first KB of a
    zip is a zip whose first member is a PDF, not a PDF."""
    try:
        return archive.detect_format(src_path)
    except archive.UnsupportedArchive:
        if pdf.detect(src_path):
            return pdf.PDF
        raise


def run_item(src_path, dest_dir, job_id, item_id=None, client=None, lang=DEFAULT_LANG,
             source=DEFAULT_SOURCE, cancel=None, on_page=None, on_total=None, members=None):
    """Every page of one archive or PDF, through the cache. Returns the record.

    `cancel` (Phase 9, AC-13) is the job's token. It is checked when each page
    has been read, inside the page immediately before translate -- so a cancel
    that landed during detect/OCR does not go on to spend a provider request --
    again when the reply is in, before erase and render, and before the
    repack. A request already in flight is not interrupted. Pages run
    PAGE_WINDOW at a time (see _run_pages); the ones past the last check when
    the token is set finish and are delivered. A set token raises Cancelled with the count of pages
    DELIVERED so far; the enforce_cap warning and the repack do not run,
    clear_running still does. No partial file can result, by construction
    rather than by care: every write in this module lands through
    atomic_write, so a page is either whole on disk or absent, and the
    archive is never begun. The pages already delivered STAY -- they are
    complete files, the next run reads the cache rather than them, and
    _repack's docstring has promised since Phase 6 that a cancelled job
    leaves the pages it finished where the next run can use them.

    The cache hit here is what AC-13's "a re-run skips completed pages" cashes
    out to, and it is keyed on the page's decoded pixels -- so a SECOND job with
    a NEW job_id hits it. That is the assert check_spotfix exists to hold: an
    earlier draft of the layout keyed the page directory on job_id, where this
    loop would have re-detected and re-OCR'd every page while every gate in the
    suite stayed green.
    """
    if source not in SOURCES:
        raise ValueError(f"source {source!r} is not one of {SOURCES}")
    _check_lang(lang)
    item_id = item_id or os.path.basename(os.fspath(src_path))
    model = _model_id(client)
    warning = None
    # Phase 6: every format AC-6 names, read through the AC-11 budget. The
    # budget's destination is dest_dir because that is where a member WOULD
    # land -- the escape rule is only meaningful relative to the root the
    # repack would write under, and taking the real one means the rule is
    # evaluated against the path the writer builds rather than a placeholder.
    # `members` makes this an `images` item (plan 1.1): a chapter of loose
    # page images, `src_path` their folder. Decided by the CALLER, never by
    # the path -- a group can be a subset of its folder, and _container
    # would read a directory as a broken archive.
    if members is not None:
        src_fmt = folder.IMAGES
        files = list(members)

        def read_pages(_src, _budget):
            return folder.pages(files)

        expected = len(files)
    else:
        src_fmt = _container(src_path)
        # Phase 7: a PDF is read by its own module and through the same
        # Budget. The rest of this loop is identical for both, which is the
        # point of the (ordinal, member, image) contract the readers share.
        read_pages = pdf.pages if src_fmt == pdf.PDF else archive.pages
        # The page count the progress lines carry, read before the first
        # page so the bar has an end to run to. Advisory and allowed to be
        # None -- see archive.expected_pages -- and never a reason for the
        # run to fail.
        expected = (pdf.page_count(src_path) if src_fmt == pdf.PDF
                    else archive.expected_pages(src_path))
    out_dir = item_dir(dest_dir, item_id)
    # `on_page(record)` after each delivered page and `on_total(n)` once,
    # here: the job's per-item progress (job.Item.note_page), so the Queue
    # can draw a page bar per row instead of counting whole files.
    if on_total is not None:
        on_total(expected)
    # The budget's root is the ITEM's directory, which is where a member would
    # actually land -- the escape rule has to be evaluated against the path the
    # writer builds, not against the job root one level above it.
    budget = safety.Budget(out_dir)
    format_warning = archive.CBR_WARNING if src_fmt == archive.RAR else None
    # Marked HERE, immediately before the try whose finally clears it, and
    # not at the top of the function: _container raises UnsupportedArchive
    # on a .cbz that is not one, and a mark with no matching clear left the
    # refcount at 1 for the process lifetime -- the job's pages pinned
    # against enforce_cap and its marker file on disk (review, measured).
    cache.mark_running(job_id)
    try:
        with expecting(expected, item_id):
            records = _run_pages(
                read_pages(src_path, budget), job_id, item_id, src_path, out_dir,
                client, lang, source, model, src_fmt, cancel, expected, on_page)
        # Once, at the end, and not per page. The plan says disk is "never
        # evicted mid-job", and per page it could not have reclaimed this job's
        # own pages anyway -- every one is pinned by its running marker -- while
        # walking the whole cache tree two hundred times for a two-hundred-page
        # item. It runs inside the try so the job is still marked running:
        # its pages are what the cap must not touch.
        #
        # A cancel that arrived while the last pages were finishing still
        # means no archive: the pages are delivered and cached, and the
        # resume repacks them without running a page.
        _check_cancel(cancel, item_id, len(records))
        warning = cache.enforce_cap(job_id)
        # Loose pages in, loose pages out: an `images` item has no archive.
        out_archive = ("" if src_fmt == folder.IMAGES
                       else _repack(src_path, out_dir, src_fmt, records, lang, budget))
    finally:
        cache.clear_running(job_id)

    return {
        "job_id": str(job_id),
        "item_id": item_id,
        "pages": records,
        "cache_warning": warning,
        "archive": out_archive,
        "src_format": src_fmt,
        "format_warning": format_warning,
    }


# Decoded pages in flight across the WHOLE process, not per item. The
# translation request is most of a page's wall time (measured: 19-27 s of a
# 25-50 s page against a gateway model, the GPU stages about 2 s), and one
# page at a time left two of the provider's three slots idle while the next
# pages waited to be detected. llm.MAX_CONCURRENT pages translating plus one
# being detected or erased keeps every slot fed. Process-wide because job.py
# runs four items at once: a per-item window of three was twelve decoded
# pages at a time -- three times the residency AC-12 was measured against,
# for no more provider throughput than the gate's three slots.
PAGE_WINDOW = MAX_CONCURRENT + 1
_SLOTS_LOCK = threading.Lock()
_SLOTS: dict[int, threading.BoundedSemaphore] = {}


def _page_slots() -> threading.BoundedSemaphore:
    """The process's page semaphore, sized by PAGE_WINDOW as it is NOW (a
    check can lower the window to prove what it buys)."""
    with _SLOTS_LOCK:
        if PAGE_WINDOW not in _SLOTS:
            _SLOTS[PAGE_WINDOW] = threading.BoundedSemaphore(PAGE_WINDOW)
        return _SLOTS[PAGE_WINDOW]


def _run_pages(pages, job_id, item_id, src_path, out_dir, client, lang, source,
               model, src_fmt, cancel, expected, on_page=None) -> list[dict]:
    """Run an item's pages concurrently. Returns records in page order.

    The reader stays on THIS thread -- pypdfium2 and the archive budget are
    not thread-safe -- and pulls the next decoded page only once it holds one
    of the process's PAGE_WINDOW slots, so decoded pages stay bounded across
    every item of every job (AC-12). Page hashing and placements happen here,
    in page order. A slot is released by the page's done-callback, which runs
    after the future holds its result or exception, so the reader that wakes
    on it always sees a page that failed.

    Cancel keeps its page-boundary meaning (AC-13): checked when the next page
    has been read, where the sequential loop checked it, and inside each page
    before and after its translation request. Pages past that point finish
    and are delivered; Cancelled counts every page that was. A failed page
    stops new pages, the pages in flight finish -- whole files either way, as
    after a cancel -- and the earliest page's error is raised.

    The reader is CLOSED here, on this thread, before anything is raised. Left
    to the garbage collector -- an exception held by this frame keeps the
    suspended generator alive in a cycle -- pdf.pages' finally took
    _PDFIUM_LOCK on whichever thread the collection ran, which deadlocked a
    thread already inside that lock (review: reproduced on scan.pdf).
    """
    import concurrent.futures as cf  # noqa: PLC0415 -- only the item path needs it

    slots = _page_slots()
    futures: list[cf.Future] = []

    def one(h, img, member, ordinal):
        # _EXPECTED is per thread: the worker publishes the item's page count
        # and id again, or its emits lose the `total` and `item_id` the UI uses.
        with expecting(expected, item_id), _page_lock(h):
            record = _run_cached_page(h, img, member, ordinal, item_id, out_dir, client,
                                      lang, source, model, src_fmt, cancel, 0)
        # The job-wide "in a row" count (Control.page_result). A refusal
        # remembered from an earlier run cost no request and says nothing new
        # about the provider, so it neither counts nor resets the streak.
        # Only pages that ASKED the provider move it: a cache hit or a
        # stored fallback says nothing about whether the provider works, and
        # counting them as successes kept a dead provider from ever pausing a
        # mostly cached re-run (review minor).
        skipped = record.get("skipped")
        if hasattr(cancel, "page_result"):
            if skipped and not skipped.get("remembered"):
                cancel.page_result(item_id, ordinal, failed=True)
            elif not skipped and record.get("asked_provider"):
                cancel.page_result(item_id, ordinal, failed=False)
        if on_page is not None:
            on_page(record)
        return record

    def page_failed():
        return any(f.done() and not isinstance(f.exception(), (type(None), Cancelled))
                   for f in futures)

    reader_error, cancelled = None, False
    reader = iter(pages)
    pool = cf.ThreadPoolExecutor(max_workers=PAGE_WINDOW,
                                 thread_name_prefix=f"pages-{item_id}"[:40])
    try:
        while True:
            slots.acquire()
            submitted = False
            try:
                if page_failed():
                    break
                try:
                    ordinal, member, img = next(reader)
                except StopIteration:
                    break
                if cancel is not None and cancel.is_set():
                    cancelled = True
                    break
                h = cache.page_hash(img)
                cache.put_placement(job_id, item_id, ordinal, h, member,
                                    src_path=os.fspath(src_path),
                                    kind=src_fmt if src_fmt == folder.IMAGES else None)
                future = pool.submit(one, h, img, member, ordinal)
                submitted = True
                future.add_done_callback(lambda _f: slots.release())
                futures.append(future)
                del img  # the worker holds the only reference now
            finally:
                if not submitted:
                    slots.release()
    except BaseException as e:  # noqa: BLE001 -- the reader's own failure, raised below
        reader_error = e
    finally:
        try:
            close = getattr(reader, "close", None)
            if close is not None:
                close()
        finally:
            # Even when close() raises: returning with pages still running
            # would let them write after run_item has cleared its running
            # marker and job.py has reported the item (review).
            pool.shutdown(wait=True)

    records, errors = [], []
    for f in futures:
        e = f.exception()
        if e is None:
            records.append(f.result())
        elif isinstance(e, Cancelled):
            cancelled = True
        else:
            errors.append(e)
    # Each future holds its exception, and so do the loop variables: drop
    # them all, or the raise below cycles exception -> traceback -> this
    # frame -> future -> exception.
    futures.clear()
    f = e = future = None  # noqa: F841
    if reader_error is not None:
        errors.append(reader_error)
        reader_error = None
    if errors:
        error = errors[0]
        errors.clear()
        try:
            raise error
        finally:
            del error
    if cancelled:
        if getattr(cancel, "paused", False):
            raise Paused(item_id, len(records), getattr(cancel, "pause_reason", ""))
        raise Cancelled(item_id, len(records))
    return records


# Per-page-hash locks, striped so the table stays bounded. Two workers on the
# same hash -- two formats of one chapter, two volumes sharing a blank page
# or a publisher's credits -- both MISS the cache and both write the same
# regions, raster and translation files, and on Windows os.replace onto a
# file another thread holds open is PermissionError [WinError 5], which the
# Item boundary reports as a FAILED item (review: 2 threads x 300 write+read
# pairs on one hash, 291 OSErrors; one FAILED item in a cold-cache batch of
# two identical archives). Under the lock the second worker waits, then
# HITS, which is also the cheaper outcome.
# 1024 stripes, not 64: a page holds its stripe through its translation, and
# with PAGE_WINDOW pages in flight two unrelated hashes sharing a stripe run
# one after the other. At 64 that was likely (review); at 1024 it is rare.
_PAGE_STRIPES = [threading.Lock() for _ in range(1024)]


def _page_lock(page_hash_: str) -> threading.Lock:
    return _PAGE_STRIPES[int(page_hash_[:8], 16) % len(_PAGE_STRIPES)]


def _run_cached_page(h, img, member, ordinal, item_id, out_dir, client, lang,
                     source, model, src_fmt, cancel=None, pages_done=0) -> dict:
    """One page of an item, through the cache. Called under `_page_lock(h)`.

    The seven stages in STAGES order, each emitting exactly once -- on the
    hit path too. The UI draws one bar segment per stage and reads the
    names, so a cached page that skipped a stage silently would leave the
    bar stuck at the one before it, and one that emitted a stage twice
    would run the bar backwards. Every branch emits its stage, once, and
    says whether it did work.
    """
    cached = cache.read_regions(h) if cache.has_page(h) else None
    if cached is not None and not cache.has_raster(h):
        # has_page said yes and the raster is gone. Reachable: another
        # job's enforce_cap can evict between the two calls, and across
        # PROCESSES the reference writes are still last-writer-wins, so
        # the in-process lock does not close it entirely. A cache is
        # allowed to lose an entry; it is not allowed to hand the
        # renderer a None and call it a page. Treated as a miss, which
        # costs a re-detect -- the cost the module docstring claims, on
        # the path where it is actually true.
        cached = None
    if cached is not None and cached.get("source", DEFAULT_SOURCE) != source:
        # Read under another source language: the cached text is the
        # other engine's. A miss, so this run's engine reads the page.
        cached = None

    # A client that sees the page decides not-text with each region's box, so
    # its nulls are trusted -- and a legacy null, decided without one, is
    # asked again. A legacy record (kept regions only) whose page holds such a
    # null has lost the very regions to re-ask, so the page is re-detected
    # once to get them back; detection is deterministic on the same pixels,
    # and a record it does not reproduce is left as it was.
    recheck = client is not None and not getattr(client, "text_only", False)
    redetect_failed = bool(cached and cached.get("redetect_failed"))
    legacy = (cached is not None and not cached.get("all_regions") and not redetect_failed
              and recheck and cache.has_unmarked_nulls(h))
    if cached is not None and not legacy:
        regions = cached["regions"]
        fmt, ocr_calls = cached.get("src_format", "PNG"), 0
        if src_fmt == pdf.PDF and fmt not in ("JPEG", "PNG"):
            # The page was first seen as, say, a WEBP member of a
            # CBZ and cached under that format; delivered as WEBP
            # bytes the PDF repack would fail at img2pdf after every
            # page was processed. A PDF page is JPEG or PNG, by the
            # reader's own naming.
            fmt = img.format or "PNG"
        emit("detect", f"{len(regions)} regions (cached)", ordinal, 10)
        emit("ocr", "0 calls (cached)", ordinal, 25)
    else:
        fmt = img.format or "PNG"
        # The models are not thread-safe and the route is. Three
        # concurrent run_item calls on an EMPTY cache all raised
        # DetectError out of OpenCV's forward pass (measured in
        # review) -- loud, not lossy, but cache.py now promises that
        # two jobs in one sidecar is the ordinary case, and the lock
        # in front of the cache is worth nothing if the detector
        # behind it falls over. manga-ocr under concurrency is
        # unmeasured and is serialised on the same principle. Phase 8's
        # queue made this lock MORE load-bearing, not idle: four workers
        # reach detect at once, and run_page takes the same lock.
        with _MODEL_LOCK:
            regions = detect(img, ordinal)
            ocr_calls = ocr(regions, img, ordinal, source)
        if legacy:
            before = {r["id"]: json.dumps(r["polygon"]) for r in cached["regions"]}
            again = {r["id"]: json.dumps(r["polygon"]) for r in regions}
            if any(again.get(rid) != poly for rid, poly in before.items()):
                print(f"cache: page {h[:12]} re-detected differently from its cached record; "
                      f"its not-text answers are kept as they were", file=sys.stderr, flush=True)
                regions, recheck, legacy, redetect_failed = cached["regions"], False, False, True
            else:
                # Saved NOW, not at the end of the page: the re-ask below writes
                # boxed answers, and a run stopped between that write and the
                # end -- a cancel, a render error -- left a record that was no
                # longer legacy (no unmarked null left) and still missing the
                # regions, for good (review).
                _persist(h, cached, regions, complete=True)
    complete = cached is None or legacy or bool(cached.get("all_regions"))

    # The user's own choice for this page wins while it covers the page: a
    # retry with another model, without the image, or typed by hand. Read
    # from that pair, nothing is asked, and the Settings model cannot put the
    # refused original back over the fix (plan 1.6).
    choice = _covering_choice(regions, h, lang)
    if choice is not None:
        model, recheck = choice["model"], False
    missing = _apply_translations(regions, h, lang, model, recheck=recheck)
    if choice is not None:
        # _covering_choice verified the pair covers every region but the
        # punctuation OCR set aside; those need no translation. Asking the
        # Settings model here sent a hand-translated page back to the model
        # that refused it, on every run (review C1).
        missing = set()
    skipped, asked = None, False
    if not missing:
        emit("translate", f"{len(regions)} regions (cached)", ordinal, 50)
    else:
        # The second check, before the stage that talks to the provider.
        # It does NOT interrupt a call already in flight -- a token set
        # during translate is seen at the next page, up to llm.TIMEOUT
        # later. What it buys is narrower and real: a cancel that arrived
        # while detect and OCR were running (seconds per page on CPU, under
        # _MODEL_LOCK) does not go on to spend a provider request. detect and
        # ocr are not yet persisted here (_persist is at the end), so the
        # cost is one page's re-detect on the next run.
        _check_cancel(cancel, item_id, pages_done)
        where = f"{item_id}, page {ordinal}" + (f" ({member})" if member else "")
        outcome = _translate_or_skip(regions, ordinal, client, lang, source, img, h, model,
                                     missing, recheck, where, cancel, item_id, pages_done)
        asked = outcome is None
        skipped = outcome if isinstance(outcome, dict) else None
    if skipped is not None:
        return _skip_page(h, img, regions, fmt, source, ordinal, item_id, member, out_dir,
                          cached, complete, redetect_failed, ocr_calls, src_fmt, skipped)
    # And once more after it, since pages run PAGE_WINDOW at a time: a page
    # whose reply arrives after the cancel stops here, before the erase and
    # the render, instead of finishing because it happened to be in flight.
    # Its translation is already cached for the resume; its detect and OCR
    # are not yet persisted, so the resume re-detects it, as before.
    _check_cancel(cancel, item_id, pages_done)
    detected = regions
    regions, dismissed = dismiss(detected)
    record = _finish_page(h, img, regions, detected, dismissed, fmt, source, ordinal, item_id,
                          member, out_dir, client, cached, complete, redetect_failed, ocr_calls,
                          src_fmt)
    if choice is not None:
        record["choice"] = choice
    record["asked_provider"] = asked
    return record


def _covering_choice(regions, h, lang) -> dict | None:
    """The user's choice for the page, when its pair covers every region.

    "Covers" is the stored file applied WITHOUT the legacy-null recheck, with
    the regions OCR set aside as punctuation counted as covered -- nobody
    translates those. A choice that does not cover the page (a region the
    record gained since) is not used, and the page is asked as usual.
    """
    choice = cache.read_choice(h, lang)
    if choice is None:
        return None
    probe = [dict(r) for r in regions]
    still = _apply_translations(probe, h, lang, choice["model"], recheck=False)
    set_aside = {r["id"] for r in regions
                 if r.get("not_text") and r.get("dismiss_reason") != VISION_REASON}
    return choice if not (still - set_aside) else None


STORED = "stored"  # _translate_or_skip: the stored translation was kept


def _translate_or_skip(regions, ordinal, client, lang, source, img, h, model, missing,
                       recheck, where, cancel, item_id, pages_done):
    """Translate the page's missing regions.

    Returns None when the provider answered, STORED when the re-ask failed
    and the stored translation is rendered instead, or the skip info dict.

    A refused or failed page no longer fails its item (plan 1.3): it comes
    back as a skip -- the original page goes in its slot -- and the run goes
    on. Four exits, in order:

      * a refusal REMEMBERED for this endpoint, model and image setting:
        skipped without a request (plan 1.4). Only refusals are remembered.
      * an account failure: the job pauses (Paused), because every page
        would fail the same way. A caller with no job to pause gets the
        ProviderError, as before.
      * the page already had a stored translation and only gaps or legacy
        nulls were re-asked: the stored translation is rendered, and the
        regions it does not cover stay as drawn (plan 1.3.1).
      * otherwise: skipped, with the provider's words for the review panel.

    A cancel or pause that landed in the retry gap wins over all of these:
    the page stops at its boundary, it is not reported skipped.
    """
    from .llm import ACCOUNT, REFUSED, ProviderError, SettingsError  # noqa: PLC0415

    with_image = client is not None and img is not None and not getattr(client, "text_only", False)
    key = refusal_key(client, with_image)
    stored_any = bool(cache.read_translation(h, lang, model))
    remembered = (cache.read_refusal(h, lang, key)
                  if client is not None and not stored_any else None)
    if remembered is not None:
        emit("translate", "skipped (refused before)", ordinal, 50)
        _log(f"translate: {where}: refused before by this model; skipped without asking")
        return dict(remembered, remembered=True)
    try:
        translate(regions, ordinal, client, lang, source, img=img, where=where, cancel=cancel)
    except SettingsError as e:
        _check_cancel(cancel, item_id, pages_done)
        _pause_job(cancel, item_id, pages_done, f"The model settings cannot be used: {e}")
        raise
    except ProviderError as e:
        _check_cancel(cancel, item_id, pages_done)
        if e.kind == ACCOUNT:
            _pause_job(cancel, item_id, pages_done,
                       f"The provider refused the account (HTTP {e.status}): {e.body[:300]}")
            raise
        if stored_any:
            _log(f"translate: {where}: re-asking failed ({e.kind}); the stored translation is kept")
            _keep_stored(regions, h, lang, model, refused=e.kind == REFUSED)
            emit("translate", f"{len(regions)} regions (stored)", ordinal, 50)
            return STORED
        info = {"kind": e.kind, "message": _describe_skip(e), "status": e.status,
                "detail": e.body[:4000], "model": model, "with_image": with_image}
        if e.kind == REFUSED:
            cache.write_refusal(h, lang, key, info)
        _log(f"translate: {where}: skipped ({e.kind}); the original page is kept in its slot")
        emit("translate", f"skipped ({e.kind})", ordinal, 50)
        return info
    # The whole page was asked, for context; only what was missing is
    # written. A stored translation the model now words differently is
    # not replaced, and the read-back below puts it back on the region.
    cache.write_translation(
        h, lang, model,
        {r["id"]: None if r.get("not_text") else r.get("translation", "")
         for r in regions if r["id"] in missing},
        boxed=recheck,
    )
    cache.clear_refusals(h, lang)
    # Read back, deliberately. write_translation refuses to overwrite an
    # `edited` entry, so the file it just wrote and the regions in memory can
    # disagree about exactly the regions the user corrected -- and the
    # regions in memory are what gets RENDERED. Without this the page would
    # show the fresh translation while the cache said the edit was kept,
    # which is the worst of both: the correction is not discarded, it is
    # just not on the page. Reachable when coverage was partial (a
    # half-written translation file) and an edit exists.
    _load_translations(regions, h, lang, model)
    return None


def _keep_stored(regions, h, lang, model, refused: bool) -> None:
    """Render the page from its stored translation; what it lacks stays as drawn.

    Reached when re-asking a gap or a legacy null failed (plan 1.3.1). The
    page already had a translation and losing it to a skip would put the
    original back over work the user had. But the regions as they stand are
    unsafe to render: a legacy null being re-asked left _apply_translations
    before `not_text` was set, and a gap never got a `translation` -- both
    would be erased and typeset as "". So the stored file is applied again
    WITHOUT the recheck, and every region it still does not cover is marked
    the way _pair_decisions marks one: off the page, art untouched,
    editable in the Editor.

    When the model REFUSED the re-ask, the legacy nulls it was asked about
    are marked boxed, so the page is not re-sent on every run to be refused
    again. An outage leaves them unmarked: next time may work.
    """
    still = _apply_translations(regions, h, lang, model, recheck=False)
    for r in regions:
        # A region already off the page keeps its own reason: overwriting
        # OCR's "punctuation only" with the vision reason made _persist strip
        # it from the record, and the page lost the region's set-aside for
        # good (review C1).
        if r["id"] in still and not r.get("not_text"):
            r["not_text"], r["dismiss_reason"] = True, VISION_REASON
        r.setdefault("translation", "")
    if refused:
        stored = cache.read_translation(h, lang, model)
        nulls = {rid: None for rid, v in stored.items()
                 if isinstance(v, dict) and v.get("text") is None
                 and not v.get("boxed") and not v.get("edited")}
        if nulls:
            cache.write_translation(h, lang, model, nulls, boxed=True)


EMPTY_FIT = {"fit_compromised": [], "fit_failed": [], "retranslated": []}
SKIPPED_REASON = "the page was skipped"


def _skip_page(h, img, regions, fmt, source, ordinal, item_id, member, out_dir, cached,
               complete, redetect_failed, ocr_calls, src_fmt, skipped) -> dict:
    """Deliver the ORIGINAL page into its slot and report it skipped (plan 1.3).

    Everything a retry needs is cached first, so it costs one provider
    request and nothing else: the detected regions (no re-detect, no OCR)
    and the page itself as the raster of the EMPTY erased set -- erasing no
    regions leaves the page as it was (inpainter.erase with no regions), so
    this raster IS the original, and a retry erases its regions from it the
    way _rerender_locked erases a skipped region.

    Every stage still emits exactly once (STAGES): translate already did,
    inpaint and render say "skipped", and _deliver emits encode and write.
    The record has the full page shape the UI reads -- empty fit summary,
    no kept regions -- and the regions under `dismissed`, NOT editable: a
    single-region rerender on a page with no translation would only raise
    CacheMiss; the Editor's manual mode is where these get typed.
    """
    detected = regions
    content = {"page_hash": h, "src_format": fmt, "source": source,
               "detections": len(detected), "fit_summary": EMPTY_FIT}
    _persist(h, content, detected, complete, redetect_failed)
    if cache.read_raster(h, set()) is None:
        cache.write_raster(h, img, src=img, kept=set())
    emit("inpaint", "0 calls (skipped)", ordinal, 65)
    emit("render", "skipped", ordinal, 80)
    out_path = _deliver(img, out_dir, member, fmt, img, ordinal)
    record = {
        "page": ordinal,
        "page_hash": h,
        "item_id": item_id,
        "member": member,
        "src_format": fmt,
        "source": source,
        "output": out_path,
        "cached": cached is not None and not ocr_calls,
        "detections": 0,
        "ocr_calls": ocr_calls,
        "inpaint_calls": 0,
        "fit_summary": {k: list(v) for k, v in EMPTY_FIT.items()},
        "regions": [],
        "dismissed": [{"id": r["id"], "polygon": r["polygon"], "text": r.get("text"),
                       "reason": SKIPPED_REASON, "editable": False} for r in detected],
        "skipped": skipped,
    }
    if src_fmt == pdf.PDF:
        record["pdf_extract"] = img.info.get("pdf_extract")
    return record


def _finish_page(h, img, regions, detected, dismissed, fmt, source, ordinal, item_id, member,
                 out_dir, client, cached, complete, redetect_failed, ocr_calls,
                 src_fmt) -> dict:
    """Erase, render, deliver and record a translated page."""
    # The cached raster erased one set of regions. This run's model may keep
    # another -- a region another model dismissed, or dismiss one it kept --
    # and then the raster is wrong for this page either way: text left under
    # a translation, or a patch of erased art where nothing will be drawn.
    kept = {r["id"] for r in regions}
    cleaned = cache.read_raster(h, kept)
    if cleaned is not None:
        inpaint_calls = 0
        emit("inpaint", "0 calls (cached)", ordinal, 65)
    else:
        cleaned, inpaint_calls = inpaint(img, regions, ordinal)
        cache.write_raster(h, cleaned, src=img, kept=kept)

    drawn, fit_summary = render(cleaned, regions, ordinal, client)
    out_path = _deliver(drawn, out_dir, member, fmt, cleaned, ordinal)

    record = {
        "page": ordinal,
        "page_hash": h,
        "item_id": item_id,
        "member": member,
        "src_format": fmt,
        "source": source,
        "output": out_path,
        "cached": cached is not None and not ocr_calls,
        "detections": len(regions),
        "ocr_calls": ocr_calls,
        "inpaint_calls": inpaint_calls,
        "fit_summary": fit_summary,
        "regions": regions,
        "dismissed": dismissed,
    }
    if src_fmt == pdf.PDF:
        # Which path the page took, so check_pdf can assert the
        # render fallback was NOT taken without re-reading the PDF.
        record["pdf_extract"] = img.info.get("pdf_extract")
    # Written back on EVERY pass, hit or miss. The fit flags are derived
    # by render, so a cached record whose region was edited shorter must
    # not keep last run's fit_compromised. Nothing here reads a stored
    # flag back in as input -- see cache.py's closing paragraph.
    _persist(h, record, detected, complete, redetect_failed)
    return record


def _repack(src_path, dest_dir, src_fmt: str, records: list[dict], lang: str,
            budget) -> str:
    """AC-6's round trip: the delivered pages, back into the input's format.

    **The loose pages stay.** They are what the spot-fix editor re-renders into
    and what AC-13's resume reads, and the archive is built FROM them rather
    than instead of them -- so a cancelled job leaves the pages it finished
    where the next run can use them, which an archive-only output cannot do
    (a half-written archive is not half a job, it is nothing). They are also
    what repack_item reads after an edit, so the volume can be rebuilt without
    rendering a page. The duplication is the price of these properties and it
    is paid on disk, not in RSS: the archive repack streams one page at a
    time. The PDF repack does not quite
    -- img2pdf's internal engine holds every page's bytes until it writes,
    about one copy of the output (1.02x measured); see `pdf.write_pdf`.

    Member names are the INPUT's, verbatim, so the member set round-trips
    identically. The delivered file's name carries `_translated`; the member
    inside the archive does not, because a reader app shows member names and
    two hundred pages all saying `_translated` is noise the user did not ask
    for.
    """
    if not records:
        # Nothing decoded. An empty archive is worse than no archive: it looks
        # to the user like the job succeeded and produced a volume of nothing.
        return ""

    if src_fmt == pdf.PDF:
        # img2pdf reads the delivered files itself and embeds their bytes
        # verbatim; the page boxes come from the source. No extras, no
        # ComicInfo: a PDF's metadata is its outline and /Info, and
        # write_pdf carries both.
        return pdf.write_pdf(
            pdf.output_path(src_path, dest_dir),
            [record["output"] for record in records], src_path,
        )

    out_fmt = archive.OUTPUT_FORMAT[src_fmt]
    dest = archive.output_path(src_path, dest_dir)

    def entries():
        # Read, close, THEN yield: the writer deflates (or LZMA-compresses,
        # for 7z) the payload while the generator is suspended, and a handle
        # held open across that is a sharing violation for the re-render
        # that wants to replace this very file. open_retry for the other
        # half -- the read that lands in the instant of that replace.
        for record in records:
            with atomic.open_retry(atomic.long_path(record["output"]), "rb") as fh:
                payload = fh.read()
            yield record["member"], payload

    # A FRESH budget for the re-read below, not the one the page loop
    # exhausted: that one has already counted every page of this archive, so
    # reusing it would charge the same bytes twice and refuse a legitimate
    # volume on its own second pass. Same rules, same caps, new archive-scoped
    # accounting -- which is what a second read of the archive is.
    #
    # And ONE re-read, through repack_extras. Calling comicinfo() and extras()
    # separately ran two admission passes over this one budget, which counted
    # every member twice and refused `member-count` at half the advertised cap
    # -- after every page had been translated, and with job.run_item then
    # deleting the output as an unsafe archive's. See repack_extras.
    reread = safety.Budget(dest_dir, max_members=budget.max_members,
                           max_ratio=budget.max_ratio,
                           max_file_bytes=budget.max_file_bytes,
                           max_total_bytes=budget.max_total_bytes)
    comic, extra = archive.repack_extras(src_path, reread)
    return archive.write_archive(
        dest, entries(), out_fmt, comic, lang, extra_entries=extra,
    )


def _is_images(placed) -> bool:
    """Whether a placement (or a source path) is a chapter of loose pages.

    The placement's `kind` decides; a source path that is a folder is the
    fallback for placements written before `kind` existed.
    """
    if isinstance(placed, dict):
        if placed.get("kind") == folder.IMAGES:
            return True
        placed = placed.get("src_path")
    return bool(placed) and os.path.isdir(atomic.long_path(os.fspath(placed)))


def repack_item(job_id, item_id, dest_dir, lang=DEFAULT_LANG) -> str:
    """The item's archive, rebuilt from the loose pages already on disk.

    What run_item's closing _repack does, without the page loop in front of
    it: no page is decoded, rendered or re-encoded here. The delivered files
    are read back in placement order and streamed into a fresh archive at the
    same path, so an edit the spot-fix editor wrote into one loose page is in
    the volume too. Runs off the request thread -- see schedule_repack -- and
    so is allowed the seconds a two-hundred-page volume takes.

    The output path is derived, not stored: _member_dest is a pure function of
    (item directory, member name), and _deliver writes to exactly that. Deriving
    it here keeps one source of truth for where a page lands; storing it in
    the placement would be a second one that could drift.
    """
    placed = cache.item_placements(job_id, item_id)
    if not placed:
        raise CacheMiss(f"job {job_id} has no pages of item {item_id!r}", "placement")
    src_path = placed[0][1].get("src_path")
    if not src_path:
        raise CacheMiss(
            f"job {job_id} did not record where item {item_id!r} came from; "
            f"run the item again to rebuild its archive", "placement")
    if _is_images(placed[0][1]):
        # A chapter of loose pages has no archive: the edited page on disk
        # IS the output. Nothing to rebuild.
        return ""
    out_dir = item_dir(dest_dir, item_id)
    records = []
    for ordinal, entry in placed:
        member = entry.get("member") or f"{item_id}_{ordinal:04d}.png"
        records.append({"member": member, "output": _member_dest(out_dir, member)})
    missing = [r["output"] for r in records if not os.path.exists(atomic.long_path(r["output"]))]
    if missing:
        raise CacheMiss(
            f"{len(missing)} of item {item_id!r}'s {len(records)} delivered pages "
            f"are no longer on disk (first: {missing[0]}); run the item again", "placement")
    return _repack(src_path, out_dir, _container(src_path), records, lang,
                   safety.Budget(out_dir))


# Quiet time after an edit before the archive is rebuilt. Long enough that a
# user correcting three bubbles on one page pays for one repack, short enough
# that the volume is current by the time they open it.
REPACK_DELAY = 1.0

# A pass running longer than this is reported as failed rather than running:
# repack_item cannot be interrupted, and a dest_dir on a network share or an
# antivirus holding the temp file could otherwise leave the editor saying
# "updating" for the rest of the session. Five minutes is ten times a
# 200-page volume's measured repack.
REPACK_STALL = 300.0

_REPACK_LOCK = threading.Lock()
_REPACKS: dict[tuple[str, str], dict] = {}
_REPACK_PUBLIC = ("status", "archive", "error", "edits", "repacks")


def schedule_repack(job_id, item_id, dest_dir, lang=DEFAULT_LANG) -> dict:
    """Rebuild the item's archive soon, on a worker thread. Returns the status.

    rerender calls this and returns; the request never waits on the archive.
    AC-10 budgets 3.0s for a re-render and the repack of a large volume is
    more than that, so the response says `archive_stale` and this status says
    when it stops being true -- /api/repack serves the same dict, and the UI
    polls it while it reads pending or running.

    Debounced and coalesced: every call restarts one timer per item, and an
    edit that lands while a repack is running is not lost -- the worker
    compares the edit counter after each pass and goes again. So the archive
    on disk always ends up carrying the LAST edit, and a burst of edits costs
    one repack, or two when one was already under way.
    """
    key = (str(job_id), str(item_id))
    with _REPACK_LOCK:
        st = _REPACKS.setdefault(key, {
            "status": "idle", "archive": "", "error": "", "edits": 0, "repacks": 0,
            "running": False, "timer": None, "since": 0.0,
        })
        st["edits"] += 1
        # A pass under way keeps saying so: it will go again for this edit
        # (see _repack_worker), so "pending" would be a step backwards.
        st["status"], st["error"] = ("running" if st["running"] else "pending"), ""
        st["dest_dir"], st["lang"] = os.fspath(dest_dir), lang
        if st["timer"] is not None:
            st["timer"].cancel()
        timer = threading.Timer(REPACK_DELAY, _repack_worker, (key,))
        timer.daemon = True  # a repack mid-write at exit is a temp file, not a torn archive
        st["timer"] = timer
        timer.start()
        return {k: st[k] for k in _REPACK_PUBLIC}


def repack_status(job_id, item_id) -> dict:
    """The repack status for one item: idle, pending, running, done or failed."""
    with _REPACK_LOCK:
        st = _REPACKS.get((str(job_id), str(item_id)))
        if st is None:
            return {"status": "idle", "archive": "", "error": "", "edits": 0, "repacks": 0}
        public = {k: st[k] for k in _REPACK_PUBLIC}
        stalled = st["running"] and time.monotonic() - st["since"] > REPACK_STALL
        if stalled:
            public["status"] = "failed"
            public["error"] = (f"the archive rebuild has been running for "
                               f"{time.monotonic() - st['since']:.0f}s; check the "
                               f"output folder, and run the item again if it is behind")
        return public


def _repack_worker(key: tuple[str, str]) -> None:
    with _REPACK_LOCK:
        st = _REPACKS[key]
        if st["running"]:
            # The pass under way re-checks the edit counter when it finishes
            # and goes again; a second worker would write the same archive.
            return
        st["running"] = True
    while True:
        with _REPACK_LOCK:
            st["status"], st["since"] = "running", time.monotonic()
            seen, dest_dir, lang = st["edits"], st["dest_dir"], st["lang"]
        try:
            out, err = repack_item(key[0], key[1], dest_dir, lang), ""
        except Exception as e:  # noqa: BLE001 -- the status carries it; a thread has nowhere else to put it
            out, err = "", f"{type(e).__name__}: {e}"
        with _REPACK_LOCK:
            st["repacks"] += 1
            if st["edits"] != seen:
                # An edit landed mid-pass: the archive just written is already
                # behind, so go again. Its own timer is still armed and would
                # run a third pass over inputs this next one covers; cancel it.
                if st["timer"] is not None:
                    st["timer"].cancel()
                    st["timer"] = None
                continue
            st["status"] = "failed" if err else "done"
            st["archive"], st["error"], st["running"] = out, err, False
            return


def flush_repacks(timeout: float = 30.0) -> None:
    """Every pending repack, now, on this thread. For the exit paths.

    The app does not call /api/shutdown on quit: it closes the sidecar's
    stdin and watch_parent exits on the EOF. A daemon timer armed one second
    ago never fires across that, and a worker mid-write is killed with its
    temp file beside the archive -- so an edit made and then the app closed
    would leave the loose page current and the volume behind, the exact
    state this machinery exists to end. Called before os._exit: pending
    timers are cancelled and their repacks run inline; a worker already
    running is waited for, up to `timeout`, so a 200-page volume finishes
    and a hung one does not hold the port past the next launch.
    """
    deadline = time.monotonic() + timeout
    with _REPACK_LOCK:
        keys = [k for k, st in _REPACKS.items() if st["status"] in ("pending", "running")]
        for k in keys:
            if _REPACKS[k]["timer"] is not None:
                _REPACKS[k]["timer"].cancel()
                _REPACKS[k]["timer"] = None
    for k in keys:
        _repack_worker(k)  # inline when idle; returns at once when a worker has it
    while time.monotonic() < deadline:
        with _REPACK_LOCK:
            if not any(_REPACKS[k]["running"] for k in keys):
                return
        time.sleep(0.05)


def rerender(job_id, item_id, ordinal: int, region_id: int, text: str, dest_dir,
             client=None, lang=DEFAULT_LANG) -> dict:
    """AC-10: one region's text changes, that page alone is re-drawn.

    Neither `detect` nor `ocr` is called from here, and check_spotfix proves it
    by COUNTER rather than by reading this source: both entrypoints are patched
    to increment-and-raise for the duration of the wall-clock case. A source
    assert would keep passing the day an indirect call arrives.

    `allow_retranslate=False` is the other half. On this path the user's text is
    authoritative: rung 5 re-translating it would overwrite the `edited: true`
    entry this same phase forbids overwriting, and the round trip would not fit
    inside AC-10's 3.0s budget. A too-long edit truncates and reports
    fit_failed, which is the honest outcome and costs zero requests.

    Under the page lock, like a page of a run: an edit that read the record
    while a run on the same page hash was migrating it -- the legacy record
    saved with all its regions, the boxed answers written -- and persisted
    after would put the kept-only regions back with all_regions False, and
    with no unmarked null left to trigger it the page is never re-detected
    again (review). The wait is one page's worth at most.
    """
    placed = cache.get_placement(job_id, item_id, ordinal)
    if placed is None:
        raise CacheMiss(
            f"job {job_id} has no page {ordinal} of item {item_id!r}", "placement"
        )
    with _page_lock(placed["page_hash"]):
        return _rerender_locked(placed, job_id, item_id, ordinal, region_id, text, dest_dir,
                                client, lang)


# -- Phase 2: the workarounds for a skipped page ---------------------------------

RETRY_MODES = ("same", "text_only", "model")
MANUAL_MODEL = "#manual"   # a model key no real model id can be (plan 1.6)


def text_only_model(model: str) -> str:
    """The key a translation made WITHOUT the page image is stored under, so
    a later run that does send the image never reuses it (llm.py's warning
    about a cache key that does not record the image)."""
    return f"{model}#text"


def _skipped_page_inputs(job_id, item_id, ordinal):
    """(placement, content record, original page) for a page of a job, or
    CacheMiss saying to run the item again. The original is the empty-set
    raster a skip cached; it is pinned while the job exists, so a miss here
    means the job is gone or the cache was cleared."""
    placed = cache.get_placement(job_id, item_id, ordinal)
    if placed is None:
        raise CacheMiss(f"job {job_id} has no page {ordinal} of item {item_id!r}", "placement")
    h = placed["page_hash"]
    record = cache.read_regions(h)
    if record is None:
        raise CacheMiss(f"page {ordinal} of item {item_id!r} is no longer cached; "
                        f"run the item again", "cache")
    original = cache.read_raster(h, set())
    if original is None:
        raise CacheMiss(f"page {ordinal} of item {item_id!r} has no cached original; "
                        f"run the item again", "raster")
    return placed, record, original


def _render_fixed(placed, record, original, regions, item_id, ordinal, dest_dir, client,
                  *, allow_retranslate: bool, choice: dict | None) -> dict:
    """Erase, render and deliver a page the user fixed, and persist it."""
    h = placed["page_hash"]
    detected = regions
    kept, dismissed = dismiss(detected)
    page = _finish_page(
        h, original, kept, detected, dismissed, record.get("src_format", "PNG"),
        record.get("source", DEFAULT_SOURCE), ordinal, item_id,
        placed.get("member") or f"{item_id}_{ordinal:04d}.png",
        item_dir(dest_dir, item_id), client if allow_retranslate else None, record,
        bool(record.get("all_regions")), bool(record.get("redetect_failed")), 0, "")
    page["cached"] = True
    if choice is not None:
        page["choice"] = choice
    return page


def retry_page(job_id, item_id, ordinal: int, dest_dir, client, lang=DEFAULT_LANG,
               mode: str = "same") -> dict:
    """One skipped page, asked again (plan 2.1). Returns its fresh record.

    `mode` is the user's pick in the review panel:
      * "same"      the Settings model, as the run asked it (for an outage);
      * "model"     `client` is another model on the same endpoint;
      * "text_only" the OCR text alone, without the page image -- what
        most often gets past a refusal the ARTWORK triggered.
    Detection and OCR come from the cache; the only cost is the request.

    On success the page is erased, rendered and delivered, the refusal
    markers go, and for "model" and "text_only" the pair is recorded as the
    user's choice (cache.write_choice) so no later run undoes it. A refusal
    rewrites the marker under this request's key; an outage or a bad reply
    leaves the markers alone. Both come back as the page's skipped record.
    An ACCOUNT failure raises the ProviderError: the caller stops the whole
    retry there and writes nothing more -- an expired key must not stamp
    markers on every page it touches.
    """
    from .llm import ACCOUNT, REFUSED, ProviderError  # noqa: PLC0415

    if mode not in RETRY_MODES:
        raise ValueError(f"mode {mode!r} is not one of {RETRY_MODES}")
    placed = cache.get_placement(job_id, item_id, ordinal)
    if placed is None:
        raise CacheMiss(f"job {job_id} has no page {ordinal} of item {item_id!r}", "placement")
    with _page_lock(placed["page_hash"]):
        placed, record, original = _skipped_page_inputs(job_id, item_id, ordinal)
        h = placed["page_hash"]
        with_image = mode != "text_only" and not getattr(client, "text_only", False)
        model = _model_id(client)
        key_model = text_only_model(model) if mode == "text_only" else model
        regions = [dict(r) for r in record["regions"]]
        missing = _apply_translations(regions, h, lang, key_model, recheck=with_image)
        if missing:
            where = f"{item_id}, page {ordinal} (retry, {mode})"
            try:
                translate(regions, ordinal, client, lang, record.get("source", DEFAULT_SOURCE),
                          img=original if with_image else None, where=where)
            except ProviderError as e:
                if e.kind == ACCOUNT:
                    raise
                info = {"kind": e.kind, "message": _describe_skip(e), "status": e.status,
                        "detail": e.body[:4000], "model": model, "with_image": with_image}
                if e.kind == REFUSED:
                    cache.write_refusal(h, lang, refusal_key(client, with_image), info)
                _log(f"translate: {where}: still failing ({e.kind})")
                return {"page": ordinal, "page_hash": h, "item_id": item_id,
                        "member": placed.get("member"), "skipped": info}
            cache.write_translation(
                h, lang, key_model,
                {r["id"]: None if r.get("not_text") else r.get("translation", "")
                 for r in regions if r["id"] in missing},
                boxed=with_image)
            _load_translations(regions, h, lang, key_model)
        cache.clear_refusals(h, lang)
        # Every successful retry records its pair (plan 2.1.2.4), "same"
        # included: an older choice must not outrank the page just fixed.
        choice = {"model": key_model,
                  "mode": {"text_only": "text_only", "model": "model"}.get(mode, "vision")}
        cache.write_choice(h, lang, choice["model"], choice["mode"])
        return _render_fixed(placed, record, original, regions, item_id, ordinal, dest_dir,
                             client, allow_retranslate=True, choice=choice)


def manual_page(job_id, item_id, ordinal: int, texts: dict, dest_dir,
                lang=DEFAULT_LANG) -> dict:
    """A skipped page translated by the user, every bubble at once (plan 2.2).

    `texts` is {region_id: text}. Each text is stored under the `#manual`
    key as an edit. Every region NOT in `texts`, and every blank one, is
    stored as a null marked `boxed` -- "no text here", decided -- so it stays
    as drawn and is never sent to a model on a later run. Regions OCR set
    aside as punctuation are left as they are. No provider is asked, and
    rung 5 does not shorten the user's words.
    """
    placed = cache.get_placement(job_id, item_id, ordinal)
    if placed is None:
        raise CacheMiss(f"job {job_id} has no page {ordinal} of item {item_id!r}", "placement")
    with _page_lock(placed["page_hash"]):
        placed, record, original = _skipped_page_inputs(job_id, item_id, ordinal)
        h = placed["page_hash"]
        given = {}
        for k, v in (texts or {}).items():
            try:
                given[int(k)] = v
            except (TypeError, ValueError):
                continue
        nulls, words = {}, {}
        for r in record["regions"]:
            if r.get("not_text") and r.get("dismiss_reason") != VISION_REASON:
                # Punctuation OCR set aside: stored as a decided null too, so
                # the #manual pair covers EVERY region (review C1).
                nulls[r["id"]] = None
                continue
            text = given.get(r["id"])
            if isinstance(text, str) and text.strip():
                words[r["id"]] = text
            else:
                nulls[r["id"]] = None
        if nulls:
            # overwrite_edits: a bubble typed in an earlier hand translation
            # and left blank now is cleared, as the user asked.
            cache.write_translation(h, lang, MANUAL_MODEL, nulls, boxed=True,
                                    overwrite_edits=True)
        for rid, text in words.items():
            cache.write_edit(h, lang, MANUAL_MODEL, rid, text)
        cache.write_choice(h, lang, MANUAL_MODEL, "manual")
        cache.clear_refusals(h, lang)
        regions = [dict(r) for r in record["regions"]]
        _apply_translations(regions, h, lang, MANUAL_MODEL, recheck=False)
        return _render_fixed(placed, record, original, regions, item_id, ordinal, dest_dir,
                             None, allow_retranslate=False,
                             choice={"model": MANUAL_MODEL, "mode": "manual"})


def _pair_decisions(regions: list[dict], h: str, lang: str, model: str) -> list[dict]:
    """The page's regions with this (lang, model)'s translations and nulls on them.

    A region the pair holds no entry for predates it: the record gained
    regions another model had once dismissed, and this pair never saw them.
    Those are off this pair's page, as they were when it was translated.
    """
    never_seen = _apply_translations(regions, h, lang, model)
    for r in regions:
        if r["id"] in never_seen:
            r["not_text"], r["dismiss_reason"] = True, VISION_REASON
    return regions


def _rerender_locked(placed, job_id, item_id, ordinal, region_id, text, dest_dir,
                     client, lang) -> dict:
    h = placed["page_hash"]
    record = cache.read_regions(h)
    if record is None or not cache.has_page(h):
        raise CacheMiss(f"page {ordinal} of item {item_id!r} is not in the page cache")

    regions = record["regions"]
    if not any(r["id"] == region_id for r in regions):
        raise CacheMiss(f"region {region_id} is not on page {ordinal}", "region")

    # The pair the page was RENDERED from: the user's choice when there is
    # one (a page fixed with another model, without the image, or by hand),
    # else the Settings model. Editing a fixed page while Settings names
    # another model would otherwise miss its translation file (plan 1.6).
    choice = cache.read_choice(h, lang)
    model = choice["model"] if choice else _model_id(client)
    # Coverage BEFORE the edit is written. A (lang, model) pair this page was
    # never translated under has no text for the other regions, and this path
    # never translates -- so rendering would put the user's edit in one bubble
    # and the OLD language's text from regions.json in every other. The review
    # called it a mixed-language page, and it is exactly that. Run the item at
    # that pair first; the error says so.
    stored = cache.read_translation(h, lang, model)
    # A pair that never translated this page has no text for its other
    # regions -- the mixed-language page below. A pair that DID, but holds no
    # entry for a region, predates it: the record gained regions another model
    # had once dismissed, and this pair never saw them. Those are off this
    # pair's page, as they were when it was translated (review).
    uncovered = [r["id"] for r in regions if r["id"] != region_id
                 and str(r["id"]) not in stored] if not stored else []
    if uncovered:
        raise CacheMiss(
            f"page {ordinal} has no {lang!r} translation under model {model!r} "
            f"for regions {uncovered}; run the item at that language first",
            "translation",
        )
    # A region the MODEL dismissed is editable: its null was a call, and the
    # user typing a translation overrules it. One OCR set aside as punctuation
    # is not -- the edit would be saved and the region would stay off the
    # page, and the editor would say "re-rendered" over no change at all.
    target = next(r for r in regions if r["id"] == region_id)
    if target.get("not_text") and target.get("dismiss_reason") != VISION_REASON:
        raise CacheMiss(
            f"region {region_id} on page {ordinal} was set aside "
            f"({target.get('dismiss_reason') or 'not text'}); there is nothing to translate there",
            "region")
    complete = bool(record.get("all_regions"))
    # The erased set BEFORE the edit, from a copy: an edit to a skipped region
    # grows the set by that region, and its raster is the base it is erased
    # onto below.
    kept_before = {r["id"] for r in dismiss(_pair_decisions([dict(r) for r in regions],
                                                            h, lang, model))[0]}
    cache.write_edit(h, lang, model, region_id, text)
    detected = _pair_decisions(regions, h, lang, model)
    regions, dismissed = dismiss(detected)
    kept = {r["id"] for r in regions}
    # The raster for THIS pair's kept set, or none: the page was last erased
    # under another model's or language's set, and typesetting over that raster
    # would leave the original text under the edit (review). The edit is saved;
    # the next run of the item draws it.
    cleaned = cache.read_raster(h, kept)
    if cleaned is None and kept - kept_before == {region_id}:
        # A skipped region, translated by hand. The source page is inside an
        # archive this path never re-opens, but it does not need to be: the
        # raster of the set without this region still shows its original
        # lettering, and erasing that one region's glyphs onto it is the
        # raster of the set with it. Cached under the new set, like any other.
        base = cache.read_raster(h, kept_before)
        if base is not None:
            cleaned, _calls = inpaint(base, [r for r in regions if r["id"] == region_id],
                                      ordinal)
            cache.write_raster(h, cleaned, src=base, kept=kept)
    if cleaned is None:
        raise CacheMiss(
            f"page {ordinal} was last erased for another model's or language's regions; "
            f"the edit is saved -- run the item again to see it", "raster")

    drawn, fit_summary = render(
        cleaned, regions, ordinal, client, allow_retranslate=False
    )
    # The member name comes from the PLACEMENT, never from the page record:
    # two identical pages share one record and only one of them can be named in
    # it, so taking it from there delivers this edit over the other ordinal's
    # file. That is the placement assert's whole subject.
    out_path = _deliver(
        drawn, item_dir(dest_dir, item_id),
        placed.get("member") or f"{item_id}_{ordinal:04d}.png",
        record.get("src_format", "PNG"), cleaned, ordinal,
    )

    # Position facts come from the PLACEMENT and the request, never from the
    # content record -- see CONTENT_KEYS. `page` in particular: the UI posts
    # back whatever `page` it was handed, so a response carrying the shared
    # record's ordinal sends the user's next edit to the other identical page.
    record = dict(
        record,
        page=ordinal,
        item_id=item_id,
        member=placed.get("member"),
        output=out_path,
        cached=True,
        ocr_calls=0,
        inpaint_calls=0,
        fit_summary=fit_summary,
        regions=regions,
        # The editor's skipped list comes from here after an edit, as it comes
        # from run_item's record before one.
        dismissed=dismissed,
        edited_region=region_id,
        # The fixed page's pair, so the Editor keeps naming it after an edit.
        choice=choice,
        edit_on_other_model=cache.has_edit_for_other_model(h, lang, model),
        # The repacked volume on disk no longer contains this page. Re-packing
        # on this thread is not an option -- a large volume takes longer than
        # AC-10's 3-second budget -- so the archive is rebuilt on a worker
        # thread once the edits go quiet, and the response SAYS it is behind
        # rather than leave the user holding a file that silently disagrees
        # with the editor. `repack` is the worker's status; /api/repack
        # serves the same dict until it reads done.
        archive_stale=not _is_images(placed),
        repack=None,
    )
    _persist(h, record, detected, complete, bool(record.get("redetect_failed")))
    record["cache_warning"] = cache.enforce_cap(job_id)
    # A placement written before src_path existed has no archive to rebuild
    # from here: the flag stays, the status stays None, and the UI says the
    # item must be run again. Placements are rewritten by every run, so this
    # is a one-run condition, not a permanent one.
    if placed.get("src_path") and not _is_images(placed):
        record["repack"] = schedule_repack(job_id, item_id, dest_dir, lang)
    return record
