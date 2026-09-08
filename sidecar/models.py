"""First-launch model fetch, and the CUDA-or-CPU decision.

Resumable by design. These are hundreds of megabytes over a home connection,
and a user who loses the download at 90% and has to start again will close the
app instead. So the partial file is a real, persistent `.part` next to the
destination -- deliberately NOT atomic.py's temp file, which exists to be
deleted on failure. Here the partial surviving IS the feature.

Every failure path names its reason. A checksum mismatch, a dead network and a
full disk are three different problems with three different user actions, and
"model download failed" tells the user none of them.
"""

from __future__ import annotations

import hashlib
import http.client
import os
import shutil
import urllib.error
import urllib.request

from . import atomic

CHUNK = 1 << 20
TIMEOUT = 60
HEADROOM = 64 << 20  # keep the volume off zero even if our own maths is exact

# Pinned by digest, not by "latest". A model that changes under a released
# build changes the app's output with no version bump to explain it.
MANIFEST = {
    "manga-ocr": {
        "url": "https://huggingface.co/kha-white/manga-ocr-base/resolve/main/pytorch_model.bin",
        "sha256": "",  # filled at Phase 1 when the real weights are pinned
        "size": 0,
    },
}


class FetchError(RuntimeError):
    """Always carries a reason a user can act on."""

    def __init__(self, reason: str, kind: str = "error"):
        self.reason = reason
        self.kind = kind  # network | checksum | space | error
        super().__init__(reason)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def _free_space(directory: str, need: int) -> None:
    try:
        free = shutil.disk_usage(directory).free
    except OSError as e:
        raise FetchError(f"cannot read free space on {directory}: {e}", "space") from None
    if need and free < need + HEADROOM:
        raise FetchError(
            f"need {need / 1e6:.0f} MB plus headroom, {free / 1e6:.0f} MB free on {directory}",
            "space",
        )


def fetch(url: str, dest, sha256: str = "", size: int = 0, progress=None) -> str:
    """Download `url` to `dest`, resuming a previous `.part` if one is there.

    Returns the destination path. Raises FetchError with a named reason on
    every failure -- never a bare urllib traceback.
    """
    dest = atomic.long_path(dest)
    directory = os.path.dirname(dest)
    os.makedirs(directory, exist_ok=True)
    part = dest + ".part"

    if os.path.exists(dest) and (not sha256 or _sha256(dest) == sha256):
        return dest

    have = os.path.getsize(part) if os.path.exists(part) else 0
    _free_space(directory, max(0, size - have))

    done = total = 0
    req = urllib.request.Request(url)
    if have:
        req.add_header("Range", f"bytes={have}-")

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            # A server that ignores Range answers 200 with the WHOLE file.
            # Appending that to our partial would produce a corrupt file that
            # only the checksum catches, so restart instead.
            if have and r.status != 206:
                have = 0
            total = have + int(r.headers.get("Content-Length") or 0)
            with open(part, "ab" if have else "wb") as fh:
                if not have:
                    fh.truncate(0)
                done = have
                while True:
                    try:
                        chunk = r.read(CHUNK)
                    except http.client.IncompleteRead as e:
                        # A dropped connection strands the bytes already
                        # received inside the exception. Writing them is the
                        # whole point of resuming: discarding them here means
                        # every interruption restarts from zero.
                        fh.write(e.partial)
                        fh.flush()
                        raise FetchError(
                            f"connection dropped after {done + len(e.partial)} bytes; "
                            f"rerun to resume",
                            "network",
                        ) from None
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total or size)
    except urllib.error.URLError as e:
        raise FetchError(f"cannot reach {url}: {e.reason}", "network") from None
    except OSError as e:
        # ENOSPC lands here mid-write, after the up-front check passed.
        raise FetchError(f"write failed for {part}: {e}", "space") from None

    # A dropped connection often just ends the read early rather than raising.
    # Checking the byte count against Content-Length is what separates an
    # INTERRUPTED download from a CORRUPT one -- and they need opposite
    # handling: the interrupted partial must survive to be resumed, the corrupt
    # one must be deleted. Without this the checksum branch below deletes both,
    # and every interruption restarts from zero.
    expected = total or size
    if expected and done < expected:
        raise FetchError(
            f"connection dropped at {done} of {expected} bytes; rerun to resume",
            "network",
        )

    if sha256:
        got = _sha256(part)
        if got != sha256:
            # Delete the partial. Keeping it means the next launch resumes onto
            # known-bad bytes and fails the same way forever.
            os.remove(part)
            raise FetchError(
                f"checksum mismatch for {os.path.basename(dest)}: "
                f"expected {sha256[:16]}..., got {got[:16]}...",
                "checksum",
            )

    os.replace(part, dest)
    return dest


def select_provider(force_cpu: bool = False) -> tuple[str, str]:
    """Return (execution_provider, reason).

    The reason is empty ONLY when CUDA was actually selected. Every fallback
    carries a sentence the Settings UI can show, because "running on CPU" with
    no explanation is indistinguishable from a bug to the person waiting.
    """
    if force_cpu:
        return "CPUExecutionProvider", "CPU forced in settings"

    try:
        import onnxruntime  # noqa: PLC0415 -- optional, absent in Phase 0
    except ImportError as e:
        return "CPUExecutionProvider", f"onnxruntime not installed ({e.name}); using CPU"

    available = onnxruntime.get_available_providers()
    if "CUDAExecutionProvider" not in available:
        return (
            "CPUExecutionProvider",
            f"no CUDA execution provider in this build (have: {', '.join(available)})",
        )

    try:
        import torch  # noqa: PLC0415

        if not torch.cuda.is_available():
            return "CPUExecutionProvider", "no CUDA device visible to torch; using CPU"
    except ImportError:
        pass  # onnxruntime says CUDA is there; torch's absence does not veto it

    return "CUDAExecutionProvider", ""
