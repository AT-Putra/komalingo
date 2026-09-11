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
    # manga-ocr is a DIRECTORY of six files, not one weight blob. transformers
    # resolves the config, the tokenizer's vocab and the weights by NAME out of
    # a single directory, so pinning pytorch_model.bin alone would pin the one
    # file the loader can least do without the other five. Every file therefore
    # carries its own digest, and `ensure` returns the directory.
    #
    # Pinned to a REVISION SHA, not to main -- the same reason the detector is
    # pinned to a tag rather than a branch. This repo's main has already moved
    # past this commit (a later one adds model.safetensors), and "the weights
    # this build was tested against" has to name a fixed point. The digest for
    # pytorch_model.bin below was computed from the downloaded bytes and
    # independently agrees with the lfs.oid HuggingFace reports for that path
    # at this revision, which for an LFS object IS the sha256 of its content.
    "manga-ocr": {
        "base_url": (
            "https://huggingface.co/kha-white/manga-ocr-base/resolve/"
            "aa6573bd10b0d446cbf622e29c3e084914df9741/"
        ),
        "files": {
            "config.json": {
                "sha256": "8c0e395de8fa699daaac21aee33a4ba9bd1309cfbff03147813d2a025f39f349",
                "size": 77546,
            },
            "preprocessor_config.json": {
                "sha256": "af4eb4d79cf61b47010fc0bc9352ee967579c417423b4917188d809b7e048948",
                "size": 228,
            },
            "pytorch_model.bin": {
                "sha256": "c63e0bb5b3ff798c5991de18a8e0956c7ee6d1563aca6729029815eda6f5c2eb",
                "size": 444135475,
            },
            "special_tokens_map.json": {
                "sha256": "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3",
                "size": 112,
            },
            "tokenizer_config.json": {
                "sha256": "d775ad1deac162dc56b84e9b8638f95ed8a1f263d0f56f4f40834e26e205e266",
                "size": 486,
            },
            "vocab.txt": {
                "sha256": "344fbb6b8bf18c57839e924e2c9365434697e0227fac00b88bb4899b78aa594d",
                "size": 24072,
            },
        },
    },
    # PP-OCRv3's Chinese detection head, which is a DB model -- the same head
    # cv2.dnn.TextDetectionModel_DB implements. Pinned to opencv_zoo's 4.10.0
    # TAG, not to main: opencv_zoo has already replaced its text_detection_db
    # directory once, and a branch URL would have gone 404 under a shipped
    # build. The digest below was computed from the downloaded bytes and
    # independently agrees with the git-lfs pointer's oid in the same tree.
    "text-detection-db": {
        "url": (
            "https://media.githubusercontent.com/media/opencv/opencv_zoo/4.10.0/"
            "models/text_detection_ppocr/text_detection_cn_ppocrv3_2023may.onnx"
        ),
        "sha256": "03f550c6b406fda8bf54bd8327815f6c7e2edd98cea02348c93d879254366587",
        "size": 2423490,
    },
    # Phase 4: PP-OCRv5 text-line RECOGNITION for zh and ko (AC-3), as ONNX,
    # run by onnxruntime -- not the paddleocr package, which drags the whole
    # paddlepaddle runtime behind it for one recogniser. The weights are
    # PaddlePaddle's (Apache-2.0), exported by the oar-ocr project and
    # published as GitHub RELEASE assets under a version tag, which is a fixed
    # point the same way opencv_zoo's 4.10.0 tag is. Each digest below is the
    # sha256 GitHub itself reports for the asset, and fetch() verifies it.
    # The dictionary travels with its model: a recogniser's output is an index
    # into a character list, and the wrong list turns every glyph into a
    # different, plausible glyph with no error raised anywhere.
    "pp-ocrv5-rec-zh": {
        "base_url": "https://github.com/GreatV/oar-ocr/releases/download/v0.3.0/",
        "files": {
            "pp-ocrv5_mobile_rec.onnx": {
                "sha256": "243a0f06d826761323e9045e9b113ab2c191c3aa50565585e628300b8eda0224",
                "size": 16562373,
            },
            "ppocrv5_dict.txt": {
                "sha256": "d1979e9f794c464c0d2e0b70a7fe14dd978e9dc644c0e71f14158cdf8342af1b",
                "size": 74012,
            },
        },
    },
    "pp-ocrv5-rec-ko": {
        "base_url": "https://github.com/GreatV/oar-ocr/releases/download/v0.3.0/",
        "files": {
            "korean_pp-ocrv5_mobile_rec.onnx": {
                "sha256": "2d7ed96308065a86103325d22af07a88c4d06afc009f21602a4882342c0cc054",
                "size": 13446374,
            },
            "ppocrv5_korean_dict.txt": {
                "sha256": "a88071c68c01707489baa79ebe0405b7beb5cca229f4fc94cc3ef992328802d7",
                "size": 47451,
            },
        },
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


def model_dir() -> str:
    """Where fetched weights live.

    Not beside the executable and not in the repo: a PyInstaller one-file
    build unpacks to a temp directory that is deleted on exit, so weights
    written there would be re-downloaded on every launch. MT_MODEL_DIR
    overrides it so a check can point at a scratch tree without touching the
    user's real cache.
    """
    override = os.environ.get("MT_MODEL_DIR", "").strip()
    if override:
        return override
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "MangaTranslator", "models")
    return os.path.join(os.path.expanduser("~"), ".cache", "MangaTranslator", "models")


def _shifted(progress, base: int, total: int):
    """One file's progress callback, reported in the whole SET's coordinates.

    A function rather than a closure defined in the caller's loop: `base` and
    `total` are bound as arguments to a fresh frame per call, so the offsets
    cannot be shared or late-bound across iterations. The loop-local version
    was correct too, but only because of a default-argument trick that a
    reader has to stop and verify; this shape is correct by construction.
    """
    if progress is None:
        return None
    return lambda done, _file_total: progress(base + done, total)


def _ensure_directory(name: str, entry: dict, progress=None) -> str:
    """Fetch every file of a multi-file entry into one directory. Returns it.

    Progress is reported across the SET, not per file. Handing the caller a
    bar that restarts at zero six times says "something is happening" and
    nothing else; here five of the six files are under 80 KB and one is
    444 MB, so per-file progress would also spend five of its six resets on
    files the user cannot perceive downloading at all.
    """
    directory = os.path.join(model_dir(), name)
    total = sum(f["size"] for f in entry["files"].values())
    fetched = 0
    for filename, meta in entry["files"].items():
        fetch(entry["base_url"] + filename,
              os.path.join(directory, filename),
              meta["sha256"], meta["size"],
              _shifted(progress, fetched, total))
        fetched += meta["size"]
    return atomic.long_path(directory)


def ensure(name: str, progress=None) -> str:
    """Fetch MANIFEST entry `name` if it is not already on disk. Returns its path.

    A FILE for a single-file entry, a DIRECTORY for a multi-file one -- which
    is what each kind of loader wants to be handed: cv2.dnn reads one .onnx,
    transformers' from_pretrained reads a directory by name.

    Single-file names come from the URL, so the manifest has one source of
    truth for them and a renamed upstream file cannot silently collide with a
    cached older one under a hand-written local name.
    """
    entry = MANIFEST.get(name)
    if entry is None:
        raise FetchError(f"no model named {name!r} in the manifest", "error")
    if "files" in entry:
        return _ensure_directory(name, entry, progress)
    dest = os.path.join(model_dir(), os.path.basename(entry["url"].split("?")[0]))
    return fetch(entry["url"], dest, entry["sha256"], entry["size"], progress)


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
