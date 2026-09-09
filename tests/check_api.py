"""Phase 0 -- the sidecar's HTTP surface and the shutdown gate (US-007). OFFLINE.

Runs the real app under a real uvicorn on a real socket rather than
fastapi.TestClient, because two of the properties under test are only
observable through the network stack: which interface the app bound, and
whether a rejected shutdown left the PROCESS alive. TestClient never binds and
never has a process to kill, so it would pass a sidecar that binds 0.0.0.0 and
exits on any POST.
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.httpread import read_bounded  # noqa: E402
from lib.result import Checks, run  # noqa: E402

NONCE = "test-nonce-4a91c2"
PORT = 8791
SMOKE = os.path.join(ROOT, "fixtures", "smoke", "tategaki_01.png")
# The server is started pointed here, so no stage can find its weights and the
# weights-failure path is reachable without touching the user's real cache.
EMPTY_MODELS = os.path.join(ROOT, "build", "work", "api-empty-models")

SERVER = """
import socket, sys, uvicorn

# Refuse every OUTBOUND connection that is not loopback, before importing the
# app. An empty MT_MODEL_DIR alone does not reach the weights-failure path --
# on a machine with a network it just re-downloads and succeeds, which is what
# the first version of this check proved by passing 200. Loopback stays open
# because uvicorn and this check's own client both need it.
_real_connect = socket.socket.connect


def _loopback_only(self, address, *a, **k):
    host = str(address[0]) if isinstance(address, tuple) else ""
    if not (host.startswith("127.") or host in ("localhost", "::1")):
        raise OSError("blocked by check_api: no outbound network in this test")
    return _real_connect(self, address, *a, **k)


socket.socket.connect = _loopback_only

from sidecar.main import app, HOST
uvicorn.run(app, host=HOST, port=int(sys.argv[1]), log_level="error")
"""


def call(method, path, port=PORT, headers=None, host="127.0.0.1", timeout=5, body=None):
    """Returns (status, body). A refused connection is status 0."""
    heads = dict(headers or {})
    if body is not None:
        heads.setdefault("content-type", "application/json")
    req = urllib.request.Request(
        f"http://{host}:{port}{path}", method=method, headers=heads
    )
    if method == "POST":
        req.data = body.encode() if isinstance(body, str) else (body or b"")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, read_bounded(r, timeout).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # The error BODY is the diagnosis and reading it is a second read on a
        # connection the first one already spent. Unguarded, e.read() raises
        # from inside this except clause and takes the whole check with it --
        # which is how removing main.py's weights handler produced a urllib
        # stack trace instead of three red asserts.
        return e.code, read_bounded(e, timeout).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError):
        return 0, ""


def wait_up(port, tries=60):
    for _ in range(tries):
        if call("GET", "/api/health", port)[0] == 200:
            return True
        time.sleep(0.25)
    return False


def main():
    c = Checks("check_api")

    shutil.rmtree(EMPTY_MODELS, ignore_errors=True)
    os.makedirs(EMPTY_MODELS, exist_ok=True)
    env = dict(os.environ, MT_SHUTDOWN_NONCE=NONCE, PYTHONIOENCODING="utf-8",
               PYTHONPATH=ROOT, MT_MODEL_DIR=EMPTY_MODELS)
    proc = subprocess.Popen(
        [sys.executable, "-c", SERVER, str(PORT)],
        env=env,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        if not wait_up(PORT):
            proc.kill()
            out, err = proc.communicate(timeout=5)
            c.check(False, f"sidecar starts: {err.decode('utf-8', 'replace')[-400:]}")
            return c.finish()

        status, body = call("GET", "/api/health")
        c.check(status == 200 and json.loads(body)["status"] == "ok", f"health: {body[:60]}")

        # -- the shutdown gate ---------------------------------------------
        c.check(call("GET", "/api/shutdown")[0] == 405, "GET /api/shutdown is 405")
        c.check(proc.poll() is None, "and the process is still up after the GET")

        c.check(call("POST", "/api/shutdown")[0] == 403, "POST with NO nonce is 403")
        c.check(proc.poll() is None, "and the process is still up")

        c.check(
            call("POST", "/api/shutdown", headers={"X-Shutdown-Nonce": "wrong"})[0] == 403,
            "POST with a WRONG nonce is 403",
        )
        c.check(proc.poll() is None, "and the process is still up")

        # Still serving, not wedged by the rejections.
        c.check(call("GET", "/api/health")[0] == 200, "still serving after three rejections")

        # -- the bind interface --------------------------------------------
        # If it bound 0.0.0.0 this reaches it on the LAN address too.
        import socket

        lan = socket.gethostbyname(socket.gethostname())
        if lan.startswith("127."):
            c.check(True, f"no non-loopback address to test against ({lan}); bind asserted below")
        else:
            c.check(
                call("GET", "/api/health", host=lan, timeout=2)[0] == 0,
                f"NOT reachable on the LAN address {lan} -- 127.0.0.1 only",
            )

        # -- a weights failure reaches the UI with its reason intact -------
        # The regression this pins: /api/translate used to catch ProviderError
        # only, so a checksum mismatch or a dead network -- the two failures
        # models.py works hardest to keep distinguishable -- arrived as a bare
        # 500 with an empty body. Everything underneath can name its reason
        # perfectly and it stops at the boundary.
        #
        # Forced by pointing MT_MODEL_DIR at an empty directory the server was
        # started with, so the first stage that needs weights cannot get them.
        status, body = call("POST", "/api/translate", body=json.dumps({
            "src_path": SMOKE, "dest_dir": os.path.join(EMPTY_MODELS, "out"), "page": 1,
        }), timeout=60)
        c.check(status == 503, f"a weights failure is 503, not a bare 500 (got {status})")
        try:
            payload = json.loads(body)
        except (ValueError, TypeError):
            payload = {}
        c.check(bool(payload.get("error")),
                f"the body carries a reason, not an empty 500 ({body[:160]!r})")
        c.check(payload.get("kind") in {"network", "checksum", "space", "weights",
                                        "config", "error"},
                f"and a machine-readable kind the UI can branch on "
                f"({payload.get('kind')!r})")

        # -- the correct nonce actually shuts it down ----------------------
        status, _ = call("POST", "/api/shutdown", headers={"X-Shutdown-Nonce": NONCE})
        c.check(status == 200, f"POST with the CORRECT nonce is accepted ({status})")
        for _ in range(40):
            if proc.poll() is not None:
                break
            time.sleep(0.25)
        c.check(proc.poll() is not None, "and the process actually exits")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)

    # -- no credentials in the source ---------------------------------------
    src = open(os.path.join(ROOT, "sidecar", "main.py"), encoding="utf-8").read()
    c.check('"0.0.0.0"' not in src and "'0.0.0.0'" not in src, "0.0.0.0 appears nowhere")
    c.check("sys.stdout.reconfigure" in src, "stdout is reconfigured to UTF-8")
    c.check("secrets.compare_digest(presented" in src, "the nonce is compared in constant time")
    c.check(
        "sk-" not in src and "localhost:20128" not in src,
        "no API key or dev base URL baked into main.py",
    )

    return c.finish()


run(main)
