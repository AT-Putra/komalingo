"""Phase 5 -- Indonesian output and the glossary (AC-4). Offline half always;
live half when MT_BASE_URL and MT_MODEL are set -- from the environment, or
from the git-ignored .env.local via lib.env_local, which never overrides a
name the environment already carries -- else exit 3.

The build order rewrote this gate once already: its first draft graded
self-consistency and glossary-key coverage, and both reviewers showed that a
stub splicing glossary terms into English sentences passes that. What the
stub cannot do is remove English's closed class -- "the", "is", "of", "to" --
and correct Indonesian never contains it (yang, itu, dan, ke, dari, dengan,
tidak share nothing with it). So:

  [glossary-doc]  sidecar/glossary_id.json and docs/honorifics.md agree: every
                  honorific rendering in the JSON is named in the document.
  [prompt]        offline, through the stub: the request for lang=id carries
                  "Indonesian", every policy rule and every honorific
                  rendering; the request for lang=en carries none of them;
                  source=ko says Korean and not Japanese; the rung-5 rewrite
                  no longer says English.
  [function-words] LIVE: across all forty outputs, zero English function words
                  (tests/lib/asserts.ENGLISH_FUNCTION_WORDS, whole tokens,
                  case-insensitive, the line's allowlist excepted).
  [chrf]          LIVE: corpus chrF++ >= 0.45 against fixtures/id/reference.json.
  [glossary]      LIVE: every honorific the reference marks for a line is
                  rendered in that line's output as the table says, and none
                  of the renderings the table forbids (Pak Guru, Bu Guru,
                  Kak, Bapak, Ibu) stands in for it.
  [determinism]   LIVE: the same forty lines asked a second time render every
                  honorific the same way -- the consistency clause of AC-4,
                  across runs, not byte-identical prose.

Stated plainly, as the build order does: chrF++ against forty lines measures
closeness to the approved Indonesian, not fluency in general. And the
reference's own provenance field says who approved it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

# Every assert below prints the Japanese source line it graded. On a cp1252
# console that is a UnicodeEncodeError in the middle of the offline half,
# before the check has decided anything -- which is what a direct
# `python tests/check_id.py` did on Windows until now. run_all.py forces
# PYTHONIOENCODING=utf-8 on its children and so never saw it, and
# PYTHONIOENCODING read out of .env.local cannot help: the interpreter has
# already chosen the codec by the time any line of this file runs. Same line
# as check_tategaki.py, for the same reason.
getattr(sys.stdout, "reconfigure", lambda **_: None)(encoding="utf-8", errors="replace")

from lib.asserts import chrf_pp, english_function_words  # noqa: E402
from lib.env_local import load_env_local  # noqa: E402
from lib.result import Checks, run, skip  # noqa: E402
from lib.stub_provider import StubProvider, requested_items  # noqa: E402
from sidecar import llm  # noqa: E402
from sidecar.llm import LLMClient, Region  # noqa: E402

GLOSSARY = os.path.join(ROOT, "sidecar", "glossary_id.json")
DOC = os.path.join(ROOT, "docs", "honorifics.md")
REFERENCE = os.path.join(ROOT, "fixtures", "id", "reference.json")

CHRF_FLOOR = 0.45
# Renderings the glossary forbids, per honorific: an output carrying one of
# these where the table's form belongs has translated the honorific away.
FORBIDDEN = {
    "-san": ["Bapak ", "Ibu ", "Pak ", "Bu "],
    "senpai": ["Kak "],
    "sensei": ["Pak Guru", "Bu Guru"],
}

load_env_local()

BASE = os.environ.get("MT_BASE_URL", "").rstrip("/")
KEY = os.environ.get("MT_API_KEY", "")
MODEL = os.environ.get("MT_MODEL", "")


def _payload_text(payload) -> str:
    texts = []
    for msg in payload.get("messages", []):
        content = msg.get("content")
        if isinstance(content, list):
            texts += [p.get("text", "") for p in content if p.get("type") == "text"]
        elif isinstance(content, str):
            texts.append(content)
    return "\n".join(texts)


# -- [glossary-doc] ----------------------------------------------------------


def _glossary_doc(c, glossary: dict) -> None:
    with open(DOC, encoding="utf-8") as fh:
        doc = fh.read()
    for h in glossary["honorifics"]:
        c.check(h["id"] in doc and h["ja"] in doc,
                f"[glossary-doc] {h['ja']} -> {h['id']} is named in docs/honorifics.md")


# -- [prompt] ----------------------------------------------------------------


def _prompt(c, glossary: dict) -> None:
    regions = [Region(id=1, text="田中さん、行こう"), Region(id=2, text="先輩！")]
    with StubProvider(delay=0) as stub:
        client = LLMClient(stub.url, "k", "stub-model")
        asyncio.run(client.translate_page(regions, lang="id", source="ja"))
        text_id = _payload_text(stub.last_payload)
        c.check("Indonesian" in text_id and "Japanese" in text_id,
                "[prompt id] names the source (Japanese) and the target (Indonesian)")
        for rule in glossary["policy"]:
            c.check(rule in text_id, f"[prompt id] carries the rule {rule[:50]!r}...")
        for h in glossary["honorifics"]:
            c.check(f"{h['ja']} -> {h['id']}" in text_id,
                    f"[prompt id] carries the honorific {h['ja']} -> {h['id']}")
        for t in glossary["terms"][:3]:
            c.check(f"{t['ja']} -> {t['id']}" in text_id,
                    f"[prompt id] carries the term {t['ja']} -> {t['id']}")
        c.check([i["id"] for i in requested_items(stub.last_payload)] == [1, 2],
                "[prompt id] the regions still come LAST and parse back out")

        asyncio.run(client.translate_page(regions, lang="en", source="ja"))
        text_en = _payload_text(stub.last_payload)
        c.check("English" in text_en and "Rules:" not in text_en
                and not any(f"{h['ja']} -> {h['id']}" in text_en for h in glossary["honorifics"]),
                "[prompt en] names English and carries no glossary")

        asyncio.run(client.translate_page(regions, lang="en", source="ko"))
        text_ko = _payload_text(stub.last_payload)
        c.check("Korean" in text_ko and "Japanese" not in text_ko,
                "[prompt ko] source=ko says Korean, not Japanese")

        try:
            asyncio.run(client.translate_page(regions, lang="fr", source="ja"))
            c.check(False, "[prompt] an unknown target raises")
        except llm.SettingsError as e:
            c.check("fr" in str(e), f"[prompt] an unknown target raises SettingsError: {e}")

        asyncio.run(client.retranslate_capped([(1, "Tanaka-san, pulang bareng, yuk.", 20)]))
        text_rw = _payload_text(stub.last_payload)
        c.check("English" not in text_rw and "same language" in text_rw,
                "[prompt rewrite] rung 5's rewrite is language-neutral")


# -- [live] ------------------------------------------------------------------


def _translate(client, lines) -> dict:
    regions = [Region(id=i + 1, text=line["ja"]) for i, line in enumerate(lines)]
    return asyncio.run(client.translate_page(regions, lang="id", source="ja"))


def _renderings(line, out: str) -> tuple:
    """Which of the line's marked honorifics appear in `out`, and which forbidden forms."""
    hits = tuple(h for h in line["honorifics"] if h.lower() in out.lower())
    bad = tuple(f for h in line["honorifics"] for f in FORBIDDEN.get(h, []) if f in out)
    return hits, bad


