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
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.childio import captured, launch_drained, said  # noqa: E402
from lib.httpread import read_bounded  # noqa: E402
from lib.result import Checks, run  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402

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


# Registered HERE, in the test's own server script, never in main.py. An
# endpoint that exists only to crash is a debug hatch, and a debug hatch that
# ships is an endpoint an attacker can reach; the property under test is how
# the app treats an unexpected exception, and that does not require the
# shipped binary to carry a way of causing one.
@app.get("/api/_boom")
def _boom():
    raise RuntimeError("deliberate: an exception no handler predicted")


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


def _parse_json(body):
    """(payload, why). `why` names the parse failure so the assert can print it.

    A bare `except: payload = {}` would report "the body has no error field"
    for a body that is not JSON at all -- the same message for two different
    faults, and the wrong one for the bug this file now pins.
    """
    try:
        return json.loads(body), ""
    except (ValueError, TypeError) as e:
        return None, f"{type(e).__name__}: {e}"


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
    # DRAINED, not merely piped. This harness used to hold both pipes and read
    # neither until the end, so the first traceback the sidecar printed filled
    # the pipe and blocked it mid-write -- and every request after that timed
    # out. Read as a server fault, that looks exactly like an application hang,
    # and it was written up as one before being driven properly. See
    # lib/childio.py; check_package.py hit the same wall first.
    proc = launch_drained([sys.executable, "-c", SERVER, str(PORT)], env=env, cwd=ROOT)
    try:
        if not wait_up(PORT):
            proc.kill()
            c.check(False, f"sidecar starts: {captured(proc)[-400:]}")
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

        # -- every error body is REAL JSON (US-P1-09) ----------------------
        # Both error envelopes used to be built by f-string. `{e.body!r}` is
        # Python repr, which switches to single quotes the moment the string
        # contains a double quote -- and a provider error from an
        # OpenAI-compatible endpoint is itself JSON, so that is the ordinary
        # case, not the exotic one. The 502 arrived labelled application/json
        # and json.loads could not read it, which is AC-8 delivering the
        # provider's own words in an envelope the UI cannot open.
        #
        # Asserted HERE, at the HTTP boundary, because check_provider asserts
        # AC-8 at the LLMClient level and stops one layer short of the bug;
        # /api/models had no HTTP-level test at all.
        with open(os.path.join(ROOT, "fixtures", "provider", "error_401.json"),
                  encoding="utf-8") as fh:
            provider_body = fh.read()
        # If the fixture were quote-free the round-trip below would pass
        # against the f-string too, so this assert guards the assert.
        c.check('"' in provider_body,
                "the provider fixture really does contain a double quote")

        with StubProvider(models_status=401, delay=0) as stub:
            status, body = call(
                "GET", f"/api/models?base_url={quote(stub.url, safe='')}&model=probe"
            )
        c.check(status == 502, f"a provider error on /api/models is 502 (got {status})")
        payload, why = _parse_json(body)
        c.check(payload is not None,
                f"and the 502 body parses as JSON ({why}; body {body[:120]!r})")
        c.check(isinstance(payload, dict) and payload.get("body") == provider_body,
                "and carries the provider's response verbatim, quotes intact")
        c.check(isinstance(payload, dict) and payload.get("status") == 401,
                f"and the provider's status ({(payload or {}).get('status')!r})")

        # A ValueError message quotes the user's own input back at them --
        # urllib formats the url with %r -- so whatever was typed into the
        # Settings base URL field ends up inside the 400 body.
        bad = 'say "hi"'
        status, body = call("GET", f"/api/models?base_url={quote(bad, safe='')}&model=probe")
        c.check(status == 400, f"a bad base_url with a double quote is 400 (got {status})")
        payload, why = _parse_json(body)
        c.check(isinstance(payload, dict) and isinstance(payload.get("error"), str),
                f"and its body parses as JSON with the quote in the message "
                f"({why}; body {body[:120]!r})")

        # -- a malformed base URL is a 400, not a bare 500 (US-P1-10) ------
        # http.client.InvalidURL is NOT a ValueError -- it descends from
        # HTTPException -- so `except ValueError` at the boundary walked past
        # it and one mistyped character in the port came back as a 500 with an
        # empty body. Exactly the shape of the weights-failure bug above: the
        # failure the user can fix arriving as the one that looks like ours.
        for label, bad in (("a nonnumeric port", "http://127.0.0.1:notaport/v1"),
                           ("a control character", "http://127.0.0.1\n:9/v1"),
                           ("no scheme at all", "127-0-0-1/v1")):
            status, body = call("GET", f"/api/models?base_url={quote(bad, safe='')}&model=probe")
            c.check(status == 400, f"base_url with {label} is 400, not 500 (got {status})")
            payload, why = _parse_json(body)
            c.check(isinstance(payload, dict) and isinstance(payload.get("error"), str),
                    f"and says why, in JSON ({why}; body {body[:100]!r})")
            # AND the sidecar still answers. Before the fix this was not a 500,
            # it was a HANG: the process stayed alive and every later request
            # timed out, so the cost of the bug was the app bricked until
            # restart, not one unhelpful status code. A check that stops at the
            # status cannot tell those two apart -- the shutdown gate below is
            # the only other place in this file that thought to ask.
            c.check(call("GET", "/api/health", timeout=4)[0] == 200,
                    f"and the sidecar still serves afterwards ({label})")

        # The same class of settings error on /api/translate, where the client
        # used to be built ABOVE the try and could not be caught at all.
        status, body = call("POST", "/api/translate", body=json.dumps({
            "src_path": SMOKE, "dest_dir": os.path.join(EMPTY_MODELS, "out"), "page": 1,
            "settings": {"base_url": "", "api_key": "", "model": ""},
        }), timeout=60)
        c.check(status == 400, f"/api/translate with empty settings is 400 (got {status})")
        payload, why = _parse_json(body)
        c.check(isinstance(payload, dict) and "base_url" in str(payload.get("error")),
                f"and names the field the user has to fill ({why}; body {body[:100]!r})")
        c.check(call("GET", "/api/health", timeout=4)[0] == 200,
                "and the sidecar still serves after the rejected translate")

        # -- an exception nobody predicted (US-P1-11) ----------------------
        # Every other error path in main.py is one somebody thought about.
        # This is the one nobody did: whatever the next bug turns out to be.
        # Starlette's default is a plain-text "Internal Server Error" under a
        # content type the UI cannot parse, which puts the sidecar's worst
        # moments outside the envelope every other failure arrives in.
        status, body = call("GET", "/api/_boom")
        c.check(status == 500, f"an unpredicted exception is 500 (got {status})")
        payload, why = _parse_json(body)
        c.check(isinstance(payload, dict) and payload.get("kind") == "internal",
                f"and its body is JSON the UI can branch on ({why}; body {body[:100]!r})")
        c.check(isinstance(payload, dict) and payload.get("exception") == "RuntimeError",
                f"naming the exception CLASS, not its message ({payload})")
        # The message must NOT travel. An unexpected exception's text can carry
        # a path, a payload fragment, or part of a provider response, and this
        # body goes to a renderer.
        c.check("deliberate:" not in body,
                f"and not the message text, which is unvetted ({body[:100]!r})")
        c.check(call("GET", "/api/health", timeout=4)[0] == 200,
                "and the sidecar still serves afterwards")
        # The trace is how the NEXT bug gets diagnosed. Tauri reads stderr into
        # the log pane, so a handler that returned a tidy 500 and swallowed the
        # traceback would trade one debugging session for every future one.
        c.check(said(proc, "RuntimeError: deliberate:"),
                f"and the full traceback still reaches stderr ({captured(proc, 3)!r:.140})")

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

    # -- the 400 envelope against a message HTTP cannot deliver -------------
    # A backslash or a newline typed into the base URL comes back through
    # urllib already escaped -- it formats the url with %r, so `\` arrives as
    # `\\` and a newline as `\n`, both of which are valid JSON escapes and
    # survive even the broken f-string. Only the double quote above breaks it
    # over HTTP, and asserting the other two through the socket would add two
    # checks that CANNOT go red.
    #
    # So the handler is called directly with a ValueError whose message really
    # does carry a raw backslash, a raw newline and a double quote -- the shape
    # any other ValueError reaching this handler could take -- and the envelope
    # it returns is parsed. Not the network path, and deliberately so: this
    # asserts the one thing the network path cannot reach.
    import sidecar.main as sidecar_main

    nasty = 'C:\\Users\\me: cannot use "that"\nand a second line'
    real_client = sidecar_main.LLMClient

    def _explode(*_a, **_k):
        raise ValueError(nasty)

    sidecar_main.LLMClient = _explode
    try:
        response = sidecar_main.models(base_url="http://127.0.0.1:1/v1", model="probe")
    finally:
        sidecar_main.LLMClient = real_client

    payload, why = _parse_json(response.body.decode("utf-8"))
    c.check(response.status_code == 400, f"a ValueError is 400 (got {response.status_code})")
    c.check(isinstance(payload, dict) and payload.get("error") == nasty,
            f"and a message with a backslash, a newline and a quote round-trips "
            f"through json.loads intact ({why}; body {response.body[:120]!r})")

    # -- no credentials in the source ---------------------------------------
    src = open(os.path.join(ROOT, "sidecar", "main.py"), encoding="utf-8").read()
    c.check('"0.0.0.0"' not in src and "'0.0.0.0'" not in src, "0.0.0.0 appears nowhere")
    c.check("sys.stdout.reconfigure" in src, "stdout is reconfigured to UTF-8")
    c.check("secrets.compare_digest(presented" in src, "the nonce is compared in constant time")
    c.check(
        "sk-" not in src and "localhost:20128" not in src,
        "no API key or dev base URL baked into main.py",
    )
    # /api/translate's ProviderError path shares _provider_response with
    # /api/models, which the HTTP asserts above exercise. This one catches a
    # NEW hand-built envelope before it reaches a path no check drives: an
    # f-string interpolated into a JSON body is the bug of US-P1-09 by
    # construction, whichever handler it appears in.
    #
    # Parsed, not grepped. A grep for the old expression would also match this
    # file's own prose about it, so the check would either go red on a comment
    # or force the comments to stop naming what they fixed.
    import ast

    fstrings = [
        node.lineno
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "content" and isinstance(kw.value, ast.JoinedStr)
    ]
    c.check(not fstrings,
            f"no error body is built by f-string interpolation -- json.dumps only "
            f"(main.py lines {fstrings})")

    return c.finish()


run(main)
