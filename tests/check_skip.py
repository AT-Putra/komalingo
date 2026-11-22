"""A refused page is skipped, not the end of the chapter. Fully OFFLINE.

The plan is .omc/plans/skip-pages-and-ux.md. One section per promise:

  [kinds]   every provider failure is sorted into account / refused /
            rejected / outage / bad_reply, by status and the provider's
            error object -- never by text the model or the user wrote.

Later sections (skip, pause, resume, retry) are added with the code they
hold to. Everything here runs against tests/lib/stub_provider or against
the client's pure functions; no network.
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from sidecar import llm  # noqa: E402
from sidecar.llm import LLMClient, ProviderError, Region  # noqa: E402
from lib.result import Checks, run  # noqa: E402
from lib.stub_provider import StubProvider  # noqa: E402

MODEL = "stub/model"  # a fixture id, not a configured default


def _reply(content, finish="stop", **message_extra):
    """A chat.completion with one choice, the shape _parse reads."""
    return {"id": "x", "object": "chat.completion", "choices": [
        {"index": 0, "finish_reason": finish,
         "message": dict({"role": "assistant", "content": content}, **message_extra)}]}


def _parse_kind(reply):
    """The kind _parse raises for `reply`, or "ok" when it parses, or the
    name of any OTHER exception -- which is the bug [kinds] exists to catch."""
    try:
        LLMClient._parse(reply)
        return "ok"
    except ProviderError as e:
        return e.kind
    except Exception as e:  # noqa: BLE001 -- reported, not hidden
        return f"raised {type(e).__name__}"


def kinds(c: Checks) -> None:
    """[kinds] status + the provider's error object decide; reply text never does."""
    err = lambda obj: json.dumps({"error": obj})  # noqa: E731

    table = [
        # (status, body, kind, why)
        (401, err({"message": "Incorrect API key provided", "code": "invalid_api_key"}),
         "account", "a 401 is the key"),
        (400, err({"code": 400, "message": "API key not valid. Please pass a valid API key.",
                   "status": "INVALID_ARGUMENT", "details": [{"reason": "API_KEY_INVALID"}]}),
         "account", "Gemini answers a bad key with 400 API_KEY_INVALID"),
        (402, err({"message": "Insufficient credits"}), "account", "402 is billing"),
        (429, err({"message": "You exceeded your current quota, please check your plan and "
                              "billing details.", "type": "insufficient_quota",
                   "code": "insufficient_quota"}),
         "account", "insufficient_quota is an empty account, not a busy minute"),
        (429, err({"code": 429, "message": "Quota exceeded for quota metric 'Generate Content "
                                           "API requests per minute'",
                   "status": "RESOURCE_EXHAUSTED"}),
         "outage", "Gemini's per-minute quota is a busy minute"),
        (403, err({"code": 403, "message": "Your chosen model requires moderation and your "
                                           "input was flagged",
                   "metadata": {"reasons": ["violence"],
                                "flagged_input": "Credits: billing by the scanlation team"}}),
         "refused", "OpenRouter's moderation 403, even when the echoed input says 'Credits'"),
        (403, err({"code": 403, "message": "Key limit exceeded"}),
         "account", "OpenRouter's budget 403"),
        (400, err({"message": "The response was filtered due to the prompt triggering Azure "
                              "OpenAI's content management policy.", "code": "content_filter"}),
         "refused", "Azure's content_filter 400"),
        (400, err({"message": "Invalid image data"}), "rejected",
         "any other 400 is this request, not the account and not a moment"),
        (404, err({"message": "The model `nope` does not exist"}), "account",
         "a missing model fails every page"),
        (500, "<html><body>Internal Server Error</body></html>", "outage", "a 5xx is a moment"),
        (408, "", "outage", "a 408 is a moment"),
    ]
    for status, body, want, why in table:
        got = llm.error_kind(status, body)
        c.check(got == want, f"[kinds] {status} -> {want}: {why} (got {got})")

    # 200 replies: structured fields only.
    c.check(_parse_kind(_reply(None, finish="content_filter")) == "refused",
            "[kinds] finish_reason=content_filter with no content is a refusal, not a KeyError")
    c.check(_parse_kind(_reply("", finish="SAFETY")) == "refused",
            "[kinds] finish_reason=SAFETY (Gemini via OpenAI-compat) is a refusal")
    c.check(_parse_kind(_reply(None, refusal="I can't help with that.")) == "refused",
            "[kinds] a non-empty message.refusal is a refusal")
    c.check(_parse_kind(_reply("Credits: translated by the scanlation team. Billing inquiries "
                               "to the editor.")) == "bad_reply",
            "[kinds] a prose 200 that says 'Credits' and 'Billing' is a bad reply, never an "
            "account problem: reply text is not read for words")
    c.check(_parse_kind(_reply('{"translations":[{"id":1,"text":"Safety first, kid'
                               , finish="length")) == "bad_reply",
            "[kinds] a cut-off reply that happens to say 'Safety' is a bad reply, not a refusal")
    c.check(_parse_kind({"error": {"message": "upstream timed out", "code": 504}}) == "outage",
            "[kinds] a 200 whose body is only an error object is read by that error's code")
    c.check(_parse_kind({"error": {"message": "something odd"}}) == "bad_reply",
            "[kinds] an error-only 200 with nothing recognisable is a bad reply")
    c.check(_parse_kind({"id": "x", "choices": []}) == "bad_reply",
            "[kinds] an empty choices list is a bad reply, not an IndexError")
    c.check(_parse_kind({"id": "x"}) == "bad_reply",
            "[kinds] a reply with no choices at all is a bad reply, not a KeyError")
    c.check(_parse_kind(_reply('{"translations": {"1": "hi"}}')) == "bad_reply",
            "[kinds] translations that are not a list are a bad reply")
    c.check(_parse_kind(_reply('{"translations":[{"id":1,"text":"a"},"junk",{"text":"b"},'
                               '{"id":"x","text":"c"}]}')) == "ok",
            "[kinds] junk entries inside a good list are skipped, not raised")

    transient = {k: ProviderError(200, "", kind=k).transient
                 for k in ("account", "refused", "rejected", "outage", "bad_reply")}
    c.check(transient == {"account": False, "refused": False, "rejected": False,
                          "outage": True, "bad_reply": True},
            f"[kinds] only an outage or a bad reply is worth asking again ({transient})")

    # Over the wire, through the transport's own raise sites.
    def kind_of(stub):
        try:
            asyncio.run(LLMClient(stub.url, None, MODEL).translate_page([Region(id=1, text="テスト")]))
            return "ok"
        except ProviderError as e:
            return e.kind
        except Exception as e:  # noqa: BLE001
            return f"raised {type(e).__name__}"

    with StubProvider(delay=0, chat_format="garbage") as stub:
        got = kind_of(stub)
    c.check(got == "bad_reply", f"[kinds] a proxy's HTML page with status 200 is a bad reply ({got})")
    with StubProvider(delay=0, status=401) as stub:
        got = kind_of(stub)
    c.check(got == "account", f"[kinds] the stub's 401 is an account problem ({got})")
    with StubProvider(delay=0, chat_format="sse-error") as stub:
        got = kind_of(stub)
    c.check(got == "outage", f"[kinds] a stream error event with code 529 is an outage ({got})")
    try:
        asyncio.run(LLMClient("http://127.0.0.1:9/v1", None, MODEL)
                    .translate_page([Region(id=1, text="テスト")]))
        got = "ok"
    except ProviderError as e:
        got = e.kind
    c.check(got == "account", f"[kinds] a refused connection is the endpoint setting, so it "
                              f"pauses rather than skipping page after page ({got})")


