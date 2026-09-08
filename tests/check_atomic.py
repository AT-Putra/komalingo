"""Phase 0 -- the write protocol. Offline, no fixtures, no network.

Asserts, from the build order:
  1. a 280-character destination path works
  2. a crash between temp-write and os.replace leaves neither a partial
     destination nor a temp file
  3. the temp file is created in the DESTINATION directory, not %TEMP%
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from sidecar import atomic  # noqa: E402
from lib.result import Checks, run  # noqa: E402


def main():
    c = Checks("check_atomic")

    with tempfile.TemporaryDirectory() as root:
        # --- 1: 280-character destination ---------------------------------
        # Built at runtime rather than committed, so the repo itself stays
        # clonable on a machine without long paths enabled.
        deep = root
        while len(deep) < 240:
            deep = os.path.join(deep, "nested_directory_segment")
        dest = os.path.join(deep, "x" * (280 - len(deep) - 5) + ".txt")
        c.check(len(dest) >= 280, f"destination path is {len(dest)} chars (>=280)")

        with atomic.atomic_write(dest) as fh:
            fh.write(b"long path payload")
        c.check(
            os.path.exists(atomic.long_path(dest))
            and open(atomic.long_path(dest), "rb").read() == b"long path payload",
            "write into a 280-char destination path succeeds",
        )

        # --- 3: temp file lives in the destination directory ---------------
        # Checked before 2 because it needs a successful write to observe.
        seen = {}
        target = os.path.join(root, "sub", "observed.bin")

        def observe(tmp, dst):
            seen["tmp"] = tmp
            seen["dst"] = dst

        atomic.crash_hook = observe
        try:
            with atomic.atomic_write(target) as fh:
                fh.write(b"payload")
        finally:
            atomic.crash_hook = None

        c.check(
            os.path.dirname(seen["tmp"]) == os.path.dirname(seen["dst"]),
            "temp file is created in the destination directory",
        )
        c.check(
            not os.path.realpath(seen["tmp"]).startswith(
                os.path.realpath(tempfile.gettempdir())
            ),
            "temp file is NOT in %TEMP% (os.replace is only atomic per-volume)",
        )

        # --- 2: crash between temp-write and os.replace ---------------------
        victim = os.path.join(root, "sub", "victim.bin")
        with atomic.atomic_write(victim) as fh:
            fh.write(b"original")

        def boom(tmp, dst):
            raise RuntimeError("simulated crash before os.replace")

        atomic.crash_hook = boom
        try:
            with atomic.atomic_write(victim) as fh:
                fh.write(b"replacement that must never land")
        except RuntimeError:
            pass
        finally:
            atomic.crash_hook = None

        c.check(
            open(atomic.long_path(victim), "rb").read() == b"original",
            "crash before os.replace leaves the destination untouched",
        )

        # A raise inside the block, rather than in the hook, is the same
        # contract from the caller's side.
        try:
            with atomic.atomic_write(os.path.join(root, "sub", "never.bin")) as fh:
                fh.write(b"partial")
                raise ValueError("caller raised mid-write")
        except ValueError:
            pass

        c.check(
            not os.path.exists(atomic.long_path(os.path.join(root, "sub", "never.bin"))),
            "raise inside the block leaves no destination file",
        )

        leftovers = [f for f in os.listdir(os.path.join(root, "sub")) if f.endswith(".tmp")]
        c.check(not leftovers, f"no temp files left behind (found {leftovers})")

    return c.finish()


run(main)
