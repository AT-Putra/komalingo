r"""AC-5: the PDF container. Read at native resolution, written back by img2pdf.

A scanned-manga PDF is a list of full-page images with a PDF wrapped around
them, and the wrapper is the only thing that makes it different from a CBZ.
So the reader's job is to hand the pipeline the SAME pixels a CBZ of the same
scans would -- which is a stronger statement than "extract the images", and
it is the one `check_pdf`'s cache-key assert holds: a page arriving as a PDF
XObject and the same page arriving as a CBZ member must produce the same
`cache.page_hash`, or AC-13's resume and AC-10's spot-fix treat one volume as
two.

**Native resolution means the XObject's pixels, decoded by the same decoder.**
A DCTDecode XObject is a JPEG file with a PDF dictionary in front of it. Its
raw stream bytes are handed to Pillow -- the decoder every CBZ member goes
through -- rather than to pdfium's, because two libjpeg builds are allowed to
differ by one in the low bit of an IDCT and the page hash is over every bit.
Every other encoding (Flate, CCITT, JBIG2, and a DCT under a rotated matrix)
goes through pdfium at the image's own pixel size, which is lossless where
the encoding is lossless and is the only decoder we have for the rest. A
DCT with an `/SMask` is NOT special-cased: it goes to Pillow and the mask is
dropped, because a scanned page has no mask and the tier is chosen on the
filter list alone -- stated so nobody reads "mask" into the rule above.

**Rendering is the fallback, never the path.** The build order's rule for
"this page is a scan" is `chars < 50 AND one image covers > 50% of the page`,
and only a page failing it is rasterised -- at 300 DPI, which is a choice the
page record carries as `pdf_extract == "render"` so a check can assert the
fallback was NOT taken on a fixture where it must not be. A scan with an OCR
text layer fails the character rule and is rendered; that is the rule as
written and the limitation is stated here rather than discovered.

**The output is built by img2pdf, which embeds the delivered page bytes
verbatim** -- a JPEG stays the JPEG `imaging.encode` produced -- with a layout
that returns each source page's displayed box exactly, so "dimensions match
the input" is true to the point rather than to the nearest integer DPI a JFIF
header can carry. The outline and `/Info` are then copied across with pypdf.
PyMuPDF would do all of this in three lines and is AGPL; it is not an option.
"""

from __future__ import annotations

import gc
import io
import math
import os
import sys
import threading

import img2pdf
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.generic import Destination, DictionaryObject, NameObject

from .. import atomic, safety
from .archive import UnsupportedArchive

PDF = "pdf"
SUFFIXES = (".pdf",)

# The two ways a page reaches the pipeline. Carried on every page record so
# the gate can tell them apart without re-reading the PDF.
XOBJECT, RENDER = "xobject", "render"

RENDER_DPI = 300
SCAN_MAX_CHARS = 50     # a page with this many characters is not a scan
SCAN_MIN_COVER = 0.5    # the one image must cover more than this of the page

_HEADER = b"%PDF-"

# pdfium's own allocation unit: every bitmap it hands back is BGR(A/x), four
# bytes a pixel, whatever the XObject's colour space was. The declared-size
# guard counts what pdfium will ask for, not what Pillow will keep.
_BYTES_PER_PX = 4

# PDFium is not thread-safe and pypdfium2 says so. Two /api/item requests for
# two PDFs in one sidecar is the ordinary case cache.py promises, so every
# pdfium call here runs under one lock -- held per CALL, not across the
# generator, because the pipeline does its own work between pages and two
# PDF jobs serialising each other's OCR would be the lock doing harm.
_PDFIUM_LOCK = threading.Lock()


class UnreadablePdf(UnsupportedArchive):
    """pdfium could not open the file: not a PDF, truncated, or encrypted.

    A subclass so the Item boundary that already turns an unsupported archive
    into a SKIPPED item with its reason does the same for a bad PDF without
    learning a new exception.
    """


def is_pdf(path) -> bool:
    """Whether `path` is named as a PDF. Cheap, name-only, like `is_archive`."""
    return os.path.splitext(os.fspath(path))[1].lower() in SUFFIXES


def detect(path) -> bool:
    """Whether the bytes start with a PDF header. The spec allows junk before
    `%PDF-`, and pdfium tolerates it, so the first 1KB is searched rather
    than the first five bytes compared."""
    with open(atomic.long_path(path), "rb") as fh:
        return _HEADER in fh.read(1024)


