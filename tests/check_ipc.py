"""Phase 0 -- the host/sidecar IPC contract (US-011). OFFLINE (US-003 stub).

**Why this is not a WebDriver test.** The story asks for the events end to end
through the running app. tauri-driver and msedgedriver are not installed on
this machine (`where tauri-driver` and `where msedgedriver` both return
nothing), so the sanctioned fallback applies: drive the same contract without
a window. src-tauri/tests/host.rs already covers the DECODE half under
`cargo test` -- one line to one event, UTF-8, non-JSON lines forwarded as logs,
per-spawn nonce. That leaves three properties host.rs cannot reach, because
each needs a real sidecar process on the other end of the pipe:

  [1] the spawned binary is TARGET-TRIPLE suffixed. Tauri's sidecar resolution
      appends the triple to the externalBin entry, and the built artifact must
      carry the same name or the app spawns nothing at runtime while building
      perfectly happily.
  [2] the stages arrive in ORDER, asserted BY NAME. A count of three events is
      satisfied by write/ocr/detect, which is a progress bar that runs
      backwards. The order is the contract, so the order is what is read.
  [3] the IPC error path carries the sidecar's OWN status and body. A generic
      "request failed" is the defect this exists to catch -- it sends the user
      hunting their provider for a message the sidecar already explained.
  [4] a non-ASCII item survives a real child-process pipe as UTF-8.
  [4] a non-ASCII item survives the pipe. Phase 0a's probe died printing
      non-Latin-1 text under a cp1252 stdout, and an all-ASCII pipe proves
      nothing. host.rs covers the decode half (bytes -> event); this covers
      the emit half (emit -> bytes) through a real child process.

Run from the repo root:
    uv run --project sidecar python tests/check_ipc.py
"""

from __future__ import annotations

import json
import os
import asyncio
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import Checks, broken_checkout, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402

TRIPLE = "x86_64-pc-windows-msvc"
CONF = os.path.join(ROOT, "src-tauri", "tauri.conf.json")
LIB_RS = os.path.join(ROOT, "src-tauri", "src", "lib.rs")
SMOKE = os.path.join(ROOT, "fixtures", "smoke", "tategaki_01.png")
CBZ = os.path.join(ROOT, "fixtures", "archives", "benign.cbz")
CBZ_PAGES = 3  # gen_fixtures ARCHIVE_PAGES; the count the bar must be told

# By name and in this order. The three the story names, in the order run_page
# drives them; the stages between are allowed and ignored, so adding a stage
# later does not break this, but reordering these three does.
REQUIRED_ORDER = ["detect", "ocr", "write"]


def emitted_stages(dest: str) -> tuple[list[str], str]:
    """Run one page as a CHILD PROCESS and read the stages off its stdout.

    In-process would prove nothing about the pipe. The events only exist as
    stdout lines, and it is the line-by-line flush behaviour that the host
    depends on -- so this reads the same bytes Tauri would read.
    """
    script = (
        "import sys, json; sys.path.insert(0, r'%s');"
        "from sidecar import pipeline;"
        "rec = pipeline.run_page(r'%s', r'%s', 1, None);"
        "pipeline.write_regions(rec, r'%s')" % (ROOT, SMOKE, dest, dest)
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT, capture_output=True, timeout=300,
        encoding="utf-8", errors="replace",
    )
    stages = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue  # a log line, not progress -- host.rs covers that split
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "stage" in rec and "pct" in rec:
            stages.append(rec["stage"])
    return stages, (r.stderr or "")[-600:]


def item_totals(dest: str) -> tuple[set[int], int, str]:
    """Run a 3-page .cbz as a CHILD PROCESS: the `total` on its lines, and the
    pages they covered. Its own cache directory, so the run is a real one and
    not a cache hit from another check's tree."""
    cache_dir = os.path.join(dest, "cache")
    os.makedirs(dest, exist_ok=True)
    script = (
        "import sys; sys.path.insert(0, r'%s');"
        "from sidecar import pipeline;"
        "pipeline.run_item(r'%s', r'%s', 'ipc-total', 'benign.cbz', None)"
        % (ROOT, CBZ, dest)
    )
    r = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT, capture_output=True, timeout=600,
        encoding="utf-8", errors="replace",
        env=dict(os.environ, MT_CACHE_DIR=cache_dir, PYTHONIOENCODING="utf-8"),
    )
    totals, pages = set(), set()
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "stage" in rec and "pct" in rec:
            totals.add(rec.get("total"))
            pages.add(rec.get("page"))
    return totals, len(pages), (r.stderr or "")[-600:]


