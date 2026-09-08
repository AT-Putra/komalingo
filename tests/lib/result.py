"""The exit-code contract, in one place so seven checks cannot drift.

    0 pass · 1 fail · 2 inconclusive (below hardware floor) · 3 skip (a required
    env var is absent and MT_REQUIRE_LIVE is unset)

run_all.py exits with the worst result, precedence 1 > 2 > 3 > 0.
"""

import os
import sys

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


def skip(reason):
    """Exit 3 -- unless MT_REQUIRE_LIVE promotes every skip to a hard failure.

    Without the promotion an environment that quietly lost its credentials
    reports green forever, which is the failure mode the ratchet exists to
    catch.
    """
    if os.environ.get("MT_REQUIRE_LIVE"):
        print(f"SKIP promoted to FAIL by MT_REQUIRE_LIVE: {reason}", flush=True)
        return FAIL
    print(f"SKIP: {reason}", flush=True)
    return SKIP


def run(main):
    sys.exit(main())
