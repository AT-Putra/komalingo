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
from contextlib import asynccontextmanager
from typing import Literal

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, Request, Response  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import atomic, cache, job, pipeline  # noqa: E402
from .detect import DetectError  # noqa: E402
from .llm import LLMClient, ProviderError, SettingsError  # noqa: E402
from .models import FetchError  # noqa: E402
from .pipeline import CacheMiss  # noqa: E402

HOST = "127.0.0.1"  # never 0.0.0.0. See the module docstring.
SHUTDOWN_NONCE = os.environ.get("MT_SHUTDOWN_NONCE", "")
# Set by Tauri, and only by Tauri: exit when stdin reaches EOF. See watch_parent.
EXIT_ON_STDIN_EOF = os.environ.get("MT_EXIT_ON_STDIN_EOF", "") == "1"


def watch_parent(stdin=None) -> threading.Thread:
    """Exit the moment stdin closes -- which, under Tauri, means the parent died.

    Tauri hands this process a stdin pipe and holds the write end for the life
    of the app. When the app exits, crashes, or `tauri dev` restarts it, the
    OS closes that end and the read here returns EOF -- with no cooperation
    from a parent that may not be running any more. Nothing else covers that
    case: the shutdown route needs the nonce, and the nonce died with the
    parent.

    Without this, a sidecar outlived every restart of the app. The next app
    spawned its own sidecar, which failed to bind 8756 and exited; the UI
    polled /api/health, the ORPHAN answered, and the UI said "ready" -- to a
    process whose stdout pipe had no reader. Its first progress print raised
    OSError [Errno 22] into the 500 envelope, and the traceback went to a
    stderr nobody was reading. Two sidecars, one port, and every symptom
    pointing at the wrong one.

    Opt-in by env, because a stdin that is closed or /dev/null is normal for
    a sidecar launched any other way -- the checks launch it with pipes they
    never write to, and a shell launch has no pipe at all. A daemon thread:
    it must never keep the process alive, only end it.
    """
    stream = stdin if stdin is not None else getattr(sys.stdin, "buffer", sys.stdin)

    def watch():
        try:
            while stream.read(4096):
                pass
        except (OSError, ValueError):
            pass  # a closed or invalid handle is the same news as EOF
        try:
            print("sidecar: stdin closed -- parent gone, exiting", file=sys.stderr, flush=True)
        except OSError:
            pass  # stderr is on the same dead pipe
        os._exit(0)

    t = threading.Thread(target=watch, name="parent-watch", daemon=True)
    t.start()
    return t


@asynccontextmanager
async def lifespan(_app: FastAPI):
    r"""Repair leaked cache references before anything can be evicted against them.

    A job killed mid-run leaves its id in every page it touched, and a leaked
    reference pins those pages against the disk cap forever -- the cache fills
    with pages nothing can evict. The ids are NAMED, so the leak is
    identifiable: any id naming no directory under cache\jobs\ is dropped. That
    is the whole reason refs.json holds a list of ids and not a count.

    A lifespan handler rather than the older startup-event decorator, which is
    deprecated in this FastAPI and warns on import -- and a deprecation warning
    on stderr is indistinguishable from a real one in the Tauri log pane.
    """
    if EXIT_ON_STDIN_EOF:
        watch_parent()
    try:
        removed = cache.prune_refs()
        if removed:
            print(f"cache: pruned {removed} stale job references",
                  file=sys.stderr, flush=True)
    except OSError as e:
        # A cache root that cannot be read is not a reason to refuse to start:
        # every page in it is re-derivable, and the alternative is a sidecar
        # that will not launch because of a directory the user could delete.
        print(f"cache: startup prune skipped ({type(e).__name__}: {e})",
              file=sys.stderr, flush=True)
    yield


app = FastAPI(title="MangaTranslator sidecar", lifespan=lifespan)


Source = Literal["ja", "zh", "ko"]  # pipeline.SOURCES, as a type pydantic can check
Target = Literal["en", "id"]  # llm.TARGET_NAMES' keys; Phase 5 adds Indonesian


class Settings(BaseModel):
    """What the Settings UI sends. No defaults -- absent means absent."""

    base_url: str
    api_key: str = ""  # optional: local servers often need none
    model: str


class TranslateRequest(BaseModel):
    src_path: str
    dest_dir: str
    page: int = 1
    source: Source = pipeline.DEFAULT_SOURCE  # the language the page is written in
    lang: Target = pipeline.DEFAULT_LANG  # the language the reader wants
    settings: Settings | None = None  # absent -> offline placeholder path


class ItemRequest(BaseModel):
    """One archive or PDF, start to finish. Phase 8 owns the QUEUE, not this route.

    job_id arrives from the caller rather than being minted here, because it is
    both the delete scope and the placement key: the UI has to be able to name
    the job it started in order to spot-fix a page of it or delete it later,
    and a server-minted id it only learns from a response it might not receive
    is an orphan waiting to happen.
    """

    src_path: str
    dest_dir: str
    job_id: str
    item_id: str | None = None
    lang: Target = pipeline.DEFAULT_LANG
    # Phase 4: which OCR reads the page. Validated here, so a typo is a 422
    # with the accepted set in it rather than a ValueError halfway through
    # an archive. RerenderRequest has no source: it never OCRs.
    source: Source = pipeline.DEFAULT_SOURCE
    settings: Settings | None = None


