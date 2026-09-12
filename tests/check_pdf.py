#!/usr/bin/env python3
r"""Phase 7 -- AC-5 (PDF). Offline.

    uv run --project sidecar python tests/check_pdf.py

Exit-code contract, uniform across every check here:
    0  pass
    1  fail
    2  inconclusive -- never here; nothing is timed or measured against a floor
    3  skip         -- fixtures/pdf/ is absent (run tests/gen_fixtures.py)

AC-5 says four things and each is asserted separately, on the product's own
path (`job.run_job`, so the Item boundary, the cache and the repack are all
the ones a user's job goes through):

  NATIVE. Every page of scan.pdf reaches the pipeline as the XObject's own
  pixels -- the page record says `xobject`, and the delivered page's pixel
  size is the XObject's, not the page box at 300 DPI. The assert can go red:
  text.pdf's one page MUST say `render` and MUST be the page box at 300 DPI,
  because it fails the scanned-page rule on both halves. A reader that
  rendered everything would pass the first fixture's page count and fail
  this; a reader that extracted everything would fail the second.

  SAME KEY. The page hash of scan.pdf's page 1 (a JPEG XObject) and page 2 (a
  Flate XObject) equals the page hash `archive.pages` yields for a CBZ built
  from the same source files. This is Phase 3's decoded-pixel property, and
  it is the assert that would have caught handing the JPEG to pdfium's
  decoder instead of Pillow's.

  ROUND TRIP. Page count, order and displayed box match to 0.01pt, the
  /Rotate 90 page included; the output embeds the delivered page bytes
  VERBATIM (the output's DCT stream is byte-equal to the delivered .jpg);
  the outline survives with its nesting and page targets, and /Info's keys
  survive with their values.

  BOUNDARY. A file named .pdf that is not one comes back SKIPPED with a
  reason; a page that would exceed the per-file cap is refused as
  FILE_SIZE_CAP through the same boundary, with its partial output
  discarded; and the same tightened budget with `enforce=False` admits the
  page -- the red-check that shows the refusal is the rule's and not an
  accident of the reader.
"""

import contextlib
import functools
import hashlib
import io
import json
import math
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import pypdfium2 as pdfium  # noqa: E402
import pypdfium2.raw as pdfium_c  # noqa: E402
from PIL import Image  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from sidecar import cache, job, pipeline, safety  # noqa: E402
from sidecar.containers import archive, pdf  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDFS = os.path.join(ROOT, "fixtures", "pdf")
SCAN, TEXT, TEXT_ROT, PARTIAL = "scan.pdf", "text.pdf", "text_rot.pdf", "partial.pdf"
ALL = (SCAN, TEXT, TEXT_ROT, PARTIAL)
BOX_TOLERANCE_PT = 0.01


def fixture(name):
    return os.path.join(PDFS, name)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _flatten(outline, depth=0):
    """expected.json's [title, page, children] -> (depth, title, page)."""
    out = []
    for title, page, children in outline:
        out.append((depth, title, page))
        out.extend(_flatten(children, depth + 1))
    return out


def _xobjects(path):
    """Per page: [(px size, filters, raw stream bytes)] of every image."""
    doc = pdfium.PdfDocument(path)
    try:
        result = []
        for i in range(len(doc)):
            page = doc[i]
            try:
                imgs = []
                for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
                    imgs.append((tuple(obj.get_px_size()), obj.get_filters(),
                                 bytes(obj.get_data(decode_simple=False))))
                result.append(imgs)
            finally:
                page.close()
        return result
    finally:
        doc.close()


# --------------------------------------------------------------------------


def check_fixtures(c, expected):
    for name, meta in expected.items():
        c.check(sha256_file(fixture(name)) == meta["sha256"],
                f"{name} matches expected.json (regenerate if not)")
    for name, meta in expected[SCAN]["source_images"].items():
        c.check(sha256_file(fixture(name)) == meta["sha256"],
                f"{name} (page {meta['page']}'s source) matches expected.json")


