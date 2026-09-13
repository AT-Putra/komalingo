"""Phase 2b -- one region per BUBBLE, so the ladder is handed what AC-1 names.

The DB detector answers per text line, and a line of tategaki is a column.
Until this phase every column went through OCR, translation and typesetting on
its own, and page 010 of the real volume came out as "don't / really / play /
it / in VR / hist game / sold on" across six regions of one bubble. No rung of
the ladder can fit an English sentence into a 34px column; AC-1's "fits inside
the original bubble" needs the bubble. sidecar/group.py merges the columns and
detect.detect() returns the merged hulls. This gate holds that claim in four
places, each of which can go red on its own:

  [geometry]  the three rules and the absorb pass, on synthetic boxes -- the
              page 010 box-art case included, as numbers.
  [fixture]   fixtures/smoke/tategaki_02.png: three bubbles of 2, 3 and 4
              columns, one region each, every glyph of a bubble inside its
              hull and no glyph of another; the rotated art title beside
              bubble 2 stays its own region.
  [pipeline]  the whole pipeline over that page with one English sentence per
              bubble: every bubble typesets at rung <= 3 with neither flag
              set, and every pixel of new ink lands inside a hull. AC-1 at
              bubble granularity, on a page the detector actually saw.
  [panels]    the git-ignored real crops, when present: the count that come
              back as a single region, and manga-ocr's CER over the largest
              region against Phase 1's ground truth -- with the CER over the
              largest UNGROUPED quad printed beside it, because an assert that
              never shows what it would say without the change under test has
              not shown that it discriminates.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from lib.asserts import cer  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402
from sidecar import group, pipeline, room, typeset  # noqa: E402
from sidecar import detect as detector  # noqa: E402
from sidecar.llm import LLMClient  # noqa: E402

SMOKE = os.path.join(ROOT, "fixtures", "smoke")
PAGE = os.path.join(SMOKE, "tategaki_02.png")
EXPECTED = os.path.join(SMOKE, "expected.json")
TATEDIR = os.path.join(ROOT, "fixtures", "tategaki")
PANELS = os.path.join(TATEDIR, "expected.json")
# The real page the picture came from. Git-ignored; asserted on only when present.
PAGE_010 = os.path.join(TATEDIR, "Isekai Tensei de Kenja ni Natte v01s", "010.jpg")
# The 「史実」 bubble on that page: six column quads, one sentence.
PAGE_010_BUBBLE = (140, 720, 325, 915)
# The stairwell page (1280x1808). Git-ignored; asserted on only when present.
# The page that forced running both detector scales and the ink guard: see
# _page_stairwell for the three blocks it lost.
PAGE_STAIRS = os.path.join(ROOT, "fixtures", "real", "stairwell_006.webp")

# The gate's own numbers. INK_COVERAGE below 1.0 only because the detector's
# quads sit a pixel or two inside the outermost antialiased glyph edges.
INK_COVERAGE = 0.99
BORDER_ERODE = 14  # px inside the ellipse box, so the outline's ink is not "glyph ink"
SINGLE_PANELS_MIN = 16  # of 24 -- measured 20 at the time of writing
PANEL_CER_MAX = 0.10  # measured 0.031; Phase 1's own bar for the crops is 0.10
STUB_SENTENCES = [
    "That is not the kind of game you play in VR at all.",
    "What a lovely day it is out there today.",
    "Without a counterattack every one of us is dead.",
]


_box = group.bbox


def _mask(size, points) -> np.ndarray:
    m = Image.new("1", size, 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in points], fill=1)
    return np.asarray(m, dtype=bool)


def _ellipse_mask(size, box, erode: int) -> np.ndarray:
    x0, y0, x1, y1 = box
    m = Image.new("1", size, 0)
    ImageDraw.Draw(m).ellipse((x0 + erode, y0 + erode, x1 - erode, y1 - erode), fill=1)
    return np.asarray(m, dtype=bool)


def _ink(img) -> np.ndarray:
    return np.asarray(img.convert("L")) < typeset.INK_THRESHOLD


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


# -- [geometry] --------------------------------------------------------------


def _geometry(c) -> None:
    """The rules as numbers, including the case that forced the RATIO clause."""
    col = [_rect(100, 100, 140, 300), _rect(146, 102, 186, 296), _rect(192, 104, 232, 290)]
    c.check(group.group(col) == [[0, 1, 2]],
            f"[geometry columns] three columns 6px apart form one block: {group.group(col)}")

    apart = [_rect(100, 100, 140, 300), _rect(300, 100, 340, 300)]
    c.check(group.group(apart) == [[0], [1]],
            f"[geometry apart] two columns 160px apart (4x their width) stay separate: "
            f"{group.group(apart)}")

    nested = [_rect(100, 100, 250, 400), _rect(200, 120, 240, 380), _rect(110, 130, 150, 390)]
    c.check(group.group(nested) == [[0, 1, 2]],
            f"[geometry nested] a whole-block quad and the columns inside it are one "
            f"block: {group.group(nested)}")

    lines = [_rect(100, 100, 400, 130), _rect(105, 136, 395, 166), _rect(120, 172, 380, 202)]
    c.check(group.group(lines) == [[0, 1, 2]],
            f"[geometry stacked] three horizontal lines 6px apart form one block: "
            f"{group.group(lines)}")

    # Page 010: a 275x179 rotated art title whose bbox overlaps the bubble's
    # 42px columns in y and is 71px from the nearest one. Without the RATIO
    # clause this merged, and the bubble's English was laid across the art.
    art = [_rect(277, 737, 319, 911), _rect(242, 741, 279, 908), _rect(207, 736, 241, 885),
           _rect(361, 695, 636, 874)]
    got = group.group(art)
    c.check(got == [[0, 1, 2], [3]],
            f"[geometry art] a 275px-wide quad beside 42px columns is NOT merged with "
            f"them: {got}")

    # Page 012: the columns of one bubble two glyphs above the columns of the
    # next, same x range. Measured against a 200px column height that is
    # "stacked"; measured in glyphs it is a gap no piece of a single column
    # ever has -- two borders and a gutter stand in it. Two blocks.
    two_bubbles = [_rect(100, 100, 140, 300), _rect(146, 100, 186, 300),
                   _rect(100, 380, 140, 580), _rect(146, 380, 186, 580)]
    got = group.group(two_bubbles)
    c.check(got == [[0, 1], [2, 3]],
            f"[geometry two-bubbles] columns 80px (2 glyphs) below other columns are "
            f"another block: {got}")
    # The same two bubbles as the net actually returned them on page 012: one
    # 86px quad for two columns of the upper bubble, 57px above a 65px quad
    # for two columns of the lower. Each quad's OWN short side says two
    # glyphs and merges them; the page's median short side (the 31px column
    # beside them) says one, and does not.
    as_returned = [_rect(787, 444, 873, 628), _rect(852, 453, 907, 595), _rect(715, 485, 747, 529),
                   _rect(756, 685, 821, 906), _rect(738, 697, 769, 847), _rect(796, 688, 853, 879),
                   # ...and the rest of the page's dialogue, single columns
                   _rect(100, 100, 131, 250), _rect(140, 100, 170, 260), _rect(300, 700, 331, 900)]
    got = group.group(as_returned)
    c.check(got == [[0, 1, 2], [3, 4, 5], [6, 7], [8]],
            f"[geometry two-bubbles-wide] wide two-column quads 57px apart, on a page "
            f"whose glyph is 31px, are two blocks: {got}")
    broken = [_rect(100, 100, 140, 200), _rect(101, 212, 139, 300)]
    got = group.group(broken)
    c.check(got == [[0, 1]],
            f"[geometry broken-column] two pieces of one column 12px apart are one "
            f"block: {got}")

    # A furigana-sized sliver between two columns fails the RATIO clause
    # against both (4px beside 40px) but sits inside the block the three
    # columns form. The absorb pass takes it; without that pass it would be
    # OCR'd and translated as a region of its own.
    sliver = [_rect(100, 100, 140, 300), _rect(146, 100, 186, 300), _rect(192, 100, 232, 300),
              _rect(141, 150, 145, 250)]
    got = group.group(sliver)
    c.check(got == [[0, 1, 2, 3]],
            f"[geometry absorb] a 4px sliver between 40px columns is absorbed into the "
            f"block around it: {got}")

    # Page 012: the clock's "23:45", white on black, one glyph left of a
    # bubble's columns. By geometry a column of the bubble; by polarity not.
    clock = [_rect(689, 420, 720, 456), _rect(738, 431, 770, 628), _rect(776, 444, 810, 628)]
    got = group.group(clock, inverse=[True, False, False])
    c.check(got == [[0], [1, 2]],
            f"[geometry polarity] a light-on-dark quad one glyph from dark-on-light "
            f"columns is not their neighbour: {got}")
    c.check(group.group(clock) == [[0, 1, 2]],
            f"[geometry polarity] ...and by geometry alone it would have been: "
            f"{group.group(clock)}")

    hull = group.convex_hull([(0, 0), (10, 0), (10, 10), (0, 10), (5, 5), (5, 0)])
    c.check(sorted(hull) == [(0.0, 0.0), (0.0, 10.0), (10.0, 0.0), (10.0, 10.0)],
            f"[geometry hull] interior and collinear points are dropped: {hull}")

    # The ink guard: the caller says what lies between two boxes. Two columns
    # 28px apart, stacked -- the stairwell's two bubbles in two panels -- are
    # one block by distance and two when a border runs between them; a quad
    # nested in another joins it whatever is drawn around them.
    stacked = [_rect(1232, 22, 1275, 238), _rect(1234, 266, 1279, 501)]
    c.check(group.group(stacked) == [[0, 1]],
            f"[geometry ink] two stacked columns 28px apart are one block by distance: "
            f"{group.group(stacked)}")
    got = group.group(stacked, separated=lambda i, j: True)
    c.check(got == [[0], [1]],
            f"[geometry ink] ...and two blocks when ink runs between them: {got}")
    got = group.group(nested, separated=lambda i, j: True)
    c.check(got == [[0, 1, 2]],
            f"[geometry ink] a nested quad still joins its block through ink: {got}")


# -- [fixture] ---------------------------------------------------------------


def _bubble_of(entry, points):
    """Which fixture bubble the hull's centroid falls in, or None (the art block)."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    for i, b in enumerate(entry["bubbles"]):
        x0, y0, x1, y1 = b["box"]
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return i
    return None