# -- the pipeline half ------------------------------------------------------
#
# Which page a request belongs to is decided by patching pipeline.translate,
# not by the stub: pages run four at a time, so request ORDER says nothing
# about which page refused, and OCR text is not ours to predict. translate()
# gets the ordinal; the transport-level kinds are [kinds]' business.

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")
PAGES = 6


def _archive(dest, pages=PAGES, seed=0):
    """`pages` pages built from benign.cbz's three, each with one pixel of its
    own so every page hash differs (check_cancel's recipe). `seed` gives a
    section pages no earlier section has cached."""
    import io as _io
    import zipfile

    from PIL import Image

    with zipfile.ZipFile(os.path.join(FIXTURES, "archives", "benign.cbz")) as zf:
        bases = [zf.read(n) for n in sorted(n for n in zf.namelist() if n.endswith(".png"))]
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as out:
        for i in range(pages):
            with Image.open(_io.BytesIO(bases[i % len(bases)])) as im:
                page = im.convert("RGB")
            page.putpixel((0, 0), (37 * (i + 1) % 256, 13 + seed, 99))
            buf = _io.BytesIO()
            page.save(buf, "PNG")
            out.writestr(f"ch1/p{i + 1:02d}.png", buf.getvalue())
    return dest


class Script:
    """A pipeline.translate stand-in: `fail[ordinal]` raises that error for
    that page, every other page goes to the real translate (and the stub)."""

    def __init__(self, fail=None, before=None):
        from sidecar import pipeline

        self.fail = dict(fail or {})
        self.before = before  # called with the ordinal before anything else
        self.asked: list[int] = []
        self._real = pipeline.translate
        self._pipeline = pipeline

    def __enter__(self):
        real = self._real

        def translate(regions, page, *a, **k):
            self.asked.append(page)
            if self.before is not None:
                err = self.before(page, k.get("where", ""))
                if isinstance(err, Exception):
                    raise err
            err = self.fail.get(page) or self.fail.get("*")
            if err is not None:
                raise err
            return real(regions, page, *a, **k)

        self._pipeline.translate = translate
        return self

    def __exit__(self, *_):
        self._pipeline.translate = self._real


def _refused():
    return ProviderError(403, json.dumps({"error": {"code": 403, "message": "input was flagged",
                                                    "metadata": {"reasons": ["violence"]}}}),
                         kind="refused")


def _outage():
    return ProviderError(503, "<html>busy</html>", kind="outage")


def _quiet(fn, *a, **k):
    import contextlib
    import io as _io

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(_io.StringIO()):
        out = fn(*a, **k)
    return out, buf.getvalue()


def _members(path):
    import zipfile

    with zipfile.ZipFile(path) as zf:
        return sorted(n for n in zf.namelist() if n.lower().endswith(".png"))