def check_detect(c):
    c.check(pdf.detect(fixture(SCAN)) and pdf.detect(fixture(TEXT)),
            "pdf.detect sees the header on both fixtures")
    cbz = os.path.join(ROOT, "fixtures", "archives", "benign.cbz")
    if os.path.isfile(cbz):
        c.check(not pdf.detect(cbz), "and not on a CBZ")
        c.check(pipeline._container(cbz) == archive.ZIP,
                "pipeline._container: benign.cbz is still zip")
    c.check(pipeline._container(fixture(SCAN)) == pdf.PDF,
            "pipeline._container: scan.pdf is pdf, by signature")
    item = job.classify(fixture(SCAN))
    c.check(item.kind == "pdf" and item.status == "pending",
            f"job.classify names the kind ({item.kind})")
    c.check(job.classify("x.PDF").kind == "pdf", "case-insensitively")


def check_native(c, expected):
    """The reader alone, before the pipeline is involved."""
    meta = expected[SCAN]
    got = list(pdf.pages(fixture(SCAN)))
    c.check([o for o, _n, _i in got] == [1, 2, 3],
            "scan.pdf: three pages, ordinals 1..3")
    c.check(all(img.info.get("pdf_extract") == pdf.XOBJECT for _o, _n, img in got),
            f"scan.pdf: every page took the XObject path "
            f"({[img.info.get('pdf_extract') for _o, _n, img in got]})")
    want_px = []
    for (w, h), rot in zip(meta["px"], meta["rotation"]):
        want_px.append((h, w) if rot in (90, 270) else (w, h))
    c.check([img.size for _o, _n, img in got] == want_px,
            f"scan.pdf: delivered pixel sizes are the XObjects' own, /Rotate "
            f"applied ({[img.size for _o, _n, img in got]})")
    c.check([img.format for _o, _n, img in got] == ["JPEG", "PNG", "JPEG"],
            f"scan.pdf: a DCT XObject stays JPEG, a Flate one becomes PNG "
            f"({[img.format for _o, _n, img in got]})")
    c.check([n for _o, n, _i in got] == ["p0001.jpg", "p0002.png", "p0003.jpg"],
            f"scan.pdf: member names carry the ordinal and the format "
            f"({[n for _o, n, _i in got]})")
    c.check(all(img.mode == "RGB" for _o, _n, img in got),
            "scan.pdf: every page is RGB, as archive.pages delivers")

    # The rotated page: the displayed orientation, not the stored one. The
    # stored image is landscape with PAGE 3 upright; displayed with /Rotate
    # 90 the text runs down the right edge. Asserted by comparing against
    # Pillow's own rotation of the stored JPEG, which is the definition.
    page3 = got[2][2]
    xobj = _xobjects(fixture(SCAN))[2][0]
    with Image.open(io.BytesIO(xobj[2])) as stored:
        stored.load()
        rotated = stored.convert("RGB").transpose(Image.Transpose.ROTATE_270)
    c.check(page3.tobytes() == rotated.tobytes(),
            "scan.pdf page 3: the delivered pixels are the stored JPEG rotated "
            "90 degrees clockwise, as the reader displays it")

    # The negative control.
    tgot = list(pdf.pages(fixture(TEXT)))
    c.check(len(tgot) == 1 and tgot[0][2].info.get("pdf_extract") == pdf.RENDER,
            f"text.pdf: the text page took the RENDER path "
            f"({tgot[0][2].info.get('pdf_extract') if tgot else 'no page'})")
    (w_pt, h_pt), = expected[TEXT]["boxes"]
    want = (math.ceil(w_pt * pdf.RENDER_DPI / 72), math.ceil(h_pt * pdf.RENDER_DPI / 72))
    size = tgot[0][2].size if tgot else (0, 0)
    c.check(all(abs(a - b) <= 1 for a, b in zip(size, want)),
            f"text.pdf: rendered at {pdf.RENDER_DPI} DPI -- {size} for a "
            f"{w_pt}x{h_pt}pt page (expected {want} +-1)")
    c.check(tgot and tgot[0][2].format == "PNG" and tgot[0][1] == "p0001.png",
            "text.pdf: a rendered page is delivered as PNG")

    # The render path under /Rotate: pdfium renders the page as DISPLAYED,
    # so the delivered bitmap is landscape and must not be turned again.
    rgot = list(pdf.pages(fixture(TEXT_ROT)))
    (rw_pt, rh_pt), = expected[TEXT_ROT]["boxes"]
    rwant = (math.ceil(rw_pt * pdf.RENDER_DPI / 72), math.ceil(rh_pt * pdf.RENDER_DPI / 72))
    rsize = rgot[0][2].size if rgot else (0, 0)
    c.check(len(rgot) == 1 and rgot[0][2].info.get("pdf_extract") == pdf.RENDER
            and all(abs(a - b) <= 1 for a, b in zip(rsize, rwant)),
            f"text_rot.pdf: rendered once, in the displayed (landscape) "
            f"orientation -- {rsize}, expected {rwant} +-1")

    # The partial-coverage page: over the rule's threshold, so XObject.
    pgot = list(pdf.pages(fixture(PARTIAL)))
    c.check(len(pgot) == 1 and pgot[0][2].info.get("pdf_extract") == pdf.XOBJECT
            and pgot[0][2].size == tuple(expected[PARTIAL]["px"][0]),
            f"partial.pdf: a {expected[PARTIAL]['cover']:.0%}-coverage image takes "
            f"the XObject path at its own size ({pgot[0][2].size if pgot else None})")
    rows = pdf.page_layout(fixture(PARTIAL))
    c.check(rows == [(*expected[PARTIAL]["boxes"][0], *expected[PARTIAL]["image_boxes"][0])],
            f"partial.pdf: page_layout reports the image's own box inside the "
            f"page's ({rows})")

    # Falsifiability of the rule itself: the text page has >= 50 chars and
    # no image; the scan pages have 0 chars and one covering image. Read
    # back from pdfium rather than from expected.json so the fixture is
    # shown to exercise BOTH halves of the rule.
    doc = pdfium.PdfDocument(fixture(TEXT))
    try:
        tp = doc[0].get_textpage()
        chars = tp.count_chars()
        tp.close()
        n_img = len(list(doc[0].get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE])))
    finally:
        doc.close()
    c.check(chars >= pdf.SCAN_MAX_CHARS and n_img == 0,
            f"text.pdf fails the scanned-page rule on both halves "
            f"({chars} chars >= {pdf.SCAN_MAX_CHARS}, {n_img} images)")