def _fixture(c, entry, src) -> dict[int, dict]:
    """detect+group on the committed page. Returns {bubble index: region dict}."""
    regions = pipeline.detect(src, 1)
    n_bubbles = len(entry["bubbles"])
    by_bubble: dict[int, list] = {}
    art = []
    for r in regions:
        b = _bubble_of(entry, r["polygon"])
        (by_bubble.setdefault(b, []) if b is not None else art).append(r)

    c.check(len(regions) == n_bubbles + 2,
            f"[fixture count] {len(regions)} regions for {n_bubbles} bubbles, one art "
            f"title and one stack of two words on the art -- ids {[r['id'] for r in regions]}")
    for i, b in enumerate(entry["bubbles"]):
        got = by_bubble.get(i, [])
        c.check(len(got) == 1,
                f"[fixture bubble {i}] {len(b['columns'])} columns came back as "
                f"{len(got)} region(s), want exactly 1")
    parts = sorted(len(a.get("parts") or []) for a in art)
    c.check(parts == [1, 2],
            f"[fixture art] two art regions: the rotated title as one quad and the two "
            f"stacked words as one block of two parts -- parts per region {parts}")

    ink = _ink(src)
    ax0, ay0, ax1, ay1 = entry["art"]["box"]
    for i, b in enumerate(entry["bubbles"]):
        if len(by_bubble.get(i, [])) != 1:
            continue
        hull = _mask(src.size, by_bubble[i][0]["polygon"])
        own = ink & _ellipse_mask(src.size, b["box"], BORDER_ERODE)
        covered = (own & hull).sum() / max(own.sum(), 1)
        c.check(covered >= INK_COVERAGE,
                f"[fixture ink {i}] hull covers {covered:.4f} of the bubble's glyph ink "
                f">= {INK_COVERAGE}")
        others = np.zeros_like(ink)
        for j, o in enumerate(entry["bubbles"]):
            if j != i:
                others |= ink & _ellipse_mask(src.size, o["box"], BORDER_ERODE)
        leak = int((others & hull).sum())
        c.check(leak == 0, f"[fixture leak {i}] {leak} ink pixels of another bubble inside "
                           f"this hull == 0")
        hx0, hy0, hx1, hy1 = _box(by_bubble[i][0]["polygon"])
        c.check(hx1 <= ax0 or hx0 >= ax1 or hy1 <= ay0 or hy0 >= ay1,
                f"[fixture art-clear {i}] the hull ({hx0:.0f},{hy0:.0f},{hx1:.0f},{hy1:.0f}) "
                f"does not reach into the art block {entry['art']['box']}")
    return {i: rs[0] for i, rs in by_bubble.items() if len(rs) == 1}


