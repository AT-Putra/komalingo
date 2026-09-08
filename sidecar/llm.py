"""OpenAI-compatible client. Owns the concurrency cap and the error contract.

Three things here are load-bearing and must not be softened:

  * Semaphore(3) is the SINGLE choke point. Every call acquires it. A second
    code path that talks to the provider without acquiring it silently doubles
    the cap the user configured.
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
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field

MAX_CONCURRENT = 3
MAX_REGIONS = 40  # above this a page is split across requests
TIMEOUT = 120


class ProviderError(RuntimeError):
    """Carries the provider's own words to the UI. See AC-8."""

    def __init__(self, status: int, body: str, url: str = ""):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status}: {body}")


@dataclass
class Region:
    id: int
    text: str
    polygon: list = field(default_factory=list)


class LLMClient:
    def __init__(self, base_url: str, api_key: str | None, model: str):
        if not base_url:
            raise ValueError("base_url is required -- it comes from Settings, not a default")
        if not model:
            raise ValueError("model is required -- it comes from Settings, not a default")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""  # optional and may be empty: local servers
        self.model = model
        self._sem = asyncio.Semaphore(MAX_CONCURRENT)
        # Latched only by an observed vision failure, never on by default.
        # A client that starts text-only silently gives up OCR correction.
        self.text_only = False
        self.text_only_reason = ""

    # -- transport ---------------------------------------------------------

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _request(self, path: str, payload=None, method="GET"):
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(url, data, self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            # Read the body BEFORE raising. This is the whole of AC-8: the
            # status alone tells the user nothing actionable.
            body = e.read().decode("utf-8", "replace")
            raise ProviderError(e.code, body, url) from None
        except urllib.error.URLError as e:
            raise ProviderError(0, f"{type(e.reason).__name__}: {e.reason}", url) from None

    async def _call(self, path, payload):
        """The only way out to the provider. Holds the semaphore for the call."""
        async with self._sem:
            return await asyncio.to_thread(self._request, path, payload, "POST")

    # -- model listing -----------------------------------------------------

    def list_models(self) -> list[str]:
        """Every id the provider reports, in the provider's own order.

        No filtering on owned_by. Aggregators report owned_by="combo" for
        their routed models; a client that only accepts known owners hides
        exactly the models this user configured the aggregator to serve.
        """
        data = self._request("/models")
        return [m["id"] for m in data.get("data", []) if m.get("id")]

    # -- translation -------------------------------------------------------

    def _messages(self, regions, page_png: bytes | None):
        instruction = (
            "Translate the Japanese in each region to English. "
            "Reply with JSON: {\"translations\":[{\"id\":<id>,\"text\":<english>}]}. "
            "Use the whole page as context.\n"
            "regions " + json.dumps([{"id": r.id, "text": r.text} for r in regions])
        )
        if page_png and not self.text_only:
            b64 = base64.b64encode(page_png).decode()
            content = [
                {"type": "text", "text": instruction},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]
        else:
            content = instruction
        return [{"role": "user", "content": content}]

    @staticmethod
    def _parse(reply) -> dict:
        raw = reply["choices"][0]["message"]["content"]
        if isinstance(raw, list):  # some providers return content parts
            raw = "".join(p.get("text", "") for p in raw)
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < 0:
            raise ProviderError(200, f"reply was not JSON: {raw[:400]}")
        parsed = json.loads(raw[start : end + 1])
        return {int(t["id"]): t["text"] for t in parsed.get("translations", [])}

    async def translate_page(self, regions, page_png: bytes | None = None) -> dict:
        """All regions of one page. One request unless the page is huge.

        Returns {region_id: english}. Batching is why a 5-bubble page costs one
        request rather than five, and why the model can see bubble 3 when it
        translates bubble 4.
        """
        if not regions:
            return {}

        batches = [regions[i : i + MAX_REGIONS] for i in range(0, len(regions), MAX_REGIONS)]
        payloads = [
            {"model": self.model, "messages": self._messages(b, page_png)} for b in batches
        ]
        replies = await asyncio.gather(
            *(self._call("/chat/completions", p) for p in payloads)
        )

        out = {}
        for reply in replies:
            out.update(self._parse(reply))
        return out

    # -- vision probe ------------------------------------------------------

    async def probe_vision(self, png: bytes, expect: str) -> bool:
        """Ask the model to read a token painted into an image.

        On failure this latches text-only mode with a reason. The latch is
        never set speculatively -- only by an observed failure, so a working
        vision model is never downgraded.
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
                                "url": "data:image/png;base64,"
                                + base64.b64encode(png).decode()
                            },
                        },
                    ],
                }
            ],
        }
        try:
            reply = await self._call("/chat/completions", payload)
            content = reply["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content)
            ok = expect.lower() in content.lower()
        except ProviderError as e:
            ok = False
            content = f"HTTP {e.status}: {e.body[:200]}"

        if not ok:
            self.text_only = True
            self.text_only_reason = f"vision probe failed; expected {expect!r}, got {content!r}"[:400]
        return ok
