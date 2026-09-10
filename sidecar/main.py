"""The FastAPI sidecar. Loopback only, nonce-gated shutdown.

Three security properties are load-bearing here:

  * The app binds 127.0.0.1, never 0.0.0.0. On 0.0.0.0 anything on the user's
    LAN -- a guest on the same cafe wifi -- can drive their translation
    pipeline and read their provider key back out of /api/settings.
  * /api/shutdown is POST only and requires the launch nonce the Tauri host
    generates at spawn. Without it, any web page the user visits can kill the
    sidecar with a single form POST to localhost; the browser sends it happily
    because a form POST is not subject to CORS preflight.
  * Base URL, API key and model have NO default and no module constant. They
    arrive from the Settings UI and live only in this process's memory. A
    default here would be a credential baked into the shipped binary.

stdout is reconfigured to UTF-8 before anything can print. PYTHONIOENCODING in
the spawn environment covers the Tauri path, but check_package.py launches the
exe directly and misses it -- belt and braces, because a cp1252 default kills
the run mid-page the first time a stage name meets a non-ASCII filename.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, Request, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import pipeline  # noqa: E402
from .detect import DetectError  # noqa: E402
from .llm import LLMClient, ProviderError, SettingsError  # noqa: E402
from .models import FetchError  # noqa: E402

HOST = "127.0.0.1"  # never 0.0.0.0. See the module docstring.
SHUTDOWN_NONCE = os.environ.get("MT_SHUTDOWN_NONCE", "")

app = FastAPI(title="MangaTranslator sidecar")


class Settings(BaseModel):
    """What the Settings UI sends. No defaults -- absent means absent."""

    base_url: str
    api_key: str = ""  # optional: local servers often need none
    model: str


class TranslateRequest(BaseModel):
    src_path: str
    dest_dir: str
    page: int = 1
    settings: Settings | None = None  # absent -> offline placeholder path


def _provider_response(e: ProviderError) -> Response:
    """AC-8's envelope, built by json.dumps and never by an f-string.

    The body is the provider's verbatim response, and a provider speaking an
    OpenAI-compatible protocol answers in JSON -- so it contains double quotes
    in the ordinary case, not the exotic one. The old `{e.body!r}` used Python
    repr, which switches to SINGLE quotes as soon as the string contains a
    double quote, and single-quoted strings are not JSON. The UI was handed a
    502 labelled application/json that json.loads could not parse, so AC-8's
    "the provider's own words reach the UI" delivered them unreadable.

    One helper for both call sites, because two hand-built envelopes are two
    chances to reintroduce this.
    """
    return Response(
        content=json.dumps({"status": e.status, "body": e.body}),
        status_code=502,
        media_type="application/json",
    )


def _bad_settings_response(e: ValueError) -> Response:
    """A 400 for settings this process cannot use. json.dumps, never f-string.

    Typed ValueError, not SettingsError, because /api/models hands it the
    wider type: on that endpoint a ValueError can ONLY be about the settings
    the request itself carries, so there is nothing else it could mislabel.
    /api/translate is the one that has to narrow, and does.

    The message quotes the user's own input back at them -- urllib formats the
    url with %r -- so it carries whatever they typed into the Settings field,
    quotes, backslashes and newlines included. That is exactly the input an
    f-string body cannot survive.
    """
    return Response(
        content=json.dumps({"error": str(e)}),
        status_code=400,
        media_type="application/json",
    )


@app.exception_handler(Exception)
def unhandled(request: Request, e: Exception) -> Response:
    """The last envelope. Every other error path in this file is deliberate;
    this one catches the ones nobody predicted, so that a bug in the sidecar
    reaches the UI as something it can read rather than as Starlette's
    plain-text "Internal Server Error" under an unparseable content type.

    It does NOT swallow the traceback. Starlette re-raises after this handler
    returns, uvicorn logs it, and Tauri reads it off stderr into the log pane
    -- which is the only way the next bug gets diagnosed. A handler that
    returned a tidy 500 and ate the trace would trade one debugging session
    for every future one.

    `type(e).__name__` and nothing else. The message of an unexpected
    exception can carry a path, a payload fragment, or a chunk of a provider
    response, and this envelope goes to a renderer; the class name says
    "something in the sidecar broke, here is what kind" without shipping
    whatever happened to be in the string. The full text is on stderr.
    """
    return Response(
        content=json.dumps({"error": "internal error in the sidecar",
                            "kind": "internal",
                            "exception": type(e).__name__}),
        status_code=500,
        media_type="application/json",
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "pid": os.getpid()}


@app.get("/api/models")
def models(base_url: str, model: str = "", api_key: str = ""):
    """Populate the Settings model dropdown from the user's own endpoint."""
    try:
        return {"models": LLMClient(base_url, api_key, model or "probe").list_models()}
    except ProviderError as e:
        # The provider's own words reach the UI. See AC-8.
        return _provider_response(e)
    except ValueError as e:
        return _bad_settings_response(e)