# -- [pipeline] --------------------------------------------------------------


def _pipeline(c, entry, src, by_bubble: dict[int, dict]) -> None:
    """One English sentence per bubble through run_page; AC-1 at bubble granularity."""
    if len(by_bubble) != len(entry["bubbles"]):
        c.check(False, "[pipeline] skipped: not every bubble is one region")
        return
    replies = {by_bubble[i]["id"]: STUB_SENTENCES[i] for i in by_bubble}
    with tempfile.TemporaryDirectory() as dest, StubProvider(replies=replies, delay=0) as stub:
        client = LLMClient(stub.url, "k", "stub-model")
        record = pipeline.run_page(PAGE, dest, 1, client)
        with Image.open(record["output"]) as im:
            out = im.convert("RGB").copy()
    regions = {r["id"]: r for r in record["regions"]}

    hulls = np.zeros((src.height, src.width), dtype=bool)
    for i, want in by_bubble.items():
        r = regions[want["id"]]
        c.check(r["polygon"] == want["polygon"],
                f"[pipeline stable {i}] run_page's region {want['id']} is the same hull "
                f"the gate mapped -- ids are stable across two detections")
        c.check(r["typeset"] == STUB_SENTENCES[i],
                f"[pipeline text {i}] the whole sentence reached the page: "
                f"{r['typeset']!r}")
        c.check(r["rung"] <= 3 and not r["fit_failed"] and not r["fit_compromised"],
                f"[pipeline fit {i}] {len(entry['bubbles'][i]['columns'])} columns as one "
                f"region typeset at rung {r['rung']} <= 3, font {r['font_px']}px, "
                f"failed={r['fit_failed']} compromised={r['fit_compromised']} -- the "
                f"same sentence per column was rung 5")
        c.check(r["font_px"] >= 2 * typeset.floor_px(src.height),
                f"[pipeline size {i}] font {r['font_px']}px >= twice the "
                f"{typeset.floor_px(src.height)}px floor -- a bubble, not a column, "
                f"has room")
        # Phase 2b: the English is laid into the ROOM -- the bubble interior
        # around the block -- and that room must be the fixture's ellipse and
        # nothing past it.
        room = r.get("room")
        if c.check(bool(room), f"[pipeline room {i}] the engine found the bubble's room"):
            room_m = _mask(src.size, room)
            leak = int((room_m & ~_ellipse_mask(src.size, entry["bubbles"][i]["box"], 0)).sum())
            c.check(leak == 0,
                    f"[pipeline room {i}] {leak} room pixels outside the fixture's ellipse == 0")
            hx = _box(r["polygon"])
            rx = _box(room)
            c.check(rx[2] - rx[0] >= 1.5 * (hx[2] - hx[0]),
                    f"[pipeline room {i}] room {rx[2] - rx[0]:.0f}px wide >= 1.5x the "
                    f"{hx[2] - hx[0]:.0f}px block -- the English gets the bubble's width")
            hulls |= room_m
        hulls |= _mask(src.size, r["polygon"])

    # No orphans: rung 1 at its largest fitting size set "Without / a /
    # counterattack" on bubble 2, and now drops a size (bounded) rather than
    # leave one short word on a line of its own. The lines are read off a
    # second typeset of the SAME regions on the cleaned page, since the
    # record carries text and size but not line breaks.
    cleaned, _ = pipeline.inpaint(src, pipeline.detect(src, 1), 1)
    _, fits = typeset.typeset_page(record["regions"], cleaned)
    for i, want in by_bubble.items():
        fit = next(f for f in fits if f.id == want["id"])
        lines = [line for _, _, line in fit.lines]
        orphans = [line for line in lines if " " not in line and len(line) < 4]
        c.check(len(lines) >= 2 and not orphans,
                f"[pipeline orphan {i}] {len(lines)} lines at {fit.font_px}px, no line is "
                f"a single word under 4 characters (orphans: {orphans}) -- {lines}")

    # The erase took the PARTS and left the art between them: on the CLEANED
    # page (the same two stages run_page ran, before any English was drawn)
    # the strip of dark block between the two stacked words is still dark
    # and each word's white glyphs are gone. A hull erase -- page 012's box
    # down the character -- turns the strip white too. Phase 2c: "gone", not
    # "white". The words are white ink on the dark block, and the eraser now
    # continues the block under them; until 2c this assert read "the quad is
    # white", which is the box-over the eraser exists to stop drawing.
    cleaned_gray = np.asarray(cleaned.convert("L"))
    gx0, gy0, gx1, gy1 = entry["art"]["stack_gap"]
    strip = cleaned_gray[gy0:gy1, gx0:gx1]
    c.check(strip.mean() < 100,
            f"[pipeline parts] the art between the two stacked words is still dark after "
            f"the erase (mean {strip.mean():.0f} < 100) -- only the parts were filled")
    stack = next(r for r in record["regions"] if len(r.get("parts") or []) == 2)
    for k, part in enumerate(stack["parts"]):
        before = np.asarray(src.convert("L"))[_mask(src.size, part)]
        after = cleaned_gray[_mask(src.size, part)]
        c.check(after.size and (before > 200).mean() > 0.05 and (after > 200).mean() < 0.01,
                f"[pipeline parts] word {k} of the stack is erased: white glyph ink "
                f"{(before > 200).mean():.2f} -> {(after > 200).mean():.3f} of its quad, "
                f"and the quad is not a white box")

    # New ink is ink on the delivered page that the source did not have, so
    # the panel borders, the art block and the title do not count. Every
    # pixel of it must sit inside some region: AC-1's "inside the bubble".
    # The art region is a region too -- the stub echoes its OCR'd title back
    # and the ladder draws it into the quad -- so its quad is part of the
    # allowed area; what is asserted is that nothing lands OUTSIDE any of them.
    every = hulls.copy()
    for r in record["regions"]:
        every |= _mask(src.size, r.get("room") or r["polygon"])
    # Ink the RENDER drew: dark on the delivered page and dark on neither the
    # source nor the cleaned page. Phase 2c's eraser continues the art under
    # erased text, so a white title glyph that ran a pixel past its quad on the
    # dark block comes back dark -- that is the erase, not English outside its
    # bubble, and this assert is about the English.
    new_ink = _ink(out) & ~_ink(src) & ~_ink(cleaned)
    outside = int((new_ink & ~every).sum())
    c.check(outside == 0,
            f"[pipeline inside] {outside} pixels of new ink outside every region == 0")
    c.check(int((new_ink & hulls).sum()) > 0,
            "[pipeline drawn] and there IS new ink inside the hulls")


