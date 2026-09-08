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
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import Checks, run  # noqa: E402

NONCE = "test-nonce-4a91c2"
PORT = 8791

SERVER = """
import os, sys, uvicorn
from sidecar.main import app, HOST
uvicorn.run(app, host=HOST, port=int(sys.argv[1]), log_level="error")
"""


def call(method, path, port=PORT, headers=None, host="127.0.0.1", timeout=5):
    """Returns (status, body). A refused connection is status 0."""
    req = urllib.request.Request(
        f"http://{host}:{port}{path}", method=method, headers=headers or {}
    )
    if method == "POST":
        req.data = b""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
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

    env = dict(os.environ, MT_SHUTDOWN_NONCE=NONCE, PYTHONIOENCODING="utf-8", PYTHONPATH=ROOT)
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
