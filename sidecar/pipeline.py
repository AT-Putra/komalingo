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
from .containers import archive, pdf
from .llm import MAX_CONCURRENT

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


def translate(regions: list[dict], page: int, client=None, lang: str = DEFAULT_LANG,
              source: str = DEFAULT_SOURCE, img: Image.Image | None = None) -> None:
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

        out = asyncio.run(
            client.translate_page([Region(id=r["id"], text=r["text"]) for r in asked],
                                  page_image=page_context_image(img) if img is not None else None,
                                  lang=lang, source=source)
        ) if asked else {}
        for r in asked:
            text = out.get(r["id"], "")
            # None is the vision model's "nothing is written there" -- see
            # llm.NOT_TEXT_INSTRUCTION. Flagged here, removed by dismiss()
            # before the inpainter runs, and stored as null in the
            # translation cache so a cache hit makes the same call.
            if text is None:
                r["not_text"] = True
                r["dismiss_reason"] = "not on the page (vision model)"
            r["translation"] = text or ""
    for r in regions:
        r.setdefault("translation", "")
    emit("translate", f"{len(regions)} regions", page, 50)


def dismiss(regions: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept, dismissed): the regions the vision model said hold no text.

    Called after translate and before inpaint, on the fresh path and the
    cached one alike. A dismissed region is not inpainted, not typeset, not
    in the page's fit summary and not in its regions -- the art under it
    stays as drawn. It is kept on the record under `dismissed`, with what the
    OCR read there, so a page that lost a real bubble to a wrong null can be
    seen to have lost it rather than never having found it.
    """
    kept = [r for r in regions if not r.get("not_text")]
    gone = [{"id": r["id"], "polygon": r["polygon"], "text": r.get("text"),
             "reason": r.get("dismiss_reason", "")}
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
        translate(regions, page, client, lang, source, img=original)
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


def _check_cancel(cancel, item_id: str, pages_done: int) -> None:
    """Raise Cancelled if the token is set. `cancel` is anything with
    is_set() -- a threading.Event from job.Job -- or None for the routes
    that have no job to be cancelled from."""
    if cancel is not None and cancel.is_set():
        raise Cancelled(item_id, pages_done)


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


def _persist(h: str, record: dict) -> None:
    cache.write_regions(h, {k: record[k] for k in CONTENT_KEYS if k in record})


def _model_id(client) -> str:
    """What the translation file is keyed on. 'offline' is a real key, not a hole.

    The placeholder translator produces text, that text gets cached, and a run
    with a real provider must not pick it up. Naming the offline path keeps the
    two in separate files for the same reason two providers are.
    """
    return getattr(client, "model", None) or "offline"


def _load_translations(regions: list[dict], h: str, lang: str, model: str) -> bool:
    """Fill translations from the cache. True only if EVERY region was covered.

    Partial coverage returns False and the caller re-translates the whole page.
    That is one wasted request against a half-written entry; the alternative is
    a page where some bubbles carry last run's text and some carry none, with
    nothing on screen saying which.
    """
    stored = cache.read_translation(h, lang, model)
    if not stored:
        return False
    covered = True
    for r in regions:
        entry = stored.get(str(r["id"]))
        if entry is None:
            covered = False
            continue
        text = entry.get("text", "")
        if text is None:  # stored null: dismissed on the first run
            r["not_text"] = True
            r.setdefault("dismiss_reason", "not on the page (vision model)")
        r["translation"] = text or ""
        r["edited"] = bool(entry.get("edited"))
    return covered


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
             source=DEFAULT_SOURCE, cancel=None):
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
    src_fmt = _container(src_path)
    # Phase 7: a PDF is read by its own module and through the same Budget.
    # The rest of this loop is identical for both, which is the point of the
    # (ordinal, member, image) contract the two readers share.
    read_pages = pdf.pages if src_fmt == pdf.PDF else archive.pages
    out_dir = item_dir(dest_dir, item_id)
    # The page count the progress lines carry, read before the first page so
    # the bar has an end to run to. Advisory and allowed to be None -- see
    # archive.expected_pages -- and never a reason for the run to fail.
    expected = pdf.page_count(src_path) if src_fmt == pdf.PDF else archive.expected_pages(src_path)
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
                client, lang, source, model, src_fmt, cancel, expected)
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
        out_archive = _repack(src_path, out_dir, src_fmt, records, lang, budget)
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
               model, src_fmt, cancel, expected) -> list[dict]:
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
            return _run_cached_page(h, img, member, ordinal, item_id, out_dir, client,
                                    lang, source, model, src_fmt, cancel, 0)

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
                                    src_path=os.fspath(src_path))
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
    if cached is not None and cache.read_raster(h) is None:
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

    if cached is not None:
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

    if _load_translations(regions, h, lang, model):
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
        translate(regions, ordinal, client, lang, source, img=img)
        cache.write_translation(
            h, lang, model,
            {r["id"]: None if r.get("not_text") else r.get("translation", "") for r in regions},
        )
        # Read back, deliberately. write_translation refuses to
        # overwrite an `edited` entry, so the file it just wrote and
        # the regions in memory can disagree about exactly the regions
        # the user corrected -- and the regions in memory are what gets
        # RENDERED. Without this the page would show the fresh
        # translation while the cache said the edit was kept, which is
        # the worst of both: the correction is not discarded, it is
        # just not on the page. Reachable when coverage was partial (a
        # half-written translation file) and an edit exists.
        _load_translations(regions, h, lang, model)
    # And once more after it, since pages run PAGE_WINDOW at a time: a page
    # whose reply arrives after the cancel stops here, before the erase and
    # the render, instead of finishing because it happened to be in flight.
    # Its translation is already cached for the resume; its detect and OCR
    # are not yet persisted, so the resume re-detects it, as before.
    _check_cancel(cancel, item_id, pages_done)
    regions, dismissed = dismiss(regions)

    if cached is not None:
        cleaned, inpaint_calls = cache.read_raster(h), 0
        emit("inpaint", "0 calls (cached)", ordinal, 65)
    else:
        cleaned, inpaint_calls = inpaint(img, regions, ordinal)
        cache.write_raster(h, cleaned, src=img)

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
        "cached": cached is not None,
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
    _persist(h, record)
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
    """
    placed = cache.get_placement(job_id, item_id, ordinal)
    if placed is None:
        raise CacheMiss(
            f"job {job_id} has no page {ordinal} of item {item_id!r}", "placement"
        )
    h = placed["page_hash"]
    record = cache.read_regions(h)
    cleaned = cache.read_raster(h)
    if record is None or cleaned is None:
        raise CacheMiss(f"page {ordinal} of item {item_id!r} is not in the page cache")

    regions = record["regions"]
    if not any(r["id"] == region_id for r in regions):
        raise CacheMiss(f"region {region_id} is not on page {ordinal}", "region")

    model = _model_id(client)
    # Coverage BEFORE the edit is written. A (lang, model) pair this page was
    # never translated under has no text for the other regions, and this path
    # never translates -- so rendering would put the user's edit in one bubble
    # and the OLD language's text from regions.json in every other. The review
    # called it a mixed-language page, and it is exactly that. Run the item at
    # that pair first; the error says so.
    stored = cache.read_translation(h, lang, model)
    uncovered = [r["id"] for r in regions if r["id"] != region_id
                 and str(r["id"]) not in stored]
    if uncovered:
        raise CacheMiss(
            f"page {ordinal} has no {lang!r} translation under model {model!r} "
            f"for regions {uncovered}; run the item at that language first",
            "translation",
        )
    cache.write_edit(h, lang, model, region_id, text)
    _load_translations(regions, h, lang, model)

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
        edited_region=region_id,
        edit_on_other_model=cache.has_edit_for_other_model(h, lang, model),
        # The repacked volume on disk no longer contains this page. Re-packing
        # on this thread is not an option -- a large volume takes longer than
        # AC-10's 3-second budget -- so the archive is rebuilt on a worker
        # thread once the edits go quiet, and the response SAYS it is behind
        # rather than leave the user holding a file that silently disagrees
        # with the editor. `repack` is the worker's status; /api/repack
        # serves the same dict until it reads done.
        archive_stale=True,
        repack=None,
    )
    _persist(h, record)
    record["cache_warning"] = cache.enforce_cap(job_id)
    # A placement written before src_path existed has no archive to rebuild
    # from here: the flag stays, the status stays None, and the UI says the
    # item must be run again. Placements are rewritten by every run, so this
    # is a one-run condition, not a permanent one.
    if placed.get("src_path"):
        record["repack"] = schedule_repack(job_id, item_id, dest_dir, lang)
    return record
