"""Phase 0 -- the packaged sidecar (US-010). OFFLINE (uses the US-003 stub).

What this file exists to catch: a one-file build that starts, answers
/api/health with a 200, and is completely broken.

PyInstaller resolves imports statically. torch and onnxruntime resolve theirs at
first USE -- `torch.load`, an ONNX session, a lazily imported backend -- which
happens nowhere near startup. So a health poll proves the bootloader unpacked
and uvicorn came up, and nothing else. The build can pass that and still die on
the first real page. Hence assert [4]: a FULL translate through the launched
exe, with four counters read back from regions.json, because "an output file
appeared" is satisfied by an empty file too.

The LLM client points at the US-003 stub, never the live endpoint. This check
is offline by contract.

Four things about the HARNESS are load-bearing, because each one of them once
turned a diagnosable failure into an undiagnosable one:

  * The exe's stdout is drained by a thread from the first byte. An undrained
    PIPE fills at roughly 64 KB, the child blocks mid-write while this process
    blocks reading its socket, and the traceback that would have named the
    defect sits unread in the full pipe forever.
  * Response bodies are read under a wall-clock budget and never raise. An
    unguarded read of an error body raises from inside an except clause,
    escapes run(), and replaces every remaining check with a stack trace that
    names urllib rather than the bug.
  * No packaged sidecar outlives the run. A one-file exe is a bootloader plus
    an app CHILD; reaping only the bootloader leaves the child holding
    build/dist/sidecar-*.exe open, and the NEXT build then dies with WinError 5
    and reports it as a build failure with an empty reason.
  * EVERY subprocess here names its encoding. text=True decodes with the ANSI
    locale codec while the tools we shell out to write the console OEM one, and
    subprocess SWALLOWS a reader thread that dies decoding -- returncode
    arrives intact and the stream comes back empty. That empty string is not
    an error, it is a legal-looking answer, which is how sidecar_pids() once
    reported "leaked pids: []" with orphans alive. The rule is narrower than
    "name the encoding": a decode failure and a true negative must never
    produce the same value. This bullet is counted here because the fourth
    such call in this file went unfixed for a while beside three that were.

Run from the repo root:
    uv run --project sidecar python tests/check_package.py
    uv run --project sidecar python tests/check_package.py --gpu
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.childio import captured, launch_drained  # noqa: E402
from lib.httpread import read_bounded  # noqa: E402
from lib.result import Checks, broken_checkout, run, skip  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402
from sidecar.models import select_provider  # noqa: E402

EXE_NAME = "sidecar-x86_64-pc-windows-msvc.exe"
DIST = os.path.join(ROOT, "build", "dist")
EXE = os.path.join(DIST, EXE_NAME)
SPEC = os.path.join(ROOT, "build", "sidecar.spec")
MANIFEST = os.path.join(ROOT, "build", "longpath.manifest")
SMOKE = os.path.join(ROOT, "fixtures", "smoke", "tategaki_01.png")

HEALTH_TIMEOUT = 30.0  # cold start budget; past this we fall back to one-dir
SHUTDOWN_TIMEOUT = 5.0
BODY_TIMEOUT = 15.0  # wall-clock budget for reading a response body
TWO_GB = 2 * 1024**3


# -- locating the SDK ------------------------------------------------------
# mt.exe lives under a version-numbered directory that differs per machine
# (10.0.26100.0 here). Hardcoding that path makes this check pass on exactly
# one computer, so it is resolved at runtime, registry first.


def kits_root() -> str | None:
    try:
        import winreg
    except ImportError:
        return None
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows Kits\Installed Roots",
                0,
                winreg.KEY_READ | view,
            )
            with key:
                return winreg.QueryValueEx(key, "KitsRoot10")[0]
        except OSError:
            continue
    return None


def find_mt() -> str | None:
    """mt.exe, via the registry, then vswhere, then PATH."""
    root = kits_root()
    if root:
        found = glob.glob(os.path.join(root, "bin", "*", "x64", "mt.exe"))
        if found:
            return sorted(found)[-1]  # newest SDK

    vswhere = os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Microsoft Visual Studio", "Installer", "vswhere.exe",
    )
    if os.path.exists(vswhere):
        r = subprocess.run(
            [vswhere, "-latest", "-property", "installationPath"],
            capture_output=True, encoding="utf-8", errors="replace",
        )
        vs = r.stdout.strip()
        if vs:
            found = glob.glob(os.path.join(vs, "**", "mt.exe"), recursive=True)
            if found:
                return found[0]

    return shutil.which("mt.exe")


# -- talking to the launched exe -------------------------------------------


def get(port: int, path: str, timeout: float = 5.0):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def post(port: int, path: str, payload=None, headers=None, timeout: float = 120.0):
    """(status, body). An HTTP error is a status, not an exception -- 403 and
    405 are expected results here, not failures."""
    data = json.dumps(payload).encode() if payload is not None else b""
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"content-type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, read_bounded(r, BODY_TIMEOUT)
    except urllib.error.HTTPError as e:
        # The error BODY is the diagnosis, and reading it is a second network
        # read on a connection whose budget the first one already spent. When
        # the child is dying it never arrives, and an unguarded e.read() then
        # raises TimeoutError out of _safe_read -- so a plain HTTP 500 reaches
        # run_all wearing the costume of a timeout. Report the status either
        # way; the body is a bonus, not a precondition.
        return e.code, read_bounded(e, BODY_TIMEOUT)


def wait_health(proc, port: int, budget: float = HEALTH_TIMEOUT):
    """Seconds to first 200, or None. Returns early if the process dies."""
    start = time.time()
    while time.time() - start < budget:
        if proc.poll() is not None:
            return None
        try:
            status, _ = get(port, "/api/health", timeout=2.0)
            if status == 200:
                return time.time() - start
        except Exception:
            time.sleep(0.3)
    return None


def free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def launch(port: int, nonce: str) -> subprocess.Popen:
    """Start the exe with its output drained from the first byte.

    The drain lives in lib/childio.py now, and the reason it has to exist is
    written there. This check learned it the first time -- a missing
    unidic_lite dictionary stayed invisible for two lanes' worth of iterations
    while its traceback sat unread in a full pipe -- and check_api learned it
    the second, which is what moved it into shared code.
    """
    env = {**os.environ, "MT_PORT": str(port), "MT_SHUTDOWN_NONCE": nonce}
    return launch_drained([EXE], env=env, cwd=DIST)


def kill(proc):
    """Kill the whole tree, not just the process we hold.

    A one-file PyInstaller exe is a bootloader that unpacks and then runs the
    app as a CHILD. proc.kill() reaps the bootloader and leaves the app alive,
    still holding build/dist/sidecar-*.exe open -- so the NEXT build dies with
    WinError 5 and check_package reports it as a build failure with an empty
    reason. Five such orphans were found alive in one session.
    """
    if not proc or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
    else:
        proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def sidecar_pids() -> set[int]:
    """Every running packaged sidecar, by image name.

    tasklist rather than psutil: this check runs on a bare interpreter and must
    not grow a dependency in order to clean up after itself.
    """
    if os.name != "nt":
        return set()
    # BYTES, decoded here. text=True would decode with the ANSI locale codec
    # while tasklist writes the console OEM codepage -- two different things
    # that only agree while every row is ASCII. When they disagree the decode
    # dies, subprocess SWALLOWS it, and r.stdout arrives empty, which parses
    # to an empty set: indistinguishable from "no sidecars are running". This
    # function's caller asserts that nothing leaked, so a silent empty set
    # turns the guard green by failing to look -- the one outcome worse than
    # the leak it exists to catch. A decode failure and a true negative must
    # never produce the same value.
    r = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {EXE_NAME}", "/NH", "/FO", "CSV"],
        capture_output=True,
    )
    if r.returncode != 0:
        raise RuntimeError(
            f"tasklist failed rc={r.returncode}: "
            f"{r.stderr.decode('utf-8', 'replace').strip()[:200]} -- "
            f"cannot prove no sidecar leaked"
        )
    pids = set()
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        fields = [f.strip('" ') for f in line.split('","')]
        if len(fields) >= 2 and fields[0].lower() == EXE_NAME.lower():
            try:
                pids.add(int(fields[1]))
            except ValueError:
                pass
    return pids


def reap(pids) -> None:
    """Kill sidecars this run is responsible for.

    Only ever called with (pids now) - (pids before launch). Sweeping by image
    name alone would also kill a sidecar another process started, and killing
    someone else's run to tidy up our own is worse than the leak.

    This exists because kill() cannot cover the case it is most needed for: a
    bootloader that has already exited leaves proc.poll() non-None, so there is
    no tree left to taskkill, while the app CHILD it spawned is still alive
    holding build/dist/sidecar-*.exe open.
    """
    for pid in sorted(pids):
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)


# -- the GPU variant -------------------------------------------------------


def main_gpu():
    """--gpu: assert onnxruntime actually SELECTED CUDA, not merely offers it.

    Exit 3 with a named reason when there is no CUDA device. That is a pass for
    this story -- this machine has no GPU -- but it must say so rather than
    reporting green, or the check silently stops meaning anything the day a GPU
    appears.
    """
    c = Checks("check_package --gpu")
    try:
        import onnxruntime
    except ImportError as e:
        return skip(f"onnxruntime not installed ({e.name}); no CUDA device")

    available = onnxruntime.get_available_providers()
    if "CUDAExecutionProvider" not in available:
        return skip(f"no CUDA device: providers are {available}")

    provider, reason = select_provider()
    c.check(provider == "CUDAExecutionProvider", f"select_provider chose CUDA ({provider}: {reason})")
    c.check(reason == "", f"and reports no fallback reason ({reason!r})")

    return c.finish()


# -- the build ------------------------------------------------------------


def build(c) -> bool:
    """Build via the spec. False if the build failed."""
    r = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm",
         "--distpath", DIST, "--workpath", os.path.join(ROOT, "build", "work"), SPEC],
        cwd=ROOT, capture_output=True,
        encoding="utf-8", errors="replace",
    )
    ok = r.returncode == 0 and os.path.exists(EXE)
    # STDERR, not just stdout. PyInstaller puts its traceback on stderr, so
    # reporting stdout alone produced "FAIL: ... builds sidecar.exe:" with
    # nothing after the colon -- which is how a plain PermissionError from a
    # leaked sidecar holding the exe open read as an unexplained build
    # failure, twice, before anyone ran PyInstaller by hand to see it.
    reason = ""
    if not ok:
        reason = (f": rc={r.returncode}\n"
                  f"{(r.stdout or '')[-600:]}\n"
                  f"{(r.stderr or '')[-800:]}")
    c.check(ok, f"build/sidecar.spec builds {EXE_NAME}{reason}")
    return ok


def main():
    if "--gpu" in sys.argv:
        return main_gpu()

    if sys.platform != "win32":
        return skip("Windows-only: mt.exe and the embedded manifest")
    if not os.path.exists(SPEC):
        return broken_checkout(f"build/sidecar.spec missing: {SPEC}")
    if not os.path.exists(MANIFEST):
        return broken_checkout(f"build/longpath.manifest missing: {MANIFEST}")

    c = Checks("check_package")

    # [1] it builds
    if not build(c):
        return c.finish()

    size = os.path.getsize(EXE)
    c.check(size < TWO_GB, f"the one-file exe is under 2GB ({size / 1024**2:.0f}MB)")

    # [3] longPathAware is IN THE EXE, not merely in the source manifest.
    #
    # mt.exe is used READ-ONLY here, to extract. It must never write to a
    # one-file exe: that is a PE with the PKG archive appended after it, and
    # rewriting the resource section shifts everything below, after which the
    # bootloader cannot find the archive ("PYI-3992: Could not load
    # PyInstaller's embedded PKG archive") and the exe dies on launch. The
    # manifest is embedded by PyInstaller instead, via EXE(manifest=...) in the
    # spec -- so this assert is what proves that argument survived.
    mt = find_mt()
    if not mt:
        c.check(False, "mt.exe found via registry/vswhere (cannot verify the manifest)")
        return c.finish()

    # Every mt.exe flag here takes a COLON, -out included. `-out extracted`
    # as two arguments fails with "c1010008: Missing command-line option
    # -out", mt.exe still exits 0, and the extraction silently produces no
    # file -- which reads as an embedding failure rather than a flag typo.
    extracted = os.path.join(ROOT, "build", "work", "embedded.manifest")
    if os.path.exists(extracted):
        os.remove(extracted)  # or a stale one from a prior run reads as a pass
    r = subprocess.run(
        [mt, "-nologo", f"-inputresource:{EXE};#1", f"-out:{extracted}"],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    embedded = ""
    if os.path.exists(extracted):
        with open(extracted, encoding="utf-8", errors="replace") as fh:
            embedded = fh.read()
    c.check(
        re.search(r"<\w*:?longPathAware[^>]*>\s*true\s*<", embedded, re.I) is not None,
        f"longPathAware is present in the exe's embedded manifest "
        f"({len(embedded)} bytes read; mt rc={r.returncode} {r.stdout.strip()[:200]})",
    )

    # Whatever is already running belongs to somebody else. Everything this
    # run is answerable for is the difference against this set.
    preexisting = sidecar_pids()

    port, nonce = free_port(), "nonce-" + os.urandom(8).hex()
    proc = launch(port, nonce)
    try:
        # [5] it starts and answers within the cold-start budget
        elapsed = wait_health(proc, port)
        if elapsed is None:
            out = captured(proc)
            c.check(False, f"/api/health returns 200 within {HEALTH_TIMEOUT}s -- fall back to one-dir. Output:\n{out}")
            return c.finish()
        c.check(True, f"/api/health returns 200 in {elapsed:.1f}s")

        # [6..10] a FULL translate through the packaged exe. This is the assert
        # that touches torch and PIL, i.e. the hidden imports a health poll
        # cannot reach.
        dest = os.path.join(ROOT, "build", "work", "translate-out")
        shutil.rmtree(dest, ignore_errors=True)
        with StubProvider() as stub:
            status, body = post(port, "/api/translate", {
                "src_path": SMOKE,
                "dest_dir": dest,
                "page": 1,
                "settings": {"base_url": stub.url, "api_key": "", "model": "stub-model"},
            })
        c.check(status == 200, f"POST /api/translate returns 200 ({status}: {body[:400]!r})")
        if status != 200:
            return c.finish()

        outputs = [p for p in glob.glob(os.path.join(dest, "*")) if not os.path.basename(p).startswith(".")]
        c.check(bool(outputs), f"an output file appears ({[os.path.basename(p) for p in outputs]})")

        regions_path = os.path.join(dest, "regions.json")
        if not os.path.exists(regions_path):
            c.check(False, f"regions.json is written ({os.listdir(dest) if os.path.isdir(dest) else 'no dest dir'})")
            return c.finish()
        with open(regions_path, encoding="utf-8") as fh:
            rec = json.load(fh)

        # "A file appeared" is satisfied by an empty file. These four counters
        # are what distinguishes a real run from a no-op: detection, OCR,
        # inpainting, and pixels actually changed inside the polygon.
        c.check(rec.get("detections", 0) >= 1, f"at least one detection ({rec.get('detections')})")
        c.check(rec.get("ocr_calls", 0) >= 1, f"at least one OCR call ({rec.get('ocr_calls')})")
        c.check(rec.get("inpaint_calls", 0) >= 1, f"at least one inpaint call ({rec.get('inpaint_calls')})")
        changed = rec.get("pixels_changed_in_polygon", {})
        c.check(
            any(v > 0 for v in changed.values()),
            f"pixels changed inside a polygon ({changed})",
        )

        # [11] the CPU EP was selected. Goes red on a build where onnxruntime
        # resolves to nothing at all: select_provider names every fallback it
        # takes, so an empty provider string means nothing chose anything.
        provider, reason = select_provider()
        c.check(
            provider == "CPUExecutionProvider",
            f"the CPU execution provider was selected ({provider}: {reason})",
        )

        # -- the two negative shutdown asserts, BEFORE the real one ----------
        status, _ = post(port, "/api/shutdown", timeout=10)
        c.check(status == 403, f"POST /api/shutdown with no nonce returns 403 ({status})")
        c.check(proc.poll() is None, "and the process is still alive")

        status, _ = post(port, "/api/shutdown", headers={"x-shutdown-nonce": "wrong"}, timeout=10)
        c.check(status == 403, f"POST /api/shutdown with a wrong nonce returns 403 ({status})")
        c.check(proc.poll() is None, "and the process is still alive")

        try:
            status, _ = get(port, "/api/shutdown")
        except urllib.error.HTTPError as e:
            status = e.code
        c.check(status == 405, f"GET /api/shutdown returns 405 ({status})")
        c.check(proc.poll() is None, "and the process is still alive")

        # [18] the real shutdown, with a write parked mid-flight.
        # The exe is a separate process, so crash_hook cannot be injected into
        # it -- instead the cache tree is scanned afterwards for the dot-temp
        # files atomic_write leaves behind if a write is interrupted.
        before = set(glob.glob(os.path.join(dest, "**", ".*.tmp"), recursive=True))
        status, _ = post(port, "/api/shutdown", headers={"x-shutdown-nonce": nonce}, timeout=10)
        c.check(status == 200, f"POST /api/shutdown with the nonce returns 200 ({status})")

        deadline = time.time() + SHUTDOWN_TIMEOUT
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        c.check(proc.poll() is not None, f"the process exits within {SHUTDOWN_TIMEOUT}s")

        orphans = set(glob.glob(os.path.join(dest, "**", ".*.tmp"), recursive=True)) - before
        c.check(not orphans, f"no temp file survives the shutdown ({sorted(orphans)})")

        # [21] and no PROCESS survives it either. A clean shutdown ends the
        # bootloader, which is all assert [19] can see -- the app child it
        # spawned can outlive it, keep the exe file open, and make the next
        # build fail with WinError 5 while reporting an empty-reason build
        # failure. That misdirection cost two lanes an hour, so it is asserted
        # here rather than left to the cleanup in finally.
        kill(proc)
        try:
            leaked = sidecar_pids() - preexisting
            c.check(not leaked,
                    f"no packaged sidecar survives the run (leaked pids: {sorted(leaked)})")
        except RuntimeError as e:
            # Unprovable is not proven. Red, with the reason.
            c.check(False, f"no packaged sidecar survives the run -- unverifiable: {e}")
    finally:
        # The guarantee, on every exit path including each early return above:
        # the tree if the bootloader still holds one, then anything this run
        # started that outlived it.
        kill(proc)
        try:
            reap(sidecar_pids() - preexisting)
        except RuntimeError as e:
            # Raising out of `finally` would replace whatever actually went
            # wrong with this. Say it and let the original failure stand.
            print(f"  cleanup could not enumerate sidecars: {e}", flush=True)

    return c.finish()


run(main)