def check_cache_key(c, expected, tmp):
    """Phase 3's property across containers: same pixels, same key."""
    sources = expected[SCAN]["source_images"]
    entries = []
    for name, meta in sorted(sources.items(), key=lambda kv: kv[1]["page"]):
        with open(fixture(name), "rb") as fh:
            entries.append((f"p{meta['page']}{os.path.splitext(name)[1]}", fh.read()))
    twin = os.path.join(tmp, "twin.cbz")
    archive.write_archive(twin, entries, archive.ZIP)

    from_cbz = {o: cache.page_hash(img) for o, _n, img in archive.pages(twin)}
    from_pdf = {o: cache.page_hash(img) for o, _n, img in pdf.pages(fixture(SCAN))}
    for name, meta in sources.items():
        o = meta["page"]
        c.check(from_cbz.get(o) == from_pdf.get(o),
                f"page {o} ({name}): cache.page_hash is identical from the CBZ "
                f"and from the PDF ({from_cbz.get(o, '')[:12]} vs "
                f"{from_pdf.get(o, '')[:12]})")
    c.check(from_pdf[1] != from_pdf[2] != from_pdf[3],
            "and the three PDF pages are three different keys")


def check_round_trip(c, expected, tmp):
    """The product's path: job.run_job, both fixtures, offline."""
    # job.run_item rather than run_job, because run_job's dict drops the
    # per-page records and pdf_extract lives there. Same boundary, same
    # per-job warning set; run_job adds only the counting.
    captured = io.StringIO()
    warned = set()
    with contextlib.redirect_stdout(captured):
        results = [job.run_item(job.classify(fixture(n)), tmp, "check-pdf",
                                warned=warned) for n in ALL]
    items = {i.item_id: i for i in results}
    c.check(all(i.status == job.OK for i in results),
            f"all {len(ALL)} PDFs complete OK ({[(i.status, i.reason) for i in results]})")
    c.check(all(i.kind == "pdf" for i in results), "every item is kind 'pdf'")
    c.check(not warned and not any(i.warning for i in results),
            f"a PDF raises no format warning ({warned})")

    # The seven stages, per page, in order -- the contract check_ipc holds
    # for archives, held here for the second container.
    events = []
    for line in captured.getvalue().splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    page_stages = [e["stage"] for e in events if e["stage"] in pipeline.STAGES]
    n_pages = sum(expected[n]["pages"] for n in ALL)
    c.check(page_stages == list(pipeline.STAGES) * n_pages,
            f"seven stages emitted once per page, in order, over {n_pages} pages "
            f"({len(page_stages)} stage events)")

    fallbacks = 0
    for name in ALL:
        meta = expected[name]
        item = items[name]
        out = item.output
        c.check(bool(out) and out.endswith("_translated.pdf") and os.path.isfile(out),
                f"{name}: output is <stem>_translated.pdf ({out})")
        if not out:
            continue

        # -- pages and boxes -------------------------------------------
        boxes = pdf.page_boxes(out)
        c.check(len(boxes) == meta["pages"],
                f"{name}: page count {len(boxes)} == {meta['pages']}")
        want = [tuple(b) for b in meta["boxes"]]
        ok_boxes = len(boxes) == len(want) and all(
            abs(a[0] - b[0]) <= BOX_TOLERANCE_PT and abs(a[1] - b[1]) <= BOX_TOLERANCE_PT
            for a, b in zip(boxes, want))
        c.check(ok_boxes, f"{name}: every displayed page box matches the input "
                          f"to {BOX_TOLERANCE_PT}pt ({boxes})")
        # The IMAGE box too: a page whose scan covers 54% of it must come
        # back with the scan at 54% of it, not stretched over the page.
        img_boxes = [(iw, ih) for _w, _h, iw, ih in pdf.page_layout(out)]
        want_img = [tuple(b) for b in meta["image_boxes"]]
        c.check(len(img_boxes) == len(want_img) and all(
            abs(a[0] - b[0]) <= BOX_TOLERANCE_PT and abs(a[1] - b[1]) <= BOX_TOLERANCE_PT
            for a, b in zip(img_boxes, want_img)),
            f"{name}: every output image box matches the input's image box "
            f"to {BOX_TOLERANCE_PT}pt ({img_boxes} vs {want_img})")
        with PdfReader(out) as reader:
            rotates = [p.get("/Rotate", 0) for p in reader.pages]
            out_info = dict(reader.metadata or {})
            out_outline = pdf._outline_items(reader, reader.outline)
        c.check(all(r in (0, None) for r in rotates),
                f"{name}: the output carries no /Rotate -- the rotation was "
                f"applied to the pixels ({rotates})")

        # -- the page records ------------------------------------------
        records = sorted(item.record["pages"], key=lambda r: r["page"])
        c.check(len(records) == meta["pages"] and item.pages == meta["pages"],
                f"{name}: one page record per page ({len(records)})")
        c.check(item.record["src_format"] == pdf.PDF
                and item.record["format_warning"] is None,
                f"{name}: the item record says src_format=pdf, no warning")
        extracts = [r.get("pdf_extract") for r in records]
        c.check(all(e == meta["extract"] for e in extracts),
                f"{name}: every page record says pdf_extract={meta['extract']!r} "
                f"({extracts})")
        fallbacks += sum(1 for e in extracts if e == pdf.RENDER)
        c.check(all(r.get("src_format") in ("JPEG", "PNG") for r in records),
                f"{name}: src_format is the delivered format "
                f"({[r.get('src_format') for r in records]})")

        # -- verbatim embedding and page order -------------------------
        out_x = _xobjects(out)
        c.check(all(len(x) == 1 for x in out_x),
                f"{name}: every output page is exactly one image XObject")
        order_ok = True
        for r, imgs in zip(records, out_x):
            delivered = r["output"]
            with open(delivered, "rb") as fh:
                payload = fh.read()
            with Image.open(io.BytesIO(payload)) as im:
                px = im.size
            (opx, filters, raw), = imgs
            if px != opx:
                order_ok = False
            if r["src_format"] == "JPEG":
                # img2pdf's promise, asserted: the DCT stream IS the file.
                c.check(filters == ["DCTDecode"] and raw == payload,
                        f"{name} page {r['page']}: the output's DCT stream is "
                        f"byte-equal to the delivered .jpg ({len(raw)} bytes)")
            else:
                c.check("FlateDecode" in filters,
                        f"{name} page {r['page']}: a delivered PNG is embedded "
                        f"as Flate ({filters})")
        c.check(order_ok, f"{name}: output pages are the delivered pages in "
                          f"order (pixel sizes {[x[0][0] for x in out_x]})")
        # Orientation: the embedded pixels' aspect is the image box's aspect.
        # This is the assert the double-rotation defect fails -- a portrait
        # bitmap in a landscape box -- and page-box equality alone cannot see.
        aspects_ok = all(
            abs((px[0] / px[1]) - (iw / ih)) <= 0.01
            for (px, _f, _r), (iw, ih) in zip((x[0] for x in out_x), img_boxes))
        c.check(aspects_ok, f"{name}: every embedded image's pixel aspect matches "
                            f"its box's aspect (no sideways page)")

        # -- outline and /Info -----------------------------------------
        want_outline = _flatten(meta.get("outline", []))
        c.check(out_outline == want_outline,
                f"{name}: outline titles, nesting and page targets survive "
                f"({out_outline})")
        for key, value in meta["info"].items():
            c.check(out_info.get(key) == value,
                    f"{name}: /Info {key} == {value!r} ({out_info.get(key)!r})")
    return fallbacks


