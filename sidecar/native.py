r"""The native libraries the sidecar needs and pip cannot deliver (AC-6, .cbr).

Exactly one format needs this module. `zipfile` reads zip/cbz, `tarfile` reads
tar/cbt and `py7zr` reads 7z/cb7, all of them pure Python; RAR is the only
container with no reader in the standard library or on PyPI, and this project
reads it through `libarchive-c`, which is a binding and ships no library.

**No libarchive release carries a Windows binary.** Not for any tag -- the
build order's §C row 7 assumed an official release asset and there is none. So
the library is fetched from conda-forge, which is the only pinnable win-64
source, and every file is checked against a sha256 recorded here.

Fetched and never committed, which is the point of doing it this way:
`models.fetch()` already resumes a partial download, verifies a sha256,
refuses on mismatch and checks free space first, and it is gated by
`check_models.py` for AC-14. Four megabytes of third-party native code in git
history cannot be taken back out; a pinned hash can be re-pinned.

**What the pins are, and what they are not.** Each sha256 below is the hash
anaconda.org reports for that exact artifact, verified on download here. That
makes the fetch reproducible and tamper-evident. It does not make conda-forge
trusted -- it makes it *pinned*: the bytes that arrive are the bytes that were
reviewed, and a later republish under the same name cannot pass silently.

**The closure is the real import table, not the declared dependency list.**
conda's metadata for libarchive names openssl; `archive.dll`'s PE imports do
not -- it uses Windows CNG through bcrypt.dll. Taking the declared list would
have bundled OpenSSL, and shipping a stale OpenSSL is worse than shipping
none. The nine files below are the transitive closure of the actual imports,
recomputed by tests/check_native.py rather than trusted from this comment.

**libxml2 is the no-ICU build on purpose.** conda-forge ships libxml2-16 in
two variants at the same version; the default links ICU, which is 16.8MB plus
its data. libarchive imports libxml2 for the XAR reader, which this project
never opens, but a hard import must still resolve -- so the variant matters
and the wrong one costs 17MB for a format nobody reads.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

from . import atomic, models

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBARCHIVE_DIR = os.path.join(ROOT, "build", "libarchive")

CONDA_FORGE = "https://conda.anaconda.org/conda-forge/"

# name -> (path under conda-forge, sha256, the DLLs it contributes)
#
# Pinned to exact builds. A range would defeat the hash, and "latest" would
# mean the closure recomputed by check_native could pass on one machine and
# fail on the next.
PACKAGES = {
    "libarchive": (
        "win-64/libarchive-3.8.9-lgpl_hb42df8c_1.conda",
        "b99265b28739c9d10bad5c2396c07d6796297d774d31e58854447e952f780bcc",
        ("archive.dll",),
    ),
    "libiconv": (
        "win-64/libiconv-1.18-hc1393d2_3.conda",
        "35e04e3ddac7720fc7c550a1c9f998604299d6a7bd1f3ec9b2825d825061daa2",
        ("iconv.dll", "charset.dll"),
    ),
    "bzip2": (
        "win-64/bzip2-1.0.8-h0ad9c76_10.conda",
        "04767466ee9227c9c57ab2c6503e0149177d34111c7418d2f420297acb1eb229",
        ("libbz2.dll",),
    ),
    "liblzma": (
        "win-64/liblzma-5.8.3-hfd05255_1.conda",
        "d36c4a1e1f80fd08e18a407e03622ff2f34dfdd022da6488ad19603dea19e6d5",
        ("liblzma.dll",),
    ),
    # h692994f, not h3cfd58e: the no-ICU variant. See the module docstring.
    "libxml2-16": (
        "win-64/libxml2-16-2.15.4-h692994f_0.conda",
        "4bea1b30d1a77854484fe7773c934b7189e66bd3d9a60ec1cfe2c1aae469e733",
        ("libxml2.dll",),
    ),
    "lz4-c": (
        "win-64/lz4-c-1.10.0-h6a83c73_2.conda",
        "6824e36be0f95ae516dc36dddd18f69cbad0e4e07906fcb10a5f26a8dc471903",
        ("lz4.dll",),
    ),
    "libzlib": (
        "win-64/libzlib-1.3.2-hfd05255_3.conda",
        "0629c2cc0404d3bb29d6baa7b4ba62da80797015e86de050db81ea5a07050527",
        ("zlib.dll",),
    ),
    "zstd": (
        "win-64/zstd-1.5.7-h534d264_7.conda",
        "ca7daae4f218a11fab82cc2857f0ea518ec3f46acec60490485347a4c22c6b3e",
        # the package also carries libzstd.dll, which nothing in the closure
        # imports; it is not copied, so the bundle stays the closure exactly
        ("zstd.dll",),
    ),
}

# Every DLL the bundle must end up holding, in one place so the check and the
# fetch agree by construction rather than by both being edited.
REQUIRED_DLLS = tuple(sorted(
    dll for _rel, _sha, dlls in PACKAGES.values() for dll in dlls
))


class NativeMissing(Exception):
    """A native dependency could not be installed, with a named reason."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def bundled() -> bool:
    """Whether build/libarchive already holds the whole closure."""
    return all(os.path.isfile(os.path.join(LIBARCHIVE_DIR, d)) for d in REQUIRED_DLLS)