def main():
    if sys.platform != "win32":
        return skip(f"Windows-only: the spawn name is {TRIPLE}")
    if not os.path.exists(CONF):
        return broken_checkout(f"src-tauri/tauri.conf.json missing: {CONF}")
    if not os.path.exists(SMOKE):
        # Committed AND generated, like benign.cbz: gen_fixtures.py writes it
        # and git tracks it. Its absence is therefore a checkout that does not
        # match the repository, not a clone that has yet to generate -- the
        # generated-only case is check_fixtures_deterministic's to report.
        return broken_checkout(f"smoke fixture missing: {SMOKE} -- it is committed; "
                               f"tests/gen_fixtures.py also regenerates it")

    c = Checks("check_ipc")

    # -- [1] the spawn name ------------------------------------------------
    with open(CONF, encoding="utf-8") as fh:
        conf = json.load(fh)
    ext = conf.get("bundle", {}).get("externalBin") or conf.get("tauri", {}).get(
        "bundle", {}
    ).get("externalBin", [])
    c.check(bool(ext), f"tauri.conf.json declares an externalBin ({ext})")

    # Tauri appends the triple itself, so the CONF entry is correctly unsuffixed
    # -- asserting a suffix here would be asserting a bug. What has to line up
    # is the built artifact, whose name is the conf entry PLUS the triple.
    base = os.path.basename(ext[0]) if ext else ""
    # dist/sidecar/: the one-dir folder check_package builds (its exe beside _internal/).
    built = os.path.join(ROOT, "build", "dist", "sidecar", f"{base}-{TRIPLE}.exe")
    c.check(
        base == "sidecar",
        f"the externalBin entry is the unsuffixed base name ({base!r}) -- "
        f"Tauri appends the triple at build time",
    )
    c.check(
        os.path.exists(built),
        f"and the built artifact carries the triple: {os.path.basename(built)} "
        f"({'present' if os.path.exists(built) else 'MISSING -- the app would spawn nothing at runtime'})",
    )

    # -- [2] the stages, in order, by name ---------------------------------
    dest = os.path.join(ROOT, "build", "work", "ipc-out")
    os.makedirs(dest, exist_ok=True)
    stages, err = emitted_stages(dest)
    c.check(bool(stages), f"the sidecar emits progress lines on stdout ({len(stages)} seen; stderr: {err[-200:]})")

    present = [s for s in stages if s in REQUIRED_ORDER]
    c.check(
        present == REQUIRED_ORDER,
        f"detect -> ocr -> write arrive IN THAT ORDER, by name "
        f"(got {present}; full stream {stages})",
    )

    # -- [5] an ITEM's lines carry its page count --------------------------
    # The chapter bar needs an end to run to. Without `total` the UI can only
    # count pages up from nothing, which is what the single-chapter panel did:
    # a per-page bar and a counter, and no way to see how much of the chapter
    # was left. Read off a real child process, like the stages above.
    totals, pages_seen, err = item_totals(os.path.join(ROOT, "build", "work", "ipc-item"))
    c.check(
        pages_seen == CBZ_PAGES and totals == {CBZ_PAGES},
        f"every progress line of a {CBZ_PAGES}-page .cbz carries total={CBZ_PAGES} "
        f"(saw totals {sorted(totals)} over {pages_seen} pages; stderr: {err[-200:]})",
    )

    # -- [4] a NON-ASCII item survives the pipe, end to end ---------------
    # Phase 0a's probe died printing raw non-Latin-1 text under a cp1252
    # stdout. emit is immune BY CONSTRUCTION: json.dumps escapes to ASCII
    # by default, so no stdout encoding can mangle the bytes -- and this
    # pins that property rather than trusting it. host.rs covers decode
    # (bytes -> event); this covers emit (emit -> bytes).
    script = (
        "import sys; sys.path.insert(0, r'%s');"
        "from sidecar import pipeline;"
        "pipeline.emit('ocr', '第1話.png', 1, 25)"
        % ROOT
    )
    uni = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT, capture_output=True, timeout=120,
        env=dict(os.environ, PYTHONIOENCODING="utf-8"),
    )
    c.check(
        uni.returncode == 0,
        f"the emit run exits 0 (stderr: {(uni.stderr or b'')[-300:]!r})",
    )
    raw = uni.stdout
    rec = None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        c.check(False, f"the pipe bytes decode as UTF-8 ({e})")
    else:
        c.check(True, "the pipe bytes decode as UTF-8")
        for ln in text.splitlines():
            ln = ln.strip()
            if ln.startswith("{"):
                try:
                    rec = json.loads(ln)
                    break
                except json.JSONDecodeError:
                    continue
    c.check(
        rec is not None and rec.get("item") == "第1話.png",
        f"a non-ASCII item round-trips through the pipe "
        f"(got {rec.get('item')!r} decoded from {raw[:120]!r})" if rec else
        "a non-ASCII item round-trips through the pipe (no JSON line decoded)",
    )

    # -- [3] the error path carries the sidecar's own status AND body ------
    # Driven, not read. StubProvider(status=500) returns a canned HTML body;
    # a client that replaced it with "request failed" is the defect, and the
    # only way to see that is to make the call and inspect what comes back.
    from sidecar.llm import LLMClient, ProviderError, Region

    with StubProvider(status=500) as stub:
        client = LLMClient(stub.url, "", "stub-model")
        try:
            asyncio.run(client.translate_page([Region(id=1, text="テスト", polygon=[])]))
            err = None
        except ProviderError as e:
            err = e

    c.check(err is not None, "a 500 from the provider raises rather than returning silently")
    if err is None:
        return c.finish()

    c.check(err.status == 500, f"the error carries the provider's OWN status ({err.status}, not 0 or a generic code)")
    c.check(
        bool(err.body.strip()) and "request failed" not in err.body.lower(),
        f"and the provider's OWN body, verbatim ({len(err.body)} bytes: {err.body[:80]!r})",
    )

    # status 0 is the sentinel for "never reached the provider" and must be
    # distinguishable from any real HTTP status the provider returned.
    dead = LLMClient("http://127.0.0.1:1/v1", "", "stub-model")
    try:
        asyncio.run(dead.translate_page([Region(id=1, text="x", polygon=[])]))
        local = None
    except ProviderError as e:
        local = e
    c.check(
        local is not None and local.status == 0,
        f"an unreachable provider is status 0, distinct from a real one "
        f"({getattr(local, 'status', 'no error raised')})",
    )

    return c.finish()


run(main)