def _open(path) -> pdfium.PdfDocument:
    name = os.path.basename(os.fspath(path))
    try:
        return pdfium.PdfDocument(atomic.long_path(path))
    except pdfium.PdfiumError as e:
        # pdfium's own message is "Failed to load document (PDFium: ...)".
        # The one case worth naming is a password, because the user can do
        # something about it.
        reason = str(e)
        if "password" in reason.lower():
            raise UnreadablePdf(f"encrypted PDF (a password is required): {name}") from e
        raise UnreadablePdf(f"not a readable PDF: {name} ({reason})") from e


def member_name(ordinal: int, fmt: str) -> str:
    """The name the delivered page is written under. A PDF has no member names
    of its own, so the ordinal is the name, zero-padded so a directory listing
    sorts the way the reader does."""
    return f"p{ordinal:04d}.{'jpg' if fmt == 'JPEG' else 'png'}"


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------


def _full_page_image(page: pdfium.PdfPage):
    """The ONE image object covering more than half the page, or None.

    Exactly one: two half-page panels overlapping enough to both pass the
    threshold are not "a single full-page image", and rendering them is the
    honest answer.
    """
    w, h = page.get_size()
    area = w * h
    if area <= 0:
        return None
    covering = []
    for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = obj.get_bounds()
        if (right - left) * (top - bottom) > SCAN_MIN_COVER * area:
            covering.append(obj)
    return covering[0] if len(covering) == 1 else None


def _is_scan(page: pdfium.PdfPage):
    """The build order's rule, both halves. Returns the image or None."""
    textpage = page.get_textpage()
    try:
        chars = textpage.count_chars()
    finally:
        textpage.close()
    if chars >= SCAN_MAX_CHARS:
        return None
    return _full_page_image(page)


def _axis_aligned(obj) -> bool:
    """Whether the image is placed with no rotation, skew or flip.

    Only then are the XObject's pixels what the reader shows, and only then
    may they be handed over undecoded-by-pdfium. A scanner that wrote its
    rotation into the matrix instead of /Rotate goes through pdfium's render
    with `scale_to_original`, which applies the matrix at native resolution.
    """
    m = obj.get_matrix()
    return m.b == 0 and m.c == 0 and m.a > 0 and m.d > 0


def _decode_xobject(obj, name: str, raw: bytes) -> Image.Image:
    """The XObject's pixels, at the XObject's size.

    Three tiers, and the order is the point. An axis-aligned DCT stream goes
    to Pillow, so the page hash is the one a CBZ of the same JPEG produces.
    Any other axis-aligned stream is `get_bitmap(render=False)`: pdfium
    decodes it at exactly `/Width x /Height`, no matrix involved. Only an
    image placed with rotation or skew is RENDERED with `scale_to_original`,
    and that is not exact: measured on a 1200px-wide Flate image, the
    rendered bitmap came back 1201 wide, because pdfium sizes a render from
    the matrix in floating point and rounds up. Native-to-the-pixel is
    therefore promised for the axis-aligned case, which is every scanner's
    output, and native-to-within-a-pixel for the rest.
    """
    filters = obj.get_filters()
    aligned = _axis_aligned(obj)
    if aligned and filters == ["DCTDecode"]:
        # `raw` is the one materialisation of the stream: the caller already
        # charged its length to the budget and hands the same bytes here.
        # Image.DecompressionBombError is deliberately NOT caught, unlike
        # archive._decode: an archive can skip a member and keep its
        # ordinals, a PDF cannot skip a page, so a bomb goes to the Item
        # boundary and the item is FAILED with its reason. check_decoded
        # bounds the declared /Width /Height before this; Pillow's bomb
        # check is the backstop for a stream whose SOF contradicts them.
        try:
            with Image.open(io.BytesIO(raw)) as img:
                img.load()
                page = img.convert("RGB")
            page.format = "JPEG"
            return page
        except (UnidentifiedImageError, OSError, ValueError) as e:
            # A DCT stream Pillow will not read (CMYK with an Adobe inversion
            # is the usual one). pdfium's decoder is the next best thing and
            # the page hash is then pdfium's; stated on stderr, not hidden.
            print(f"pdf: {name}: Pillow refused the JPEG stream "
                  f"({type(e).__name__}: {e}); decoding through pdfium",
                  file=sys.stderr, flush=True)
    if aligned:
        bitmap = obj.get_bitmap(render=False)
    else:
        bitmap = obj.get_bitmap(render=True, scale_to_original=True)
    page = _take(bitmap)
    page.format = "PNG"
    return page


