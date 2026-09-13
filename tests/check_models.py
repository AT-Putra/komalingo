"""Phase 0 -- resumable fetch and EP selection (AC-14). OFFLINE.

Serves bytes from an in-process http.server that honours Range, so this check
never touches the network and never inherits check_probe.py's live-endpoint
skip. Model download is an INSTALL-BLOCKING path: if it can only be verified
when a live endpoint happens to be up, it is not verified.

The interruption is real -- the server closes the connection mid-file, the
client raises, and the second call resumes from the surviving .part.
"""

import hashlib
import os
import sys
import types
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from sidecar import models  # noqa: E402
from lib.result import Checks, run  # noqa: E402

# Big enough to span several CHUNK reads so the cut lands mid-transfer.
PAYLOAD = bytes((i * 37 + 11) % 256 for i in range(3_000_000))
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


class Server:
    """Serves PAYLOAD with Range support. cut_after truncates the response."""

    def __init__(self, cut_after=None, honour_range=True):
        state = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, format, *args):  # noqa: A002 -- base signature
                pass

            def do_GET(self):
                start = 0
                rng = self.headers.get("Range")
                if rng and state.honour_range:
                    start = int(rng.split("=")[1].split("-")[0])
                    self.send_response(206)
                    self.send_header(
                        "Content-Range", f"bytes {start}-{len(PAYLOAD) - 1}/{len(PAYLOAD)}"
                    )
                else:
                    self.send_response(200)

                body = PAYLOAD[start:]
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()

                if state.cut_after is not None:
                    # Write a prefix, then drop the connection. The client sees
                    # a short read against a declared Content-Length.
                    self.wfile.write(body[: state.cut_after])
                    self.wfile.flush()
                    self.close_connection = True
                    raise BrokenPipeError("simulated interruption")
                self.wfile.write(body)

        self.cut_after = cut_after
        self.honour_range = honour_range
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self):
        h, p = self._server.server_address[:2]
        return f"http://{h}:{p}/model.bin"

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


