"""OpenAI-compatible client. Owns the concurrency cap and the error contract.

Three things here are load-bearing and must not be softened:

  * _GATE, a BoundedSemaphore(3), is the SINGLE choke point. Every request
    acquires it. A second code path that talks to the provider without
    acquiring it silently doubles the cap the user configured.
    It is a THREADING semaphore at module level, not an asyncio one per
    client, since Phase 8: the queue runs items on worker threads and
    pipeline.translate runs asyncio.run per page, so every worker has its own
    event loop -- and an asyncio.Semaphore is bound to whichever loop first
    waits on it. Measured before the change, 8 threads each translating a
    41-region page against the stub: 7 of 8 raised "is bound to a different
    event loop" and the eighth hung forever on a waiter no loop would wake.
    Not 3xN; a crash and a deadlock. The cap is the app's, so the gate is the
    process's: two LLMClients do not get two caps.
  * Batching is per PAGE, not per bubble. One request carries the whole page
    image plus an ordered region list, so the model can use neighbouring
    dialogue as context. Splitting only above MAX_REGIONS.
  * Errors carry HTTP status AND the response body verbatim (AC-8). Replacing
    a provider's 401 body with "connection failed" is the single most expensive
    thing this client could do to a user holding a wrong API key.

Base URL, API key and model are constructor ARGUMENTS with no defaults. There
is deliberately no module-level fallback: a default here would be a credential
hardcoded in the sidecar, which is exactly what the UI settings exist to avoid.
"""

from __future__ import annotations

import asyncio
import base64
import http.client
import io
import json
import os
import random
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field

MAX_CONCURRENT = 3
# The choke point. Acquired in _request, the sync transport every provider
# call goes through, so it holds across threads, loops and client instances.
# Module-level on purpose: see the docstring.
_GATE = threading.BoundedSemaphore(MAX_CONCURRENT)
MAX_REGIONS = 40  # above this a page is split across requests
TIMEOUT = 120

# -- the vision probe (AC-9) -----------------------------------------------
#
# No 0/O, 1/I, 5/S, 8/B or 2/Z. The reply test is an exact substring match,
# so a model that reads O as 0 would fail a probe it in fact passed -- and
# with the full alphabet a 4-char token carried a confusable pair about 73%
# of the time. 32**4 is still ~1.05M tokens.
PROBE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# (base_url, model) pairs a probe has SUCCEEDED against, for this process.
# Successes only. A cached failure would turn one gateway hiccup into
# text-only for every later job until the sidecar restarts, with nothing in
# the UI that could retry it; a failure is re-probed by the next job, which
# costs one request. D.4 asks for the result to be stored per pair and
# invalidated on either change -- keying on the pair is the invalidation.
_VISION_OK: set[tuple[str, str]] = set()
_VISION_LOCK = threading.Lock()


def probe_png(token: str) -> bytes:
    """A PNG with `token` painted large and black on white. No prompt text.

    Built HERE, in the product, and imported by check_probe rather than
    re-painted there: the live gate then exercises the image the app sends,
    not a look-alike. 64px -- PIL's default bitmap font is ~11px and at that
    size the probe measured glyph resolution rather than whether the model
    reads pixels, flipping red and green across runs against a healthy
    endpoint.
    """
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415 -- probe-only

    img = Image.new("RGB", (320, 120), "white")
    ImageDraw.Draw(img).text((20, 20), token, fill="black",
                             font=ImageFont.load_default(size=64))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def probe_token() -> str:
    return "".join(random.choices(PROBE_ALPHABET, k=4))

