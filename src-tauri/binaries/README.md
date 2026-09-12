# Sidecar binaries

`sidecar-<target-triple>.exe` is produced by `build/sidecar.spec` (PyInstaller)
and is NOT committed -- it is hundreds of megabytes of torch. Tauri resolves
the target-triple-suffixed name at build time and fails the build if the file
is absent, so before `npm run tauri dev` or `npm run tauri build` it has to be
here. From the repo root:

    uv run --project sidecar python -m sidecar.native        # once: fetch libarchive
    uv run --project sidecar python tests/check_package.py  # builds build/dist/<exe> and proves it
    copy build\dist\sidecar-x86_64-pc-windows-msvc.exe src-tauri\binaries\

`check_package.py` is the build step on purpose: it launches the exe it just
built, drives a translate and a `.cbr` through it, and refuses the shutdown
route without the nonce. An exe that only built is not proven.

Until 2026-09-12 a zero-byte placeholder was TRACKED here so that `cargo
build` could link before the packaging story existed; that hid the fact that
the app had never spawned a real sidecar from this path, and it defeated the
`.gitignore` rule for `*.exe` in this directory (an ignore rule does not apply
to a file already in the index), so the real 330MB binary copied over it
would have shown as a modification one `git add -A` away from history. The
placeholder is untracked now; the ignore rule covers the real file.