def main():
    c = Checks("check_models")

    import tempfile

    with tempfile.TemporaryDirectory() as root:
        dest = os.path.join(root, "weights", "model.bin")
        part = models.atomic.long_path(dest) + ".part"

        # --- 1: an interrupted download leaves a partial ------------------
        with Server(cut_after=900_000) as s:
            try:
                models.fetch(s.url, dest, DIGEST, len(PAYLOAD))
                c.check(False, "an interrupted download raises")
            except (models.FetchError, OSError, Exception) as e:  # noqa: BLE001
                c.check(True, f"interruption surfaces as {type(e).__name__}")

        partial = os.path.getsize(part) if os.path.exists(part) else 0
        c.check(0 < partial < len(PAYLOAD), f"a partial survives the interruption ({partial} B)")
        c.check(not os.path.exists(models.atomic.long_path(dest)), "no destination file yet")

        # --- 2: the resume is byte-identical ------------------------------
        with Server() as s:
            out = models.fetch(s.url, dest, DIGEST, len(PAYLOAD))
        with open(out, "rb") as fh:
            got = fh.read()
        c.check(got == PAYLOAD, f"resumed file is byte-identical ({len(got)} B)")
        c.check(not os.path.exists(part), "the .part is gone once the file is complete")

        # And it really did resume rather than silently restart.
        c.check(partial > 0, f"control: the resume started from {partial} B, not 0")

        # --- 3: a bad checksum is rejected AND the partial deleted --------
        dest2 = os.path.join(root, "weights", "bad.bin")
        part2 = models.atomic.long_path(dest2) + ".part"
        with Server() as s:
            try:
                models.fetch(s.url, dest2, "0" * 64, len(PAYLOAD))
                c.check(False, "a corrupted checksum is rejected")
            except models.FetchError as e:
                c.check(e.kind == "checksum", f"checksum failure is named, got kind={e.kind}")
                c.check("expected" in e.reason and "got" in e.reason, f"reason: {e.reason[:70]}")
        c.check(not os.path.exists(part2), "the bad partial is DELETED, not left to resume onto")
        c.check(not os.path.exists(models.atomic.long_path(dest2)), "no destination written")

        # --- 4: a server ignoring Range restarts rather than corrupting ---
        dest3 = os.path.join(root, "weights", "norange.bin")
        part3 = models.atomic.long_path(dest3) + ".part"
        os.makedirs(os.path.dirname(part3), exist_ok=True)
        with open(part3, "wb") as fh:
            fh.write(b"\x00" * 500_000)  # junk a naive client would append to
        with Server(honour_range=False) as s:
            out3 = models.fetch(s.url, dest3, DIGEST, len(PAYLOAD))
        with open(out3, "rb") as fh:
            c.check(fh.read() == PAYLOAD, "a 200 answer to a Range request restarts cleanly")

        # --- 5: no network is a NAMED failure, not a traceback ------------
        try:
            models.fetch("http://127.0.0.1:1/model.bin", os.path.join(root, "x.bin"))
            c.check(False, "an unreachable host raises FetchError")
        except models.FetchError as e:
            c.check(e.kind == "network", f"network failure is named: {e.reason[:60]}")

        # --- 6: no free space is a named failure --------------------------
        try:
            models.fetch("http://127.0.0.1:1/m.bin", os.path.join(root, "huge.bin"), size=1 << 60)
            c.check(False, "an impossible size fails before downloading")
        except models.FetchError as e:
            c.check(
                e.kind == "space" and "free" in e.reason,
                f"no-space failure is named: {e.reason[:70]}",
            )

    # --- 7: the CPU fallback always carries a reason ----------------------
    ep, reason = models.select_provider()
    c.check(ep.endswith("ExecutionProvider"), f"an execution provider is chosen: {ep}")
    c.check(
        ep == "CUDAExecutionProvider" or bool(reason),
        f"the CPU fallback carries a non-empty reason: {reason!r}",
    )

    ep, reason = models.select_provider(force_cpu=True)
    c.check(ep == "CPUExecutionProvider" and bool(reason), "forced CPU still explains itself")
    # The env switch is what a user -- or a check that must not depend on the
    # box -- reaches for; it must win over a GPU that is present.
    saved = os.environ.get(models.FORCE_CPU_ENV)
    os.environ[models.FORCE_CPU_ENV] = "1"
    try:
        ep, reason = models.select_provider()
    finally:
        if saved is None:
            os.environ.pop(models.FORCE_CPU_ENV, None)
        else:
            os.environ[models.FORCE_CPU_ENV] = saved
    c.check(ep == "CPUExecutionProvider" and models.FORCE_CPU_ENV in reason,
            f"{models.FORCE_CPU_ENV}=1 forces CPU and names itself as the reason: {reason!r}")

    # --- 8: every manifest entry is actually PINNED -----------------------
    # A manifest whose whole stated purpose is "pinned by digest, not by
    # latest" is worth nothing if an entry can carry sha256 "". manga-ocr sat
    # exactly like that from Phase 0 until US-P1-07, and nothing was red.
    for name, entry in sorted(models.MANIFEST.items()):
        parts = entry["files"] if "files" in entry else {name: entry}
        for filename, meta in sorted(parts.items()):
            c.check(
                len(meta.get("sha256", "")) == 64 and meta.get("size", 0) > 0,
                f"{name}/{filename} is pinned "
                f"(sha256 {meta.get('sha256', '')[:12]!r}..., size {meta.get('size', 0)})",
            )
        url = entry.get("base_url") or entry.get("url", "")
        c.check(
            "/resolve/main/" not in url and "/main/" not in url,
            f"{name} is pinned to a revision, not a moving branch: ...{url[-58:]}",
        )

    # --- 9: ocr_ja loads from ensure()'s path, never the default repo id ---
    # The defect this pins is invisible at runtime: MangaOcr's default argument
    # is the repo id, so reverting to MangaOcr(force_cpu=True) still WORKS on
    # any machine with a warm HuggingFace cache, and silently downloads
    # whatever main holds on any machine without one. Neither shows up as a
    # failing check, so the wiring is asserted directly. No network, no 444 MB
    # load: ensure and MangaOcr are both stubbed and the argument is captured.
    import sidecar.ocr_ja as ocr_ja

    captured = {}

    class FakeMangaOcr:
        def __init__(self, pretrained_model_name_or_path=None, force_cpu=False):
            captured["path"] = pretrained_model_name_or_path
            captured["force_cpu"] = force_cpu

        def __call__(self, image):
            return ""

    fake_module = types.ModuleType("manga_ocr")
    fake_module.MangaOcr = FakeMangaOcr
    real_ensure, real_model, real_mod = models.ensure, ocr_ja._MODEL, sys.modules.get("manga_ocr")
    sentinel = os.path.join("sentinel-dir", "manga-ocr")
    ensured = []
    try:
        models.ensure = lambda name, progress=None: (ensured.append(name), sentinel)[1]
        sys.modules["manga_ocr"] = fake_module
        ocr_ja._MODEL = None
        ocr_ja._get_model()
    finally:
        models.ensure, ocr_ja._MODEL = real_ensure, real_model
        if real_mod is None:
            sys.modules.pop("manga_ocr", None)
        else:
            sys.modules["manga_ocr"] = real_mod

    c.check(ensured == ["manga-ocr"],
            f"ocr_ja asks models.ensure for the pinned model (asked for {ensured})")
    c.check(captured.get("path") == sentinel,
            f"ocr_ja hands MangaOcr that path, not a repo id (got {captured.get('path')!r})")
    # CPU unless select_provider says CUDA: on a box with no GPU this is True
    # as it always was; on the GPU build it is False, and a literal True here
    # would have pinned manga-ocr to the CPU on the one machine that has one.
    want_cpu = models.select_provider()[0] != "CUDAExecutionProvider"
    c.check(captured.get("force_cpu") is want_cpu,
            f"ocr_ja forces CPU exactly when select_provider does not say CUDA "
            f"(want force_cpu={want_cpu}, got {captured.get('force_cpu')!r})")

    check_rename(c)
    check_warmup(c)
    return c.finish()


