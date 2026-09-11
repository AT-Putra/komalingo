r"""The single write protocol. Every file this app produces goes through here.

Two invariants the rest of the codebase depends on:
  1. The temp file lives in the DESTINATION directory, never %TEMP%. os.replace
     is only atomic within one volume, and %TEMP% is routinely on another.
  2. Every path is long-path-prefixed unconditionally. Prefixing only when the
     path looks long means the prefix is exercised for the first time on a
     user's machine rather than in CI.
"""

from __future__ import annotations

import os
import sys
import threading
from contextlib import contextmanager

# Crash-injection hook. check_package.py sets this to park a write between the
# temp-write and the os.replace, then kills the process, to prove no temp file
# survives a mid-flight shutdown. Left as a module global on purpose: the
# subprocess under test cannot be handed a callback any other way.
crash_hook = None

_PREFIX = "\\\\?\\"
_UNC_PREFIX = "\\\\?\\UNC\\"


def long_path(path) -> str:
    r"""Absolute, normalized, and \\?\-prefixed on Windows.

    The prefix turns off Win32 path parsing entirely, so the path must already
    be absolute with no '.', '..' or '/' left in it -- hence abspath+normpath
    first, unconditionally.
    """
    p = os.path.normpath(os.path.abspath(os.fspath(path)))
    if sys.platform != "win32" or p.startswith(_PREFIX):
        return p
    if p.startswith("\\\\"):  # UNC \\server\share -> \\?\UNC\server\share
        return _UNC_PREFIX + p[2:]
    return _PREFIX + p


@contextmanager
def atomic_write(dest, mode: str = "wb", encoding: str | None = None):
    """Yield a handle whose bytes land at `dest` only if the block completes.

    On any exception the temp file is removed and `dest` is left exactly as it
    was -- including not existing.
    """
    dest = long_path(dest)
    directory = os.path.dirname(dest)
    os.makedirs(directory, exist_ok=True)

    # In the destination directory (invariant 1), and prefixed with a dot so a
    # directory glob run mid-write does not pick it up as real output.
    #
    # Thread ident as well as pid. The sidecar's routes are sync, so FastAPI
    # runs two concurrent requests in two threadpool threads of ONE process --
    # and two threads writing the same destination with a pid-only temp name
    # open the same temp file, and the second fails with PermissionError
    # [WinError 32] out of a job that did nothing wrong. Measured by the Phase
    # 3 review: 72 of 240 concurrent writes. The name still matches `.*.tmp`,
    # which is what check_package's stray-file sweep looks for.
    tmp = os.path.join(
        directory,
        f".{os.path.basename(dest)}.{os.getpid()}.{threading.get_ident()}.tmp",
    )

    fh = open(tmp, mode, encoding=encoding)
    try:
        yield fh
        fh.flush()
        os.fsync(fh.fileno())  # os.replace is atomic; it is not durable
        fh.close()
        if crash_hook is not None:
            crash_hook(tmp, dest)
        os.replace(tmp, dest)
    except BaseException:
        try:
            fh.close()
        finally:
            try:
                os.remove(tmp)
            except FileNotFoundError:
                pass
        raise
