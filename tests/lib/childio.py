"""Spawn a child whose output is drained from the first byte, and keep it.

The drain is not a convenience, and this module exists because the same
mistake has now been made twice in this suite.

A pipe holds a fixed amount -- 64 KB on Linux, as little as 4 KB for an
anonymous pipe on Windows. Past that the child BLOCKS on write. If the harness
is meanwhile blocked reading the child's socket, the two wait on each other
forever, and every real failure inside the child reaches the reader as a bare
500, a reset, or a read that times out with no body.

check_package.py hit it first: a missing unidic_lite dictionary stayed
invisible for two lanes' worth of iterations while its traceback sat unread in
a full pipe. check_api.py hit it second, and much worse -- it did not merely
hide a diagnosis, it MANUFACTURED one. An unhandled exception in the sidecar
made the next request time out, the check reported "the sidecar stopped
answering", and that was written up as an application-level hang that does not
exist. The server was fine; it was blocked writing a traceback into a pipe
this harness never read. A test harness that can invent a bug is worse than
one that hides it, because the invented bug gets fixed.

So: drain from a thread that starts before the first request, keep the lines,
and hand them back on demand -- whether or not the child is still alive.
"""

from __future__ import annotations

import subprocess
import threading

# Keyed by pid, so `captured(proc)` works from anywhere without threading the
# handle through every call site.
_CAPTURED: dict[int, list] = {}


def launch_drained(cmd, merge_stderr: bool = True, **kwargs) -> subprocess.Popen:
    """Popen with stdout (and by default stderr) read continuously by threads.

    merge_stderr=False keeps the two streams as separate pipes, both drained
    into the SAME capture list -- interleaved the way a console would show
    them, which is what a reader wants when the question is "what did the
    child say before it broke".
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
        **kwargs,
    )
    lines: list = []
    _CAPTURED[proc.pid] = lines

    def drain(pipe):
        for raw in iter(pipe.readline, b""):
            lines.append(raw.decode("utf-8", "replace").rstrip())

    for pipe in (proc.stdout, proc.stderr):
        if pipe is not None:
            threading.Thread(target=drain, args=(pipe,), daemon=True).start()
    return proc


def captured(proc, tail: int = 40) -> str:
    """What the child actually said, whether or not it is still alive."""
    return "\n".join(_CAPTURED.get(proc.pid, [])[-tail:])


def said(proc, needle: str) -> bool:
    """True if the child ever printed `needle`. Reads the whole capture."""
    return any(needle in line for line in _CAPTURED.get(proc.pid, []))