def check_warmup(c):
    """[warmup] models load ahead of the first page, and never in the way of one.

    Every loader is replaced by a recorder here: the point is the ordering,
    locking and skipping around the loads, and a GPU model load would make
    this offline check depend on the box it runs on.
    """
    import tempfile
    import time as _time

    from fastapi.testclient import TestClient

    from sidecar import detect, inpainter, main, ocr_ja, pipeline, textmask

    real = (detect._model, ocr_ja._get_model, inpainter._lama, textmask.session,
            models.on_disk, pipeline.warm_models, main.start_warmup)
    saved_env = {k: os.environ.get(k) for k in (pipeline.WARMUP_ENV, "MT_INPAINTER")}
    os.environ.pop("MT_INPAINTER", None)
    calls, logs = [], []

    def recorder(name, fail=False):
        def load():
            calls.append(name)
            if fail:
                raise RuntimeError(f"{name} is broken")
        return load

    try:
        # -- every model the page needs, in one pass -----------------------
        detect._model, ocr_ja._get_model = recorder("detector"), recorder("manga-ocr")
        inpainter._lama = recorder("lama")
        textmask.session = lambda weights, progress=None: calls.append("text-mask") or object()
        textmask._SESSION = None
        models.on_disk = lambda name: True
        loaded = pipeline.warm_models(log=logs.append)
        c.check(loaded == ["detector", "manga-ocr", "text-mask", "lama"] and calls == loaded,
                f"[warmup] warm_models loads the detector, manga-ocr, the text mask and LaMa: {loaded}")

        # -- a model not on disk is skipped, never fetched -----------------
        calls.clear(); logs.clear(); textmask._SESSION = None
        models.on_disk = lambda name: name != "manga-ocr"
        loaded = pipeline.warm_models(log=logs.append)
        c.check("manga-ocr" not in calls and "manga-ocr" not in loaded
                and any("manga-ocr not downloaded" in m for m in logs),
                f"[warmup] a model not yet downloaded is skipped and named, not fetched at launch: {logs}")

        # -- a failure is logged, and the rest still load ------------------
        calls.clear(); logs.clear(); textmask._SESSION = None
        models.on_disk = lambda name: True
        ocr_ja._get_model = recorder("manga-ocr", fail=True)
        loaded = pipeline.warm_models(log=logs.append)
        c.check("manga-ocr" not in loaded and "lama" in loaded
                and any("manga-ocr failed to load" in m and "is broken" in m for m in logs),
                f"[warmup] a model that fails to load is logged and skipped, and the others still "
                f"load: loaded={loaded}")

        # -- fill mode needs no erase models -------------------------------
        calls.clear(); textmask._SESSION = None
        ocr_ja._get_model = recorder("manga-ocr")
        os.environ["MT_INPAINTER"] = "fill"
        loaded = pipeline.warm_models(log=logs.append)
        c.check(loaded == ["detector", "manga-ocr"],
                f"[warmup] with MT_INPAINTER=fill the erase models are not loaded: {loaded}")
        os.environ.pop("MT_INPAINTER", None)

        # -- a page arriving mid-warm-up waits, and one copy is built ------
        built = []

        def slow_session(weights, progress=None):
            _time.sleep(0.5)
            built.append(object())
            return built[-1]

        textmask.session, textmask._SESSION = slow_session, None
        detect._model = ocr_ja._get_model = inpainter._lama = (lambda: None)
        import threading as _threading
        warm = _threading.Thread(target=pipeline.warm_models, kwargs={"log": logs.append})
        warm.start()
        _time.sleep(0.15)  # the warm-up holds the lock inside the slow build
        with pipeline._MODEL_LOCK:
            page_view = textmask._model()
        warm.join(5)
        c.check(len(built) == 1 and page_view is built[0],
                f"[warmup] a page that asks for a model mid-warm-up gets the warm-up's copy, "
                f"not a second one: {len(built)} built")

        # -- the lifespan never waits on it --------------------------------
        def slow_warm(log=None):
            _time.sleep(4)
            return []

        pipeline.warm_models = slow_warm
        os.environ[pipeline.WARMUP_ENV] = "1"
        with tempfile.TemporaryDirectory(prefix="mt-warm-cache-") as tmp:
            os.environ["MT_CACHE_DIR"] = tmp
            t0 = _time.perf_counter()
            with TestClient(main.app) as client:
                r = client.get("/api/health")
                waited = _time.perf_counter() - t0
            c.check(r.status_code == 200 and waited < 2.0,
                    f"[warmup] /api/health answers while a 4 s warm-up is still running: "
                    f"{r.status_code} in {waited:.2f}s")

            started = []
            main.start_warmup = lambda: started.append(1)
            os.environ.pop(pipeline.WARMUP_ENV, None)
            with TestClient(main.app) as client:
                client.get("/api/health")
            c.check(not started,
                    "[warmup] without MT_WARMUP=1 (a check, a TestClient) nothing is warmed")
            os.environ[pipeline.WARMUP_ENV] = "1"
            with TestClient(main.app) as client:
                client.get("/api/health")
            c.check(started == [1], "[warmup] with MT_WARMUP=1 the lifespan starts it once")
            os.environ.pop("MT_CACHE_DIR", None)
    finally:
        (detect._model, ocr_ja._get_model, inpainter._lama, textmask.session,
         models.on_disk, pipeline.warm_models, main.start_warmup) = real
        textmask._SESSION = None
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # -- no_download: a bad or missing file is refused, never fetched ---------
    import urllib.request as _urlreq

    real_urlopen = _urlreq.urlopen
    opened = []
    _urlreq.urlopen = lambda *a, **k: opened.append(a) or (_ for _ in ()).throw(AssertionError("network"))
    try:
        with tempfile.TemporaryDirectory(prefix="mt-nodl-") as tmp:
            bad = os.path.join(tmp, "model.onnx")
            with open(bad, "wb") as fh:
                fh.write(b"right size, wrong bytes")
            kinds = []
            for dest in (bad, os.path.join(tmp, "missing.onnx")):
                try:
                    with models.no_download():
                        models.fetch("http://example.invalid/model.onnx", dest, "0" * 64, 23)
                    kinds.append("returned")
                except models.FetchError as e:
                    kinds.append(e.kind)
        c.check(kinds == ["absent", "absent"] and not opened,
                f"[warmup] under no_download a file that fails its checksum, and a missing one, "
                f"raise FetchError('absent') without opening a connection: {kinds}, {len(opened)} opened")
        try:
            models.fetch("http://example.invalid/model.onnx", os.path.join(tempfile.gettempdir(),
                         "mt-nodl-outside.onnx"), "0" * 64, 23)
        except (models.FetchError, AssertionError):
            pass
        c.check(len(opened) == 1,
                "[warmup] and outside no_download the same fetch does try the network")
    finally:
        _urlreq.urlopen = real_urlopen

    # -- presence by size, and the cuDNN search mode ------------------------
    with tempfile.TemporaryDirectory(prefix="mt-ondisk-") as tmp:
        saved = os.environ.get("MT_MODEL_DIR")
        os.environ["MT_MODEL_DIR"] = tmp
        try:
            entry = models.MANIFEST["text-detection-db"]
            dest = os.path.join(tmp, os.path.basename(entry["url"].split("?")[0]))
            absent = models.on_disk("text-detection-db")
            with open(dest, "wb") as fh:
                fh.truncate(entry["size"] - 1)
            short = models.on_disk("text-detection-db")
            with open(dest, "wb") as fh:
                fh.truncate(entry["size"])
            whole = models.on_disk("text-detection-db")
            c.check((absent, short, whole) == (False, False, True) and not models.on_disk("no-such-model"),
                    f"[warmup] on_disk is true only for a file of the manifest's size "
                    f"(absent, short, whole) = {(absent, short, whole)}")
        finally:
            if saved is None:
                os.environ.pop("MT_MODEL_DIR", None)
            else:
                os.environ["MT_MODEL_DIR"] = saved

    import onnxruntime
    seen = []
    real_session, real_select = onnxruntime.InferenceSession, models.select_provider
    onnxruntime.InferenceSession = lambda path, sess_options=None, providers=None: seen.append(providers)
    try:
        models.select_provider = lambda force_cpu=None: ("CUDAExecutionProvider", "")
        models.onnx_session("x.onnx")
        models.select_provider = lambda force_cpu=None: ("CPUExecutionProvider", "forced")
        models.onnx_session("x.onnx")
    finally:
        onnxruntime.InferenceSession, models.select_provider = real_session, real_select
    c.check(seen == [[("CUDAExecutionProvider", {"cudnn_conv_algo_search": "HEURISTIC"})],
                     ["CPUExecutionProvider"]],
            f"[warmup] CUDA sessions use HEURISTIC cuDNN search, CPU sessions no options: {seen}")