def _take(bitmap) -> Image.Image:
    """A PdfBitmap's pixels as an RGB Pillow image, and the bitmap freed HERE.

    `to_pil` shares pdfium's buffer and `convert` copies out of it, so after
    this the bitmap is garbage -- but its finalizer would run
    FPDFBitmap_Destroy whenever the collector got to it, from whatever
    thread, outside `_PDFIUM_LOCK`. Closing under the lock is the only order
    that respects "every pdfium call under the lock".
    """
    try:
        return bitmap.to_pil().convert("RGB")
    finally:
        bitmap.close()


def _render(page: pdfium.PdfPage) -> Image.Image:
    img = _take(page.render(scale=RENDER_DPI / 72))
    img.format = "PNG"
    return img


_TRANSPOSE = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
              270: Image.Transpose.ROTATE_90}


def _displayed(img: Image.Image, rotation: int) -> Image.Image:
    """The page as the reader shows it. /Rotate is clockwise; Pillow's
    ROTATE_n is counter-clockwise, hence the mapping. Lossless at these
    angles, and a no-op at 0."""
    op = _TRANSPOSE.get(rotation % 360)
    if op is None:
        return img
    fmt = img.format
    out = img.transpose(op)
    out.format = fmt
    return out


def page_count(path) -> int:
    """How many pages `pages` will yield. The document's own count, no render.

    Advisory: the progress line carries it so the UI can show "page 3 of 24"
    instead of counting up from nothing. A PDF delivers every page or fails,
    so unlike an archive's candidate list this is exact.
    """
    doc = _open(path)
    try:
        return len(doc)
    finally:
        doc.close()


def pages(path, budget: safety.Budget | None = None):
    """Yield `(ordinal, member, image)` for every page, 1-based.

    Same contract as `archive.pages`, and the budget is the same `Budget`:
    each page is one member, charged its raw stream size as a CBZ would be
    charged the member's stored size, and refused before allocation if its
    decoded raster would exceed the per-file cap -- pdfium allocates what the
    dictionary declares and a 40000x40000 `/Width /Height` is 4.8GB. The
    render fallback is guarded the same way at its 300 DPI size.

    Every page is delivered or the item fails: a PDF has no "undecodable
    member" the way an archive does. A page that fails the scanned-page rule
    is rendered, and an XObject pdfium cannot decode is a PdfiumError that
    the Item boundary reports. The image carries `.info["pdf_extract"]`
    naming which path it took.
    """
    budget = budget or safety.Budget(os.path.dirname(os.fspath(path)))
    with _PDFIUM_LOCK:
        pdf = _open(path)
        count = len(pdf)
    try:
        for index in range(count):
            ordinal = index + 1
            with _PDFIUM_LOCK:
                img, how = _read_page(pdf, index, ordinal, budget)
            img.info["pdf_extract"] = how
            yield ordinal, member_name(ordinal, img.format), img
    finally:
        with _PDFIUM_LOCK:
            pdf.close()


def _read_page(pdf, index: int, ordinal: int, budget):
    """One page's pixels and the path they took. Runs under the pdfium lock."""
    page = pdf[index]
    try:
        obj = _is_scan(page)
        if obj is not None:
            name = f"page {ordinal} (xobject)"
            px_w, px_h = obj.get_px_size()
            budget.check_decoded(name, px_w * px_h * _BYTES_PER_PX)
            budget.begin(safety.Member(name))
            # The stream, once: its length is what the budget charges (the
            # bytes a CBZ would store for this page) and its bytes are what
            # the DCT tier decodes.
            raw = bytes(obj.get_data(decode_simple=False))
            budget.account(len(raw))
            # An XObject pdfium cannot decode raises PdfiumError out of here,
            # and that is the per-page failure the build order routes through
            # the Item boundary: the item is FAILED with pdfium's reason, not
            # quietly rendered into something that looks like success.
            img = _decode_xobject(obj, name, raw)
            return _displayed(img, page.get_rotation()), XOBJECT
        name = f"page {ordinal} (render)"
        w_pt, h_pt = page.get_size()
        # ceil, as pypdfium2 sizes the bitmap.
        px_w = math.ceil(w_pt * RENDER_DPI / 72)
        px_h = math.ceil(h_pt * RENDER_DPI / 72)
        budget.check_decoded(name, px_w * px_h * _BYTES_PER_PX)
        budget.begin(safety.Member(name))
        img = _render(page)
        # Counted, not copied: tobytes() would allocate a second raster
        # (26MB for A4 at 300 DPI) to learn a number the size already gives.
        budget.account(img.width * img.height * len(img.getbands()))
        # NOT _displayed: pdfium renders the page as the reader shows it,
        # /Rotate included -- get_size() is post-rotation and so is the
        # bitmap. The first draft rotated this a second time and delivered a
        # portrait text page sideways into a landscape box (architect review,
        # measured on text.pdf under /Rotate 90: render 1801x1200, delivered
        # 1200x1801, box 432x288). Only the XObject path holds stored,
        # unrotated pixels that need turning.
        return img, RENDER
    finally:
        page.close()


