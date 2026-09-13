"""The app's per-user data directory, and the one-time move from its old name.

The app was MangaTranslator until 2026-09-13 and is Komalingo since. Its
weights (hundreds of MB) and its page cache live under a directory named
after it, so a rename that only changed the string would leave the old tree
orphaned on disk and download every model again on the first launch. The
old directory is RENAMED into place instead -- one os.rename on the same
volume, instant whatever the size -- the first time anything asks.
"""

from __future__ import annotations

import os

NAME = "Komalingo"
OLD_NAMES = ("MangaTranslator",)


def under(base: str) -> str:
    """`base`/Komalingo, moving an old-named sibling there if it is the only one.

    Never merges and never deletes: when the new directory already exists the
    old one is left exactly where it is. When the rename fails -- another
    process holds a file open inside the old tree -- this launch keeps
    reading the OLD directory, so nothing is re-downloaded, and the next
    launch tries again.
    """
    new = os.path.join(base, NAME)
    if os.path.exists(new):
        return new
    for old in OLD_NAMES:
        prev = os.path.join(base, old)
        if not os.path.isdir(prev):
            continue
        try:
            os.rename(prev, new)
        except OSError:
            if os.path.exists(new):
                return new  # another process moved it first
            return prev
        return new
    return new