class JobRequest(BaseModel):
    """AC-7: a folder, or an explicit list, through the queue.

    Exactly one of `dir` and `paths`. A folder is what the user points at; a
    list is what a test or a drag-and-drop hands over. The job runs in the
    background and this request answers at once with the first status
    snapshot; the UI polls GET /api/job/{id} for the rest. The id is the
    caller's for the reason ItemRequest gives.
    """

    job_id: str
    dest_dir: str
    dir: str | None = None
    paths: list[str] | None = None
    lang: Target = pipeline.DEFAULT_LANG
    source: Source = pipeline.DEFAULT_SOURCE
    settings: Settings | None = None


class RerenderRequest(BaseModel):
    """AC-10's payload: one region of one page of one job.

    The page is addressed by (item_id, ordinal) and NOT by page hash, because
    two byte-identical pages in an archive share a hash -- spot-fixing one and
    silently editing both is precisely the bug placement exists to prevent, and
    taking a hash here would hand the caller the tool to reintroduce it.
    """

    job_id: str
    item_id: str
    ordinal: int
    region_id: int
    text: str
    dest_dir: str
    lang: Target = pipeline.DEFAULT_LANG
    settings: Settings | None = None


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


def _probed(client):
    """Run the vision probe for a route-built client; return its warning or "".

    The page image goes out on every route (pipeline.translate), and the
    only thing that stops it going out to a model that cannot take it is the
    client's text_only latch -- which only a probe sets. Job runs one per
    batch. These two routes build a fresh client per request and, until this
    existed, went straight to translate: a text-only model that had worked
    all along failed on its first page with the provider's 400 and nothing
    in the UI said why. Cached per (base_url, model), so the cost is one
    request per pair per process, not per item.
    """
    if client is None:
        return ""
    ok, reason = client.ensure_vision()
    return "" if ok else reason


def _client(settings: Settings | None):
    """Build an LLMClient, or None for the offline placeholder path.

    Called INSIDE each route's try, never above it: the constructor rejects an
    empty base_url or model, and pydantic cannot know those are required
    downstream. Built above the try, that error goes unhandled -- and unhandled
    here does not mean an unhelpful 500, it means the sidecar stops answering
    at all (US-P1-11).
    """
    if settings is None:
        return None
    return LLMClient(settings.base_url, settings.api_key, settings.model)


def _cache_miss_response(e: CacheMiss) -> Response:
    """404 with a named kind. A missing cache entry is not a server fault.

    `kind` is what lets the UI branch without parsing prose: "placement" means
    this job never ran that page, "cache" means the page was evicted and the
    item needs re-running, "region" means the editor and the page disagree
    about what is on it. A bare 404 collapses three different next actions into
    one dead end.
    """
    return Response(
        content=json.dumps({"error": e.reason, "kind": e.kind}),
        status_code=404,
        media_type="application/json",
    )


def _missing_source_response(path: str) -> Response | None:
    """404 naming the path when src_path is not a file; None when it is.

    Checked BEFORE the client is built and the vision probe runs, so a typo
    in a path does not cost a provider round trip to discover. Without this
    the pipeline's Image.open raised FileNotFoundError into the last-resort
    500 envelope, which by design withholds the message -- so the one string
    the user needed, the path it could not find, was the one string the UI
    did not have. Here the path is the user's own input, not an unvetted
    exception message, and it travels. `kind` "input" is what the UI branches
    on, the same way start_job answers a missing folder with 404.
    """
    if os.path.isfile(atomic.long_path(path)):
        return None
    return Response(
        content=json.dumps({"error": f"no such file: {path}", "kind": "input"}),
        status_code=404,
        media_type="application/json",
    )


# Decided once, on the first health poll: select_provider imports torch and
# onnxruntime and preloads the CUDA DLLs, which is a second of work that the
# first OCR would do anyway. Cached so the poll stays cheap afterwards.
_PROVIDER: tuple[str, str] | None = None


@app.get("/api/health")
def health():
    """Liveness, plus which execution provider this process will run on.

    The provider is the packaged build's own answer, from inside the exe --
    the one place it can be asked. check_package reads it here rather than
    calling select_provider in its own process, which for a year said "CPU"
    about a venv and nothing about the binary.
    """
    global _PROVIDER
    if _PROVIDER is None:
        from . import models  # noqa: PLC0415

        _PROVIDER = models.select_provider()
    provider, reason = _PROVIDER
    return {"status": "ok", "pid": os.getpid(), "provider": provider, "provider_reason": reason}


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
    missing = _missing_source_response(req.src_path)
    if missing is not None:
        return missing
    try:
        # INSIDE the try. The constructor rejects an empty base_url or model,
        # and the settings payload can carry both as empty strings -- pydantic
        # types them, it cannot know they are required downstream. Built above
        # the try, that error went unhandled -- and unhandled here does not
        # mean an unhelpful 500, it means the sidecar stops answering at all
        # (US-P1-11). The one failure the user could have fixed in two seconds
        # cost them a restart.
        client = _client(req.settings)
        vision_warning = _probed(client)
        record = pipeline.run_page(req.src_path, req.dest_dir, req.page, client, req.source,
                                   req.lang)
        record["vision_warning"] = vision_warning
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