@app.post("/api/translate")
def translate(req: TranslateRequest):
    """Run one page. Progress lines go to stdout, which Tauri reads."""
    try:
        # INSIDE the try. The constructor rejects an empty base_url or model,
        # and the settings payload can carry both as empty strings -- pydantic
        # types them, it cannot know they are required downstream. Built above
        # the try, that error went unhandled -- and unhandled here does not
        # mean an unhelpful 500, it means the sidecar stops answering at all
        # (US-P1-11). The one failure the user could have fixed in two seconds
        # cost them a restart.
        client = None
        if req.settings:
            client = LLMClient(req.settings.base_url, req.settings.api_key, req.settings.model)
        record = pipeline.run_page(req.src_path, req.dest_dir, req.page, client)
    except ProviderError as e:
        return _provider_response(e)
    except SettingsError as e:
        # SettingsError, NOT ValueError. A page run is a lot of code, and a
        # ValueError from inside the pipeline is our bug -- it belongs in a
        # 500 that says so, not in a 400 that blames the user's settings for
        # it. The named type is what keeps this handler honest about which of
        # the two it caught.
        return _bad_settings_response(e)
    except (FetchError, DetectError) as e:
        # ONE handler for both, because DetectError deliberately mirrors
        # FetchError's (reason, kind) shape -- see its docstring. A caller that
        # can show one does not need a second display path for the other.
        #
        # Without this the whole naming discipline underneath stops here.
        # models.py goes to real trouble to make a dead network, a checksum
        # mismatch and a full disk three distinguishable failures with three
        # different user actions, and an uncaught exception flattens all three
        # into a bare 500 with an empty body -- which is exactly as useful to
        # the person waiting as "model download failed", the string that
        # docstring exists to forbid.
        #
        # 503, not 500: the app is not broken, a resource it needs is not
        # available. `kind` is what lets the UI branch -- network means check
        # the connection, checksum means the file is bad and refetching helps,
        # space means free some disk. Nothing downstream has to parse prose.
        return Response(
            content=json.dumps({"error": e.reason, "kind": e.kind}),
            status_code=503,
            media_type="application/json",
        )
    pipeline.write_regions(record, req.dest_dir)
    return record


@app.get("/api/shutdown")
def shutdown_get():
    """GET can never shut anything down. A link or an <img> is a GET."""
    return Response(status_code=405)


@app.post("/api/shutdown")
def shutdown(request: Request, response: Response):
    """POST + correct nonce + loopback client, or the process stays up.

    Every rejection path returns 403 and returns NORMALLY. Raising here would
    still be a 500 with the process alive, but the check asserts on the status
    and a 500 hides which guard fired.
    """
    client = request.client.host if request.client else ""
    if client not in ("127.0.0.1", "::1"):
        return Response(status_code=403, content="loopback only")

    presented = request.headers.get("x-shutdown-nonce", "")
    if not SHUTDOWN_NONCE or not presented:
        return Response(status_code=403, content="nonce required")
    # compare_digest: a plain == leaks the nonce one character at a time to
    # anything that can time the response.
    if not secrets.compare_digest(presented, SHUTDOWN_NONCE):
        return Response(status_code=403, content="bad nonce")

    # Exit after the response is on the wire, or the caller sees a dropped
    # connection instead of the 200 that tells it the shutdown was accepted.
    threading.Timer(0.25, lambda: os._exit(0)).start()
    return {"status": "shutting down"}


def main():
    import uvicorn

    port = int(os.environ.get("MT_PORT", "0") or 0)
    uvicorn.run(app, host=HOST, port=port or 8756, log_level="warning")


if __name__ == "__main__":
    main()
