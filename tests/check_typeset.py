"""Phase 2a -- the five-rung fit ladder. Owns AC-1's fit half. OFFLINE.

Every fixture here asserts the POSITIVE case: not "nothing crashed" but "this
specific rung was taken, and its specific consequence is visible in the
result". A gate written the other way passes against an engine that quietly
never implements rungs 3, 4 or 5, because an easy string never reaches them.

Six things here are load-bearing.

**Overflow is measured on the DELIVERED PAGE, by this file, and the engine's
own report must agree with it.** The engine measures its ink in a scratch frame
(typeset._raster_metrics). A review round showed that reading only that report
is not enough: with the engine's measurement stubbed to zeros, or with the page
drawn 20px away from where it was measured, this gate stayed green, because it
was taking the engine's word for what the engine had drawn. So `_page_overflow`
measures the page the caller actually receives, with its own code, and
`[measure-agrees]` requires the engine's report to equal it.

**The rung counter is read from the result, not inferred from the pixels.**
Two rungs produce the same raster on a string that fits either way, so a gate
that guesses the rung from the image cannot tell "rung 4 was not needed" from
"rung 4 is not implemented".

**The retry is issued through a real LLMClient against a real socket.** The
"exactly one retry request" assert counts requests arriving at
tests/lib/stub_provider.py, the far side of llm.py's Semaphore(3). The cap the
request carried is read back out of the request itself.

**Rung 5's capacity is asserted, not trusted,** and so is the monotonicity every
search in the ladder stands on: `[monotone]` scans the fit predicate over every
prefix for a fit after a miss.

**Every branch rung 5 can take has a fixture.** A reply that fits
(rung5-success), a reply longer than its cap (rung5-length, rejected), and a
reply within its cap that still does not fit (rung5-geometry, accepted then
truncated). The spec names all three; a branch no fixture reaches is a branch
no assert watches.

**Each fixture forces its rung, and that is itself asserted.** Five of the six
fixtures once landed on rung 1. `[rung]` reports a fixture that stops forcing
instead of letting it pass on a rung it was not written for.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider, requested_items  # noqa: E402
from sidecar import typeset  # noqa: E402
from sidecar.llm import LLMClient  # noqa: E402
from sidecar.region import ellipse_points  # noqa: E402

BUBBLES = os.path.join(ROOT, "fixtures", "bubbles")
EXPECTED = os.path.join(BUBBLES, "expected.json")

# NOT in fixtures/bubbles/, where the build order named it, and the reason is
# a hard incompatibility rather than a preference: check_fixtures_deterministic
# proves its "two regenerations from an EMPTY TREE" claim by rmtree-ing
# fixtures/smoke/ and fixtures/bubbles/ before each run. A committed file in
# that directory is deleted on every suite run -- measured: this store vanished
# the first time run_all executed after it was written.
#
# And say plainly what it IS: a DRIFT DETECTOR, not an independent expectation.
# It is snapshotted from the implementation (MT_WRITE_EXPECTED_METRICS) and its
# only job is to make any change in the engine's per-fixture numbers visible as
# a diff someone has to accept. The asserts in main() are the expectations.
METRICS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "expected_metrics.json")

RID = 1  # one region per fixture page; the stub keys its reply on this id
_NO_SOURCE_KEY = object()  # sentinel: build the region with no "text" key at all


def _polygon_mask(size, points) -> np.ndarray:
    mask = Image.new("1", size, 0)
    ImageDraw.Draw(mask).polygon([tuple(p) for p in points], fill=1)
    return np.asarray(mask, dtype=bool)


def _ink(img) -> np.ndarray:
    return np.asarray(img.convert("L")) < typeset.INK_THRESHOLD


def _ink_in_polygon(img, points) -> int:
    """Ink pixels inside the polygon. The raster half of "renders empty"."""
    return int((_ink(img) & _polygon_mask(img.size, points)).sum())


def _page_overflow(img, points) -> tuple[int, int]:
    """(horizontal, vertical) px of DELIVERED ink outside the polygon. This file's code.

    Every ink pixel outside the polygon mask is measured to the nearest polygon
    pixel: in its own row when that row crosses the polygon, otherwise to the
    nearest row that does. Written here, not imported from the engine, and run
    on the page the caller receives -- so a broken engine measurement, or a page
    drawn somewhere other than where it was measured, cannot agree with it by
    sharing its mistake.
    """
    mask = _polygon_mask(img.size, points)
    outside = _ink(img) & ~mask
    if not outside.any():
        return 0, 0
    mask_rows = np.nonzero(mask.any(axis=1))[0]
    ox = oy = 0
    for r in np.nonzero(outside.any(axis=1))[0]:
        cols = np.nonzero(outside[r])[0]
        row_poly = np.nonzero(mask[r])[0]
        if row_poly.size == 0:
            oy = max(oy, int(np.abs(mask_rows - r).min()))
            continue
        nearest = np.array([np.abs(row_poly - col).min() for col in cols])
        ox = max(ox, int(nearest.max()))
    return ox, oy


def _typeset(entry, replies, *, allow_retranslate=True, translation=None,
             source=_NO_SOURCE_KEY):
    """One fixture page through the ladder against a live stub provider.

    Returns (delivered image, Fit, requests observed at the provider, last payload).
    """
    src = Image.new("RGB", tuple(entry["page_size"]), "white")
    region = {
        "id": RID,
        "polygon": ellipse_points(entry["box"]),
        "translation": entry["translation_in"] if translation is None else translation,
    }
    if source is not _NO_SOURCE_KEY:
        region["text"] = source
    with StubProvider(replies=replies, delay=0) as stub:
        client = LLMClient(stub.url, "k", "stub-model")
        out, fits = typeset.typeset_page(
            [region], src, allow_retranslate=allow_retranslate, client=client
        )
        return out, fits[0], stub.chat_requests, stub.last_payload


def _poly_width(points) -> float:
    xs = [p[0] for p in points]
    return max(xs) - min(xs)


def _check_page(c, label, img, fit, points) -> tuple[int, int]:
    """The delivered-page asserts every typeset result gets, wherever it came from."""
    per_side = math.ceil(typeset.BLEED_FRAC * _poly_width(points) / 2)
    allowed = per_side if fit.fit_compromised else 0
    page_ox, page_oy = _page_overflow(img, points)
    c.check(page_ox <= allowed and page_oy == 0,
            f"{label} [page-overflow] delivered page: {page_ox}px of ink beside and "
            f"{page_oy}px above/below the polygon; allowed {allowed}px beside "
            f"({'4% of polygon width per side' if allowed else 'zero, not compromised'}) "
            f"and 0 above/below")
    c.check((fit.overflow_px_x, fit.overflow_px_y) == (page_ox, page_oy),
            f"{label} [measure-agrees] the engine reports overflow "
            f"({fit.overflow_px_x}, {fit.overflow_px_y}) and the delivered page "
            f"measures ({page_ox}, {page_oy}) -- they must be the same number")
    return page_ox, page_oy


def main():
    c = Checks("check_typeset")

    if not os.path.exists(EXPECTED):
        return skip(f"no bubble fixtures at {BUBBLES} -- run tests/gen_fixtures.py")

    with open(EXPECTED, encoding="utf-8") as fh:
        index = json.load(fh)
    measured = {}

    for name in sorted(index):
        entry = index[name]
        want = entry["expect"]
        page_w, page_h = entry["page_size"]
        floor = typeset.floor_px(page_h)
        points = ellipse_points(entry["box"])
        poly_w = _poly_width(points)
        replies = {RID: entry["retry_reply"]} if "retry_reply" in entry else None

        # The committed PNG and the record describe the same page. The gate
        # typesets onto a blank page of that size (the PNG carries Japanese
        # source glyphs that would read as ink), so this is what ties the image
        # file to the geometry the asserts use.
        with Image.open(os.path.join(BUBBLES, name)) as im:
            c.check(im.size == (page_w, page_h),
                    f"{name} [png] fixture image is {im.size}, record says "
                    f"{(page_w, page_h)} -- the geometry and the file must agree")

        img, fit, requests, payload = _typeset(entry, replies)
        summary = typeset.summary([fit])

        # -- the absolutes --------------------------------------------------
        c.check(fit.font_px >= floor,
                f"{name} [floor] font {fit.font_px}px >= floor {floor}px")
        c.check(fit.clipped_glyphs == 0 and fit.offpage_ink_px == 0,
                f"{name} [clip] {fit.clipped_glyphs} clipped glyphs, "
                f"{fit.offpage_ink_px} ink pixels off the page raster -- both must be 0")
        c.check(fit.overflow_px_y == 0,
                f"{name} [vertical] engine reports {fit.overflow_px_y}px of ink above or "
                f"below the polygon == 0 -- rung 4 bleeds horizontally or not at all")
        _check_page(c, name, img, fit, points)

        # -- the fixture still forces the rung it was written for ---------
        c.check(fit.rung == entry["forces_rung"],
                f"{name} [rung] took rung {fit.rung}, fixture forces "
                f"{entry['forces_rung']} -- a fixture that stops forcing is an "
                f"assert that stopped being able to go red")
        c.check(fit.rung4_skipped == want.get("rung4_skipped", False),
                f"{name} [skip4] rung4_skipped={fit.rung4_skipped}, "
                f"want {want.get('rung4_skipped', False)}")

        # -- the flags the job summary reports ----------------------------
        c.check(fit.fit_compromised == want["fit_compromised"],
                f"{name} [compromised] fit_compromised={fit.fit_compromised}, "
                f"want {want['fit_compromised']}")
        c.check(fit.fit_failed == want["fit_failed"],
                f"{name} [failed] fit_failed={fit.fit_failed}, want {want['fit_failed']}")
        if "reason" in want:
            c.check(fit.reason == want["reason"],
                    f"{name} [reason] {fit.reason!r}, want {want['reason']!r}")
        if "retranslated" in want:
            c.check(fit.retranslated == want["retranslated"],
                    f"{name} [retranslated] retranslated={fit.retranslated}, want "
                    f"{want['retranslated']} -- whether the page shows the provider's "
                    f"reply or the original")
            c.check((RID in summary["retranslated"]) == want["retranslated"],
                    f"{name} [surfaced] region {RID} "
                    f"{'appears' if want['retranslated'] else 'does not appear'} in the "
                    f"job summary's retranslated list")
        if want["fit_failed"]:
            c.check(RID in summary["fit_failed"],
                    f"{name} [surfaced] region {RID} appears in the job summary's "
                    f"fit_failed list -- an unreported truncation is a silent one")
        if want["fit_compromised"]:
            c.check(RID in summary["fit_compromised"],
                    f"{name} [surfaced] region {RID} appears in the job summary's "
                    f"fit_compromised list")

        # -- rung 5's request budget, and the cap it carried --------------
        if want.get("retranslate"):
            c.check(requests == 1,
                    f"{name} [retry] exactly one retry request reached the provider, "
                    f"saw {requests} -- counted at llm.py's semaphore, not at the caller")
            sent = {i.get("id"): i for i in requested_items(payload)}
            c.check(sent.get(RID, {}).get("max_chars") == fit.capacity,
                    f"{name} [cap-sent] the request capped region {RID} at "
                    f"{sent.get(RID, {}).get('max_chars')} chars, the computed "
                    f"capacity is {fit.capacity}")
        elif entry["forces_rung"] < 5:
            c.check(requests == 0,
                    f"{name} [retry] no retry request issued below rung 5, saw {requests}")

        if entry["forces_rung"] == 5:
            source = entry["translation_in"]
            fits_at = typeset._floor_fits(points, page_w, page_h)
            cap = fit.capacity
            first_ok = bool(fits_at(source[:cap])) if cap else True
            next_bad = cap >= len(source) or not fits_at(source[:cap + 1])
            c.check(first_ok and next_bad,
                    f"{name} [cap] capacity {cap}: the first {cap} characters fit "
                    f"({first_ok}) and {cap + 1} do not ({next_bad}) -- a cap that is "
                    f"not the boundary is a guess")

        if "reply_rejected" in want:
            c.check(fit.reply_rejected == want["reply_rejected"],
                    f"{name} [reply] reply_rejected={fit.reply_rejected}, want "
                    f"{want['reply_rejected']} -- a reply longer than its cap must not "
                    f"be trusted over the original")

        # -- the branch-specific consequence ------------------------------
        if "rendered_text" in want:
            c.check(fit.text == want["rendered_text"],
                    f"{name} [rendered] rendered {fit.text!r}, "
                    f"want {want['rendered_text']!r} -- byte for byte")
            if want["rendered_text"] == "":
                ink = _ink_in_polygon(img, points)
                c.check(ink == 0,
                        f"{name} [empty] {ink} ink pixels inside the polygon == 0 "
                        f"-- 'renders empty' is a claim about the raster, not the record")

        if want.get("ellipsis"):
            token = entry["translation_in"]
            c.check(fit.text.endswith(typeset.ELLIPSIS),
                    f"{name} [ellipsis] rendered {fit.text!r} ends with an ellipsis")
            c.check(len(fit.text) < len(token) and token.startswith(fit.text[:-1]),
                    f"{name} [prefix] rendered text is a proper prefix of the token "
                    f"plus an ellipsis ({fit.text!r} vs {token!r:.40})")

        if want.get("word_boundary"):
            source = entry["retry_reply"] if fit.retranslated else entry["translation_in"]
            words = source.split()
            n = len(fit.text.split())
            c.check(0 < n < len(words) and fit.text == " ".join(words[:n]),
                    f"{name} [boundary] truncation stopped at a word boundary of the "
                    f"{'reply' if fit.retranslated else 'original'}, short of its end "
                    f"({n}/{len(words)} words, ...{fit.text[-30:]!r})")

        measured[name] = {
            "rung": fit.rung,
            "rung4_skipped": fit.rung4_skipped,
            "font_px": fit.font_px,
            "fit_compromised": fit.fit_compromised,
            "fit_failed": fit.fit_failed,
            "retranslated": fit.retranslated,
            "reason": fit.reason,
            "capacity": fit.capacity,
            "overflow_px_x": fit.overflow_px_x,
            "overflow_px_y": fit.overflow_px_y,
            "clipped_glyphs": fit.clipped_glyphs,
            "rendered_chars": len(fit.text),
            "poly_w": round(poly_w, 3),
        }

    _batching_and_spotfix(c, index)
    _edge_cases(c, index)
    _compare_metrics(c, measured)

    print("METRICS " + json.dumps({
        "max_overflow_pct": max(
            (100.0 * m["overflow_px_x"] / m["poly_w"] for m in measured.values()),
            default=0.0,
        ),
        "min_font_px": min((m["font_px"] for m in measured.values()), default=0),
        "clipped_glyph_count": sum(m["clipped_glyphs"] for m in measured.values()),
        "fit_compromised_count": sum(1 for m in measured.values() if m["fit_compromised"]),
        "fit_failed_count": sum(1 for m in measured.values() if m["fit_failed"]),
    }))
    return c.finish()


def _batching_and_spotfix(c, index) -> None:
    """Two properties no single-region fixture can show.

    Batching is the reason rung 5 costs one extra request on a page of hard
    bubbles rather than one per bubble, and a per-region implementation passes
    every single-region fixture above. The spot-fix path is the reason
    `allow_retranslate` exists at all.
    """
    entry = index["rung5-length.png"]
    page_w, page_h = entry["page_size"]
    box = entry["box"]
    shifted = [box[0], box[1] + page_h, box[2], box[3] + page_h]
    regions = [
        {"id": 1, "polygon": ellipse_points(box), "translation": entry["translation_in"]},
        {"id": 2, "polygon": ellipse_points(shifted), "translation": entry["translation_in"]},
    ]
    src = Image.new("RGB", (page_w, page_h * 2), "white")

    with StubProvider(replies={1: entry["retry_reply"], 2: entry["retry_reply"]},
                      delay=0) as stub:
        client = LLMClient(stub.url, "k", "stub-model")
        _, fits = typeset.typeset_page(regions, src, client=client)
        c.check(all(f.rung == 5 for f in fits),
                f"[batch] both regions reached rung 5 (rungs {[f.rung for f in fits]}) "
                f"-- the batching assert below is vacuous otherwise")
        c.check(stub.chat_requests == 1,
                f"[batch] two rung-5 regions on one page cost {stub.chat_requests} "
                f"request, want exactly 1 -- one per bubble is the defect")
        c.check(sorted(i.get("id") for i in requested_items(stub.last_payload)) == [1, 2],
                "[batch] that one request carried BOTH regions")

    with StubProvider(replies={1: entry["retry_reply"]}, delay=0) as stub:
        client = LLMClient(stub.url, "k", "stub-model")
        _, fits = typeset.typeset_page(
            [regions[0]], src, allow_retranslate=False, client=client
        )
        c.check(stub.chat_requests == 0,
                f"[spotfix] allow_retranslate=False issued {stub.chat_requests} "
                f"requests, want 0 -- the user's text is authoritative on re-render")
        c.check(fits[0].fit_failed,
                "[spotfix] the spot-fix path falls straight to truncation with "
                "fit_failed shown, so the user can shorten it themselves")


def _edge_cases(c, index) -> None:
    """Inputs the six forcing fixtures do not reach, each with a named defect behind it."""
    entry = index["rung4.png"]
    points = ellipse_points(entry["box"])
    words = index["rung5-length.png"]["translation_in"].split()

    # -- empty translations: lost text versus nothing to lose ---------------
    # A whitespace translation with a real source is text loss and is flagged:
    # a provider that omitted this id must not yield a bubble that looks blank.
    img, fit, requests, _ = _typeset(entry, None, translation="   ", source="こんにちは")
    c.check(fit.fit_failed and fit.reason == typeset.REASON_EMPTY,
            f"[empty-translation] real source, empty translation -> fit_failed="
            f"{fit.fit_failed}, reason={fit.reason!r}")
    c.check(requests == 0 and RID in typeset.summary([fit])["fit_failed"],
            f"[empty-translation] no retry for nothing to shorten ({requests} requests), "
            f"and the region is in the summary's fit_failed list")
    c.check(_ink_in_polygon(img, points) == 0, "[empty-translation] nothing drawn")

    # A source not supplied at all is treated as lost text too -- unknown is not
    # evidence of blank.
    _, fit, _, _ = _typeset(entry, None, translation="")
    c.check(fit.fit_failed and fit.reason == typeset.REASON_EMPTY,
            f"[empty-translation] no source supplied -> fit_failed={fit.fit_failed}, "
            f"reason={fit.reason!r}")

    # A region the OCR blank gate emptied had nothing to lose. Flagging it would
    # report every false-positive detection as an incomplete page -- a false
    # alarm on the signal AC-1 exists to make trustworthy.
    _, fit, requests, _ = _typeset(entry, None, translation="", source="")
    c.check(not fit.fit_failed and fit.reason == typeset.REASON_NO_SOURCE and requests == 0,
            f"[blank-source] blank OCR source, empty translation -> fit_failed="
            f"{fit.fit_failed}, reason={fit.reason!r}, {requests} requests -- not a "
            f"failure, and not reported as one")

    # -- rung 4's bleed actually reaching the page --------------------------
    # On an ellipse the narrowest-chord rule keeps even rung-4 ink inside the
    # polygon, so no forcing fixture shows bleed landing on the page. A
    # rectangle's chord IS its edge, so here it does -- and a real non-zero
    # overflow is the only thing an engine report zeroed out cannot agree with.
    rect = [(30, 20), (140, 20), (140, 110), (30, 110)]
    text = " ".join(words[:21])
    img, fits = typeset.typeset_page(
        [{"id": RID, "polygon": rect, "translation": text}], Image.new("RGB", (170, 130), "white")
    )
    fit = fits[0]
    c.check(fit.rung == 4 and fit.fit_compromised,
            f"[rect-bleed] a 110x90 rectangle forced to rung 4 (rung {fit.rung}, "
            f"compromised {fit.fit_compromised}) -- the case below is vacuous otherwise")
    page_ox, _ = _check_page(c, "[rect-bleed]", img, fit, rect)
    c.check(page_ox > 0,
            f"[rect-bleed] bleed reaches the delivered page ({page_ox}px) -- the "
            f"allowance is exercised on a real raster, not only by sabotage")

    # -- concave polygons ---------------------------------------------------
    # Text laid across a notch put 1443 ink pixels outside a U-shaped polygon
    # while the engine reported zero overflow: its chord took the outermost
    # crossings, and its overflow measure compared against the same outer
    # extent. The page measurement here shares neither.
    concave = {
        "U": [(20, 20), (60, 20), (60, 70), (100, 70), (100, 20), (140, 20),
              (140, 150), (20, 150)],
        "H": [(20, 20), (60, 20), (60, 60), (100, 60), (100, 20), (140, 20),
              (140, 150), (100, 150), (100, 110), (60, 110), (60, 150), (20, 150)],
    }
    for label, poly in concave.items():
        for k in (4, 12):
            img, fits = typeset.typeset_page(
                [{"id": RID, "polygon": poly, "translation": " ".join(words[:k])}],
                Image.new("RGB", (170, 180), "white"),
            )
            _check_page(c, f"[concave {label} {k} words]", img, fits[0], poly)

    # -- the event-loop constraint holds on EVERY page ----------------------
    # The guard used to live on the rung-5 path only, so an async caller passed
    # on easy pages and broke in production on the first hard one.
    async def _inside_loop():
        typeset.typeset_page(
            [{"id": RID, "polygon": points, "translation": "Hi"}],
            Image.new("RGB", tuple(entry["page_size"]), "white"),
        )

    try:
        asyncio.run(_inside_loop())
        raised = False
    except typeset.TypesetError:
        raised = True
    c.check(raised, "[async-guard] typeset_page refuses a running event loop on an EASY "
                    "page, not only on one hard enough to reach rung 5")

    # -- monotonicity -------------------------------------------------------
    # Asserted DIRECTLY: scan the floor predicate over every prefix of an
    # overflowing string and require that nothing fits after something failed.
    # A first version compared two capacities instead, and a red-check restoring
    # the old exact-line-count predicate did NOT turn it red -- the two binary
    # searches happened to walk the same path through the holes.
    length = index["rung5-length.png"]
    pts = ellipse_points(length["box"])
    w, h = length["page_size"]
    text = length["translation_in"]
    fits_at = typeset._floor_fits(pts, w, h)
    seq = [bool(fits_at(text[:n])) for n in range(1, len(text) + 1)]
    holes = [n + 1 for n in range(1, len(seq)) if seq[n] and not seq[n - 1]]
    c.check(not holes and seq[0] and not seq[-1],
            f"[monotone] the floor predicate over all {len(text)} prefixes has no fit "
            f"after a miss (holes at prefix lengths {holes[:8]}) -- every search in "
            f"the ladder depends on this")
    base = typeset._capacity(pts, text, w, h)
    longer = typeset._capacity(pts, text + " and then a great many more words besides", w, h)
    c.check(base == longer == sum(seq),
            f"[monotone-cap] capacity {base} equals the scanned boundary {sum(seq)}, "
            f"and appending words leaves it unchanged ({longer})")


def _compare_metrics(c, measured) -> None:
    """Compare against the committed per-fixture drift detector, or rewrite it.

    MT_WRITE_EXPECTED_METRICS=1 rewrites the store. It is an env var and not an
    automatic first-run write: a gate that writes its own store whenever the
    store is missing cannot fail on a clean clone.
    """
    if os.environ.get("MT_WRITE_EXPECTED_METRICS"):
        with open(METRICS_PATH, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(measured, fh, indent=2, sort_keys=True, ensure_ascii=False)
            fh.write("\n")
        print(f"  wrote {METRICS_PATH} from this run (MT_WRITE_EXPECTED_METRICS)")
        return

    if not os.path.exists(METRICS_PATH):
        c.check(False, f"[metrics] {METRICS_PATH} is missing -- regenerate it with "
                       f"MT_WRITE_EXPECTED_METRICS=1 and commit it")
        return

    with open(METRICS_PATH, encoding="utf-8") as fh:
        want = json.load(fh)
    for name in sorted(measured):
        got, exp = measured[name], want.get(name)
        if exp is None:
            c.check(False, f"[metrics] {name} has no committed record")
            continue
        diff = {k: (exp.get(k), got.get(k)) for k in set(exp) | set(got)
                if exp.get(k) != got.get(k)}
        c.check(not diff, f"[metrics] {name} matches the committed drift record"
                          + (f" -- drifted: {diff}" if diff else ""))


run(main)
