"""Shared assert helpers, created where first needed (Phase 1: assert_cer).

Phase 2a adds assert_fit and assert_erased here; Phase 5 adds chrF++.
Each helper lands alongside the check that first calls it.
"""


def cer(got: str, want: str) -> float:
    """Character error rate: edit distance over length of ground truth.

    Empty ground truth with empty output is 0.0; empty truth with non-empty
    output is 1.0 (a hallucination, not a division by zero).
    """
    if not want:
        return 0.0 if not got else 1.0
    prev = list(range(len(want) + 1))
    for i, gc in enumerate(got, 1):
        cur = [i]
        for j, wc in enumerate(want, 1):
            cur.append(min(prev[j] + 1, cur[-1] + 1, prev[j - 1] + (gc != wc)))
        prev = cur
    return prev[-1] / len(want)


def assert_cer(c, got: str, want: str, ceiling: float, label: str) -> float:
    """Record a CER assert on a Checks object; returns the measured rate.

    The RATE, not the pass/fail. Every caller so far also accumulates a set
    mean, and returning a bool made them compute the same edit distance a
    second time to get it -- the pass/fail is one comparison away for anyone
    who wants it, and the rate is not recoverable from a bool at all.
    """
    rate = cer(got, want)
    c.check(
        rate <= ceiling,
        f"{label}: CER {rate:.3f} <= {ceiling} "
        f"(got {got!r:.60}, want {want!r:.60})",
    )
    return rate


assert cer("", "") == 0.0
assert cer("x", "") == 1.0
assert cer("こんにちは", "こんにちは") == 0.0
assert abs(cer("こんばんは", "こんにちは") - 2 / 5) < 1e-9


def assert_fit(c, region: dict, page_h: int, label: str) -> bool:
    """AC-1's fit clause on one regions.json entry, as Phase 2a states it.

    Phase 4 is the first caller: AC-3 is "same as AC-1 for zh and ko", so the
    same five facts are asserted over the zh and ko pages that check_typeset
    holds over its forcing fixtures. `region` is the dict pipeline.render
    wrote back -- rung, font_px and both flags are the ENGINE's report, so a
    caller that wants raster evidence too takes it from check_typeset's
    delivered-page measure; this helper is the record half.
    """
    from sidecar import typeset

    floor = typeset.floor_px(page_h)
    ok = (region.get("font_px", 0) >= floor and region.get("rung", 9) <= 3
          and not region.get("fit_failed") and not region.get("fit_compromised")
          and region.get("typeset") == region.get("translation"))
    c.check(ok, f"{label}: rung {region.get('rung')} <= 3, font {region.get('font_px')}px >= "
                f"floor {floor}, failed={region.get('fit_failed')}, "
                f"compromised={region.get('fit_compromised')}, whole translation rendered")
    return ok


def assert_erased(c, src_gray, cleaned_gray, parts, label: str, drop: float = 0.80) -> float:
    """AC-1's erasure clause: ink inside the region's parts fell by `drop`.

    Necessary and, as check_inpaint says of its own assert 3, not sufficient
    -- a white box satisfies it. It is what a second engine's pages can be
    held to without re-deriving check_inpaint's ring geometry for every
    fixture, and it is red on a page nothing erased. Arrays are gray floats.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    h, w = src_gray.shape
    mask = Image.new("1", (w, h), 0)
    for part in parts:
        ImageDraw.Draw(mask).polygon([tuple(p) for p in part], fill=1)
    m = np.asarray(mask, dtype=bool)
    before = int((src_gray[m] < 128).sum())
    after = int((cleaned_gray[m] < 128).sum())
    fell = 1.0 - after / before if before else 1.0
    c.check(before == 0 or fell >= drop,
            f"{label}: ink inside the parts {before} -> {after} px, fell {fell:.2f} >= {drop}")
    return fell