def check_boundary(c, tmp):
    fake = os.path.join(tmp, "fake.pdf")
    with open(fake, "wb") as fh:
        fh.write(b"this is a text file wearing a .pdf extension\n")
    item = job.run_item(job.classify(fake), tmp, "check-pdf-fake")
    c.check(item.status == job.SKIPPED and item.reason,
            f"a text file named .pdf is SKIPPED with a reason ({item.reason!r})")

    # A zip signature under a .pdf name is dispatched by signature to the
    # archive reader, which finds no central directory. That is a corrupt
    # archive, and it is reported the way a corrupt .cbz is: FAILED with the
    # library's reason, never raised out of the boundary.
    zipped = os.path.join(tmp, "zipped.pdf")
    with open(zipped, "wb") as fh:
        fh.write(b"PK\x03\x04 this is a zip header in a .pdf\n")
    item = job.run_item(job.classify(zipped), tmp, "check-pdf-zipped")
    c.check(item.status in (job.SKIPPED, job.FAILED) and item.reason,
            f"a zip signature named .pdf is reported, not raised "
            f"({item.status}: {item.reason!r})")

    empty = os.path.join(tmp, "empty.pdf")
    open(empty, "wb").close()
    item = job.run_item(job.classify(empty), tmp, "check-pdf-empty")
    c.check(item.status == job.SKIPPED and item.reason,
            f"an empty .pdf is SKIPPED with a reason ({item.reason!r})")

    garbage = os.path.join(tmp, "garbage.pdf")
    with open(garbage, "wb") as fh:
        fh.write(b"%PDF-1.4\n" + b"\x00" * 200)
    item = job.run_item(job.classify(garbage), tmp, "check-pdf-garbage")
    c.check(item.status == job.SKIPPED and "not a readable PDF" in item.reason,
            f"a PDF header over garbage is SKIPPED as unreadable ({item.reason!r})")

    # The per-file cap on a DECLARED size: 600x900x3 is 1.62MB, so a 1MB cap
    # refuses page 1 before pdfium allocates it.
    tight = functools.partial(safety.Budget, max_file_bytes=1 << 20)
    orig = pipeline.safety.Budget
    pipeline.safety.Budget = tight
    try:
        item = job.run_item(job.classify(fixture(SCAN)), tmp, "check-pdf-cap")
    finally:
        pipeline.safety.Budget = orig
    c.check(item.status == job.SKIPPED and safety.FILE_SIZE_CAP in item.reason,
            f"a page over the per-file cap is SKIPPED as {safety.FILE_SIZE_CAP} "
            f"({item.reason!r})")
    c.check(not os.path.exists(pipeline.item_dir(tmp, SCAN)),
            "and the refused item's output directory is discarded")

    # Red-check: same budget, enforcement off, every page admitted.
    admitted = list(pdf.pages(fixture(SCAN),
                              safety.Budget(tmp, max_file_bytes=1 << 20, enforce=False)))
    c.check(len(admitted) == 3,
            f"the same budget with enforce=False admits all 3 pages "
            f"-- the refusal above is the rule's ({len(admitted)})")
    try:
        list(pdf.pages(fixture(SCAN), safety.Budget(tmp, max_file_bytes=1 << 20)))
        direct = None
    except safety.UnsafeArchive as e:
        direct = e
    c.check(direct is not None and direct.reason == safety.FILE_SIZE_CAP
            and "page 1" in direct.member,
            f"and directly, the refusal names the page ({direct})")