def check_rename(c):
    """[rename] MangaTranslator's data directory moves to Komalingo, once, whole.

    The weights under it are hundreds of MB; a rename that only changed the
    string would download every one of them again and orphan the old tree.
    """
    import tempfile

    from sidecar import appdir, cache

    with tempfile.TemporaryDirectory(prefix="mt-rename-") as base:
        old = os.path.join(base, "MangaTranslator", "models", "manga-ocr")
        os.makedirs(old)
        with open(os.path.join(old, "weights.bin"), "wb") as fh:
            fh.write(b"w" * 1024)

        saved = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "MT_MODEL_DIR", "MT_CACHE_DIR")}
        os.environ["LOCALAPPDATA"] = base
        os.environ.pop("MT_MODEL_DIR", None)
        os.environ.pop("MT_CACHE_DIR", None)
        try:
            got = models.model_dir() if os.name == "nt" else None
            got_cache = cache.root()
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        moved = os.path.join(base, "Komalingo", "models", "manga-ocr", "weights.bin")
        if os.name == "nt":
            c.check(got == os.path.join(base, "Komalingo", "models"),
                    f"[rename] model_dir is under Komalingo: {got}")
        c.check(got_cache == os.path.join(base, "Komalingo", "cache"),
                f"[rename] the cache root is under Komalingo: {got_cache}")
        c.check(os.path.getsize(moved) == 1024 and not os.path.exists(os.path.join(base, "MangaTranslator")),
                "[rename] the old MangaTranslator tree was MOVED into place, weights and all, "
                "not copied and not left behind")

        # Both present: never merged, the old one left exactly where it is.
        os.makedirs(os.path.join(base, "MangaTranslator", "stray"))
        c.check(appdir.under(base) == os.path.join(base, "Komalingo")
                and os.path.isdir(os.path.join(base, "MangaTranslator", "stray")),
                "[rename] with both directories present the new one wins and the old one is untouched")

    with tempfile.TemporaryDirectory(prefix="mt-rename-") as base:
        c.check(appdir.under(base) == os.path.join(base, "Komalingo")
                and not os.listdir(base),
                "[rename] on a fresh machine the path is Komalingo and nothing is created by asking")


run(main)
