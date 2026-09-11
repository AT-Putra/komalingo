"""Phase 4 -- Chinese and Korean through PP-OCRv5 (AC-3). OFFLINE after first fetch.

AC-3 says "same as AC-1 for zh and ko", so this gate is the Phase 1 and 2a
asserts over a second engine, at the same numeric bars, through the same
helpers in tests/lib/asserts.py -- not a new standard written for the new
engine to meet.

  [ocr]     check_tategaki's bars, unchanged: per bubble CER <= 0.35, set
            mean <= 0.10, exact match >= 16/20 of the set. Measured through
            pipeline.ocr(source=lang) -- the route production takes, parts and
            join and all -- and NOT through a whole-bubble shortcut a page
            never takes.
  [fit]     every bubble region of every page typesets at rung <= 3 with
            neither flag and the whole English rendered (assert_fit); ink
            inside each region's parts is erased (assert_erased). The whole
            pipeline, with a StubProvider answering one sentence per region.
  [route]   "JP always manga-ocr, never Paddle" as a COUNTER: both engines are
            patched to count, and source=ja moves one counter while zh and ko
            move the other. A source grep would keep passing the day an
            indirect call arrives.
  [blank]   the hallucination gate: three blank crops read as nothing.
  [ja]      ocr_cjk refuses "ja" by name, at the engine.
  [cache]   the page cache is keyed on pixels and nothing about the run, so a
            page read under ja and re-run under zh would hand the zh run
            manga-ocr's reading of Chinese. regions.json now records the
            source, and a mismatch is a miss: measured as four run_item passes
            over the CBZ fixture -- ja miss, ja hit, zh miss, zh hit.

Skips (exit 3) when the fixtures are absent or the weights cannot be fetched;
never passes silently on either.
"""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from lib.asserts import assert_cer, assert_erased, assert_fit  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402
from sidecar import models, ocr_cjk, ocr_ja, pipeline  # noqa: E402
from sidecar.llm import LLMClient  # noqa: E402

FIXTURES = os.path.join(ROOT, "fixtures")
LANGS = ("zh", "ko")
CBZ = os.path.join(FIXTURES, "cbz", "sample.cbz")

# check_tategaki's numbers, verbatim. The point of the gate is that they are
# the SAME numbers, so they are not restated as constants of their own.
PANEL_CEILING = 0.35
MEAN_CEILING = 0.10
EXACT_FRAC = (16, 20)

SENTENCES = [
    "What on earth are you doing here?",
    "Run, before it finds us!",
    "This cannot be happening.",
    "I will never give up on this.",
    "Wait for me at the gate.",
    "That is wonderful news!",
]