# -- [panels] ----------------------------------------------------------------


def _largest(polys):
    return max(polys, key=lambda p: (_box(p)[2] - _box(p)[0]) * (_box(p)[3] - _box(p)[1]))


def _panels(c) -> dict:
    """Real crops: single-region rate and OCR over the largest region, vs ungrouped."""
    with open(PANELS, encoding="utf-8") as fh:
        entries = json.load(fh)
    missing = [e["file"] for e in entries
               if not os.path.exists(os.path.join(TATEDIR, e["file"]))]
    if missing:
        print(f"  [panels] skipped: {len(missing)}/{len(entries)} panels absent")
        return {}

    from sidecar import ocr_ja  # noqa: PLC0415 -- loads the OCR model; only here

    single, grouped_cer, raw_cer = 0, [], []
    for e in entries:
        with Image.open(os.path.join(TATEDIR, e["file"])) as im:
            im.load()
            src = im.convert("RGB")
        raw = [p for p, _ in detector.quads(src)]
        regions = detector.detect(src)
        single += len(regions) == 1
        crop = tuple(int(v) for v in _box(_largest([r.polygon for r in regions])))
        grouped_cer.append(cer(ocr_ja.ocr(src.crop(crop)), e["text"]))
        crop = tuple(int(v) for v in _box(_largest(raw)))
        raw_cer.append(cer(ocr_ja.ocr(src.crop(crop)), e["text"]))
        print(f"    {e['file'][-17:]}: {len(raw):>2} quads -> {len(regions)} region(s), "
              f"CER {grouped_cer[-1]:.3f} (ungrouped largest quad {raw_cer[-1]:.3f})")

    mean_g = sum(grouped_cer) / len(grouped_cer)
    mean_r = sum(raw_cer) / len(raw_cer)
    c.check(single >= SINGLE_PANELS_MIN,
            f"[panels single] {single}/{len(entries)} crops come back as exactly one "
            f"region >= {SINGLE_PANELS_MIN}")
    c.check(mean_g <= PANEL_CER_MAX,
            f"[panels cer] mean CER over the largest grouped region {mean_g:.4f} <= "
            f"{PANEL_CER_MAX}; over the largest UNGROUPED quad it is {mean_r:.4f}")
    c.check(mean_g < mean_r,
            f"[panels discriminates] grouping lowers the CER ({mean_r:.4f} -> "
            f"{mean_g:.4f}) -- the assert above would go red on the ungrouped pipeline")
    return {"single_group_panels": single, "group_cer": round(mean_g, 4)}


