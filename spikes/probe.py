#!/usr/bin/env python3
"""Phase 0a spike: does the endpoint actually pass images through?

Freezes the translate call signature before any plumbing is written against it.

    set MT_BASE_URL=http://localhost:20128/v1
    set MT_API_KEY=              (may be empty -- 9router REQUIRE_API_KEY defaults false)
    set MT_MODEL=some/vision-model
    uv run python spikes/probe.py

Exit 0 pass, 1 fail, 3 skip (env absent). Section C row 4: the token is rendered
INTO the image and never appears in the prompt text, so a route that drops the
image part cannot echo it back. 3 attempts, majority wins; on a tie we report
"unconfirmed" and default to text-only rather than claiming failure.
"""

import base64
import io
import json
import os
import random
import string
import sys
import urllib.error
import urllib.request

from PIL import Image, ImageDraw

BASE = os.environ.get("MT_BASE_URL", "").rstrip("/")
KEY = os.environ.get("MT_API_KEY", "")
MODEL = os.environ.get("MT_MODEL", "")

if not BASE or not MODEL:
    print("SKIP: MT_BASE_URL and MT_MODEL must both be set")
    sys.exit(3)


def post(path, payload=None):
    req = urllib.request.Request(
        BASE + path,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={"Content-Type": "application/json",
                 **({"Authorization": "Bearer " + KEY} if KEY else {})},
        method="GET" if payload is None else "POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # AC-8: status AND body, verbatim. Never a generic string.
        return e.code, e.read().decode("utf-8", "replace")


def token_image(tok):
    """A 4-char token painted large and black on white. No prompt text carries it."""
    img = Image.new("RGB", (320, 120), "white")
    ImageDraw.Draw(img).text((20, 40), tok, fill="black")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def attempt():
    tok = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    status, body = post("/chat/completions", {
        "model": MODEL,
        "max_tokens": 32,
        "temperature": 0,
        "messages": [{"role": "user", "content": [
            {"type": "text",
             "text": "Reply with only the characters written in this image."},
            {"type": "image_url",
             "image_url": {"url": "data:image/png;base64," + token_image(tok)}},
        ]}],
    })
    if status != 200:
        print(f"  http {status}: {body[:300]}")
        return False
    try:
        reply = json.loads(body)["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError, TypeError) as e:
        print(f"  unparseable 200: {type(e).__name__}: {body[:300]}")
        return False
    hit = tok.lower() in reply.lower()
    print(f"  token {tok} {'FOUND' if hit else 'absent'} in {reply.strip()[:80]!r}")
    return hit


status, body = post("/models")
if status != 200:
    print(f"FAIL: GET /models -> {status}: {body[:300]}")
    sys.exit(1)
ids = [m.get("id") for m in json.loads(body).get("data", [])]
combos = [m.get("id") for m in json.loads(body).get("data", [])
          if m.get("owned_by") == "combo"]
print(f"GET /models -> {len(ids)} models, {len(combos)} owned_by=combo")
if MODEL not in ids:
    print(f"FAIL: MT_MODEL={MODEL!r} not in the returned list")
    sys.exit(1)

hits = sum(attempt() for _ in range(3))
print(f"vision passthrough: {hits}/3")
if hits >= 2:
    print("PASS: vision confirmed, hybrid mode (OCR text + page image) is live")
    sys.exit(0)
if hits == 0:
    print("FAIL: image part dropped on every attempt -- latch text-only mode")
    sys.exit(1)
print("UNCONFIRMED: 1/3 -- default to text-only, do not claim failure (Section C row 4)")
sys.exit(1)