# Only when the page image travels. A text-only model cannot see whether a
# region is lettering or a hand, and asked anyway it would guess -- and a
# guess of null erases a bubble. The detector (PP-OCR's DBNet, trained on
# documents and street signs) fires on fingers: five parallel strokes, at the
# same confidence as a hand-drawn sound effect, so no threshold separates
# them (measured over five real pages: hands 0.94-0.965, ポッ 0.953, カチャ
# 0.933, dialogue 0.98+). The vision model already looks at the page for
# context; it is the one party that can say "there is nothing written
# there". null, not "": an empty string is a translation that came out empty
# and reaches the page as a visible fit_failed; null is a region that never
# was one, and the pipeline drops it before the inpainter paints over the art.
NOT_TEXT_INSTRUCTION = (
    "If a region's text is not actually written on the page at that spot -- the "
    "detector marked artwork, not lettering -- answer {\"id\":<id>,\"text\":null} "
    "for that region and translate nothing there.\n"
)


def is_null_word(text) -> bool:
    """The instruction's null, written as the STRING "null".

    Measured on a real 32-page job: the model answered `"text":"null"` for 49
    regions and a JSON null for 261 on the same pages. The string is a
    translation as far as the types go, so it was typeset -- the word "null",
    painted into the bubble, on every one of them. Nobody translates a line
    to the English word "null", and the only place that word reaches this
    client from is the instruction above, so it means what the null means.
    """
    return isinstance(text, str) and text.strip().strip("\"'").lower() == "null"

# "At that spot" meant nothing while the spot was not in the request: the
# model got each region's OCR text and had to guess where on the page it was.
# Measured on three hand-labelled real pages, 21 runs per prompt: without
# boxes 13-15 of 47 regions flipped between null and translated from run to
# run -- faces the detector fired on were typeset over on some runs, and a
# real line was dropped on others; with boxes 4-5 of 47 flipped, no dialogue
# was dropped, and the misfires were rejected every time. The cost measured
# one request at a time was about 5 s a page.
BOX_INSTRUCTION = (
    "Each region's box is [x0,y0,x1,y1] in thousandths of the page's width and "
    "height, from the top-left corner.\n"
)

# Phase 5: the prompt is ASSEMBLED from the job's source and target rather
# than hardcoding "Japanese to English". The names are what the model reads;
# the codes are what the pipeline, the cache and the API carry.
SOURCE_NAMES = {"ja": "Japanese", "zh": "Chinese", "ko": "Korean"}
TARGET_NAMES = {"en": "English", "id": "Indonesian"}

# Per-target glossary files, quoted into the prompt as data. Indonesian is
# the only one today; a second target adds a file and a line here, not prose
# in _messages. The rules themselves live in the JSON (and docs/honorifics.md
# states them for a reader) so check_id can grade the output against the
# same table the model was shown.
GLOSSARIES = {"id": os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary_id.json")}
_GLOSSARY_CACHE: dict[str, str] = {}


def glossary_text(lang: str) -> str:
    """The glossary block for `lang`, or "" when the target has none."""
    path = GLOSSARIES.get(lang)
    if not path:
        return ""
    if lang not in _GLOSSARY_CACHE:
        with open(path, encoding="utf-8") as fh:
            g = json.load(fh)
        lines = ["Rules:"] + [f"- {rule}" for rule in g["policy"]]
        lines.append("Honorifics, source -> rendering: "
                     + "; ".join(f"{h['ja']} -> {h['id']}" for h in g["honorifics"]))
        lines.append("Terms, source -> rendering: "
                     + "; ".join(f"{t['ja']} -> {t['id']}" for t in g["terms"]))
        lines.append("Keep as they are: " + ", ".join(g["keep"]))
        _GLOSSARY_CACHE[lang] = "\n".join(lines) + "\n"
    return _GLOSSARY_CACHE[lang]


class SettingsError(ValueError):
    """The configured settings cannot be used. Not the provider's fault.

    A ValueError subclass on purpose: every caller that already handles the
    "base_url is required" ValueError keeps working unchanged. The named type
    exists so /api/translate can catch THIS and not every ValueError raised
    anywhere inside a page run -- a decode failure deep in the pipeline is our
    bug and belongs in a 500, while a mistyped port belongs in a 400 the user
    can act on. One `except ValueError` around the whole run would report both
    as the second.
    """


class ProviderError(RuntimeError):
    """Carries the provider's own words to the UI. See AC-8."""

    def __init__(self, status: int, body: str, url: str = ""):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status}: {body}")

    @property
    def transient(self) -> bool:
        """Whether the same request, sent again, has a real chance.

        0 is the transport: a timeout, a reset, a refused connection. 200 is
        a reply that arrived and was unusable -- cut off mid-JSON, an error
        event inside a stream, a proxy's login page. 408 and 429 and every
        5xx are the provider saying "not now". A 401 or a 400 is the REQUEST
        that is wrong, and a second copy of it is wrong the same way.
        """
        return self.status in (0, 200, 408, 429) or self.status >= 500


