# Sidecar binaries

`sidecar-<target-triple>.exe` is produced by `build/sidecar.spec` (US-010,
PyInstaller) and is NOT committed -- it is hundreds of megabytes of torch.

Tauri resolves the target-triple-suffixed name at build time and fails the
build if the file is absent, so a zero-byte placeholder lives here until the
packaging story lands. check_package.py builds the real one; check_ipc.py
asserts the app finds it at this exact name.

ponytail: a placeholder, not a binary. Ceiling: `cargo build` links and the
name resolution is proven, but the app cannot actually spawn it. Upgrade path:
US-010 writes the real exe to this path and check_package.py launches it.