def skip_pages(c: Checks, tmp: str, stub) -> None:
    """[skip] a refused page is delivered as the original; the run goes on."""
    import zipfile

    from PIL import Image
    from sidecar import cache, job, pipeline

    vol = _archive(os.path.join(tmp, "in", "vol1.cbz"))
    out = os.path.join(tmp, "out-skip")
    client = LLMClient(stub.url, None, MODEL)

    with Script({2: _refused(), 4: _outage()}) as script:
        status, log = _quiet(job.run_job, [vol], out, "skip-1", client, workers=1)
    item = status["items"][0]
    c.check(len(script.asked) == PAGES and 2 in script.asked and 4 in script.asked,
            f"[skip] every page with text was asked, refused ones included ({sorted(script.asked)})")
    c.check(item["status"] == job.OK and item["pages"] == PAGES,
            f"[skip] the item finishes OK with all {PAGES} pages, not FAILED "
            f"({item['status']}, {item['pages']}, {item['reason']!r})")
    skipped = {p["ordinal"]: p["kind"] for p in item["pages_skipped"]}
    c.check(skipped == {2: "refused", 4: "outage"},
            f"[skip] exactly the two failed pages are listed, with their kinds ({skipped})")
    c.check(item["pages_done"] == PAGES and item["pages_total"] == PAGES,
            f"[skip] live progress counts every delivered page "
            f"({item['pages_done']}/{item['pages_total']})")
    c.check(status["pages_skipped"] == 2, f"[skip] the job totals the skipped pages "
                                          f"({status['pages_skipped']})")

    archive = item["output"]
    c.check(bool(archive) and os.path.isfile(archive) and len(_members(archive)) == PAGES,
            f"[skip] the archive is built with every page in its slot ({archive})")
    # Page 2 in the archive is the ORIGINAL page: same pixels as the input member.
    with zipfile.ZipFile(vol) as zin, zipfile.ZipFile(archive) as zout:
        src_names = sorted(n for n in zin.namelist() if n.endswith(".png"))
        out_names = _members(archive)
        import io as _io
        with Image.open(_io.BytesIO(zin.read(src_names[1]))) as a, \
                Image.open(_io.BytesIO(zout.read(out_names[1]))) as b:
            same2 = a.convert("RGB").tobytes() == b.convert("RGB").tobytes()
        with Image.open(_io.BytesIO(zin.read(src_names[0]))) as a, \
                Image.open(_io.BytesIO(zout.read(out_names[0]))) as b:
            same1 = a.convert("RGB").tobytes() == b.convert("RGB").tobytes()
    c.check(same2 and not same1,
            f"[skip] the skipped page is the untouched original, a translated one is not "
            f"(page 2 original={same2}, page 1 original={same1})")

    # The next run: the refusal is remembered, the outage is not.
    with Script() as script:
        status, _ = _quiet(job.run_job, [vol], out, "skip-2", client, workers=1)
    item = status["items"][0]
    skipped = {p["ordinal"]: p["kind"] for p in item["pages_skipped"]}
    c.check(2 not in script.asked and skipped == {2: "refused"},
            f"[skip] a re-run does not ask the refused page again and still lists it "
            f"(asked {sorted(script.asked)}, skipped {skipped})")
    c.check(4 in script.asked,
            f"[skip] a page skipped for an OUTAGE is asked again on the next run "
            f"(asked {sorted(script.asked)})")

    # The record shape the UI reads, straight from the pipeline.
    with Script({2: _refused()}):
        record, log = _quiet(pipeline.run_item, vol, os.path.join(tmp, "out-rec"), "skip-rec",
                             None, client, cancel=pipeline.Control())
    page2 = next(p for p in record["pages"] if p["page"] == 2)
    c.check(page2.get("skipped", {}).get("kind") == "refused"
            and page2.get("regions") == [] and isinstance(page2.get("fit_summary"), dict)
            and all(k in page2["fit_summary"] for k in ("fit_failed", "fit_compromised")),
            f"[skip] the skipped record has the full page shape: no regions, an empty fit "
            f"summary, the reason ({ {k: page2.get(k) for k in ('regions', 'fit_summary')} })")
    c.check(page2["dismissed"] and not any(d["editable"] for d in page2["dismissed"]),
            "[skip] its regions are listed but not editable one by one (manual mode types them)")
    c.check(page2["skipped"].get("detail") and page2["skipped"].get("message"),
            "[skip] it carries the provider's words (detail) and a plain sentence (message)")

    # STAGES: each stage once for the skipped page, in order.
    stages = []
    for line in log.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if isinstance(ev, dict) and ev.get("page") == 2 and ev.get("stage") in pipeline.STAGES:
            stages.append(ev["stage"])
    c.check(stages == list(pipeline.STAGES),
            f"[skip] the skipped page emits every stage exactly once ({stages})")

    from PIL import Image as _Image

    def _jpeg(path: str) -> tuple[int, int] | None:
        """The size of a JPEG under the page cache root, else None."""
        root = os.path.normcase(os.path.abspath(cache.root()))
        plain = path[4:] if path.startswith("\\\\?\\") else path
        if not os.path.normcase(os.path.abspath(plain)).startswith(root + os.sep):
            return None
        try:
            with _Image.open(path) as im:
                return im.size if im.format == "JPEG" else None
        except OSError:
            return None

    originals = [p.get("original") or "" for p in record["pages"]]
    thumbs = [p.get("thumb") or "" for p in record["pages"]]
    sizes_o = [_jpeg(o) for o in originals]
    sizes_t = [_jpeg(t) for t in thumbs]
    c.check(all(sizes_o) and all(sizes_t)
            and all(max(s) <= pipeline.THUMB_LONG_EDGE
                    and s[1] <= s[0] * pipeline.THUMB_ASPECT + 1 for s in sizes_t),
            f"[skip] every page record, skipped or not, carries its original and a strip "
            f"thumbnail, both JPEGs under the page cache root ({sizes_o}, {sizes_t})")

    # An edit's record is the one the Editor swaps in: without these the
    # Original button and the strip chip lose the page after any edit.
    page1 = next(p for p in record["pages"] if p["page"] != 2 and p["regions"])
    edited = pipeline.rerender("skip-rec", page1["item_id"], page1["page"],
                               page1["regions"][0]["id"], "Edited.",
                               os.path.join(tmp, "out-rec"), client, "en")
    c.check(edited.get("original") == page1["original"] and edited.get("thumb") == page1["thumb"],
            f"[skip] a spot-fix re-render's record keeps the page's original and thumbnail "
            f"({edited.get('original')!r}, {edited.get('thumb')!r})")

    # A grayscale page is not widened to RGB first (a 4000 x 6000 L page is
    # 72 MB more as RGB, four pages in flight); a spread's thumb is its
    # right-hand page, the first one read, not the gutter.
    gray_h, spread_h = "a" * 64, "b" * 64
    gray = _Image.new("L", (900, 1300), 200)
    spread = _Image.new("RGB", (3000, 2000), (255, 255, 255))
    spread.paste((0, 0, 0), (1500, 0, 3000, 2000))  # the right half is black
    for h in (gray_h, spread_h):
        os.makedirs(cache.page_dir(h), exist_ok=True)
    g_orig, _ = pipeline._write_previews(gray_h, gray)
    _, s_thumb = pipeline._write_previews(spread_h, spread)
    with _Image.open(g_orig) as im:
        g_mode = im.mode
    with _Image.open(s_thumb) as im:
        s_size, s_px = im.size, im.convert("L").getpixel((im.size[0] // 2, im.size[1] // 2))
    c.check(g_mode == "L", f"[skip] a grayscale page's preview stays grayscale ({g_mode})")
    c.check(s_size[1] >= s_size[0] and s_px < 40,
            f"[skip] a spread's thumbnail is its right-hand page ({s_size}, centre {s_px})")
    # A long strip keeps its width, so the toggle shows it readable; a big
    # scan shrinks by its short edge; the area bound catches a wide strip.
    shapes = {(720, 20000): 1, (4000, 6000): 4, (1600, 20000): 2, (1200, 1700): 1, (64, 64): 1}
    got = {s: pipeline._preview_factor(*s) for s in shapes}
    c.check(got == shapes,
            f"[skip] the original preview is reduced by its short edge, bounded by area ({got})")

    h2 = page2["page_hash"]
    key_img = pipeline.refusal_key(client, True)
    c.check(cache.read_refusal(h2, "en", key_img) is not None,
            "[skip] a refusal is remembered for this endpoint, model and image setting")
    c.check(cache.read_raster(h2, set()) is not None,
            "[skip] the original page is cached as the empty-set raster, for the retry")

    # Without the image it is a different question: asked again.
    client.text_only = True
    try:
        with Script() as script:
            _quiet(job.run_job, [vol], os.path.join(tmp, "out-noimg"), "skip-3", client,
                   workers=1)
    finally:
        client.text_only = False
    c.check(2 in script.asked,
            f"[skip] the same model WITHOUT the image is asked again "
            f"(asked {sorted(script.asked)})")


def pauses(c: Checks, tmp: str, stub) -> None:
    """[pause] account problems and failing streaks stop the job, settled."""
    from sidecar import job, pipeline

    vol = _archive(os.path.join(tmp, "in", "pause1.cbz"), seed=1)
    client = LLMClient(stub.url, None, MODEL)

    account = ProviderError(401, '{"error":{"message":"Incorrect API key"}}', kind="account")
    with Script({"*": account}) as script:
        status, _ = _quiet(job.run_job, [vol], os.path.join(tmp, "out-p1"), "pause-1", client,
                           workers=1)
    item = status["items"][0]
    c.check(status["done"] and status["paused"] and "account" in status["pause_reason"],
            f"[pause] an account failure pauses the job, and the job settles (done) "
            f"({status['done']}, {status['paused']}, {status['pause_reason'][:60]!r})")
    c.check(item["status"] == job.PAUSED and not item["pages_skipped"],
            f"[pause] the item is paused, with no page skipped for an account problem "
            f"({item['status']}, {item['pages_skipped']})")
    c.check(len(script.asked) <= pipeline.PAGE_WINDOW,
            f"[pause] no page starts after the pause; only the window in flight asked "
            f"({len(script.asked)} asked, window {pipeline.PAGE_WINDOW})")

    bad = ProviderError(200, "reply was not JSON: Sorry, I can't help with that.",
                        kind="bad_reply")
    vol_bad = _archive(os.path.join(tmp, "in", "pause2.cbz"), seed=2)
    with Script({"*": bad}):
        status, _ = _quiet(job.run_job, [vol_bad], os.path.join(tmp, "out-p2"), "pause-2", client,
                           workers=1)
    item = status["items"][0]
    c.check(status["paused"] and "in a row" in status["pause_reason"]
            and item["status"] == job.PAUSED and len(item["pages_skipped"]) >= 3,
            f"[pause] 3 failed pages in a row pause the job "
            f"({status['paused']}, {item['status']}, {len(item['pages_skipped'])} skipped)")

    # Two items running at once: the pause stops both, and wait() returns.
    vol2 = _archive(os.path.join(tmp, "in", "pause3.cbz"), seed=3)
    with Script({"*": account}):
        batch = job.Job("pause-3", [vol, vol2], os.path.join(tmp, "out-p3"), client, workers=2)
        _quiet(lambda: batch.start().wait(120))
        status = batch.status()
    c.check(status["done"] and all(i["status"] in (job.PAUSED, "pending") for i in status["items"]),
            f"[pause] with two items running, both stop and the job settles "
            f"({[(i['item_id'], i['status']) for i in status['items']]})")

    # Cancel settles a paused job: nothing left paused or pending.
    batch.cancel()
    status = batch.status()
    c.check(not status["paused"] and all(i["status"] == job.CANCELLED for i in status["items"]),
            f"[pause] cancel on a paused job settles it ({status['paused']}, "
            f"{[i['status'] for i in status['items']]})")

    # A cancel in the gap before the retry wins over the skip.
    holder = {}

    def cancel_then_fail(page, where):
        holder["job"].cancel()

    vol4 = _archive(os.path.join(tmp, "in", "pause4.cbz"), seed=4)
    with Script({"*": _outage()}, before=cancel_then_fail):
        batch = job.Job("pause-4", [vol4], os.path.join(tmp, "out-p4"), client, workers=1)
        holder["job"] = batch
        _quiet(lambda: batch.start().wait(120))
        status = batch.status()
    item = status["items"][0]
    c.check(item["status"] == job.CANCELLED and not item["pages_skipped"],
            f"[pause] a cancel that lands while a page is failing ends CANCELLED, "
            f"not skipped ({item['status']}, {item['pages_skipped']})")

    # The probe answering 401: the job pauses before any page is sent.
    with StubProvider(delay=0, status=401) as bad_stub:
        probe_client = LLMClient(bad_stub.url, None, "probe-account-model")
        vol5 = _archive(os.path.join(tmp, "in", "pause5.cbz"), seed=5)
        status, _ = _quiet(job.run_job, [vol5], os.path.join(tmp, "out-p5"), "pause-5",
                           probe_client, workers=1)
        requests = bad_stub.chat_requests
    c.check(status["paused"] and not probe_client.text_only and requests == 1
            and status["items"][0]["status"] == "pending",
            f"[pause] a 401 on the vision probe pauses before any page, and does not latch "
            f"text-only (paused={status['paused']}, text_only={probe_client.text_only}, "
            f"{requests} request(s), item {status['items'][0]['status']})")


def resumes(c: Checks, tmp: str, stub) -> None:
    """[resume] a paused job goes on under the same id, and does not loop."""
    from sidecar import cache, job
    from sidecar import main as sidecar_main

    # Not a resume check, but this section has main imported: the Editor
    # allows the page cache's folder from health, a cheap call, instead of
    # the cache stats, which walk every page.
    saved_provider = sidecar_main._PROVIDER
    if saved_provider is None:
        sidecar_main._PROVIDER = ("cpu", "check_skip")
    try:
        named = sidecar_main.health().get("cache_root")
    finally:
        sidecar_main._PROVIDER = saved_provider
    want = os.path.abspath(os.environ["MT_CACHE_DIR"])
    c.check(named == want and cache.root() == want,
            f"[review] health names the page cache's folder, the one this run uses ({named!r})")

    client = LLMClient(stub.url, None, MODEL)
    account = ProviderError(401, '{"error":{"message":"Incorrect API key"}}', kind="account")

    # Paused on page 3, resumed with a working key: the item finishes.
    vol = _archive(os.path.join(tmp, "in", "resume1.cbz"), seed=6)
    with Script({3: account}):
        first = job.Job("resume-1", [vol], os.path.join(tmp, "out-r1"), client, workers=1)
        _quiet(lambda: first.start().wait(120))
    c.check(first.status()["paused"], "[resume] (setup) the job paused on the account error")
    with Script() as script:
        nxt = first.resume(client)
        _, log = _quiet(lambda: nxt.start().wait(120))
        status = nxt.status()
    item = status["items"][0]
    starts = [ln for ln in log.splitlines() if '"item_start"' in ln]
    c.check(status["done"] and not status["paused"] and item["status"] == job.OK
            and item["pages"] == PAGES,
            f"[resume] the resumed job finishes the item with every page "
            f"({item['status']}, {item['pages']})")
    c.check(nxt.job_id == first.job_id and len(starts) == 1,
            f"[resume] under the same job id, and the item runs once ({len(starts)} item_start)")
    c.check(3 in script.asked,
            f"[resume] the page that paused it is asked again ({sorted(script.asked)})")

    # Three prose refusals pause it; resumed against the same refusals, the
    # carried pages do not count, so it does not pause again (R3-B1).
    vol = _archive(os.path.join(tmp, "in", "resume2.cbz"), seed=7)
    prose = ProviderError(200, "reply was not JSON: I'm sorry, I can't translate this.",
                          kind="bad_reply")
    fail = {1: prose, 2: prose, 3: prose}
    with Script(fail):
        first = job.Job("resume-2", [vol], os.path.join(tmp, "out-r2"), client, workers=1)
        _quiet(lambda: first.start().wait(120))
    before = first.status()
    with Script(fail):
        nxt = first.resume(client)
        _quiet(lambda: nxt.start().wait(120))
        status = nxt.status()
    item = status["items"][0]
    c.check(before["paused"] and not status["paused"] and item["status"] == job.OK
            and sorted(p["ordinal"] for p in item["pages_skipped"]) == [1, 2, 3],
            f"[resume] after 3 prose refusals, resume finishes instead of pausing again "
            f"(first paused={before['paused']}, then paused={status['paused']}, "
            f"{item['status']}, skipped {[p['ordinal'] for p in item['pages_skipped']]})")

    # Item ids survive the resume, a digest-suffixed one included.
    for sub in ("a", "b"):
        os.makedirs(os.path.join(tmp, "in", sub), exist_ok=True)
    va = _archive(os.path.join(tmp, "in", "a", "vol.cbz"), pages=2, seed=8)
    vb = _archive(os.path.join(tmp, "in", "b", "vol.cbz"), pages=2, seed=9)

    def only_b(page, where):
        return account if "vol-" in where and where.split(",")[0] == ids[1] else None

    first = job.Job("resume-3", [va, vb], os.path.join(tmp, "out-r3"), client, workers=1)
    ids = [i.item_id for i in first.items]
    with Script(before=only_b):
        _quiet(lambda: first.start().wait(120))
    with Script():
        nxt = first.resume(client)
        _quiet(lambda: nxt.start().wait(120))
    after = [i.item_id for i in nxt.items]
    c.check(first.status()["paused"] and ids == after and all(i != "vol.cbz" for i in ids)
            and [i.status for i in nxt.items] == [job.OK, job.OK],
            f"[resume] both disambiguated ids are kept and both items finish "
            f"({ids} -> {after}, {[i.status for i in nxt.items]})")

    # The sidecar's job table: a paused job is never pruned or replaced,
    # and resume answers 409 while the job is still stopping.
    class Fake:
        def __init__(self, done, paused):
            self.done, self.paused = done, paused

    saved = dict(sidecar_main._jobs)
    saved_keep = sidecar_main.KEEP_FINISHED_JOBS
    try:
        sidecar_main._jobs.clear()
        sidecar_main._jobs["paused-one"] = Fake(True, True)
        sidecar_main._jobs["finished-one"] = Fake(True, False)
        sidecar_main.KEEP_FINISHED_JOBS = 0
        req = sidecar_main.JobRequest(job_id="new-one", dest_dir=os.path.join(tmp, "out-r4"),
                                      paths=[])
        _quiet(sidecar_main.start_job, req)
        c.check("paused-one" in sidecar_main._jobs and "finished-one" not in sidecar_main._jobs,
                f"[resume] pruning drops finished jobs and keeps the paused one "
                f"({sorted(sidecar_main._jobs)})")
        again = sidecar_main.start_job(sidecar_main.JobRequest(
            job_id="paused-one", dest_dir=os.path.join(tmp, "out-r4"), paths=[]))
        c.check(getattr(again, "status_code", 200) == 409,
                "[resume] a new job cannot replace a paused one under its id")
        sidecar_main._jobs["stopping"] = Fake(False, True)
        resp = sidecar_main.resume_job("stopping", sidecar_main.ResumeRequest(
            settings=sidecar_main.Settings(base_url=stub.url, api_key="", model=MODEL)))
        c.check(getattr(resp, "status_code", 200) == 409,
                "[resume] resume answers 409 while the job is still stopping")
    finally:
        sidecar_main._jobs.clear()
        sidecar_main._jobs.update(saved)
        sidecar_main.KEEP_FINISHED_JOBS = saved_keep


def _loose_pages(directory, names, seed):
    """Write benign.cbz's pages as loose PNG files named `names`."""
    import io as _io
    import zipfile

    from PIL import Image

    os.makedirs(directory, exist_ok=True)
    with zipfile.ZipFile(os.path.join(FIXTURES, "archives", "benign.cbz")) as zf:
        bases = [zf.read(n) for n in sorted(n for n in zf.namelist() if n.endswith(".png"))]
    for i, name in enumerate(names):
        with Image.open(_io.BytesIO(bases[i % len(bases)])) as im:
            page = im.convert("RGB")
        page.putpixel((1, 1), (seed, 7 * (i + 1) % 256, 3))
        page.save(os.path.join(directory, name), "PNG")
    return [os.path.join(directory, n) for n in names]


def inputs(c: Checks, tmp: str, stub) -> None:
    """[input] folders become items by the user's folder rule (plan 1.1)."""
    import shutil

    from sidecar import job

    series = os.path.join(tmp, "series")
    loose = _loose_pages(series, ["001.png", "010.png", "002.png"], seed=40)
    _loose_pages(os.path.join(series, "ch02"), ["p1.png", "p2.png"], seed=41)
    shutil.copy(_archive(os.path.join(tmp, "in", "extra.cbz"), pages=1, seed=42),
                os.path.join(series, "extra.cbz"))
    with open(os.path.join(series, "notes.txt"), "w") as fh:
        fh.write("not a page")

    items = job.expand([series])
    by_id = {i.item_id: i for i in items}
    c.check(sorted(by_id) == ["ch02", "extra.cbz", "notes.txt", "series"],
            f"[input] a folder is: its archive, its loose images as one chapter, each "
            f"subfolder of images as one chapter, the unsupported file reported ({sorted(by_id)})")
    c.check([os.path.basename(m) for m in by_id["series"].members] == ["001.png", "002.png", "010.png"]
            and by_id["series"].kind == "images",
            f"[input] the chapter's pages are in natural order "
            f"({[os.path.basename(m) for m in by_id['series'].members]})")
    c.check(by_id["notes.txt"].status == job.SKIPPED and by_id["notes.txt"].reason,
            "[input] the unsupported file is still listed with its reason")

    items = job.expand([series, loose[0]])
    c.check(sum(1 for i in items if i.item_id == "series") == 1
            and len(next(i for i in items if i.item_id == "series").members) == 3,
            "[input] dropping the folder AND a file inside it gives one chapter, not two")

    items = job.expand([loose[0], loose[1]])
    c.check(len(items) == 1 and [os.path.basename(m) for m in items[0].members] == ["001.png", "010.png"],
            f"[input] picked images become one chapter of exactly those files "
            f"({[(i.item_id, [os.path.basename(m) for m in i.members]) for i in items]})")

    a = _loose_pages(os.path.join(tmp, "x", "Vol.1"), ["1.png"], seed=43)
    b = _loose_pages(os.path.join(tmp, "y", "Vol.1"), ["1.png"], seed=44)
    ids = [i.item_id for i in job.disambiguate(job.expand([a[0], b[0]]))]
    c.check(len(set(ids)) == 2 and all(i.startswith("Vol.1-") and "." in i[:5] for i in ids),
            f"[input] two chapters named Vol.1 get distinct ids that keep the dot ({ids})")

    # A refused page inside a chapter of loose images is a skipped page.
    out = os.path.join(series, "translated")
    client = LLMClient(stub.url, None, MODEL)
    with Script({2: _refused()}):
        status, _ = _quiet(job.run_job, [series], out, "input-1", client, workers=2)
    chapter = next(i for i in status["items"] if i["item_id"] == "series")
    c.check(chapter["status"] == job.OK and chapter["pages"] == 3
            and [p["ordinal"] for p in chapter["pages_skipped"]] == [2]
            and os.path.isdir(chapter["output"]),
            f"[input] the chapter finishes with page 2 skipped, its output a folder of pages "
            f"({chapter['status']}, {chapter['pages']}, {chapter['pages_skipped']}, "
            f"{chapter['output']})")
    written = sorted(os.listdir(chapter["output"])) if os.path.isdir(chapter["output"]) else []
    c.check(written == ["001_translated.png", "002_translated.png", "010_translated.png"],
            f"[input] every page is delivered under the user's own name ({written})")
    from PIL import Image
    with Image.open(loose[2]) as orig, Image.open(os.path.join(chapter["output"],
                                                               "002_translated.png")) as got:
        same = orig.convert("RGB").tobytes() == got.convert("RGB").tobytes()
    c.check(same, "[input] the skipped page (002.png, page 2) is the untouched original")

    # The output folder inside the input is not read back as input.
    again = {i.item_id for i in job.expand([series], dest_dir=out)}
    c.check("translated" not in again and not any("translated" in i for i in again),
            f"[input] a second run does not take the first run's output as a chapter ({sorted(again)})")


def _wait_retry(sidecar_main, job_id, item_id, timeout=120):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        st = sidecar_main.retry_status(job_id, item_id)
        if not isinstance(st, dict):
            return {"status": f"no retry (HTTP {getattr(st, 'status_code', '?')})",
                    "kind": "", "done": -1}
        if st["status"] != "running":
            return st
        time.sleep(0.1)
    return sidecar_main.retry_status(job_id, item_id)


def retries(c: Checks, tmp: str, stub) -> None:
    """[retry] the four workarounds, and what they must never do (plan 2)."""
    import shutil

    from lib.stub_provider import vision_capable
    from sidecar import cache, job, pipeline
    from sidecar import main as sidecar_main

    client = LLMClient(stub.url, None, MODEL)
    model_b = "stub/model-b"
    vision_capable(stub, model_b)
    settings = sidecar_main.Settings(base_url=stub.url, api_key="", model=MODEL)

    vol = _archive(os.path.join(tmp, "in", "retry1.cbz"), pages=4, seed=20)
    out = os.path.join(tmp, "out-retry")
    with Script({2: _refused(), 3: _refused()}):
        first = job.Job("retry-1", [vol], out, client, workers=1)
        _quiet(lambda: first.start().wait(120))
    item_id = first.items[0].item_id
    c.check(sorted(p["ordinal"] for p in first.items[0].pages_skipped) == [2, 3],
            "[retry] (setup) pages 2 and 3 were refused")
    sidecar_main._jobs["retry-1"] = first

    # Retry without the image.
    stub.payloads.clear()
    rec2, _ = _quiet(pipeline.retry_page, "retry-1", item_id, 2, out, client, "en", "text_only")
    sent_image = any(
        isinstance(m.get("content"), list) and any(part.get("type") == "image_url"
                                                   for part in m["content"])
        for pl in stub.payloads if isinstance(pl, dict) for m in pl.get("messages", []))
    h2 = rec2.get("page_hash")
    c.check(stub.payloads and not sent_image,
            f"[retry] without the image: the request carries no image part "
            f"({len(stub.payloads)} request(s), image sent={sent_image})")
    c.check(rec2.get("regions") and rec2.get("choice") == {"model": MODEL + "#text",
                                                           "mode": "text_only"}
            and cache.read_translation(h2, "en", MODEL + "#text")
            and not cache.read_translation(h2, "en", MODEL),
            f"[retry] its translation lives under <model>#text, never under the vision key "
            f"(choice {rec2.get('choice')})")
    c.check(not cache.has_refusals(h2), "[retry] a fixed page loses its refusal marker")

    # Retry with another model, then edit while Settings names model A.
    client_b = LLMClient(stub.url, None, model_b)
    rec3, _ = _quiet(pipeline.retry_page, "retry-1", item_id, 3, out, client_b, "en", "model")
    h3 = rec3.get("page_hash")
    c.check(rec3.get("choice", {}).get("model") == model_b and rec3.get("regions"),
            f"[retry] another model translates the page and is pinned as its choice "
            f"({rec3.get('choice')})")
    region = rec3["regions"][0]["id"]
    try:
        edited, _ = _quiet(pipeline.rerender, "retry-1", item_id, 3, region, "EDITED", out,
                           client, "en")
        ok_edit = any(r["id"] == region and r.get("translation") == "EDITED"
                      for r in edited["regions"])
        why = ""
    except Exception as e:  # noqa: BLE001 -- the failure IS the finding
        ok_edit, why = False, f"{type(e).__name__}: {e}"
    c.check(ok_edit, f"[retry] an edit on the model-B page works while Settings says model A "
                     f"{why}")

    # A full re-run under model A keeps both fixes, and asks neither page.
    with Script({2: _refused(), 3: _refused()}) as script:
        status, _ = _quiet(job.run_job, [vol], out, "retry-2", client, workers=1)
    item = status["items"][0]
    c.check(2 not in script.asked and 3 not in script.asked and not item["pages_skipped"],
            f"[retry] a re-run under model A keeps the fixes: pages 2 and 3 not asked, "
            f"none skipped (asked {sorted(script.asked)}, skipped {item['pages_skipped']})")

    # A cap squeeze keeps the fixed pages (they hold choices) while it may
    # take everything else.
    saved = {k: os.environ.get(k) for k in ("MT_CACHE_CAP_BYTES", "MT_CACHE_TARGET_BYTES")}
    os.environ["MT_CACHE_CAP_BYTES"] = "1"
    os.environ["MT_CACHE_TARGET_BYTES"] = "1"
    try:
        _quiet(cache.enforce_cap)
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    c.check(cache.read_choice(h3, "en") is not None and cache.read_translation(h3, "en", model_b),
            "[retry] a cap squeeze does not evict a page the user fixed with another model")

    # Translate it myself: one region typed, the rest left as drawn.
    vol_m = _archive(os.path.join(tmp, "in", "manual1.cbz"), pages=1, seed=21)
    with Script({1: _refused()}):
        status, _ = _quiet(job.run_job, [vol_m], out, "manual-1", client, workers=1)
    m_item = status["items"][0]["item_id"]
    page = next(iter(cache.item_placements("manual-1", m_item)))[1]
    regions = cache.read_regions(page["page_hash"])["regions"]
    typed = regions[0]["id"]
    rec, _ = _quiet(pipeline.manual_page, "manual-1", m_item, 1, {str(typed): "Typed by hand"},
                    out, "en")
    on_page = {r["id"]: r.get("translation") for r in rec["regions"]}
    left = [d["id"] for d in rec["dismissed"]]
    c.check(on_page.get(typed) == "Typed by hand"
            and all(r["id"] in left for r in regions if r["id"] != typed and not r.get("not_text")),
            f"[retry] translate-it-myself draws the typed bubble and leaves the rest as drawn "
            f"(on page {on_page}, left {left})")
    with Script() as script:
        status, _ = _quiet(job.run_job, [vol_m], out, "manual-2", client, workers=1)
    page_rec = status["items"][0]
    c.check(1 not in script.asked and not page_rec["pages_skipped"],
            f"[retry] a vision re-run does not ask the hand-translated page, and its blank "
            f"regions stay as drawn (asked {script.asked})")

    # An expired key: the retry stops at the first page and writes no marker.
    vol_k = _archive(os.path.join(tmp, "in", "retry-key.cbz"), pages=3, seed=22)
    # Pages 1 and 3 refused, 2 translated between them: not three in a row,
    # so the job finishes (a paused job refuses retries until resumed).
    with Script({1: _refused(), 3: _refused()}):
        keyjob = job.Job("retry-key", [vol_k], out, client, workers=1)
        _quiet(lambda: keyjob.start().wait(120))
    k_item = keyjob.items[0].item_id
    hashes = [e["page_hash"] for _o, e in cache.item_placements("retry-key", k_item)]
    before = sum(len(cache._refusal_files(h)) for h in hashes)
    sidecar_main._jobs["retry-key"] = keyjob
    with StubProvider(delay=0, status=401) as dead:
        req = sidecar_main.RetryRequest(
            job_id="retry-key", item_id=k_item, ordinals=[1, 3], dest_dir=out, mode="same",
            settings=sidecar_main.Settings(base_url=dead.url, api_key="", model=MODEL))
        _quiet(sidecar_main.retry_pages, req)
        st = _wait_retry(sidecar_main, "retry-key", k_item)
        requests = dead.chat_requests
    after = sum(len(cache._refusal_files(h)) for h in hashes)
    c.check(st["status"] == "failed" and st["kind"] == "account" and st["done"] == 0
            and before == after and requests <= 1,
            f"[retry] an expired key stops the retry before any page and writes no marker "
            f"({st['status']}, {st['kind']}, {st['done']} done, markers {before}->{after}, "
            f"{requests} request(s))")

    # The retry route through the job table: it serves the fixed pages back.
    req = sidecar_main.RetryRequest(job_id="retry-key", item_id=k_item, ordinals=[3],
                                    dest_dir=out, mode="text_only", settings=settings)
    _quiet(sidecar_main.retry_pages, req)
    st = _wait_retry(sidecar_main, "retry-key", k_item)
    served = sidecar_main.job_item("retry-key", k_item)
    fixed = [p for p in served["pages"] if p.get("page") == 3]
    c.check(st["status"] == "done" and fixed and fixed[0].get("regions")
            and [p["ordinal"] for p in keyjob.items[0].pages_skipped] == [1],
            f"[retry] the route fixes page 3, GET /item serves it, and the item lists only "
            f"page 1 as skipped ({st['status']}, "
            f"{[p['ordinal'] for p in keyjob.items[0].pages_skipped]})")

    # Retrying a page that is already fixed asks nobody (review).
    before = stub.chat_requests
    _quiet(sidecar_main.retry_pages, sidecar_main.RetryRequest(
        job_id="retry-key", item_id=k_item, ordinals=[3], dest_dir=out, mode="same",
        settings=settings))
    st = _wait_retry(sidecar_main, "retry-key", k_item)
    c.check(st["status"] == "done" and st["done"] == 0 and stub.chat_requests == before,
            f"[retry] a second retry of a page fixed since asks nobody "
            f"({st['done']} retried, {stub.chat_requests - before} request(s))")

    # 409 while the job runs.
    class Running:
        done, paused = False, False

    sidecar_main._jobs["busy"] = Running()
    resp = sidecar_main.retry_pages(sidecar_main.RetryRequest(
        job_id="busy", item_id="x", ordinals=[1], dest_dir=out, settings=settings))
    c.check(getattr(resp, "status_code", 200) == 409, "[retry] refused with 409 while the job runs")

    # An evicted page answers CacheMiss, not a crash.
    h1 = hashes[0]
    shutil.rmtree(cache.page_dir(h1), ignore_errors=True)
    try:
        pipeline.retry_page("retry-key", k_item, 1, out, client, "en", "same")
        got = "no error"
    except pipeline.CacheMiss as e:
        got = f"CacheMiss({e.kind})"
    except Exception as e:  # noqa: BLE001
        got = f"{type(e).__name__}"
    c.check(got.startswith("CacheMiss"), f"[retry] a page no longer cached answers CacheMiss ({got})")

    for jid in ("retry-1", "retry-key", "busy"):
        sidecar_main._jobs.pop(jid, None)


def review_fixes(c: Checks, tmp: str, stub) -> None:
    """[review] the code review's findings, each held by a case."""
    import ssl
    import urllib.request

    from sidecar import cache, job, pipeline
    from sidecar import main as sidecar_main

    # M1: a reply that translates none of the asked regions is a bad reply,
    # not a page of empty bubbles cached forever.
    client = LLMClient(stub.url, None, MODEL)

    async def empty_reply(path, payload):
        return _reply('{"translations": []}')

    client._call = empty_reply
    try:
        asyncio.run(client.translate_page([Region(id=1, text="テスト"), Region(id=2, text="二")]))
        got = "ok"
    except ProviderError as e:
        got = e.kind
    c.check(got == "bad_reply", f"[review] an empty translations list is a bad reply ({got})")

    # M4: an OSError that is not a ConnectionError (a TLS EOF mid-body) is
    # an outage, not an exception that fails the chapter.
    real_urlopen = urllib.request.urlopen

    def tls_eof(*a, **k):
        raise ssl.SSLEOFError(8, "EOF occurred in violation of protocol")

    urllib.request.urlopen = tls_eof
    try:
        asyncio.run(LLMClient(stub.url, None, MODEL).translate_page([Region(id=1, text="テ")]))
        got = "ok"
    except ProviderError as e:
        got = e.kind
    except Exception as e:  # noqa: BLE001
        got = f"raised {type(e).__name__}"
    finally:
        urllib.request.urlopen = real_urlopen
    c.check(got == "outage", f"[review] a TLS error is an outage ProviderError ({got})")
    try:
        llm._from_event_stream("data: [1, 2]\n\ndata: [DONE]\n", 200, "u")
        got = "ok"
    except ProviderError as e:
        got = e.kind
    except Exception as e:  # noqa: BLE001
        got = f"raised {type(e).__name__}"
    c.check(got == "bad_reply", f"[review] a stream chunk that is not an object is a bad reply ({got})")
    refused = llm._from_event_stream(
        'data: {"choices":[{"index":0,"delta":{"refusal":"I can\'t help"}}]}\n\ndata: [DONE]\n',
        200, "u")
    c.check(_parse_kind(refused) == "refused",
            "[review] a refusal streamed in delta.refusal is read as a refusal")

    # Moderation metadata wins over account words; a settings field named
    # safety_settings is not a refusal.
    body = json.dumps({"error": {"code": 403, "message": "flagged; no credits were used",
                                 "metadata": {"reasons": ["sexual"]}}})
    c.check(llm.error_kind(403, body) == "refused",
            "[review] moderation reasons decide before an account word in the message")
    body = json.dumps({"error": {"code": 400, "message": "Unknown name \"safety_settings\": "
                                                        "Cannot find field."}})
    c.check(llm.error_kind(400, body) == "rejected",
            f"[review] a 400 about a safety_settings FIELD is rejected, not a refusal "
            f"({llm.error_kind(400, body)})")

    # C1: a page typed by hand that has a punctuation-only region stays the
    # user's page on every later run, and its punctuation stays punctuation.
    vol = _archive(os.path.join(tmp, "in", "manual-punct.cbz"), pages=1, seed=30)
    out = os.path.join(tmp, "out-review")
    with Script({1: _refused()}):
        status, _ = _quiet(job.run_job, [vol], out, "punct-1", client_ok(stub), workers=1)
    item_id = status["items"][0]["item_id"]
    placed = next(iter(cache.item_placements("punct-1", item_id)))[1]
    h = placed["page_hash"]
    record = cache.read_regions(h)
    punct = record["regions"][-1]
    punct["not_text"], punct["dismiss_reason"] = True, "punctuation only"
    cache.write_regions(h, record)
    typed = {str(r["id"]): "Typed" for r in record["regions"][:-1]}
    _quiet(pipeline.manual_page, "punct-1", item_id, 1, typed, out, "en")
    for run_id in ("punct-2", "punct-3"):
        with Script({"*": _refused()}) as script:
            status, _ = _quiet(job.run_job, [vol], out, run_id, client_ok(stub), workers=1)
        if script.asked or status["items"][0]["pages_skipped"]:
            break
    regions_now = {r["id"]: r for r in cache.read_regions(h)["regions"]}
    c.check(not script.asked and not status["items"][0]["pages_skipped"]
            and regions_now[punct["id"]].get("dismiss_reason") == "punctuation only",
            f"[review] a hand-translated page with a punctuation region is never re-asked, "
            f"never reverts, and its punctuation keeps its reason (asked {script.asked}, "
            f"skipped {status['items'][0]['pages_skipped']}, "
            f"reason {regions_now[punct['id']].get('dismiss_reason')!r})")

    # Manual can blank a bubble it typed before.
    first_id = record["regions"][0]["id"]
    rec, _ = _quiet(pipeline.manual_page, "punct-1", item_id, 1, {}, out, "en")
    c.check(all(r["id"] != first_id for r in rec["regions"]),
            "[review] a second hand translation can clear a bubble typed in the first")

    # M2: /api/item does not pause on a streak (it has no resume): three
    # prose refusals in a row are three skipped pages, and the Editor opens.
    vol = _archive(os.path.join(tmp, "in", "item-streak.cbz"), pages=4, seed=31)
    prose = ProviderError(200, "reply was not JSON: I'm sorry.", kind="bad_reply")
    with Script({"*": prose}):
        resp, _ = _quiet(sidecar_main.translate_item, sidecar_main.ItemRequest(
            src_path=vol, dest_dir=out, job_id="item-streak",
            settings=sidecar_main.Settings(base_url=stub.url, api_key="", model=MODEL)))
    pages = resp.get("pages", []) if isinstance(resp, dict) else []
    c.check(isinstance(resp, dict) and not resp.get("paused") and len(pages) == 4
            and all(p.get("skipped") for p in pages),
            f"[review] /api/item skips four refused pages instead of pausing forever "
            f"(paused={resp.get('paused') if isinstance(resp, dict) else resp}, {len(pages)} pages)")

    # M3: resume without settings is refused, not run on the offline placeholder.
    class Paused:
        done, paused, cancelled = True, True, False

    sidecar_main._jobs["needs-settings"] = Paused()
    try:
        resp = sidecar_main.resume_job("needs-settings", sidecar_main.ResumeRequest())
        c.check(getattr(resp, "status_code", 200) == 400,
                "[review] resume without settings answers 400")
    finally:
        sidecar_main._jobs.pop("needs-settings", None)

    # M5: manual refuses on a paused job; a new job cannot replace one whose
    # item is being retried.
    sidecar_main._jobs["paused-manual"] = Paused()
    try:
        resp = sidecar_main.manual_page(sidecar_main.ManualRequest(
            job_id="paused-manual", item_id="x", ordinal=1, dest_dir=out))
        c.check(getattr(resp, "status_code", 200) == 409,
                "[review] the manual route refuses while the job is paused")
    finally:
        sidecar_main._jobs.pop("paused-manual", None)
    sidecar_main._retries.add(("held-job", "x"))
    try:
        resp = sidecar_main.start_job(sidecar_main.JobRequest(
            job_id="held-job", dest_dir=out, paths=[]))
        c.check(getattr(resp, "status_code", 200) == 409,
                "[review] a new job cannot replace one whose page retry is running")
    finally:
        sidecar_main._retries.discard(("held-job", "x"))

    # Cancel while the job is still pausing: a PAUSED item becomes CANCELLED.
    j = job.Job("cancel-pausing", [vol], out, client)
    j.items[0].status = job.PAUSED
    j._control.pause("x")
    j.cancel()
    c.check(j.items[0].status == job.CANCELLED,
            f"[review] cancel converts a paused item even before the job settles "
            f"({j.items[0].status})")


def client_ok(stub):
    return LLMClient(stub.url, None, MODEL)


def main():
    import tempfile

    from lib.result import skip as skip_check
    from lib.stub_provider import vision_capable

    c = Checks("check_skip")
    kinds(c)
    if not os.path.isfile(os.path.join(FIXTURES, "archives", "benign.cbz")):
        return skip_check("fixtures/archives/benign.cbz is absent -- run tests/gen_fixtures.py")
    with tempfile.TemporaryDirectory() as tmp, StubProvider(delay=0) as stub:
        os.environ["MT_CACHE_DIR"] = os.path.join(tmp, "cache")
        os.makedirs(os.path.join(tmp, "in"))
        vision_capable(stub, MODEL)
        skip_pages(c, tmp, stub)
        pauses(c, tmp, stub)
        resumes(c, tmp, stub)
        inputs(c, tmp, stub)
        retries(c, tmp, stub)
        review_fixes(c, tmp, stub)
    return c.finish()


run(main)
