"""An OpenAI-compatible provider stub, in-process, no new dependency.

Replays the hand-authored bodies in fixtures/provider/ and counts what the
client did: peak concurrency and total chat-completion requests. Those two
counters are what check_provider.py's semaphore and batching asserts read.

The 200ms delay lives HERE, not in the caller. A stub that answers instantly
may never put more than one request in flight even with the semaphore removed,
so the concurrency assert would pass against a broken client -- it could not go
red. Owning the delay in one place also stops a later check from quietly
lowering it.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

FIXTURES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "fixtures",
    "provider",
)

REQUEST_DELAY = 0.2  # seconds. See the module docstring before changing this.


class StubProvider:
    """Usable as a context manager; `.url` is the OpenAI-compatible base URL."""

    def __init__(self, status=200, delay=REQUEST_DELAY, models_status=200, replies=None):
        self.status = status  # 200, 401 or 500 -- selects the canned body
        # GET /models answers separately from the chat path, because the
        # Settings dropdown fails on its own: a wrong key is rejected when the
        # user first lists models, long before any page is translated.
        self.models_status = models_status
        # Per-region canned replies, {region_id: text}. Phase 2a's rung-5 gate
        # needs the reply CONTENT to differ per fixture -- one fixture's retry
        # must come back short enough to fit and another's must not -- and the
        # difference between those two branches is the whole of the
        # "the reply is rendered, not merely requested" assert. Default None
        # keeps the echoing behaviour every earlier check was written against.
        self.replies = replies
        self.delay = delay
        self.chat_requests = 0
        self.peak_concurrency = 0
        self._in_flight = 0
        self._lock = threading.Lock()
        self.last_payload = None
        # Every payload, in arrival order. last_payload answers "what did the
        # most recent request carry"; a section asking "did ANY request carry
        # an image" needs all of them.
        self.payloads = []

        stub = self
        fixtures = _load_fixtures()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format, *args):  # noqa: A002 -- base class signature
                pass  # the test prints its own asserts; server noise buries them

            def _respond(self, code, body: bytes, ctype):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.rstrip("/").endswith("/models"):
                    if stub.models_status == 200:
                        self._respond(200, fixtures["models"], "application/json")
                    else:
                        # The provider's own words, verbatim, quotes and all --
                        # what AC-8 promises to carry to the UI unchanged.
                        self._respond(stub.models_status, fixtures["401"],
                                      "application/json")
                else:
                    self._respond(404, b'{"error":"not found"}', "application/json")

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""

                with stub._lock:
                    stub.chat_requests += 1
                    stub._in_flight += 1
                    stub.peak_concurrency = max(stub.peak_concurrency, stub._in_flight)
                    try:
                        stub.last_payload = json.loads(raw or b"{}")
                    except ValueError:
                        stub.last_payload = None
                    stub.payloads.append(stub.last_payload)
                try:
                    if stub.delay:
                        threading.Event().wait(stub.delay)
                    if stub.status == 401:
                        self._respond(401, fixtures["401"], "application/json")
                    elif stub.status == 500:
                        self._respond(500, fixtures["500"], "text/html")
                    else:
                        self._respond(200, _chat_reply(stub.last_payload, stub.replies),
                                      "application/json")
                finally:
                    with stub._lock:
                        stub._in_flight -= 1

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/v1"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def _load_fixtures() -> dict:
    def read(name, mode="rb"):
        with open(os.path.join(FIXTURES, name), mode) as fh:
            return fh.read()

    return {
        "models": read("models_200.json"),
        "401": read("error_401.json"),
        "500": read("error_500.html"),
    }


def requested_items(payload) -> list:
    """The region objects a request asked about, read out of the prompt.

    Parsed from the JSON array after the 'regions ' marker rather than by
    counting '"id"' in the whole prompt: the reply-format template the client
    sends also contains an "id", so counting would report one region too many.

    Returned WHOLE, not reduced to ids, because Phase 2a's rung-5 gate needs the
    `max_chars` each region was capped at. A stub that reads only ids cannot
    see a wrong cap, so a rung 5 that sends the provider a nonsense limit would
    pass every request-count assert.
    """
    texts = []
    if isinstance(payload, dict):
        for msg in payload.get("messages", []):
            content = msg.get("content")
            if isinstance(content, list):
                texts += [p.get("text", "") for p in content if p.get("type") == "text"]
            elif isinstance(content, str):
                texts.append(content)

    for text in texts:
        marker = text.rfind("regions ")
        if marker < 0:
            continue
        try:
            items = json.loads(text[marker + len("regions ") :])
        except ValueError:
            continue
        if isinstance(items, list) and all(isinstance(i, dict) and "id" in i for i in items):
            return items
    return []


def _region_ids(payload) -> list:
    """The ids a request asked about; [0] when the prompt carried none."""
    return [i["id"] for i in requested_items(payload)] or [0]


def _chat_reply(payload, replies=None) -> bytes:
    """Echo one translation per region the request asked about.

    The client batches a whole page into one request, so the reply must carry
    a list -- a stub that always answers with a single string would let a
    one-request-per-bubble client pass the batching assert. Real ids are echoed
    back, so a client that mismaps a split batch onto 0..n cannot pass either.
    """
    ids = _region_ids(payload)
    if replies is not None:
        texts = [replies.get(i, f"STUB {i}") for i in ids]
    else:
        texts = [f"STUB {i}" for i in ids]
    body = json.dumps(
        {"translations": [{"id": i, "text": t} for i, t in zip(ids, texts)]},
        ensure_ascii=False,
    )
    return json.dumps(
        {
            "id": "chatcmpl-stub",
            "object": "chat.completion",
            "model": "stub",
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": body}, "finish_reason": "stop"}
            ],
        }
    ).encode()


def vision_capable(stub, model: str) -> None:
    """Stipulate that (stub.url, model) reads images, so a job does not probe.

    The stub cannot read pixels: it replays canned text. Since US-C-02 a Job
    with a client probes the provider once before its first page and latches
    text-only when the token does not come back -- which, against this stub,
    it never does. That is the product behaving correctly, and it would put
    every job-running section in the suite behind a text-only client and a
    warning they are not about. This seeds the client-side success cache the
    way a real vision-capable endpoint would have, so those sections assert
    what they were written to assert. The probe itself is asserted in
    check_batch's [probe] section, which does NOT call this.
    """
    from sidecar import llm  # noqa: PLC0415

    with llm._VISION_LOCK:
        llm._VISION_OK.add((stub.url, model))