def check_info_names(c, tmp):
    """/Info values that are NAMES (`/Trapped /False`) stay names.

    The fixture cannot carry one: pypdf's add_metadata stringifies every
    value, which is exactly the defect being asserted against, so the source
    is built here through the writer's own dictionary.
    """
    from pypdf import PdfWriter
    from pypdf.generic import NameObject
    src = os.path.join(tmp, "trapped.pdf")
    writer = PdfWriter(clone_from=fixture(SCAN))
    writer._info[NameObject("/Trapped")] = NameObject("/False")  # noqa: SLF001
    with open(src, "wb") as fh:
        writer.write(fh)
    pages = [fixture("scan_p1.jpg"), fixture("scan_p2.png"), fixture("scan_p1.jpg")]
    out = pdf.write_pdf(os.path.join(tmp, "trapped_out.pdf"), pages, src)
    with open(out, "rb") as fh, PdfReader(fh) as reader:
        value = reader.metadata.get("/Trapped")
        title = reader.metadata.get("/Title")
    c.check(isinstance(value, NameObject) and value == "/False",
            f"/Trapped /False is copied as a NAME, not a text string "
            f"({type(value).__name__} {value!r})")
    c.check(title == "scan fixture", "and the text-string keys still come across")


def check_no_agpl(c):
    with open(os.path.join(ROOT, "sidecar", "containers", "pdf.py"), encoding="utf-8") as fh:
        src = fh.read()
    c.check("import fitz" not in src and "pymupdf" not in src.lower().replace("pymupdf would", ""),
            "pdf.py does not import PyMuPDF (AGPL)")
    c.check("extractall" not in src, "pdf.py never calls extractall")


def main():
    if not os.path.isdir(PDFS) or not os.path.isfile(fixture(SCAN)):
        return skip("fixtures/pdf/ is absent -- run tests/gen_fixtures.py")
    with open(os.path.join(PDFS, "expected.json"), encoding="utf-8") as fh:
        expected = json.load(fh)

    c = Checks("check_pdf")
    fallbacks = 0
    with tempfile.TemporaryDirectory() as tmp:
        check_fixtures(c, expected)
        check_detect(c)
        check_no_agpl(c)
        check_native(c, expected)
        check_cache_key(c, expected, tmp)
        fallbacks = check_round_trip(c, expected, tmp)
        check_info_names(c, tmp)
        check_boundary(c, tmp)

    # Recorded, not ratcheted: a count over a fixed fixture set (text.pdf and
    # text_rot.pdf exist to be the two), the same class as fit_failed_count.
    # The asserts above hold it at exactly two; the record is the history.
    print("METRICS " + json.dumps({"pdf_render_fallbacks": fallbacks}), flush=True)
    return c.finish()


if __name__ == "__main__":
    run(main)