def page_boxes(path) -> list[tuple[float, float]]:
    """Every page's DISPLAYED box in points, `/Rotate` applied. What the
    output must reproduce, page for page."""
    return [(w, h) for w, h, _iw, _ih in page_layout(path)]


def page_layout(path) -> list[tuple[float, float, float, float]]:
    """Per page: `(page w, page h, image w, image h)` in displayed points.

    The image size is the covering XObject's displayed bounds when the page
    takes the XObject path, and the page box when it is rendered (a render IS
    the whole page). Under /Rotate 90 or 270 the bounds swap, because
    `get_bounds` is in unrotated page space and the output carries no
    /Rotate. The writer hands both back to img2pdf so a scan whose image
    covers 60% of a bordered page comes back at 60% of a bordered page,
    centred, rather than stretched over the box -- measured before this
    existed: a 600x900 image at 54% of a 400x400 page came back as the whole
    page, aspect 1.5 forced to 1.0 (architect review).
    """
    with _PDFIUM_LOCK:
        pdf = _open(path)
        try:
            layout = []
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    w, h = page.get_size()
                    obj = _is_scan(page)
                    if obj is None:
                        layout.append((w, h, w, h))
                    else:
                        left, bottom, right, top = obj.get_bounds()
                        iw, ih = right - left, top - bottom
                        if page.get_rotation() in (90, 270):
                            iw, ih = ih, iw
                        layout.append((w, h, iw, ih))
                finally:
                    page.close()
            return layout
        finally:
            pdf.close()


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------


def output_path(src_path, dest_dir, suffix: str = "_translated") -> str:
    stem = os.path.splitext(os.path.basename(os.fspath(src_path)))[0]
    return os.path.join(os.fspath(dest_dir), f"{stem}{suffix}.pdf")


def _outline_items(reader: PdfReader, nodes):
    """Flatten pypdf's nested outline into `(depth, title, page index)`.

    pypdf represents nesting as a list whose child lists FOLLOW their parent
    entry, so the walk carries a depth rather than a tree.
    """
    out = []

    def walk(items, depth):
        for entry in items:
            if isinstance(entry, list):
                walk(entry, depth + 1)
            elif isinstance(entry, Destination):
                try:
                    idx = reader.get_destination_page_number(entry)
                except Exception:  # noqa: BLE001 -- a dangling destination
                    idx = None
                out.append((depth, str(entry.title), idx))

    walk(nodes, 0)
    return out


def copy_outline(reader: PdfReader, writer: PdfWriter) -> int:
    """Rebuild the source outline on the writer, page numbers by index.

    By index and not by object, because the output's pages are new objects
    with nothing but their position in common with the input's. Returns how
    many items were written, so a caller can assert the count survived.
    """
    parents: list = [None]
    n = 0
    for depth, title, idx in _outline_items(reader, reader.outline):
        if idx is None or idx >= len(writer.pages):
            continue
        del parents[depth + 1:]
        while len(parents) <= depth:
            parents.append(parents[-1])
        item = writer.add_outline_item(title, idx, parent=parents[depth])
        parents.append(item)
        n += 1
    return n


