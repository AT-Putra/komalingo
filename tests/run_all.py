"""Phase 0 -- the aggregate regression runner (US-013).

Discovers tests/check_*.py, runs them in phase order, prints one table, and
exits with the WORST result under the shared contract:

    0 pass · 1 fail · 2 inconclusive · 3 skip        precedence 1 > 2 > 3 > 0

Two things here are load-bearing.

**A wrong interpreter must fail loudly, not quietly.** The system Python has no
PIL. Run under it and every check that opens an image exits 1 with
ModuleNotFoundError, which reads as a determinism or imaging regression and is
not one -- Phase 0a lost time to exactly that. So the interpreter is asserted
BEFORE any check runs, and a miss aborts with its own message rather than
producing a table of misattributed failures.

**A check that silently went from pass to skip is a regression.** Fixtures
vanish, an env var gets dropped, and the run still prints green because a skip
is not a failure. That is why every run appends its per-check status to
tests/baseline.json and compares against the last comparable record.

Comparison is scoped to the newest prior record with an IDENTICAL `skipped`
set. Without that scoping a developer's `full` record (real-panel fixtures
present) and CI's `synthetic` record differ by several legitimately-skipped
checks, and the ratchet reads that as a pass-to-skip regression. When no
comparable record exists -- a clean clone, or a new environment class -- this
exits 3 with the reason `no baseline record for env_class=<x>` and writes the
first record. A floor that silently never fires is the same cannot-go-red
defect the store was added to remove.

Run from the repo root:
    uv run --project sidecar python tests/run_all.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(ROOT, "tests")
BASELINE = os.path.join(TESTS, "baseline.json")

PASS, FAIL, INCONCLUSIVE, SKIP = 0, 1, 2, 3
NAMES = {PASS: "PASS", FAIL: "FAIL", INCONCLUSIVE: "INCONCLUSIVE", SKIP: "SKIP"}

# Worst-first. `max` over this ranking is the exit code: 1 beats 2 beats 3
# beats 0, which is NOT numeric order -- 1 is the largest by rank, not value.
RANK = {FAIL: 3, INCONCLUSIVE: 2, SKIP: 1, PASS: 0}

# Which way is WORSE for each baseline metric -- the metric ratchet reads this.
# A metric in neither set is recorded but never ratcheted, which is a decision
# to make explicitly here rather than by forgetting to list it.
#
# fit_compromised_count and fit_failed_count are deliberately in NEITHER set.
# They count outcomes over a fixed set of forcing fixtures, so their value is
# decided by which fixtures exist, not by how good the engine is: adding a
# legitimate rung-5 fixture would read 4 -> 5 as a regression, while a forcing
# fixture that silently stopped forcing would read 4 -> 3 as an improvement.
# Both directions are wrong. The per-fixture asserts in check_typeset, and its
# drift detector, are what guard those numbers.
#
# id_chrf is recorded and NOT ratcheted, for a third reason: it is a live
# model's prose scored against forty lines, and two runs of the same model on
# the same lines came back 0.6596 and 0.6386 (Phase 5). METRIC_EPS is for
# float noise, and a ratchet that reads a 0.02 swing in a language model as a
# regression goes red on the weather. check_id's own floor (>= 0.45) is the
# gate; the record is the history. id_function_word_hits IS ratcheted -- it
# is a count that should be zero and stay zero.
#
# archive_peak_rss_mb is in NEITHER set for the same class of reason: it is a
# whole-process RSS reading taken on whatever box happens to run it, it moves
# with the interpreter build and the allocator, and a ratchet that reads a few
# MB of drift as a memory regression goes red on the weather. check_archives'
# own 400MB gate is what holds AC-12; the record is the history.
# archive_hostile_rejected IS ratcheted -- it counts AC-11 rules observed
# firing on a real fixture, and that count going down means a rule stopped
# working or a fixture stopped being hostile.
LOWER_IS_BETTER = {
    "max_overflow_pct",
    "clipped_glyph_count",
    "mean_cer",
    "ring_assert_skipped",
    "cjk_mean_cer",
    "id_function_word_hits",
}
HIGHER_IS_BETTER = {"min_font_px", "exact_match", "cjk_exact_match",
                    "archive_hostile_rejected"}
METRIC_EPS = 1e-9  # float noise, not tolerance: any real movement counts

# Phase order, not alphabetical: a foundational failure should be read first.
# Names not listed here still run, after these, sorted -- a check added later
# is never silently dropped just because nobody updated this list.
PHASE_ORDER = [
    "check_fixtures_deterministic",
    "check_atomic",
    "check_imaging",
    "check_provider",
    "check_models",
    "check_pipeline",
    "check_api",
    "check_settings",
    "check_package",
    "check_ipc",
    "check_probe",
    "check_tategaki",
    "check_typeset",
    "check_inpaint",
    "check_spotfix",
    "check_group",
    "check_cjk",
    "check_id",
    "check_archives",
]

# Real-panel fixtures are git-ignored. Their presence is what separates a
# developer's environment from CI's, and it changes which checks can run.
# This must name the directory the panels are ACTUALLY reassembled into --
# tests/gen_tategaki_panels.py writes here. It pointed at fixtures/panels/,
# which no phase ever created, so every run recorded env_class=synthetic and
# the distinction the ratchet buckets on was decorative.
REAL_PANELS = os.path.join(ROOT, "fixtures", "tategaki", "panels")


def env_class() -> str:
    return "full" if os.path.isdir(REAL_PANELS) and os.listdir(REAL_PANELS) else "synthetic"


def assert_interpreter() -> None:
    """Abort loudly on an interpreter that cannot run the checks.

    This is deliberately not a check result. A missing PIL is not a failing
    check, it is a runner invoked the wrong way, and reporting it as eleven
    red checks sends the reader looking in eleven wrong places.
    """
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.stderr.write(
            "run_all.py: wrong interpreter -- PIL is not importable.\n"
            f"  running under: {sys.executable}\n"
            "  run it as:     uv run --project sidecar python tests/run_all.py\n"
            "Aborting rather than reporting this as check failures.\n"
        )
        raise SystemExit(FAIL)


def discover() -> list[str]:
    """check_*.py in phase order, then anything unlisted, sorted."""
    found = {
        f[:-3]
        for f in os.listdir(TESTS)
        if f.startswith("check_") and f.endswith(".py")
    }
    ordered = [n for n in PHASE_ORDER if n in found]
    return ordered + sorted(found - set(ordered))


def harvest_metrics(stdout: str) -> dict:
    """Read a check's `METRICS {...}` line, if it printed one.

    A named channel, not a parse of the assert prose: the asserts are worded
    for a human reader and get reworded, and a ratchet that scrapes them goes
    quietly blind the first time someone improves the wording.
    """
    for line in reversed((stdout or "").splitlines()):
        if line.startswith("METRICS "):
            try:
                return json.loads(line[len("METRICS "):])
            except json.JSONDecodeError:
                print(f"      ignoring unparseable METRICS line: {line[:80]}")
            return {}
    return {}


def run_check(name: str) -> tuple[int, float, str]:
    start = time.time()
    # text=True decodes the child with the LOCALE codec, which on Windows is
    # cp1252. Any check that prints Japanese -- every OCR check from Phase 1
    # on -- then kills subprocess's reader thread with UnicodeDecodeError, and
    # subprocess SWALLOWS it: returncode arrives intact and r.stdout is
    # silently empty. The check reports PASS with no output, its METRICS line
    # never reaches the baseline, and on a FAIL the reason never prints
    # either. Decode as UTF-8 and never raise; force the child to emit it.
    r = subprocess.run(
        [sys.executable, os.path.join(TESTS, name + ".py")],
        cwd=ROOT, capture_output=True,
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    elapsed = time.time() - start
    tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
    print(f"  {name:<32} {NAMES.get(r.returncode, r.returncode):<12} {elapsed:6.1f}s  {tail[0][:70]}")
    if r.returncode == FAIL:
        for line in (r.stdout or "").splitlines():
            if "FAIL" in line:
                print(f"      {line.strip()}")
        if r.stderr.strip():
            print(f"      stderr: {r.stderr.strip()[-300:]}")
    return r.returncode, elapsed, r.stdout or ""


def load_records() -> list[dict]:
    if not os.path.exists(BASELINE):
        return []
    try:
        with open(BASELINE, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as e:
        # A corrupt store must not read as "no prior record", which would
        # silently pass the ratchet. Say so and treat it as a failure.
        print(f"\nbaseline.json is unreadable ({e}) -- refusing to treat that as no history")
        raise SystemExit(FAIL)
    return data if isinstance(data, list) else [data]


def append_record(record: dict) -> None:
    records = load_records() if os.path.exists(BASELINE) else []
    records.append(record)
    with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def metric_regressions(now_metrics: dict, last_metrics: dict) -> list[str]:
    """Every metric that moved the WRONG way against the last comparable record.

    A function rather than a loop inside main() so it can be driven directly:
    a ratchet that has only ever been exercised by a run in which nothing
    regressed has never been seen to fire. A metric the previous record never
    measured (None) has no floor yet and is skipped, not failed.
    """
    out = []
    for key, now in now_metrics.items():
        was = last_metrics.get(key)
        if was is None or now is None:
            continue
        if key in LOWER_IS_BETTER and now > was + METRIC_EPS:
            out.append(f"metric {key}: {was} -> {now} (lower is better)")
        elif key in HIGHER_IS_BETTER and now < was - METRIC_EPS:
            out.append(f"metric {key}: {was} -> {now} (higher is better)")
    return out


def main() -> int:
    assert_interpreter()

    checks = discover()
    print(f"run_all: {len(checks)} checks, env_class={env_class()}, {sys.executable}\n")

    results: dict[str, int] = {}
    measured: dict = {}
    for name in checks:
        results[name], _, stdout = run_check(name)
        measured.update(harvest_metrics(stdout))

    # A code outside the 0/1/2/3 contract is not a check RESULT -- it is a
    # child that crashed or was killed. Windows reports a Ctrl-C'd child as
    # 3221225794 (0xC000013A, STATUS_CONTROL_C_EXIT), and this runner used to
    # store that integer as the check's status and append the record anyway.
    # Two such records reached tests/baseline.json during Phase 2a and had to
    # be removed by hand: they claimed PASS for checks that never finished, and
    # the ratchet compares the next run against exactly those claims.
    #
    # An interrupted run has measured nothing, so it writes nothing. Refusing
    # here is not lost information -- the information was never collected.
    offcontract = {n: c for n, c in results.items() if c not in NAMES}
    if offcontract:
        print("\n  ABORTED -- these checks did not return a result code:")
        for name, code in sorted(offcontract.items()):
            print(f"    {name}: exit {code}")
        print("  No baseline record written: an interrupted run has measured nothing.")
        return FAIL

    worst = max(results.values(), key=lambda code: RANK.get(code, RANK[FAIL])) if results else PASS
    skipped = sorted(n for n, code in results.items() if code == SKIP)

    print(f"\n  {'-' * 60}")
    for code in (FAIL, INCONCLUSIVE, SKIP, PASS):
        names = sorted(n for n, c in results.items() if c == code)
        if names:
            print(f"  {NAMES[code]:<12} {len(names):>2}  {', '.join(names)}")
    print(f"  {'-' * 60}\n  run_all: {NAMES.get(worst, worst)}")

    record = {
        "phase": "6",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env_class": env_class(),
        "skipped": skipped,
        "checks": {n: NAMES.get(c, str(c)) for n, c in sorted(results.items())},
        # Phase 2a fills the typeset half of this schema for the first time:
        # check_typeset prints max_overflow_pct, min_font_px,
        # clipped_glyph_count, fit_compromised_count and fit_failed_count, and
        # check_tategaki has printed mean_cer/exact_match since Phase 1. A key
        # left null here means no check claimed it this run -- which is a
        # reportable fact, not a default.
        "metrics": {
            "max_overflow_pct": None,
            "min_font_px": None,
            "clipped_glyph_count": None,
            "fit_compromised_count": None,
            "fit_failed_count": None,
            "mean_cer": None,
            "exact_match": None,
            # Phase 2a: check_inpaint's assert 1 does not run on a region whose
            # ring is mostly border ink. The count is carried HERE as well as
            # printed, because an unannounced skip is the same defect class as
            # an assert that cannot fail -- and a skip that is only ever
            # printed is unannounced to everyone reading the record later.
            "ring_assert_skipped": None,
            # Phase 4: check_cjk's Phase 1 bars over the zh and ko pages, one
            # number each across both languages. AC-3 is "same as AC-1 for zh
            # and ko"; a record that could not show the second engine's floor
            # would let it drift with nothing going red.
            "cjk_mean_cer": None,
            "cjk_exact_match": None,
            # Phase 5: check_id's live half. Null on a run without MT_BASE_URL
            # and MT_MODEL, where check_id skips; the skip set then differs
            # from a live run's and the two are never compared -- which is
            # the scoping the store was given in Phase 0.
            "id_chrf": None,
            "id_function_word_hits": None,
            # Phase 6: check_archives. peak_rss_mb is the AC-12 measurement,
            # recorded and NOT ratcheted -- see the comment above
            # LOWER_IS_BETTER. hostile_rejected counts the AC-11 rules seen
            # firing on a real fixture, and IS ratcheted: that count going down
            # means a rule stopped working or a fixture stopped being hostile,
            # and neither is something a green run should be able to hide.
            "archive_peak_rss_mb": None,
            "archive_hostile_rejected": None,
        },
    }
    # Only keys the schema already names: a check cannot invent a baseline
    # column by printing one.
    for key in record["metrics"]:
        if key in measured:
            record["metrics"][key] = measured[key]

    # -- the ratchet ------------------------------------------------------
    ec = env_class()
    prior = [r for r in load_records()
             if r.get("env_class") == ec and sorted(r.get("skipped", [])) == skipped]

    if not prior:
        append_record(record)
        print(f"\n  no baseline record for env_class={ec} with this skip set -- wrote the first one")
        # The ratchet's own verdict is 3, but it must not MASK a red check.
        # Returning SKIP unconditionally here would report a failing run as
        # exit 3 on any clean clone -- the first run is exactly when a real
        # failure is most likely and least excusable to hide.
        return max(worst, SKIP, key=lambda code: RANK.get(code, RANK[FAIL]))

    last = prior[-1]
    regressions = []
    for name, status in record["checks"].items():
        was = last["checks"].get(name)
        if was == "PASS" and status != "PASS":
            regressions.append(f"{name}: PASS -> {status}")

    # The build order's clause is "every METRIC no worse than the last record",
    # and until Phase 2a only check STATUS was compared -- max_overflow_pct could
    # have doubled with every check still green. A metric the previous record
    # never measured (None) has no floor yet and is skipped, not failed.
    #
    # A deliberate trade is allowed, and must say so: MT_ACCEPT_METRIC_REGRESSION
    # carries the one-line reason into the record. A silent one is a regression.
    accepted = os.environ.get("MT_ACCEPT_METRIC_REGRESSION", "").strip()
    regressions += metric_regressions(record["metrics"], last.get("metrics") or {})
    if regressions and accepted and all(r.startswith("metric ") for r in regressions):
        record["accepted_regression"] = {"reason": accepted, "metrics": regressions}
        print(f"\n  metric regression ACCEPTED ({accepted}):")
        for r in regressions:
            print(f"    {r}")
        regressions = []

    append_record(record)
    if regressions:
        print(f"\n  REGRESSION against {last['timestamp']}:")
        for r in regressions:
            print(f"    {r}")
        return FAIL

    print(f"\n  no regression against {last['timestamp']} ({len(last['checks'])} checks)")
    return worst


if __name__ == "__main__":
    sys.exit(main())
