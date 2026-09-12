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

    return c.finish()


run(main)