def _copy_info(info, writer: PdfWriter) -> None:
    """Every string-valued /Info key of the source onto the writer, names
    kept as names.

    `add_metadata` turns every value into a text string, and NameObject is a
    str subclass, so `/Trapped /False` came out of the first draft as the
    TEXT string '/False' (review). pypdf's public `metadata` getter returns
    a copy, so the names are written onto the writer's own dictionary, which
    is the one `write` serialises; the attribute is private and the pin
    (`pypdf>=6,<7`) is what makes relying on it acceptable.
    """
    writer.add_metadata({str(k): v for k, v in info.items()
                         if isinstance(v, str) and not isinstance(v, NameObject)})
    names = {NameObject(str(k)): NameObject(str(v)) for k, v in info.items()
             if isinstance(v, NameObject)}
    if names:
        target = getattr(writer, "_info", None)
        if isinstance(target, DictionaryObject):
            target.update(names)


def write_pdf(dest, page_paths, src_path) -> str:
    """The delivered pages, in order, as a PDF shaped like the input.

    `page_paths` are the loose translated pages on disk -- img2pdf reads each
    file itself and embeds its bytes without re-encoding, so the JPEG the
    pipeline wrote is the JPEG the reader opens. The page box and the image
    box come from `page_layout(src_path)`, one per delivered page, through a
    layout function img2pdf calls once per image in order; img2pdf centres
    the image on the page, so a bordered scan keeps its border.

    Two stages, and the residency is the reason for the shape. img2pdf
    writes to a scratch file beside the destination rather than returning
    bytes, and pypdf clones from a FILE-BACKED reader over that scratch:
    the outline (see `copy_outline`) and every `/Info` key of the source are
    added to the clone, and `write` serialises object by object. Measured on
    100 pages of 1200x1800 JPEG (81MB): Python-heap peak 1.02x the page
    bytes, the two phases sequential rather than stacked. The first draft
    held img2pdf's returned bytes, pypdf's clone of a BytesIO and img2pdf's
    retained image data at once -- 510MB for 210MB of pages, measured in
    review -- against a `_repack` docstring that promises one page at a
    time. pypdf's incremental mode was tried and rejected: it clones the
    page objects AND copies the whole stream on write, 2.02x measured.

    img2pdf runs with `nodate` and the internal engine, so two runs over the
    same pages write the same bytes; the dates the source carried come across
    with the rest of `/Info`. The result lands through `atomic_write`.
    """
    page_paths = [os.fspath(p) for p in page_paths]
    layout_rows = page_layout(src_path)
    if len(layout_rows) != len(page_paths):
        raise ValueError(
            f"{len(page_paths)} delivered pages for a {len(layout_rows)}-page PDF"
        )
    it = iter(layout_rows)

    def layout(_px_w, _px_h, _dpi):
        return next(it)

    dest = atomic.long_path(dest)
    directory = os.path.dirname(dest)
    os.makedirs(directory, exist_ok=True)
    # atomic_write's naming: dot-prefixed, pid and thread in the name, `.tmp`
    # so check_package's stray-file sweep recognises it if a crash leaves it.
    scratch = os.path.join(
        directory,
        f".{os.path.basename(dest)}.img2pdf.{os.getpid()}.{threading.get_ident()}.tmp",
    )
    try:
        with open(scratch, "wb") as fh:
            img2pdf.convert(
                [atomic.long_path(p) for p in page_paths],
                engine=img2pdf.Engine.internal, nodate=True,
                layout_fun=layout, outputstream=fh,
            )
        # img2pdf's document and writer objects refer to each other, so the
        # page bytes it retained stay resident until the cycle collector
        # runs -- measured: 1.00x the page bytes still current after convert
        # returned, 0.00x after this. Without it the pypdf phase below sits
        # on top of img2pdf's copy and the peak doubles.
        gc.collect()
        # File HANDLES, not paths, for both readers: PdfReader(path) reads
        # the whole file into memory (measured 1.00x) while PdfReader(fh)
        # seeks in place (0.00x). And under context managers: pypdf holds a
        # file open until closed, and on Windows an open file is one the
        # caller's cleanup cannot delete.
        with open(scratch, "rb") as built, PdfReader(built) as built_reader:
            writer = PdfWriter(clone_from=built_reader)
            with (open(atomic.long_path(src_path), "rb") as src_fh,
                  PdfReader(src_fh) as reader):
                copy_outline(reader, writer)
                info = reader.metadata
                if info:
                    _copy_info(info, writer)
            with atomic.atomic_write(dest) as fh:
                writer.write(fh)
    finally:
        try:
            os.remove(scratch)
        except OSError:
            pass
    return dest