def _timed_out() -> str:
    """The body of a timeout ProviderError. socket's own text is "timed out",
    which tells the user nothing they can act on; the number of seconds does."""
    return f"TimeoutError: the provider sent no complete reply within {TIMEOUT}s"


def _decode_reply(raw: bytes, content_type: str, status: int, url: str):
    """A 2xx body as the dict the OpenAI shape describes, or a ProviderError.

    Two framings arrive with a success status. The ordinary one is a single
    JSON object. The other is text/event-stream: measured on a gateway model
    (ag/gemini-pro-agent) that streamed a reply the request never asked to
    stream -- a `data:` line per chunk, then `data: [DONE]`. json.loads on that
    raised JSONDecodeError, which is neither a ProviderError nor a
    SettingsError, so /api/translate answered a bare 500 and the user learned
    nothing. The stream is reassembled into the chat.completion it stands for.

    Anything else with a 2xx status -- a proxy's login page, an empty body --
    is a ProviderError carrying the body, so AC-8 holds: the caller sees what
    the provider actually sent, not a traceback.
    """
    text = raw.decode("utf-8", "replace")
    if "text/event-stream" in content_type.lower() or text.lstrip().startswith("data:"):
        return _from_event_stream(text, status, url)
    try:
        return json.loads(text)
    except ValueError:
        raise ProviderError(status, f"reply was not JSON: {text[:400]}", url) from None


def _from_event_stream(text: str, status: int, url: str) -> dict:
    """Concatenate the chunks of choice 0 into one chat.completion.

    `delta` is the streaming field and `message` what some gateways put in a
    single-event stream; content may be a string or a list of parts, as in
    the non-streaming shape. An `error` event is the provider refusing
    mid-stream and is raised in its own words.
    """
    parts, finish, meta, events = [], None, {}, 0
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue  # blank separators, `event:` and `: keep-alive` comments
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            raise ProviderError(status, f"stream event was not JSON: {data[:400]}", url) from None
        events += 1
        if chunk.get("error"):
            raise ProviderError(status, json.dumps(chunk["error"], ensure_ascii=False), url)
        meta = meta or {k: chunk[k] for k in ("id", "model") if k in chunk}
        for choice in chunk.get("choices") or []:
            if choice.get("index", 0) != 0:
                continue
            piece = (choice.get("delta") or choice.get("message") or {}).get("content")
            if isinstance(piece, list):
                piece = "".join(p.get("text", "") for p in piece if isinstance(p, dict))
            if isinstance(piece, str):
                parts.append(piece)
            finish = choice.get("finish_reason") or finish
    if not events:
        raise ProviderError(status, f"reply was an empty event stream: {text[:400]}", url)
    return dict(meta, object="chat.completion", choices=[
        {"index": 0, "message": {"role": "assistant", "content": "".join(parts)},
         "finish_reason": finish}])


def image_data_url(data: bytes) -> str:
    """A data URL whose media type is what the bytes ARE, by signature.

    The page context is JPEG and the probe image is PNG; a data URL that
    called both image/png would hand a provider that trusts the label a JPEG
    it decodes as a PNG.
    """
    mime = "image/jpeg" if data[:3] == b"\xff\xd8\xff" else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


