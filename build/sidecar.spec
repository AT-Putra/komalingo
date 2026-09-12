# -*- mode: python ; coding: utf-8 -*-
"""One-file build of the sidecar.

Run from the repo root:  uv run --project sidecar pyinstaller build/sidecar.spec

Three things here are load-bearing and easy to undo by accident:

  * The entry point is build/launch.py, NOT sidecar/main.py. main.py uses
    relative imports, and a script run as __main__ has no package.

  * torch and onnxruntime are collected wholesale rather than named import by
    import. Their submodules resolve at first USE, not at import, so a health
    poll on the built exe proves nothing about them -- which is exactly why
    check_package.py runs a full translate through the packaged binary.

  * unidic_lite's dicdir and manga_ocr's assets are collected as DATA. Nothing
    imports either, so the module graph cannot see them, and without them
    manga-ocr's tokenizer and its warm-up inference both fail inside the frozen
    exe. Deleting that block produces a binary that passes every check short of
    a real translate.

The longPathAware manifest MUST be applied here, through EXE(manifest=...), and
NOT merged in afterwards with mt.exe. A one-file exe is a PE followed by an
appended PKG archive; mt.exe rewrites the resource section, moves everything
after it, and the bootloader can no longer find the archive it is standing on:

    [PYI-3992:ERROR] Could not load PyInstaller's embedded PKG archive

The build then produces an exe that launches and dies. PyInstaller embeds the
manifest before appending the archive, which is the only ordering that survives.
"""
import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

hidden = ["uvicorn", "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
          "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "fastapi", "pydantic"]
binaries = []
datas = []
for optional in ("torch", "onnxruntime"):
    try:
        hidden += collect_submodules(optional)
        binaries += collect_dynamic_libs(optional)
    except Exception as exc:
        print(f"[sidecar.spec] {optional} not collected: {exc}")

# Two packages carry files the module graph cannot see, because nothing
# imports them -- and the OCR stage is unusable without either:
#
#   unidic_lite  dicdir/ is a compiled MeCab dictionary, not modules. Without
#                it manga-ocr's BertJapaneseTokenizer cannot be built at all.
#   manga_ocr    assets/example.jpg. MangaOcr.__init__ runs a warm-up
#                inference on that image, so constructing the model fails
#                without it even though no code path imports it.
#
# Both failures land on the FIRST OCR CALL -- an exe that builds, launches and
# answers /api/health, which is exactly why check_package.py drives a full
# translate through the packaged binary rather than polling health.
#
# fugashi is deliberately NOT collected here. Its native side already arrives
# on its own: the binary dependency scan follows fugashi.cp312-win_amd64.pyd to
# the delvewheel DLL beside it, and PKG-00.toc carries both that .pyd and
# fugashi.libs\libmecab-<hash>.dll. collect_dynamic_libs("fugashi") and
# collect_data_files("fugashi") both return empty lists against this
# environment -- listing it would be a no-op that reads like insurance.
REQUIRED_DATA = {
    "unidic_lite": os.path.join("unidic_lite", "dicdir"),
    "manga_ocr": os.path.join("manga_ocr", "assets"),
}
for package, expected in REQUIRED_DATA.items():
    collected = collect_data_files(package)
    if not any(dest.replace("/", os.sep).rstrip(os.sep).endswith(expected) for _, dest in collected):
        # Loud, not a warning. This block exists because the previous build
        # shipped exactly this gap in silence, and a printed warning inside a
        # three-minute PyInstaller log is indistinguishable from no warning.
        raise SystemExit(
            f"[sidecar.spec] {expected} did not collect from {package}. Building "
            f"would produce an exe that starts, answers /api/health, and then "
            f"dies on the first OCR call. Refusing to bake that in."
        )
    datas += collected

# libarchive, for the .cbr read path (AC-6). Nine native DLLs that pip cannot
# deliver: sidecar/native.py fetches them from conda-forge under pinned
# sha256s into build/libarchive, and archive.libarchive_path() looks for them
# at <_MEIPASS>/libarchive inside a frozen build -- which is where this puts
# them. Refused loudly when incomplete, for the REQUIRED_DATA reason: an exe
# without them builds, launches, answers /api/health, translates every zip,
# 7z and tar, and fails on the user's first .cbr with a message about a
# missing library. check_package.py drives a .cbr through the built exe so
# that gap cannot ship twice.
import sys as _sys
_sys.path.insert(0, ROOT)
from sidecar import native as _native  # noqa: E402

_missing = [d for d in _native.REQUIRED_DLLS
            if not os.path.isfile(os.path.join(_native.LIBARCHIVE_DIR, d))]
if _missing:
    raise SystemExit(
        f"[sidecar.spec] build/libarchive is incomplete ({', '.join(_missing)} "
        f"absent). Run `uv run --project sidecar python -m sidecar.native` "
        f"first. Refusing to build an exe that cannot read .cbr."
    )
binaries += [(os.path.join(_native.LIBARCHIVE_DIR, d), "libarchive")
             for d in _native.REQUIRED_DLLS]

a = Analysis(
    [os.path.join(ROOT, "build", "launch.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)

# PyInstaller's binary scan follows archive.dll's imports and copies its eight
# siblings a SECOND time, to the bundle root, under their bare names
# (PKG-00.toc showed zlib.dll, zstd.dll, liblzma.dll ... twice). archive.dll
# resolves its siblings from its own directory first, so the copies are
# harmless today -- and a bare zlib.dll at the root of the frozen search path
# is a latent shadow for any extension module that loads one by name, and it
# is not the closure "exactly" that native.py promises. Keep only the copies
# under libarchive/.
_closure = {os.path.normcase(os.path.join(_native.LIBARCHIVE_DIR, d))
            for d in _native.REQUIRED_DLLS}
a.binaries = [
    entry for entry in a.binaries
    if not (os.path.normcase(entry[1]) in _closure
            and not entry[0].replace("\\", "/").startswith("libarchive/"))
]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="sidecar-x86_64-pc-windows-msvc",
    manifest=os.path.join(ROOT, "build", "longpath.manifest"),
    debug=False,
    strip=False,
    upx=False,
    console=True,
    target_arch=None,
)
