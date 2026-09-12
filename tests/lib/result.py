"""The exit-code contract, in one place so seven checks cannot drift.

    0 pass · 1 fail (an assert went red, OR a committed file this checkout
    should already have is missing -- see broken_checkout()) · 2 inconclusive
    (below hardware floor) · 3 skip (a precondition the box cannot meet,
    named in the reason)

run_all.py exits with the worst result, precedence 1 > 2 > 3 > 0.
"""

import sys

from lib.env_local import env_flag

PASS, FAIL, INCONCLUSIVE, SKIP = 0, 1, 2, 3
NAMES = {PASS: "PASS", FAIL: "FAIL", INCONCLUSIVE: "INCONCLUSIVE", SKIP: "SKIP"}


class Checks:
    """Collects numbered asserts so one failure does not hide the rest."""

    def __init__(self, name):
        self.name = name
        self.failures = []
        self.n = 0

    def check(self, ok, description):
        self.n += 1
        status = "ok" if ok else "FAIL"
        print(f"  [{self.n}] {status}: {description}", flush=True)
        if not ok:
            self.failures.append(f"{self.n}: {description}")
        return ok

    def finish(self):
        if self.failures:
            print(f"{self.name}: FAIL ({len(self.failures)}/{self.n})", flush=True)
            return FAIL
        print(f"{self.name}: PASS ({self.n}/{self.n})", flush=True)
        return PASS


def skip(reason, *, live=False):
    """Exit 3 -- unless this is a LIVE skip and MT_REQUIRE_LIVE promotes it.

    Without the promotion an environment that quietly lost its credentials
    reports green forever, which is the failure mode the ratchet exists to
    catch.

    `live` is KEYWORD-ONLY and marks the one thing MT_REQUIRE_LIVE is about:
    a check that could not reach a live endpoint because MT_BASE_URL /
    MT_MODEL are absent. Two of this suite's twenty-three skip sites are
    that (check_probe's module gate, check_id's live half). The other
    twenty-one are a missing fixture, an unavailable weight file, a
    non-Windows host or an absent CUDA device, and promoting THOSE is what
    made the sign-off run unpassable on every box: check_archives runs every
    assert green and then downgrades itself to SKIP because AC-6's .cbr
    clause needs an artifact no free tool can author, and MT_REQUIRE_LIVE
    turned that honest downgrade into a red run.

    MT_REQUIRE_LIVE is read through env_flag, so the MT_REQUIRE_LIVE=0 that
    section E tells CI to set is OFF. It used to be read as a non-empty
    string, which made "0" mean on.

    A precondition that VANISHES is caught by the ratchet instead --
    run_all.last_status() reads PASS -> SKIP per check against the newest
    record in the same env_class that ran it. That clause was unreachable
    when this scoping was first written, and saying so here was wrong until
    last_status() existed; the sign-off's architect review is what found it.
    """
    if live and env_flag("MT_REQUIRE_LIVE"):
        print(f"SKIP promoted to FAIL by MT_REQUIRE_LIVE: {reason}", flush=True)
        return FAIL
    print(f"SKIP: {reason}", flush=True)
    return SKIP


def broken_checkout(reason):
    """Exit 1 -- a file this checkout should already have is missing.

    skip() exists for a precondition the box cannot meet: no CUDA device, no
    live credentials, artwork nobody is allowed to redistribute. A file that
    is committed to git is none of those -- its absence does not describe
    this machine, it describes a checkout that does not match the
    repository (a shallow clone, an interrupted checkout, a fixture deleted
    by hand). MT_REQUIRE_LIVE has no business promoting that, and neither
    does the ratchet's last_status() have any business remembering it as a
    downgrade to reason about: it is simply wrong, on every box, every time,
    and reporting it as a skip would let a broken checkout hide behind the
    same green-with-an-asterisk the suite reserves for honest absence.
    """
    print(f"BROKEN CHECKOUT: {reason}", flush=True)
    return FAIL


def run(main):
    sys.exit(main())