def _load(lang: str) -> dict | None:
    path = os.path.join(FIXTURES, lang, "expected.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        index = json.load(fh)
    if any(not os.path.exists(os.path.join(FIXTURES, lang, name)) for name in index):
        return None
    return index


def _centroid(points):
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def _regions_in(regions, box):
    x0, y0, x1, y1 = box
    return [r for r in regions
            if x0 <= _centroid(r["polygon"])[0] <= x1 and y0 <= _centroid(r["polygon"])[1] <= y1]


# -- [ocr] -----------------------------------------------------------------


def _ocr(c, lang: str, index: dict) -> tuple[float, float]:
    """The Phase 1 bars over this language's pages. Returns (mean CER, exact fraction)."""
    cers, exact, total = [], 0, 0
    for name in sorted(index):
        with Image.open(os.path.join(FIXTURES, lang, name)) as im:
            src = im.convert("RGB").copy()
        regions = pipeline.detect(src, 1)
        pipeline.ocr(regions, src, 1, lang)
        for b in index[name]["bubbles"]:
            hits = _regions_in(regions, b["box"])
            got = ocr_cjk.SEPARATOR[lang].join(r["text"] for r in hits)
            rate = assert_cer(c, got, b["text"], PANEL_CEILING,
                              f"[ocr {lang}] {name} {b['orientation'][:4]} "
                              f"({len(hits)} region{'s' if len(hits) != 1 else ''})")
            cers.append(rate)
            exact += got == b["text"]
            total += 1
    mean = sum(cers) / len(cers)
    floor = math.ceil(EXACT_FRAC[0] * total / EXACT_FRAC[1])
    c.check(exact >= floor, f"[ocr {lang}] exact match {exact}/{total} >= {floor} (16/20)")
    c.check(mean <= MEAN_CEILING, f"[ocr {lang}] mean CER {mean:.4f} <= {MEAN_CEILING}")
    return mean, exact / total


# -- [fit] / [erased] --------------------------------------------------------


def _fit(c, lang: str, index: dict) -> None:
    """AC-1's clauses over the second engine's pages, whole pipeline."""
    for name in sorted(index):
        path = os.path.join(FIXTURES, lang, name)
        with Image.open(path) as im:
            src = im.convert("RGB").copy()
        src_gray = np.asarray(src.convert("L"), dtype=np.float64)
        regions = pipeline.detect(src, 1)
        cleaned, _ = pipeline.inpaint(src, regions, 1)
        cleaned_gray = np.asarray(cleaned.convert("L"), dtype=np.float64)
        for r in regions:
            assert_erased(c, src_gray, cleaned_gray, r.get("parts") or [r["polygon"]],
                          f"[erased {lang}] {name} region {r['id']}")

        replies = {r["id"]: SENTENCES[i % len(SENTENCES)] for i, r in enumerate(regions)}
        with tempfile.TemporaryDirectory() as dest, StubProvider(replies=replies, delay=0) as stub:
            record = pipeline.run_page(path, dest, 1, LLMClient(stub.url, "k", "stub-model"), lang)
        c.check(record["source"] == lang,
                f"[fit {lang}] {name} regions.json records source={record['source']!r}")
        page_h = index[name]["size"][1]
        for b in index[name]["bubbles"]:
            for r in _regions_in(record["regions"], b["box"]):
                assert_fit(c, r, page_h, f"[fit {lang}] {name} region {r['id']} "
                                         f"({b['orientation'][:4]}, {r['typeset'][:24]!r})")


# -- [route] / [blank] / [ja] ------------------------------------------------


def _route(c, index_zh: dict) -> None:
    """Both engines patched to counters; each source moves exactly one."""
    calls = {"ja": 0, "cjk": 0}
    real_ja, real_cjk = ocr_ja.ocr, ocr_cjk.ocr

    def fake_ja(*a, **k):
        calls["ja"] += 1
        return "日本語"

    def fake_cjk(img, parts, lang):
        calls["cjk"] += 1
        return f"{lang}文"

    name = sorted(index_zh)[0]
    with Image.open(os.path.join(FIXTURES, "zh", name)) as im:
        src = im.convert("RGB").copy()
    regions = pipeline.detect(src, 1)
    try:
        ocr_ja.ocr, ocr_cjk.ocr = fake_ja, fake_cjk
        for source, mover in (("ja", "ja"), ("zh", "cjk"), ("ko", "cjk")):
            calls["ja"] = calls["cjk"] = 0
            n = pipeline.ocr([dict(r) for r in regions], src, 1, source)
            other = "cjk" if mover == "ja" else "ja"
            c.check(calls[mover] == len(regions) == n and calls[other] == 0,
                    f"[route] source={source!r}: {calls['ja']} manga-ocr calls, "
                    f"{calls['cjk']} PP-OCR calls for {len(regions)} regions -- "
                    f"{'manga-ocr only' if mover == 'ja' else 'PP-OCR only'}, one per region")
        try:
            pipeline.ocr([dict(r) for r in regions], src, 1, "fr")
            c.check(False, "[route] an unknown source raises")
        except ValueError as e:
            c.check("ja" in str(e) and "zh" in str(e) and "ko" in str(e),
                    f"[route] an unknown source raises ValueError naming the set: {e}")
    finally:
        ocr_ja.ocr, ocr_cjk.ocr = real_ja, real_cjk


def _blank_and_ja(c) -> None:
    white = Image.new("RGB", (240, 60), "white")
    gray = Image.new("RGB", (240, 60), (128, 128, 128))
    bordered = white.copy()
    ImageDraw.Draw(bordered).rectangle((0, 0, 239, 59), outline="black", width=5)
    part = [[(0, 0), (240, 0), (240, 60), (0, 60)]]
    for lang in LANGS:
        got = [ocr_cjk.ocr(img, part, lang) for img in (white, gray, bordered)]
        c.check(got == ["", "", ""],
                f"[blank {lang}] three blank crops read as nothing: {got}")
    try:
        ocr_cjk.ocr(white, part, "ja")
        c.check(False, "[ja] ocr_cjk refuses 'ja'")
    except ocr_cjk.OcrError as e:
        c.check("manga-ocr" in str(e), f"[ja] ocr_cjk refuses 'ja' by name: {e}")


def _cache(c) -> None:
    """A cached page is a hit under its own source and a miss under another."""
    import contextlib
    import io

    from sidecar import cache

    if not os.path.exists(CBZ):
        c.check(False, f"[cache] {CBZ} is missing -- run tests/gen_fixtures.py")
        return
    # The fixture carries two byte-identical pages on purpose (Phase 3's
    # placement case). The later twin is a HIT even on a cold run: its pixels
    # were ingested one twin earlier. A miss run therefore has exactly that
    # page cached and no other.
    with open(os.path.join(FIXTURES, "cbz", "expected.json"), encoding="utf-8") as fh:
        twins = json.load(fh)["sample.cbz"]["identical_ordinals"]
    later_twin = max(twins)
    with tempfile.TemporaryDirectory() as cache_dir, tempfile.TemporaryDirectory() as dest:
        os.environ["MT_CACHE_DIR"] = cache_dir
        cache.clear_tier()
        cache._running.clear()
        runs = []
        for i, source in enumerate(("ja", "ja", "zh", "zh")):
            with contextlib.redirect_stdout(io.StringIO()):
                record = pipeline.run_item(CBZ, dest, f"job-{i}", client=None, source=source)
            runs.append((source, {p["page"]: p["cached"] for p in record["pages"]},
                         {p.get("source") for p in record["pages"]}))
        del os.environ["MT_CACHE_DIR"]
        cache.clear_tier()
    for (source, cached, sources), hit in zip(runs, (False, True, False, True)):
        want = {page: (hit or page == later_twin) for page in cached}
        c.check(cached == want and sources == {source},
                f"[cache] run under {source!r}: {'HIT' if hit else 'MISS'} -- cached pages "
                f"{sorted(p for p, v in cached.items() if v)} (want "
                f"{sorted(p for p, v in want.items() if v)}), records say source={sources}")


def main():
    c = Checks("check_cjk")

    indexes = {lang: _load(lang) for lang in LANGS}
    missing = [lang for lang, idx in indexes.items() if idx is None]
    if missing:
        return skip(f"no {'/'.join(missing)} fixtures under {FIXTURES} -- run tests/gen_fixtures.py")
    try:
        for lang in LANGS:
            models.ensure(ocr_cjk.LANGS[lang])
    except models.FetchError as e:
        return skip(f"PP-OCRv5 weights unavailable ({e.kind}): {e.reason}")

    means, exacts = [], []
    for lang in LANGS:
        mean, exact = _ocr(c, lang, indexes[lang])
        means.append(mean)
        exacts.append(exact)
        _fit(c, lang, indexes[lang])
    _route(c, indexes["zh"])
    _blank_and_ja(c)
    _cache(c)

    print("METRICS " + json.dumps({"cjk_mean_cer": round(sum(means) / len(means), 4),
                                   "cjk_exact_match": round(sum(exacts) / len(exacts), 4)}))
    return c.finish()


run(main)
