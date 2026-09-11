# Honorifics and register in the Indonesian output (AC-4)

This is the prose statement of `sidecar/glossary_id.json`. The JSON is what
the prompt quotes and what `tests/check_id.py` grades against; this document
is what a reader is pointed at when they ask why a bubble says *Tanaka-san*
and not *Pak Tanaka*. `check_id` asserts that every honorific in the JSON is
named here, so the two cannot drift apart silently. Edit both.

## The rule

Japanese honorific suffixes are **kept in romaji**, hyphenated to the name,
the way Indonesian manga publishers have printed them for twenty years and
the way their readers expect them. They are never translated into Indonesian
kinship or courtesy terms, because those carry different information: *Pak*
says the speaker is younger or lower, *-san* only says the speaker is being
ordinarily polite, and a translation that swaps one for the other changes
the relationship on the page.

The one honorific the source **omits** is also information. A bare name is
intimacy or contempt, and the output keeps it bare so the reader can tell
which from the panel.

## The table

| Japanese | Rendered as | When |
|---|---|---|
| さん | `-san` | ordinary politeness; kept as a suffix on the name |
| ちゃん | `-chan` | affection; children and close friends; kept |
| くん | `-kun` | younger males and juniors; kept |
| 様 | `-sama` | deference; kept |
| 殿 | `-dono` | archaic deference; kept |
| 先輩 | `senpai` | a senior at school or work — as a form of address (*Senpai!*) or as a suffix (*Tanaka-senpai*); **never** *Kak* |
| 後輩 | `kouhai` | a junior, as a noun |
| 先生 | `sensei` | a teacher, doctor or artist — as address or suffix; **never** *Pak Guru* / *Bu Guru* |
| (bare name) | (bare name) | no suffix in the source, no suffix in the output |

## Register

Indonesian marks distance with pronouns where Japanese marks it with verb
forms, so the pronoun choice carries the register:

- Casual dialogue between friends and family: *aku* / *kau* or *kamu*,
  dropped particles, contractions (*nggak*, *udah*) where the speaker is
  plainly informal.
- Formal or deferential speech (to a superior, a customer, a stranger):
  *saya* / *Anda*, full forms.
- Narration boxes: standard written Indonesian, no slang.

## What stays as it is

Brand names, abbreviations and any Latin-script token in the source (*VR*,
*OK*, *TV*, a game title on a box) are copied through. The glossary's `keep`
list names the common ones; the rule is general. Sound effects are the
exception: kana SFX are rendered as Indonesian onomatopoeia (*ドキドキ* →
*deg-deg*), as printed editions do, not left in kana.

## What the gate holds

`tests/check_id.py` translates forty reference lines and asserts, in order of
weight: no English function word survives in any output; the corpus scores
chrF++ ≥ 0.45 against the approved Indonesian; every honorific in a source
line is rendered as this table says, and the same way everywhere it occurs.
Naturalness beyond the reference set is not gated — the build order says so
in as many words — and this document is the standard a human reviewer
applies where the gate stops.
