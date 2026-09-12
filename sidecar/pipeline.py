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

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict

from PIL import Image, ImageDraw

from . import atomic, cache, imaging, ocr_cjk, ocr_ja, safety, typeset
from . import detect as detector
from .containers import archive, pdf

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


# The source languages the pipeline reads, and which engine reads each. ja is
# manga-ocr's -- whole bubble, one pass, furigana and all -- and NEVER
# PaddleOCR's: PP-OCRv5 reads Japanese at 60% (spec, component table). zh and
# ko are PP-OCRv5's, per text line. Phase 4, AC-3.
SOURCES = ("ja", "zh", "ko")
DEFAULT_SOURCE = "ja"
DEFAULT_LANG = "en"


def ocr(regions: list[dict], img: Image.Image, page: int, source: str = DEFAULT_SOURCE) -> int:
    """Source text per region. Returns the number of OCR calls made.

    One call per region on both paths. manga-ocr takes the whole region
    (its hull) in one pass; PP-OCRv5 takes the region's PARTS -- one per text
    line as the detector saw them -- and ocr_cjk joins them in reading order,
    which is still one call here and one entry in regions.json.
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
    emit("ocr", f"{len(regions)} calls", page, 25)
    return len(regions)


def translate(regions: list[dict], page: int, client=None, lang: str = DEFAULT_LANG,
              source: str = DEFAULT_SOURCE) -> None:
    """Target-language text per region. One LLM request for the whole page.

    client is injected -- there is no default and no module-level base URL. The
    credentials come from the Settings UI at runtime, never from this file.
    Phase 5: `lang` and `source` reach the prompt. Until then the job's lang
    was a cache key and nothing else, and the prompt said English regardless.
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
            client.translate_page([Region(id=r["id"], text=r["text"]) for r in regions],
                                  lang=lang, source=source)
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
        # Phase 2b: the PARTS, not the hull. A region is now the hull of the
        # quads the detector returned for one block, and the hull spans
        # whatever lies between them -- white inside a bubble, a character's
        # face under text laid across the art. Only the quads held glyphs.
        for part in r.get("parts") or [r["polygon"]]:
            draw.polygon([tuple(p) for p in part], fill="white")
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
             lang: str = DEFAULT_LANG) -> dict:
    """One page through all seven stages, in order. Returns the regions record."""
    with Image.open(atomic.long_path(src_path)) as src:
        src.load()
        original = src.convert("RGB").copy()

        regions = detect(src, page)
        ocr_calls = ocr(regions, src, page, source)
        translate(regions, page, client, lang, source)
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


# Serialises the detector and OCR across concurrent jobs. See run_item.
_MODEL_LOCK = threading.Lock()


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
        r["translation"] = entry.get("text", "")
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
             source=DEFAULT_SOURCE):
    """Every page of one archive or PDF, through the cache. Returns the record.

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
    cache.mark_running(job_id)
    records: list[dict] = []
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
    # The budget's root is the ITEM's directory, which is where a member would
    # actually land -- the escape rule has to be evaluated against the path the
    # writer builds, not against the job root one level above it.
    budget = safety.Budget(out_dir)
    format_warning = archive.CBR_WARNING if src_fmt == archive.RAR else None
    try:
        for ordinal, member, img in read_pages(src_path, budget):
            h = cache.page_hash(img)
            cache.put_placement(job_id, item_id, ordinal, h, member)
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

            # The seven stages, in STAGES order, each emitting exactly once --
            # on the hit path too. The UI draws one bar segment per stage and
            # reads the names, so a cached page that skipped a stage silently
            # would leave the bar stuck at the one before it; a cached page
            # that emitted a stage twice would run the bar backwards. Every
            # branch below emits its stage, once, and says whether it did work.
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
                # unmeasured and is serialised on the same principle. Phase
                # 8's queue will make this lock idle; today it is load-bearing.
                with _MODEL_LOCK:
                    regions = detect(img, ordinal)
                    ocr_calls = ocr(regions, img, ordinal, source)

            if _load_translations(regions, h, lang, model):
                emit("translate", f"{len(regions)} regions (cached)", ordinal, 50)
            else:
                translate(regions, ordinal, client, lang, source)
                cache.write_translation(
                    h, lang, model, {r["id"]: r.get("translation", "") for r in regions}
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
            records.append(record)
        # Once, at the end, and not per page. The plan says disk is "never
        # evicted mid-job", and per page it could not have reclaimed this job's
        # own pages anyway -- every one is pinned by its running marker -- while
        # walking the whole cache tree two hundred times for a two-hundred-page
        # item. It runs inside the try so the job is still marked running:
        # its pages are what the cap must not touch.
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


def _repack(src_path, dest_dir, src_fmt: str, records: list[dict], lang: str,
            budget) -> str:
    """AC-6's round trip: the delivered pages, back into the input's format.

    **The loose pages stay.** They are what the spot-fix editor re-renders into
    and what AC-13's resume reads, and the archive is built FROM them rather
    than instead of them -- so a cancelled job leaves the pages it finished
    where the next run can use them, which an archive-only output cannot do
    (a half-written archive is not half a job, it is nothing). The duplication
    is the price of both properties and it is paid on disk, not in RSS: the
    archive repack streams one page at a time. The PDF repack does not quite
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
        for record in records:
            with open(atomic.long_path(record["output"]), "rb") as fh:
                yield record["member"], fh.read()

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
        # here is not an option -- rebuilding a 200-page archive is minutes
        # against AC-10's 3-second budget -- so the honest move is to SAY the
        # archive is behind rather than leave the user holding a file that
        # silently disagrees with the editor. run_item rebuilds it.
        archive_stale=True,
    )
    _persist(h, record)
    record["cache_warning"] = cache.enforce_cap(job_id)
    return record
