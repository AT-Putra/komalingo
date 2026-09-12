"""Phase 0 -- LLM client contract. Fully OFFLINE, against tests/lib/stub_provider.

Runs with no MT_BASE_URL and no API key: everything here talks to the in-process
stub. The live endpoint is check_probe.py's job, and keeping the two apart is
what lets this check run on a machine with no network at all.

The three load-bearing asserts:
  * 10 concurrent pages never put more than 3 requests in flight (the semaphore)
  * a 5-region page costs exactly 1 chat request (page-context batching)
  * a 401 and a 500 arrive at the caller with status AND body verbatim (AC-8)

It also owns the [env-local] section. lib/env_local.py is what puts
MT_BASE_URL / MT_API_KEY / MT_MODEL in front of the two LIVE checks, and
those two skip on a machine with no credentials -- so the parsing and, more
importantly, the does-not-override rule would be exercised nowhere that can
go red in CI. It is asserted here, offline, against a temporary file and
names of its own.
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from sidecar.llm import LLMClient, ProviderError, Region  # noqa: E402
from lib.env_local import load_env_local  # noqa: E402
from lib.result import Checks, run  # noqa: E402
from lib.stub_provider import FIXTURES, StubProvider  # noqa: E402

MODEL = "cx/gpt-5.6-sol"  # a fixture model id, not a configured default


def regions(n):
    return [Region(id=i, text=f"テスト{i}") for i in range(n)]


def env_local(c) -> None:
    """[env-local] the loader fills gaps and never overwrites (lib/env_local.py)."""
    names = ["MTTEST_QUOTED", "MTTEST_PLAIN", "MTTEST_SPACED", "MTTEST_HELD"]
    file_lines = [
        "# a comment",
        "",
        'MTTEST_QUOTED="quoted value"',
        "MTTEST_PLAIN=plain",
        "  MTTEST_SPACED = spaced ",
        "MTTEST_HELD=from-the-file",
        "a line with no equals sign",
    ]
    for n in names:
        os.environ.pop(n, None)
    os.environ["MTTEST_HELD"] = "from-the-environment"
    # .env.local.example tells a developer to set MT_NO_ENV_LOCAL=1 to
    # reproduce CI's skip path. Inherited here it short-circuits the loader
    # and reddens three of these asserts -- indistinguishable from a real
    # regression, and produced by following the documentation.
    inherited = os.environ.pop("MT_NO_ENV_LOCAL", None)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env.local")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(chr(10).join(file_lines) + chr(10))
            loaded = load_env_local(path)

            c.check(sorted(loaded) == ["MTTEST_PLAIN", "MTTEST_QUOTED", "MTTEST_SPACED"],
                    f"[env-local] returns the names it SET, comments and junk lines "
                    f"ignored (got {sorted(loaded)})")
            c.check(os.environ.get("MTTEST_QUOTED") == "quoted value",
                    "[env-local] surrounding quotes are stripped")
            c.check(os.environ.get("MTTEST_SPACED") == "spaced",
                    "[env-local] whitespace around the key and the value is stripped")
            c.check(os.environ.get("MTTEST_HELD") == "from-the-environment",
                    f"[env-local] a name already in the environment WINS over the file "
                    f"(got {os.environ.get('MTTEST_HELD')!r})")
            c.check("MTTEST_HELD" not in loaded,
                    "[env-local] and it is not reported as loaded")
            c.check(not any(v in loaded for v in ("plain", "quoted value")),
                    "[env-local] no VALUE is ever returned -- MT_API_KEY is a credential")

            # An absent file is a clean clone, which must skip rather than raise.
            c.check(load_env_local(os.path.join(tmp, "nothing-here")) == [],
                    "[env-local] an absent file returns [] and raises nothing")

            # The suppression the skip path depends on: without it, the one
            # kind of box that HAS credentials cannot reproduce CI's skip.
            os.environ.pop("MTTEST_PLAIN", None)
            os.environ["MT_NO_ENV_LOCAL"] = "1"
            try:
                c.check(load_env_local(path) == [] and "MTTEST_PLAIN" not in os.environ,
                        "[env-local] MT_NO_ENV_LOCAL=1 reads nothing at all")
            finally:
                os.environ.pop("MT_NO_ENV_LOCAL", None)
    finally:
        for n in names:
            os.environ.pop(n, None)
        if inherited is not None:
            os.environ["MT_NO_ENV_LOCAL"] = inherited


def main():
    c = Checks("check_provider")

    env_local(c)

    # --- construction refuses to invent credentials ------------------------
    for missing, label in ((("", MODEL), "base_url"), (("http://x/v1", ""), "model")):
        try:
            LLMClient(missing[0], None, missing[1])
            c.check(False, f"empty {label} is rejected")
        except ValueError:
            c.check(True, f"empty {label} is rejected rather than defaulted")

    with StubProvider() as stub:
        client = LLMClient(stub.url, None, MODEL)  # no API key: local servers

        # --- models list is unfiltered ------------------------------------
        models = client.list_models()
        ids = [m["id"] for m in models]
        c.check(len(models) == 4, f"all 4 fixture models are listed, got {len(models)}")
        c.check(
            "cx/gpt-5.6-sol" in ids and "cx/claude-opus-5" in ids,
            "owned_by=combo models are NOT filtered out",
        )
        c.check(
            all(isinstance(m.get("owned_by"), str) for m in models)
            and {m["owned_by"] for m in models} == {"combo", "openai", "local"},
            f"and each carries its owner ({[m.get('owned_by') for m in models]})",
        )

        # --- batching: 5 regions -> 1 request ------------------------------
        before = stub.chat_requests
        out = asyncio.run(client.translate_page(regions(5), page_png=b"\x89PNG-fake"))
        issued = stub.chat_requests - before
        c.check(issued == 1, f"a 5-region page issues exactly 1 chat request, got {issued}")
        c.check(len(out) == 5, f"all 5 regions come back translated, got {len(out)}")

        # The image really went with it -- otherwise "page context" is a lie.
        content = stub.last_payload["messages"][0]["content"]
        c.check(
            any(p.get("type") == "image_url" for p in content),
            "the page image travels in the same request as the regions",
        )

        # --- batching splits above MAX_REGIONS -----------------------------
        before = stub.chat_requests
        asyncio.run(client.translate_page(regions(41)))
        issued = stub.chat_requests - before
        c.check(issued == 2, f"41 regions split into 2 requests, got {issued}")

        # --- concurrency: 10 pages, never more than 3 in flight ------------
        stub.peak_concurrency = 0

        async def ten_pages():
            await asyncio.gather(*(client.translate_page(regions(2)) for _ in range(10)))

        asyncio.run(ten_pages())
        c.check(
            stub.peak_concurrency <= 3,
            f"10 queued pages never exceed 3 in flight, peaked at {stub.peak_concurrency}",
        )
        # And the stub could have seen more -- otherwise the cap assert is
        # vacuous and would pass with the semaphore deleted.
        c.check(
            stub.peak_concurrency > 1,
            f"control: the stub did see real concurrency ({stub.peak_concurrency} > 1)",
        )

    # --- AC-8: the provider's own words reach the caller -------------------
    with open(os.path.join(FIXTURES, "error_401.json"), "rb") as fh:
        body_401 = fh.read().decode()
    with open(os.path.join(FIXTURES, "error_500.html"), "rb") as fh:
        body_500 = fh.read().decode()

    for status, expected in ((401, body_401), (500, body_500)):
        with StubProvider(status=status, delay=0) as stub:
            client = LLMClient(stub.url, "sk-wrong", MODEL)
            try:
                asyncio.run(client.translate_page(regions(1)))
                c.check(False, f"a {status} raises ProviderError")
            except ProviderError as e:
                c.check(e.status == status, f"ProviderError carries status {status}, got {e.status}")
                c.check(
                    e.body == expected,
                    f"the {status} body arrives VERBATIM, not summarised",
                )

    # --- an unreachable host is still a ProviderError, not a traceback -----
    client = LLMClient("http://127.0.0.1:1/v1", None, MODEL)
    try:
        asyncio.run(client.translate_page(regions(1)))
        c.check(False, "an unreachable provider raises ProviderError")
    except ProviderError as e:
        c.check(e.status == 0 and e.body, f"unreachable host reports why: {e.body[:60]}")

    return c.finish()


run(main)