@dataclass
class Region:
    id: int
    text: str
    polygon: list = field(default_factory=list)
    # [x0, y0, x1, y1] in thousandths of the page (see BOX_INSTRUCTION). Sent
    # only with the page image: a text-only model has no page to place it on.
    box: list | None = None


class LLMClient:
    def __init__(self, base_url: str, api_key: str | None, model: str):
        if not base_url:
            raise SettingsError("base_url is required -- it comes from Settings, not a default")
        if not model:
            raise SettingsError("model is required -- it comes from Settings, not a default")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""  # optional and may be empty: local servers
        self.model = model
        # Latched only by an observed vision failure, never on by default.
        # A client that starts text-only silently gives up OCR correction.
        self.text_only = False
        self.text_only_reason = ""
        # Why the last probe could not run, when it could not. Distinct from
        # text_only_reason: one says "this model cannot read images", the
        # other says "nobody found out".
        self.probe_error = ""

    # -- transport ---------------------------------------------------------

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request(self, path: str, payload=None, method="GET"):
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        try:
            req = urllib.request.Request(url, data, self._headers(), method=method)
        except ValueError as e:
            # A base_url with no scheme lands here: urllib formats the url with
            # %r into "unknown url type: 'nas/v1/models'". Raised at REQUEST
            # construction, outside the transport try below, so it needs its
            # own handler -- and it must arrive as SettingsError so a page run
            # can tell it apart from a ValueError raised by the pipeline.
            raise SettingsError(f"invalid base URL {url!r}: {e}") from None
        try:
            with _GATE:
                try:
                    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                        return _decode_reply(r.read(), r.headers.get("Content-Type", ""),
                                             r.status, url)
                except urllib.error.HTTPError as e:
                    # Read the body BEFORE raising -- and inside the gate,
                    # so the whole exchange, error body included, is one
                    # held slot. This is the whole of AC-8: the status
                    # alone tells the user nothing actionable.
                    body = e.read().decode("utf-8", "replace")
                    raise ProviderError(e.code, body, url) from None
        except urllib.error.URLError as e:
            if isinstance(e.reason, TimeoutError):
                raise ProviderError(0, _timed_out(), url) from None
            raise ProviderError(0, f"{type(e.reason).__name__}: {e.reason}", url) from None
        except TimeoutError:
            # urlopen wraps a timeout it hits while CONNECTING in URLError,
            # caught above. A timeout during r.read() -- headers arrived, then
            # the body stalled -- is the bare socket.timeout, which is neither
            # a URLError nor an HTTPException, so it walked out of this
            # function as "TimeoutError: timed out" and /api/translate
            # answered 500 "internal error" with a 40-frame traceback.
            # Measured 2026-09-15 on a gateway that sent status 200 and then
            # stopped. The user's provider stalled; that is a 502 in the
            # provider's words, not a bug in the sidecar.
            raise ProviderError(0, _timed_out(), url) from None
        except ConnectionError as e:
            # Same seam: a reset or a dropped connection mid-body is an
            # OSError that urllib does not wrap once urlopen has returned.
            raise ProviderError(0, f"{type(e).__name__}: {e}", url) from None
        except http.client.InvalidURL as e:
            # The two errors this module raises say different things, and a
            # malformed base URL belongs on the ValueError side: nothing is
            # wrong with the provider, the SETTINGS are unusable. __init__
            # already speaks that dialect for a missing base_url, so main.py's
            # 400 handler is already listening for it.
            #
            # Caught HERE because InvalidURL is not a ValueError -- it descends
            # from HTTPException, so `except ValueError` at the HTTP boundary
            # walked straight past it, and "localhost:por/v1" (one typo in the
            # port) went unhandled. Which cost more than a 500: measured, the
            # sidecar stayed alive and stopped answering. See US-P1-11.
            raise SettingsError(f"invalid base URL {url!r}: {e}") from None
        except http.client.HTTPException as e:
            # Everything else under HTTPException is the provider breaking
            # protocol mid-conversation -- BadStatusLine, IncompleteRead, a
            # RemoteDisconnected that urllib did not wrap. Status 0 because no
            # HTTP status ever arrived; the class name is the only fact there
            # is, and AC-8 says the caller gets that rather than a synonym.
            raise ProviderError(0, f"{type(e).__name__}: {e}", url) from None

    async def _call(self, path, payload):
        """The only way out to the provider. _request holds the gate for the
        call, on the thread that makes it; the loop is free meanwhile."""
        return await asyncio.to_thread(self._request, path, payload, "POST")

    # -- model listing -----------------------------------------------------

    def list_models(self) -> list[dict]:
        """Every model the provider reports, in the provider's own order, as
        {"id", "owned_by"} -- the shape the Settings combobox renders.

        No filtering on owned_by. Aggregators report owned_by="combo" for
        their routed models; a client that only accepts known owners hides
        exactly the models this user configured the aggregator to serve. The
        owner travels because it is what tells two similarly named ids apart
        in an aggregator's list.

        Objects, not bare ids: the UI typed this as objects from the start
        while this returned strings, and the first component to read `.id`
        off a string took the whole window down with it. check_api pins the
        shape at the HTTP boundary now.
        """
        data = self._request("/models")
        out = []
        for m in data.get("data", []):
            if not isinstance(m, dict) or not isinstance(m.get("id"), str) or not m["id"]:
                continue
            owner = m.get("owned_by")
            out.append({"id": m["id"], "owned_by": owner if isinstance(owner, str) else ""})
        return out

    # -- translation -------------------------------------------------------

    def _messages(self, regions, page_image: bytes | None, lang: str = "en", source: str = "ja"):
        if lang not in TARGET_NAMES:
            raise SettingsError(f"target language {lang!r} is not one of {sorted(TARGET_NAMES)}")
        if source not in SOURCE_NAMES:
            raise SettingsError(f"source language {source!r} is not one of {sorted(SOURCE_NAMES)}")
        target = TARGET_NAMES[lang]
        with_image = bool(page_image) and not self.text_only
        # The glossary sits between the instruction and the regions, and the
        # regions stay LAST: the stub provider and check_id read the request
        # back from the text after the final "regions " marker.
        boxes = with_image and any(r.box for r in regions)
        listed = [{"id": r.id, "text": r.text, **({"box": r.box} if boxes and r.box else {})}
                  for r in regions]
        instruction = (
            f"Translate the {SOURCE_NAMES[source]} in each region to {target}. "
            f"Reply with JSON: {{\"translations\":[{{\"id\":<id>,\"text\":<{target.lower()}>}}]}}. "
            "Use the whole page as context.\n"
            + (NOT_TEXT_INSTRUCTION if with_image else "")
            + (BOX_INSTRUCTION if boxes else "")
            + glossary_text(lang)
            + "regions " + json.dumps(listed, ensure_ascii=False)
        )
        if with_image:
            content = [
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": image_data_url(page_image)}},
            ]
        else:
            content = instruction
        return [{"role": "user", "content": content}]

    @staticmethod
    def _parse(reply) -> dict:
        """{region_id: text}. A JSON null stays None -- see NOT_TEXT_INSTRUCTION.

        None and "" are different answers and must stay different: None is
        "there is no text there", "" is "I translated it to nothing", and the
        pipeline drops the first before inpaint while the second reaches the
        page as a visible fit_failed. Anything that is not a string or null
        is treated as "" rather than raising -- a provider that answers with a
        number for one region does not get to fail the page. The string
        "null" is the null -- see is_null_word.
        """
        choice = reply["choices"][0]
        raw = choice["message"]["content"]
        if isinstance(raw, list):  # some providers return content parts
            raw = "".join(p.get("text", "") for p in raw)
        if not isinstance(raw, str):
            raw = "" if raw is None else str(raw)
        # A reply the provider cut off is the common way to get here, and
        # finish_reason says so: "length" is the provider's token cap, and
        # measured 2026-09-15 a gateway returned status 200 with the content
        # ending at `{"translations":[{"id":1,"text":"`. Which brace survived
        # the cut decides whether the slice below is missing (no "}" at all)
        # or present but unparseable ({"id":1,"text":"hi"},{"id":2,"text":"
        # keeps region 1's brace) -- and the second used to escape as a
        # JSONDecodeError, a bare 500. Both are the same fact about the
        # provider, so both are one ProviderError carrying the fragment.
        start, end = raw.find("{"), raw.rfind("}")
        try:
            if start < 0 or end < start:
                raise ValueError("no JSON object in the reply")
            parsed = json.loads(raw[start : end + 1])
        except ValueError:
            reason = choice.get("finish_reason")
            cut = (" (cut off: finish_reason=length, the provider's token limit)"
                   if reason == "length" else
                   f" (finish_reason={reason})" if reason and reason != "stop" else "")
            raise ProviderError(200, f"reply was not JSON{cut}: {raw[:400]}") from None
        if not isinstance(parsed, dict):
            raise ProviderError(200, f"reply was JSON but not an object: {raw[:400]}")
        out = {}
        for t in parsed.get("translations", []):
            text = t.get("text", "")
            if is_null_word(text):
                text = None
            out[int(t["id"])] = text if text is None or isinstance(text, str) else ""
        return out

    async def translate_page(self, regions, page_image: bytes | None = None, *,
                             lang: str = "en", source: str = "ja") -> dict:
        """All regions of one page. One request unless the page is huge.

        Returns {region_id: text in `lang`}. Batching is why a 5-bubble page
        costs one request rather than five, and why the model can see bubble 3
        when it translates bubble 4. `source` names the language the OCR read
        and `lang` the one the reader wants; both go into the instruction.
        """
        if not regions:
            return {}

        batches = [regions[i : i + MAX_REGIONS] for i in range(0, len(regions), MAX_REGIONS)]
        payloads = [
            {"model": self.model, "messages": self._messages(b, page_image, lang, source)}
            for b in batches
        ]
        replies = await asyncio.gather(
            *(self._call("/chat/completions", p) for p in payloads)
        )

        out = {}
        for reply in replies:
            out.update(self._parse(reply))
        return out

    async def retranslate_capped(self, items) -> dict:
        """Rung 5's length-capped retry. ONE request for every capped region.

        `items` is [(region_id, english, max_chars)]. The cap is per region and
        computed by typeset.py from the polygon's fitted capacity, so it is
        carried per item rather than as one number for the page -- a page's
        bubbles do not share a capacity.

        Batched for the same reason translate_page is: a page of hard bubbles
        must cost ONE extra request, not one per bubble. It goes through _call
        like everything else, so it acquires the same gate; a shortcut
        straight to _request here would silently double the cap the user set.
        """
        if not items:
            return {}
        # Language-neutral on purpose: the text may be English or Indonesian,
        # and "each English text" once told the model to switch languages on
        # an Indonesian page.
        instruction = (
            "Rewrite each text to the SAME MEANING in at most max_chars characters, "
            "in the same language the text is already in. Do not translate to "
            "another language; do not add notes. "
            "Reply with JSON: {\"translations\":[{\"id\":<id>,\"text\":<shorter>}]}.\n"
            "regions "
            + json.dumps(
                [{"id": i, "text": t, "max_chars": n} for i, t, n in items],
                ensure_ascii=False,
            )
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": instruction}],
        }
        return self._parse(await self._call("/chat/completions", payload))

    # -- vision probe ------------------------------------------------------

    # Statuses that are EVIDENCE the model cannot take an image: the request
    # was understood and the image part was refused. Everything else -- 0
    # (unreachable), 401/403 (a key problem, not a vision one), 408, 429, 5xx
    # -- says nothing about vision and must not latch: a 429 on the one probe
    # request would otherwise put a 200-page job text-only and write every
    # page's translation into the cache under a key that does not record it,
    # so a later vision-capable run hits those pages and never sends the image.
    # Loud beats silent here: an unlatched client whose provider is really
    # down fails each item with the provider's own body (AC-8), which the user
    # can read; a wrongly latched one degrades every page and says so once.
    _IMAGE_REFUSED = (400, 413, 415, 422)

    async def probe_vision(self, png: bytes, expect: str) -> bool:
        """Ask the model to read a token painted into an image.

        Latches text-only ONLY on evidence of a text-only model: a reply that
        was produced and does not contain the token, or a status that says
        the image part was refused (_IMAGE_REFUSED). A probe that could not
        run -- unreachable, rate-limited, a proxy answering 200 with HTML, an
        empty choices list -- returns False WITHOUT latching and records why
        in `probe_error`, so the caller can warn "the probe could not run"
        rather than "the model is text-only". The latch is never speculative.
        """
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Reply with only the text in this image."},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url(png)
                            },
                        },
                    ],
                }
            ],
        }
        self.probe_error = ""
        try:
            reply = await self._call("/chat/completions", payload)
        except ProviderError as e:
            if e.status in self._IMAGE_REFUSED:
                self.text_only = True
                self.text_only_reason = (
                    f"vision probe failed; the image part was refused "
                    f"(HTTP {e.status}: {e.body[:200]!r})"
                )[:400]
            else:
                self.probe_error = f"vision probe could not run (HTTP {e.status}: {e.body[:200]!r})"[:400]
            return False
        except (SettingsError, ValueError) as e:
            # A base URL without a scheme, or a 200 whose body is not JSON (a
            # captive portal, a proxy error page). Neither is a fact about the
            # model. Until this branch existed either one escaped the probe
            # entirely and, called from a worker thread, killed the worker.
            self.probe_error = f"vision probe could not run ({type(e).__name__}: {str(e)[:200]})"[:400]
            return False

        try:
            content = reply["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content)
            if not isinstance(content, str):
                raise TypeError(f"content is {type(content).__name__}")
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            self.probe_error = (f"vision probe could not run (unexpected reply shape: "
                                f"{type(e).__name__}: {e})")[:400]
            return False

        if expect.lower() in content.lower():
            return True
        self.text_only = True
        self.text_only_reason = f"vision probe failed; expected {expect!r}, got {content!r}"[:400]
        return False

    def ensure_vision(self) -> tuple[bool, str]:
        """Probe once per (base_url, model) per process; latch on evidence.

        The call the product was missing. probe_vision existed and text_only
        was honoured in translate_page, but nothing outside check_probe ever
        ran the probe -- so a text-only model was never detected in the app
        and every page went out with an image the provider could not read.
        Job._ensure_vision calls this on the first worker before any item is
        claimed; /api/item and /api/translate call it after building their
        client, because the image is sent on every route and a route that
        never probed would send it blind.

        Returns (ok, reason). A latched client returns its existing reason
        without a request; a pair cached as vision-capable returns True
        without a request; a probe that could not run returns False with
        probe_error and does NOT latch -- the next call tries again.
        """
        if self.text_only:
            return False, self.text_only_reason
        key = (self.base_url, self.model)
        with _VISION_LOCK:
            if key in _VISION_OK:
                return True, ""
        token = probe_token()
        ok = asyncio.run(self.probe_vision(probe_png(token), token))
        if ok:
            with _VISION_LOCK:
                _VISION_OK.add(key)
            return True, ""
        return False, self.text_only_reason or self.probe_error
