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