@app.post("/api/item")
def translate_item(req: ItemRequest):
    """Every page of one archive or PDF, through the page cache.

    A second run of the same archive under a NEW job_id hits the cache and
    calls neither detection nor OCR, which is what makes this route -- and not
    only the re-render one -- part of AC-10's evidence. See cache.py on why the
    page directory is keyed on content and on nothing about the run.
    """
    missing = _missing_source_response(req.src_path)
    if missing is not None:
        return missing
    try:
        client = _client(req.settings)
        vision_warning = _probed(client)
        record = pipeline.run_item(
            req.src_path, req.dest_dir, req.job_id, req.item_id,
            client, req.lang, req.source,
        )
        record["vision_warning"] = vision_warning
    except ProviderError as e:
        return _provider_response(e)
    except SettingsError as e:
        return _bad_settings_response(e)
    except (FetchError, DetectError) as e:
        return Response(
            content=json.dumps({"error": e.reason, "kind": e.kind}),
            status_code=503,
            media_type="application/json",
        )
    return record


# The jobs this sidecar has run, by id, for GET /api/job/{id}. In memory:
# the queue is a property of this process, a restarted sidecar has no
# running jobs, and a finished job's outputs are on disk where AC-13's
# resume finds them without this table.
_jobs: dict[str, job.Job] = {}
_jobs_lock = threading.Lock()
# Finished jobs kept for GET /api/job/{id} after the fact. Beyond this many,
# the oldest finished ones are dropped when a new job starts -- a finished
# Job holds every item's full record, and a day of batches would otherwise
# hold a day of page polygons (review, N6). Running jobs are never dropped.
KEEP_FINISHED_JOBS = 20


def _job_response(status: int, error: str) -> Response:
    return Response(content=json.dumps({"error": error}), status_code=status,
                    media_type="application/json")


@app.post("/api/job")
def start_job(req: JobRequest):
    """Start a batch. Answers with the first status snapshot, immediately."""
    if (req.dir is None) == (req.paths is None):
        return _job_response(422, "exactly one of dir and paths is required")
    try:
        client = _client(req.settings)
    except SettingsError as e:
        return _bad_settings_response(e)
    try:
        paths = job.scan(req.dir) if req.dir is not None else list(req.paths or [])
    except NotADirectoryError as e:
        return _job_response(404, str(e))
    with _jobs_lock:
        existing = _jobs.get(req.job_id)
        if existing is not None and not existing.done:
            return _job_response(409, f"job {req.job_id!r} is still running")
        finished = [jid for jid, j in _jobs.items() if j.done and jid != req.job_id]
        for jid in finished[:max(0, len(finished) - KEEP_FINISHED_JOBS)]:
            del _jobs[jid]
        started = job.Job(req.job_id, paths, req.dest_dir, client, req.lang, req.source)
        _jobs[req.job_id] = started
    started.start()
    return started.status()


@app.get("/api/job/{job_id}")
def job_status(job_id: str):
    with _jobs_lock:
        found = _jobs.get(job_id)
    if found is None:
        return _job_response(404, f"no job {job_id!r} in this sidecar")
    return found.status()


@app.post("/api/job/{job_id}/cancel")
def cancel_job(job_id: str):
    """AC-13: items not yet started are cancelled outright; an item mid-run
    stops at its next page boundary with the pages it delivered kept and no
    archive written. An item already past its last page finishes its repack
    and comes back OK -- there is no page boundary left to stop at, and
    discarding finished work is not what cancel means. The response is the
    status at the moment of the request; poll GET /api/job/{id} to watch the
    running items stop."""
    with _jobs_lock:
        found = _jobs.get(job_id)
    if found is None:
        return _job_response(404, f"no job {job_id!r} in this sidecar")
    found.cancel()
    return found.status()


@app.post("/api/rerender")
def rerender(req: RerenderRequest):
    """AC-10: click a bubble, edit the translation, re-render that page alone.

    Neither detection nor OCR runs on this path, and nothing here re-translates
    -- pipeline.rerender passes allow_retranslate=False, so rung 5 falls
    straight to truncation and issues zero LLM requests. check_spotfix asserts
    both by counter rather than by reading the source.

    A provider client is still accepted and still threaded through, because the
    MODEL is part of the translation file's key: an edit made while pointed at
    one model must land in that model's file and must not leak into another's.
    """
    try:
        record = pipeline.rerender(
            req.job_id, req.item_id, req.ordinal, req.region_id, req.text,
            req.dest_dir, _client(req.settings), req.lang,
        )
    except CacheMiss as e:
        return _cache_miss_response(e)
    except ProviderError as e:
        return _provider_response(e)
    except SettingsError as e:
        return _bad_settings_response(e)
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