def _page_010(c) -> None:
    """The page the picture came from, when it is on disk."""
    if not os.path.exists(PAGE_010):
        print("  [page010] skipped: the real page is not on disk")
        return
    with Image.open(PAGE_010) as im:
        im.load()
        src = im.convert("RGB")
    raw = detector.quads(src)
    regions = detector.detect(src)
    bx0, by0, bx1, by1 = PAGE_010_BUBBLE
    in_bubble = [r for r in regions
                 if bx0 <= sum(p[0] for p in r.polygon) / len(r.polygon) <= bx1
                 and by0 <= sum(p[1] for p in r.polygon) / len(r.polygon) <= by1]
    # 12, not the 10 the coarse-only detector gave: running the fine scale too
    # (detect.py, the stairwell page) finds the whiteboard's 「閉4」 at
    # (84, 660) -- real text the coarse pass never saw -- and a small-kana
    # fragment of the カチャッ sound effect that RATIO keeps out of its block.
    # The bound is against over-splitting; the bubble assert below is the one
    # that says the grouping still holds.
    c.check(len(regions) <= 12,
            f"[page010 count] {len(raw)} quads -> {len(regions)} regions <= 12")
    c.check(len(in_bubble) == 1,
            f"[page010 bubble] the 「史実」 bubble's columns are {len(in_bubble)} region(s), "
            f"want 1")


