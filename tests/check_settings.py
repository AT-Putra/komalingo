"""Phase 0 -- the Settings UI and the IPC client (US-009). OFFLINE.

The frontend has no test runner in Phase 0 and adding one to assert six
properties would cost more than it returns. What actually needs proving is not
React behaviour but two things a `tsc` pass cannot see:

  * No credential, base URL or model is baked into src/. This is the standing
    constraint for the whole project -- the three values come from the Settings
    UI at runtime, and a default anywhere in src/ would ship as a hidden
    credential nobody can see to remove.
  * The API key is treated as OPTIONAL. A local llama.cpp or Ollama server
    needs none, and a `required` on that field locks those users out entirely.

Both are properties of the source, so the source is what this reads -- but
never by looking for a word that a comment could also contain. Each assert
targets a construct only real code can produce. See the US-007 note in
progress.txt for why that distinction earns its keep.

The build itself (`npm run build`, i.e. tsc + vite) is the type check, and it
runs here so a broken import fails this check rather than surfacing three
stories later.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from lib.result import Checks, run  # noqa: E402

SRC = os.path.join(ROOT, "src")


def read(*parts):
    with open(os.path.join(SRC, *parts), encoding="utf-8") as fh:
        return fh.read()


def strip_comments(text):
    """Source with comments removed.

    The point of the whole file: an assert that matches its own explanatory
    comment is an assert that cannot go red. US-007 shipped one of those --
    "compare_digest" stayed green with both guards deleted because the word
    appeared in the comment above them. Stripping first makes that impossible
    here rather than relying on care.
    """
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    # (?<!:) or the // in "http://" is read as a line comment and the rest of
    # the line vanishes -- which is precisely the line a hardcoded base URL
    # lives on. Without it, planting the dev endpoint in api.ts left assert [1]
    # green: the needle had already been stripped before the search ran.
    return re.sub(r"(?<!:)//[^\n]*", "", text)


def walk_src():
    for base, _, files in os.walk(SRC):
        for f in files:
            if f.endswith((".ts", ".tsx")):
                yield os.path.join(base, f)


def main():
    c = Checks("check_settings")

    settings = read("routes", "Settings.tsx")
    apilib = read("lib", "api.ts")
    code = {p: strip_comments(open(p, encoding="utf-8").read()) for p in walk_src()}

    # A sweep over an empty set passes every needle trivially. Assert the
    # search space first, by name, so "found in []" always means "looked and
    # found nothing" rather than "never looked".
    swept = {os.path.relpath(p, SRC).replace("\\", "/") for p in code}
    c.check(
        {"lib/api.ts", "routes/Settings.tsx"} <= swept,
        f"the sweep actually reads the settings sources ({sorted(swept)})",
    )

    # -- nothing hardcoded, anywhere in src/ --------------------------------
    # The dev key and dev endpoint are the concrete things that must never
    # appear; the model name likewise. Comments stripped, so a docstring
    # mentioning them would not mask a real one.
    for needle, label in (
        ("sk-", "an API key"),
        ("localhost:20128", "the dev base URL"),
        ("cx/gpt-5.6-sol", "the dev model"),
    ):
        hits = [os.path.relpath(p, ROOT) for p, s in code.items() if needle in s]
        c.check(not hits, f"no {label} anywhere in src/ ({needle!r}) -- found in {hits}")

    # A default value on any of the three is the same failure wearing a
    # different hat: it ships as a credential the user cannot see to remove.
    # loadSettings must fall back to empty strings.
    # api.ts holds TWO literal records with these fields -- the merge-with-
    # stored one and the fallback. Both must default to empty, so this asserts
    # on every occurrence of each field rather than picking one record and
    # trusting the regex to have found the right one. (It did not, first try:
    # it matched the merge record and reported the spread as a default.)
    lib_code = strip_comments(apilib)
    for field in ("base_url", "model", "api_key"):
        vals = re.findall(field + r':\s*("[^"]*")', lib_code)
        c.check(bool(vals), f"api.ts sets a literal {field} default")
        c.check(
            all(v == '""' for v in vals),
            f"and every {field} default is empty, not a value ({vals})",
        )

    # -- the API key is optional and may be empty ---------------------------
    # Required-ness in this form is expressed by disabling the buttons, so that
    # is where it has to be checked. `ready` gates the test button; if api_key
    # were in it, an empty key would disable the whole page for local servers.
    ready = re.search(r"const ready\s*=\s*([^;]+);", strip_comments(settings))
    c.check(ready is not None, "Settings computes a `ready` gate")
    if ready:
        expr = ready.group(1)
        c.check("base_url" in expr and "model" in expr, "ready requires base_url and model")
        c.check("api_key" not in expr, f"and NOT api_key -- it may be empty ({expr.strip()})")

    c.check(
        'type="password"' in settings,
        "the API key field is a password input, not plain text",
    )

    # -- the error path shows the provider's own words (AC-8) ---------------
    c.check("describeError" in strip_comments(settings), "Settings renders errors via describeError")
    c.check(
        re.search(r"HTTP \$\{e\.status\}", apilib) is not None
        and re.search(r"\$\{e\.body\}", apilib) is not None,
        "describeError interpolates the sidecar's own status AND body",
    )
    # status 0 is "never reached the sidecar" -- it must not render as "HTTP 0",
    # which reads like a real response and sends the user hunting the provider.
    c.check(
        re.search(r"e\.status === 0\s*\?\s*e\.body", apilib) is not None,
        "status 0 renders the body alone, not a fake HTTP 0",
    )

    # -- settings persist across restarts -----------------------------------
    c.check(
        "localStorage.setItem" in lib_code and "localStorage.getItem" in lib_code,
        "settings are persisted",
    )
    c.check(
        "JSON.parse" in lib_code and "try" in lib_code,
        "and a corrupt stored record is caught rather than blanking the page",
    )

    # -- the model list comes from the user's endpoint ----------------------
    c.check("api.models" in strip_comments(settings), "Settings loads models from the endpoint")
    c.check(
        "Test with sample image" in settings,
        "the sample-image test button exists",
    )

    # -- it compiles --------------------------------------------------------
    r = subprocess.run(
        ["npm", "run", "build"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        shell=(os.name == "nt"),
    )
    c.check(r.returncode == 0, f"npm run build exits 0{'' if r.returncode == 0 else ': ' + r.stderr[-400:]}")

    return c.finish()


run(main)
