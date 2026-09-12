"""Phase 0 -- the probe that touches a LIVE endpoint (US-012).

Only this file talks to a live endpoint. All other checks run against the
stub server in tests/lib/stub_provider.py. This one must read MT_BASE_URL,
MT_API_KEY, MT_MODEL from .env.local (git-ignored, loaded by lib.env_local --
the real environment wins over the file) or die with exit 3.

The probe paints a random 4-char token into an image and asserts it returns
in the reply. A forced-failure probe must latch text-only mode. The translate
route on fixtures/smoke/tategaki_01.png must change pixels inside a polygon.

Exit contract: 0 pass, 1 fail, 2 inconclusive, 3 skip (named reason).
MT_REQUIRE_LIVE=1 promotes skip to 1.

Run: uv run --project sidecar python tests/check_probe.py
"""

import base64
import json
import os
import random
import sys
import asyncio
import urllib.error
import urllib.request


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "lib"))

from lib.env_local import load_env_local
from lib.result import Checks, run, skip

load_env_local()

BASE = os.environ.get("MT_BASE_URL", "").rstrip("/")
KEY = os.environ.get("MT_API_KEY", "")
MODEL = os.environ.get("MT_MODEL", "")

if not BASE or not MODEL:
    # live=True: this is the skip MT_REQUIRE_LIVE exists for. The inline copy
    # that used to live here read the variable as a non-empty string, so the
    # MT_REQUIRE_LIVE=0 that section E tells CI to set promoted the skip
    # instead of suppressing the promotion. One contract, in lib/result.py.
    sys.exit(skip(
        f"MT_BASE_URL and MT_MODEL must both be set "
        f"(got BASE={bool(BASE)} MODEL={bool(MODEL)})",
        live=True,
    ))


def post(path, payload=None):
    """Return (status, body) -- never raise on HTTP error."""
    req = urllib.request.Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            **({"Authorization": f"Bearer {KEY}"} if KEY else {}),
        },
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # AC-8: status AND body verbatim.
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return 0, f"{type(e.reason).__name__}: {e.reason}"


# The alphabet and the image are the PRODUCT's, imported rather than
# re-painted here. Until the job path was wired (US-C-02) this file painted
# its own token and the app painted nothing, so the gate exercised a picture
# the app never sent. Now sidecar.llm owns both and Job._ensure_vision sends
# the same bytes this check does.
from sidecar.llm import PROBE_ALPHABET as ALPHABET, probe_png  # noqa: E402


def redact(text):
    """Never echo the live key, whatever the gateway reflected back."""
    return text.replace(KEY, "***") if KEY else text


def attempt():
    tok = "".join(random.choices(ALPHABET, k=4))
    payload = {
        "model": MODEL,
        "max_tokens": 32,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Reply with only the characters written in this image."},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,"
                                                     + base64.b64encode(probe_png(tok)).decode()}},
            ],
        }],
    }
    status, body = post("/chat/completions", payload)
    if status != 200:
        print(f"  http {status}: {redact(body)[:300]!r}")
        return False
    try:
        reply = json.loads(body)["choices"][0]["message"]["content"]
        if isinstance(reply, list):
            reply = "".join(p.get("text", "") for p in reply)
    except (KeyError, IndexError, ValueError, TypeError) as e:
        print(f"  unparseable 200: {type(e).__name__}: {redact(body)[:300]!r}")
        return False
    hit = tok.lower() in reply.lower()
    print(f"  token {tok} {'FOUND' if hit else 'absent'} in {reply.strip()[:80]!r}")
    return hit


