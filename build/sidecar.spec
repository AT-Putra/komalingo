# -*- mode: python ; coding: utf-8 -*-
"""One-file build of the sidecar.

Run from the repo root:  uv run --project sidecar pyinstaller build/sidecar.spec

Two things here are load-bearing and easy to undo by accident:

  * The entry point is build/launch.py, NOT sidecar/main.py. main.py uses
    relative imports, and a script run as __main__ has no package.

  * torch and onnxruntime are collected wholesale rather than named import by
    import. Their submodules resolve at first USE, not at import, so a health
    poll on the built exe proves nothing about them -- which is exactly why
    check_package.py runs a full translate through the packaged binary.

The longPathAware manifest MUST be applied here, through EXE(manifest=...), and
NOT merged in afterwards with mt.exe. A one-file exe is a PE followed by an
appended PKG archive; mt.exe rewrites the resource section, moves everything
after it, and the bootloader can no longer find the archive it is standing on:

    [PYI-3992:ERROR] Could not load PyInstaller's embedded PKG archive

The build then produces an exe that launches and dies. PyInstaller embeds the
manifest before appending the archive, which is the only ordering that survives.
"""
import os

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

hidden = ["uvicorn", "uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
          "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on", "fastapi", "pydantic"]
binaries = []
for optional in ("torch", "onnxruntime"):
    try:
        hidden += collect_submodules(optional)
        binaries += collect_dynamic_libs(optional)
    except Exception as exc:
        print(f"[sidecar.spec] {optional} not collected: {exc}")

a = Analysis(
    [os.path.join(ROOT, "build", "launch.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=[],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "pytest"],
    noarchive=False,
)
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
