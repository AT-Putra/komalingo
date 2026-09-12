"""Load the git-ignored .env.local into os.environ for the two live checks.

check_probe.py's docstring has said since Phase 0 that it "must read
MT_BASE_URL, MT_API_KEY, MT_MODEL from .env.local (git-ignored) or die with
exit 3". The code read os.environ only and nothing in the repo ever loaded
the file, so on a fully configured box -- credentials on disk, gateway up --
check_probe and check_id's live half both recorded SKIP and the only two
checks that touch a live endpoint had never run. A promise in a docstring
that no code keeps is worse than no promise: the record said "skipped, no
env var" while the env var was sitting in the repo root.

Three decisions, stated here because each one is a way this could go wrong:

**The real environment wins.** A name already in os.environ is left alone.
CI sets its own values and must not have a developer's file substituted for
them, and an operator overriding one variable for one run
(MT_MODEL=other-model ... check_id) has to see that override take effect.
The file fills gaps; it does not overwrite.

**Nothing is printed but names.** MT_API_KEY is a live credential and these
checks print their whole environment of reasons on failure. The return value
is the list of names set, so a caller can say what it loaded without saying
what it loaded it to.

**MT_NO_ENV_LOCAL suppresses the load entirely.** CI's skip path -- no
file, both checks exit 3 -- is otherwise unreproducible on the one kind of
box that has the file, which would leave the skip branch and its
MT_REQUIRE_LIVE promotion untested everywhere they can actually be run.
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT = os.path.join(ROOT, ".env.local")

# The key shape a shell would accept. Anything else in the file is prose, a
# stray line, or `export KEY=value` -- which would otherwise set a variable
# literally named "export KEY" and leave KEY unset, a silent skip.
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def env_flag(name: str) -> bool:
    """A boolean environment flag, read as a boolean.

    os.environ.get() hands back the STRING "0", which is truthy, so every
    `if os.environ.get(FLAG)` in this suite treated FLAG=0 as ON. Section E
    of the build order tells CI to set MT_REQUIRE_LIVE=0 -- the documented CI
    setting did the exact inverse of what it asks. One implementation, here,
    because the same bug was written twice: once in lib/result.py's skip()
    and once in this module's own MT_NO_ENV_LOCAL guard.
    """
    return os.environ.get(name, "").strip().lower() not in (
        "", "0", "false", "no", "off",
    )


def load_env_local(path=None):
    """Set absent names from `path` into os.environ. Return the names set.

    An absent file is a no-op returning [] -- a clean clone has no
    .env.local by design, and that is a skip, not an error. A malformed line
    is ignored rather than raised on, for the same reason: this is an
    environment file, not a deliverable, and one stray line should not take
    the whole gate down with a traceback about parsing.
    """
    if env_flag("MT_NO_ENV_LOCAL"):
        return []
    try:
        # utf-8-sig, not utf-8: a .env.local saved by Notepad or VS Code on
        # Windows carries a BOM, and under plain utf-8 the first key parses
        # as "﻿MT_BASE_URL" -- MT_BASE_URL stays unset and both live
        # checks skip, silently, which is the defect this module exists to
        # remove. UnicodeDecodeError joins OSError for the same reason a
        # malformed line is ignored: a UTF-16 file (PowerShell 5.1's Out-File
        # default) must not take a check down with a traceback at import.
        with open(path or DEFAULT, encoding="utf-8-sig") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        return []

    loaded = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not KEY_RE.match(key) or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ[key] = value
        loaded.append(key)
    return loaded