def _page_stairwell(c) -> None:
    """The page that lost three blocks to the coarse-only detector and GAP alone.

    Blocks by their bbox on the page, from the detector's own quads:
      caption 「喜ぶ二人」 (973, 363, 54x166)  -- found at 1984 only, 0.99
      bubble  「バレないよう」 (1235, 11)      -- panel 1
      bubble  「ありがとう!!」 (1236, 269)      -- panel 2, 28px below, same x
      caption 「だから…」 (104, 1594)          -- 49px left of the bubble below
      bubble  「先に入ってて／飲み物…」 (201..289, 1404) -- two columns
    """
    if not os.path.exists(PAGE_STAIRS):
        print("  [stairwell] skipped: the real page is not on disk")
        return
    with Image.open(PAGE_STAIRS) as im:
        im.load()
        src = im.convert("RGB")
    regions = detector.detect(src)

    def at(x, y):
        """Regions whose bbox contains the point."""
        out = []
        for r in regions:
            xs = [p[0] for p in r.polygon]
            ys = [p[1] for p in r.polygon]
            if min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys):
                out.append(r.id)
        return out

    caption = at(1000, 445)
    c.check(len(caption) == 1,
            f"[stairwell caption] 「喜ぶ二人」 beside the black hair is a region: {caption} "
            f"({len(regions)} regions on the page)")
    p1, p2 = at(1255, 120), at(1257, 380)
    c.check(len(p1) == 1 and len(p2) == 1 and p1 != p2,
            f"[stairwell panels] the columns 28px apart in two panels are two regions: "
            f"panel 1 {p1}, panel 2 {p2}")
    narration, bubble_a, bubble_b = at(128, 1670), at(223, 1600), at(266, 1520)
    c.check(len(narration) == 1 and len(bubble_a) == 1 and narration != bubble_a,
            f"[stairwell narration] 「だから…」 49px left of a bubble is not part of it: "
            f"{narration} vs {bubble_a}")
    c.check(bubble_a == bubble_b,
            f"[stairwell bubble] ...while the bubble's own two columns stay one region: "
            f"{bubble_a} vs {bubble_b}")

    # The room, on the same page: four of its five bubbles are drawn against
    # a page edge, and room.py declined every one until the page edge stopped
    # counting as the window. The caption in the open panel beside the last
    # bubble must still be declined -- it touches the page edge too, and
    # without the fill test it became a 174x403 room set at 60px.
    dicts = [{"id": r.id, "polygon": r.polygon, "parts": r.parts} for r in regions]
    cleaned, _ = pipeline.inpaint(src, dicts, 1)
    points = [[tuple(p) for p in r.polygon] for r in regions]

    def room_of(rid):
        i = next(k for k, r in enumerate(regions) if r.id == rid)
        return room.room(cleaned, points[i], [pts for k, pts in enumerate(points) if k != i])

    quiet = at(1006, 120)  # 「静かにしてね」, the bubble against the top edge
    top_bubble = room_of(quiet[0]) if len(quiet) == 1 else None
    tb = group.bbox(top_bubble) if top_bubble else None
    c.check(tb is not None and tb[2] - tb[0] > 45 and tb[1] < 20,
            f"[stairwell room] the bubble cut by the top page edge gets a room wider than "
            f"its column, reaching the edge: {tb}")
    open_panel = room_of(narration[0]) if len(narration) == 1 else "n/a"
    c.check(open_panel is None,
            f"[stairwell room] ...and the caption in the open panel beside a page edge is "
            f"declined: {open_panel if open_panel is None else group.bbox(open_panel)}")


def main():
    c = Checks("check_group")

    if not os.path.exists(PAGE) or not os.path.exists(EXPECTED):
        return skip(f"no multi-column smoke page at {PAGE} -- run tests/gen_fixtures.py")
    try:
        detector.weights()
    except detector.DetectError as e:
        return skip(f"detector weights unavailable: {e}")

    with open(EXPECTED, encoding="utf-8") as fh:
        entry = json.load(fh)["tategaki_02.png"]
    with Image.open(PAGE) as im:
        src = im.convert("RGB").copy()

    _geometry(c)
    by_bubble = _fixture(c, entry, src)
    _pipeline(c, entry, src, by_bubble)
    metrics = _panels(c) if os.path.exists(PANELS) else {}
    _page_010(c)
    _page_stairwell(c)

    if metrics:
        print("METRICS " + json.dumps(metrics))
    return c.finish()


run(main)