def _live(c, lines) -> dict:
    client = LLMClient(BASE, KEY, MODEL)
    out = _translate(client, lines)
    hyps = [out.get(i + 1, "") for i in range(len(lines))]
    refs = [line["id"] for line in lines]

    c.check(all(hyps), f"[live] every line came back ({sum(1 for h in hyps if h)}/{len(lines)})")

    hits_total = 0
    for line, hyp in zip(lines, hyps):
        hits = english_function_words(hyp, allow=line["allow"])
        hits_total += len(hits)
        c.check(not hits, f"[function-words] {hyp!r:.60} carries no English function word "
                          f"(found {hits})")

    score = chrf_pp(hyps, refs)
    c.check(score >= CHRF_FLOOR, f"[chrf] corpus chrF++ {score:.4f} >= {CHRF_FLOOR} against "
                                 f"the reference ({len(lines)} lines)")

    first = []
    for line, hyp in zip(lines, hyps):
        want = tuple(line["honorifics"])
        got, bad = _renderings(line, hyp)
        first.append(got)
        if want:
            c.check(got == want and not bad,
                    f"[glossary] {line['ja']!r:.24} -> {hyp!r:.50}: renders {list(want)} "
                    f"(got {list(got)}, forbidden forms {list(bad)})")

    again = _translate(client, lines)
    second = [_renderings(line, again.get(i + 1, ""))[0] for i, line in enumerate(lines)]
    c.check(first == second,
            f"[determinism] a second request renders every honorific the same way "
            f"({sum(a != b for a, b in zip(first, second))} lines differ)")

    return {"id_chrf": round(score, 4), "id_function_word_hits": hits_total}


def main():
    c = Checks("check_id")

    with open(GLOSSARY, encoding="utf-8") as fh:
        glossary = json.load(fh)
    with open(REFERENCE, encoding="utf-8") as fh:
        reference = json.load(fh)
    lines = reference["lines"]
    c.check(len(lines) >= 40, f"[reference] {len(lines)} lines >= 40")
    c.check("provenance" in reference and "human_approved" in reference,
            f"[reference] provenance stated (human_approved={reference.get('human_approved')})")
    for h in glossary["honorifics"]:
        if h["id"].startswith("("):
            continue
        n = sum(h["id"] in line["honorifics"] for line in lines)
        c.check(n >= 2, f"[reference] {h['id']} occurs in {n} lines >= 2")

    _glossary_doc(c, glossary)
    _prompt(c, glossary)

    if not BASE or not MODEL:
        # The offline half has run; the live half cannot. The whole check is
        # a skip rather than a pass, because a pass here would say the
        # Indonesian was graded and it was not.
        print(f"  offline asserts: {c.n - len(c.failures)}/{c.n} ok")
        if c.failures:
            return c.finish()
        return skip(f"MT_BASE_URL and MT_MODEL must both be set for the live half "
                    f"(got BASE={bool(BASE)} MODEL={bool(MODEL)})", live=True)

    metrics = _live(c, lines)
    print("METRICS " + json.dumps(metrics))
    return c.finish()


run(main)
