#!/usr/bin/env python3
"""Phase 0a gate: two regenerations from an empty tree are byte-identical.

    uv run --project sidecar python tests/check_fixtures_deterministic.py

Exit-code contract (uniform across every check in this repo):
    0  pass
    1  fail        -- a file differed between runs, or a run crashed
    2  inconclusive -- below the declared hardware floor (never here; this
                       check is pure I/O and has no floor)
    3  skip        -- a required env var is absent and MT_REQUIRE_LIVE is
                      unset (never here; this check is fully offline)

Only 0 and 1 are reachable. The 2/3 rows are stated so the contract is
visible in every check, not because this one can produce them.

Not destructive: the tree is deleted, then regenerated twice, so a populated
`fixtures/smoke/` and `fixtures/bubbles/` is left behind either way.
"""

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"
SUBDIRS = ("smoke", "bubbles", "cbz")
GENERATOR = ROOT / "tests" / "gen_fixtures.py"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot():
    """Relative-path -> sha256 for everything under the generated subdirs."""
    out = {}
    for sub in SUBDIRS:
        for p in sorted((FIXTURES / sub).rglob("*")):
            if p.is_file():
                out[p.relative_to(FIXTURES).as_posix()] = sha256(p)
    return out


def generate(label):
    for sub in SUBDIRS:
        shutil.rmtree(FIXTURES / sub, ignore_errors=True)
    r = subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT,
                       capture_output=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"FAIL: generator exited {r.returncode} on run {label}")
        print(r.stdout, r.stderr, sep="\n")
        return None
    return snapshot()


def main():
    if not GENERATOR.exists():
        print(f"FAIL: {GENERATOR} does not exist")
        return 1

    first = generate("1")
    if first is None:
        return 1
    second = generate("2")
    if second is None:
        return 1

    if not first:
        print("FAIL: run 1 produced no files at all")
        return 1

    added = sorted(set(second) - set(first))
    removed = sorted(set(first) - set(second))
    changed = sorted(k for k in first.keys() & second.keys()
                     if first[k] != second[k])

    for k in sorted(first):
        mark = "MATCH" if second.get(k) == first[k] else "DIFFER"
        print(f"  {mark:6} {first[k][:16]}  {k}")

    if added or removed or changed:
        for k in removed:
            print(f"FAIL: {k} present in run 1, absent in run 2")
        for k in added:
            print(f"FAIL: {k} absent in run 1, present in run 2")
        for k in changed:
            print(f"FAIL: {k} hash {first[k][:16]} -> {second[k][:16]}")
        return 1

    print(f"PASS: {len(first)} files byte-identical across two regenerations "
          f"from an empty tree")
    return 0


if __name__ == "__main__":
    sys.exit(main())
