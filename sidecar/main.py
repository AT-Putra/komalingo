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
from .llm import LLMClient, ProviderError  # noqa: E402

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
        return Response(
            content=f'{{"status":{e.status},"body":{e.body!r}}}',
            status_code=502,
            media_type="application/json",
        )
    except ValueError as e:
        return Response(content=f'{{"error":"{e}"}}', status_code=400, media_type="application/json")


@app.post("/api/translate")
def translate(req: TranslateRequest):
    """Run one page. Progress lines go to stdout, which Tauri reads."""
    client = None
    if req.settings:
        client = LLMClient(req.settings.base_url, req.settings.api_key, req.settings.model)
    try:
        record = pipeline.run_page(req.src_path, req.dest_dir, req.page, client)
    except ProviderError as e:
        return Response(
            content=f'{{"status":{e.status},"body":{e.body!r}}}',
            status_code=502,
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