def _bsdtar() -> str:
    r"""Windows' own tar.exe, which is bsdtar and therefore reads .tar.zst.

    A `.conda` package is a zip holding `pkg-*.tar.zst`, and no zstd decoder
    ships with CPython 3.12 (`compression.zstd` arrives in 3.14). Rather than
    add a build-time dependency for one unpack, this uses the bsdtar Windows
    has shipped in System32 since Windows 10 1803 -- which is itself
    libarchive, so the thing being installed is what unpacks it.

    Named failure, not a FileNotFoundError from subprocess, because "tar is
    missing" is a sentence someone can act on and a WinError 2 is not.
    """
    candidate = os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"), "System32", "tar.exe"
    )
    if os.path.isfile(candidate):
        return candidate
    found = shutil.which("tar")
    if found:
        return found
    raise NativeMissing(
        "no tar.exe: a .conda package is zstd-compressed inside and Windows' "
        "bundled bsdtar is what unpacks it here. Windows 10 1803 and later "
        "ship it in System32"
    )


def _unpack(conda_path: str, into: str) -> None:
    """Extract one .conda package's Library/bin into `into`."""
    with tempfile.TemporaryDirectory(prefix="mt-native-") as tmp:
        try:
            with zipfile.ZipFile(atomic.long_path(conda_path)) as z:
                inner = [
                    n for n in z.namelist()
                    if n.startswith("pkg-") and n.endswith(".tar.zst")
                ]
                if not inner:
                    raise NativeMissing(
                        f"{os.path.basename(conda_path)} carries no pkg-*.tar.zst; "
                        f"it is not a .conda package"
                    )
                z.extract(inner[0], tmp)
        except zipfile.BadZipFile as e:
            raise NativeMissing(
                f"{os.path.basename(conda_path)} is not readable as a zip ({e})"
            ) from e

        result = subprocess.run(
            [_bsdtar(), "-xf", os.path.join(tmp, inner[0]), "-C", tmp],
            capture_output=True, encoding="utf-8", errors="replace",
        )
        if result.returncode != 0:
            raise NativeMissing(
                f"unpacking {os.path.basename(conda_path)} failed "
                f"(tar exit {result.returncode}): {result.stderr.strip()[:200]}"
            )

        binaries = os.path.join(tmp, "Library", "bin")
        if not os.path.isdir(binaries):
            raise NativeMissing(
                f"{os.path.basename(conda_path)} has no Library/bin"
            )
        os.makedirs(into, exist_ok=True)
        for name in os.listdir(binaries):
            if name.endswith(".dll"):
                shutil.copy2(os.path.join(binaries, name), os.path.join(into, name))


def ensure_libarchive(progress=None) -> str:
    """Put the libarchive closure in build/libarchive. Return archive.dll's path.

    Idempotent: a complete bundle returns immediately without touching the
    network, so this is safe to call on every start. Only the DLLs the closure
    names are kept -- a package that also carries something unimported does
    not get to widen the bundle by accident.
    """
    target = os.path.join(LIBARCHIVE_DIR, "archive.dll")
    if bundled():
        return target

    cache = os.path.join(LIBARCHIVE_DIR, ".packages")
    staging = os.path.join(LIBARCHIVE_DIR, ".staging")
    shutil.rmtree(staging, ignore_errors=True)

    for name, (rel, sha256, _dlls) in PACKAGES.items():
        dest = os.path.join(cache, os.path.basename(rel))
        try:
            models.fetch(CONDA_FORGE + rel, dest, sha256=sha256, progress=progress)
        except models.FetchError as e:
            raise NativeMissing(f"{name}: {e.reason}") from e
        _unpack(dest, staging)

    missing = [d for d in REQUIRED_DLLS if not os.path.isfile(os.path.join(staging, d))]
    if missing:
        raise NativeMissing(
            f"the packages unpacked but the closure is incomplete: {', '.join(missing)} "
            f"absent from {staging}"
        )

    # Only now, and only the closure: a half-populated build/libarchive would
    # read to libarchive_path() as a usable bundle and fail at load instead.
    os.makedirs(LIBARCHIVE_DIR, exist_ok=True)
    for name in REQUIRED_DLLS:
        # atomic._replace, not shutil.move: it is the module's own retrying
        # os.replace, and a DLL that another process has mapped is exactly the
        # case Windows makes a moving target.
        atomic._replace(
            atomic.long_path(os.path.join(staging, name)),
            atomic.long_path(os.path.join(LIBARCHIVE_DIR, name)),
        )
    shutil.rmtree(staging, ignore_errors=True)
    return target


if __name__ == "__main__":  # pragma: no cover -- the operator entry point
    def _say(done, total):
        if total:
            sys.stdout.write(f"\r  {done / 1e6:6.2f} / {total / 1e6:6.2f} MB")
            sys.stdout.flush()

    try:
        path = ensure_libarchive(progress=_say)
    except NativeMissing as exc:
        sys.stderr.write(f"\nlibarchive not installed: {exc.reason}\n")
        raise SystemExit(1) from exc
    total = sum(
        os.path.getsize(os.path.join(LIBARCHIVE_DIR, d)) for d in REQUIRED_DLLS
    )
    print(f"\nlibarchive ready: {path}")
    print(f"  {len(REQUIRED_DLLS)} DLLs, {total / 1e6:.2f} MB")
