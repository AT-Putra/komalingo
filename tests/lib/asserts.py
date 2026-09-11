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


# -- Phase 5: chrF++ and the English function-word gate (AC-4) --------------

# Closed-class English: exactly what a stub that splices Indonesian glossary
# terms into English sentences cannot remove, and exactly what correct
# Indonesian never contains -- its closed class (yang, itu, dan, ke, dari,
# dengan, tidak) shares nothing with this list. A general English wordlist
# would false-fail on loanwords (data, film, bank, radio, hotel, video); these
# words have no Indonesian homograph. Whole tokens, case-insensitive. One
# known collision: "as" is also the abbreviation AS (Amerika Serikat); a
# reference line that names it lists "AS" in its per-line allowlist.
ENGLISH_FUNCTION_WORDS = frozenset("""
the a an is are was were be been being am of and to in that it with for from
this these those has have had will would shall should not but they their them
he she his her him we our us you your i my me at on by or if as so than then
there here what which who whom whose when where why how do does did can could
may might must into about because while until unless although though after
before over under between through during without within against
""".split())


def english_function_words(text: str, allow=()) -> list[str]:
    """The English function words in `text`, as whole tokens, in order."""
    import re

    allowed = {a.lower() for a in allow}
    tokens = re.findall(r"[A-Za-z]+", text)
    return [t for t in tokens if t.lower() in ENGLISH_FUNCTION_WORDS and t.lower() not in allowed]


def _ngrams(items, n: int) -> dict:
    out: dict = {}
    for i in range(len(items) - n + 1):
        g = items[i:i + n]
        out[g] = out.get(g, 0) + 1
    return out


def _words(sent: str) -> tuple:
    """chrF++'s word tokens: whitespace split, one leading or trailing ASCII
    punctuation mark split off as its own token (Popovic's chrF++.py, and
    sacrebleu's _remove_punctuation, issue #124 behaviour included)."""
    import string

    out = []
    for w in sent.split():
        if len(w) > 1 and w[-1] in string.punctuation:
            out += [w[:-1], w[-1]]
        elif len(w) > 1 and w[0] in string.punctuation:
            out += [w[0], w[1:]]
        else:
            out.append(w)
    return tuple(out)


def chrf_pp(hyps, refs, n_char: int = 6, n_word: int = 2, beta: float = 2.0) -> float:
    """Corpus chrF++ (Popovic 2017) over the stdlib, sacrebleu's arithmetic:
    character 1..6-grams on the text with whitespace removed plus word
    1..2-grams; precision and recall averaged over the orders both sides
    have n-grams for (the effective order); F with beta=2. Cross-checked
    against sacrebleu's CHRF(char_order=6, word_order=2, beta=2) -- see
    progress.txt, Phase 5 -- rather than depending on it: forty lines of
    arithmetic do not justify a package. `hyps` and `refs` are parallel lists
    of strings; a single string on each side is one sentence.
    """
    if isinstance(hyps, str):
        hyps, refs = [hyps], [refs]
    orders = [("c", n) for n in range(1, n_char + 1)] + [("w", n) for n in range(1, n_word + 1)]
    match = {o: 0 for o in orders}
    hyp_total = {o: 0 for o in orders}
    ref_total = {o: 0 for o in orders}
    for hyp, ref in zip(hyps, refs):
        for kind, n in orders:
            h = tuple(hyp.replace(" ", "")) if kind == "c" else _words(hyp)
            r = tuple(ref.replace(" ", "")) if kind == "c" else _words(ref)
            hg, rg = _ngrams(h, n), _ngrams(r, n)
            match[(kind, n)] += sum(min(c, rg.get(g, 0)) for g, c in hg.items())
            hyp_total[(kind, n)] += sum(hg.values())
            ref_total[(kind, n)] += sum(rg.values())
    live = [o for o in orders if hyp_total[o] and ref_total[o]]
    if not live:
        return 0.0
    p = sum(match[o] / hyp_total[o] for o in live) / len(live)
    r = sum(match[o] / ref_total[o] for o in live) / len(live)
    if p == 0 or r == 0:
        return 0.0
    return (1 + beta * beta) * p * r / (beta * beta * p + r)


assert chrf_pp("Tanaka-san, pulang bareng, yuk.", "Tanaka-san, pulang bareng, yuk.") == 1.0
assert chrf_pp("", "Tanaka-san, pulang bareng, yuk.") == 0.0
assert english_function_words("the cat") == ["the"]
assert english_function_words("data film bank radio hotel video") == []
assert english_function_words("Main game pakai VR itu mewah banget, ya.") == []
assert english_function_words("Go to the guild", allow=["the"]) == ["to"]