def main():
    c = Checks("check_probe")

    # Assert 1: live endpoint
    status, body = post("/models")
    if status != 200:
        c.check(False, f"GET /models -> {status}: {redact(body)[:300]!r}")
        return c.finish()
    try:
        data = json.loads(body)
        models = data.get("data", [])
        ids = [m.get("id") for m in models]
        combos = [m.get("id") for m in models if m.get("owned_by") == "combo"]
        c.check(MODEL in ids, f"MT_MODEL={MODEL!r} is selectable (found {len(ids)} models)")
        c.check(combos, f"at least one combo model (found {len(combos)})")
    except Exception as e:
        c.check(False, f"unparseable /models: {e}")

    # Assert 2: random token painted into image and returned
    hit = attempt()
    c.check(hit, "token appears in reply")
    if not hit:
        return c.finish()

    # Assert 3: a FORCED-FAILURE vision probe latches text-only mode.
    #
    # The previous version of this assert sent a valid request and asserted the
    # token was ABSENT -- which goes red against a healthy endpoint, and green
    # when vision is broken. Backwards. What is being tested is the LATCH: an
    # observed vision failure must turn text_only on and record why, and it
    # must never be on speculatively.
    #
    # The failure is forced by asking for a token that was never painted, so
    # the endpoint is real, the reply is real, and only the expectation is
    # impossible.
    from sidecar.llm import LLMClient

    client = LLMClient(BASE, KEY, MODEL)
    c.check(not client.text_only, "a fresh client is NOT text-only (the latch is never speculative)")

    absent = "".join(random.choices(ALPHABET, k=8))
    painted = "".join(random.choices(ALPHABET, k=4))
    png = probe_png(painted)

    ok = asyncio.run(client.probe_vision(png, absent))
    c.check(not ok, f"a probe for text that is not in the image fails ({painted!r} painted, {absent!r} demanded)")
    c.check(client.text_only, "and that observed failure LATCHES text-only mode")
    c.check(
        absent in client.text_only_reason,
        f"with a reason naming what was expected ({client.text_only_reason[:120]!r})",
    )

    # The positive half: the same probe against the token actually painted must
    # succeed and leave the latch alone. Without this, a client hardwired to
    # return False would pass every assert above.
    fresh = LLMClient(BASE, KEY, MODEL)
    hit = asyncio.run(fresh.probe_vision(png, painted))
    c.check(hit, f"the same probe SUCCEEDS for the token actually painted ({painted!r})")
    c.check(not fresh.text_only, "and a successful probe leaves text-only off")

    # Assert 6: the LIVE model translates the page, and the result lands in
    # the pipeline's own output.
    #
    # Note on scope. Phase 0's ocr() is a placeholder that returns a fixed
    # string and reads nothing from the image, so there is no OCR round-trip
    # to assert here -- assert 2 above is what proves the model can read
    # pixels. What this asserts is the half that IS wired: the live client
    # reaches run_page, and its reply replaces the offline placeholder.
    SMOKE = os.path.join(ROOT, "fixtures", "smoke", "tategaki_01.png")
    if not os.path.exists(SMOKE):
        c.check(False, f"smoke image missing: {SMOKE}")
        return c.finish()

    from sidecar.llm import LLMClient
    from sidecar import pipeline

    dest = os.path.join(ROOT, "build", "work", "probe-out")
    live = LLMClient(BASE, KEY, MODEL)
    try:
        rec = pipeline.run_page(SMOKE, dest, 1, live)
    except Exception as e:
        c.check(False, f"run_page with the LIVE client raised {type(e).__name__}: {e}")
        return c.finish()

    regions = rec.get("regions", [])
    c.check(bool(regions), f"the live run produced regions ({len(regions)})")

    translations = [r.get("translation", "") for r in regions]
    c.check(
        all(t.strip() for t in translations),
        f"every region has a non-empty translation ({translations!r})",
    )
    # "HELLO" is pipeline.py's offline placeholder. Seeing it here means the
    # client never reached the provider and the run proved nothing -- which is
    # exactly the false green this assert exists to catch.
    c.check(
        not any(t.strip() == "HELLO" for t in translations),
        f"and none of them is the offline placeholder 'HELLO' ({translations!r})",
    )
    c.check(
        any(v > 0 for v in rec.get("pixels_changed_in_polygon", {}).values()),
        f"pixels changed inside a polygon ({rec.get('pixels_changed_in_polygon')})",
    )

    return c.finish()


run(main)
