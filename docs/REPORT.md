# Chat filter — accuracy defect report

**Ragnarok: Rebirth Global** · reported by a player · 2026-09-09

---

## The one-line version

The chat filter matches **raw substrings**, so ordinary words containing a
blocked fragment are censored — `cucumber` is blocked because of three letters
inside it — while the same design lets deliberate evasion straight through.

## Verified live, in game

| typed | result | why |
|---|---|---|
| `cucumber` | **blocked** | contains a 3-letter fragment |
| `Heisenberg` | **blocked** | contains a blocked fragment |
| `thank` | **was blocked** (since fixed) | contains a blocked fragment |
| `okay` | fine | control — no fragment |
| `okkk` | **blocked** | contains `kkk` |

`okkk` blocking while `okay` passes is a clean proof that matching is
**substring-based**, not word-based. `cucumber` and `Heisenberg` show what that
costs. None of these are edge cases a player has to hunt for; they came up in
ordinary conversation.

## What this looks like at scale

Running the filter word list shipped inside the client against **the game's own
English item and skill names**:

```
Freezing            ->  ****zing          Card Skills   ->  card ski**s
Immunity Control    ->  i**unity control  Downpour      ->  downpo**
Savage Card         ->  **vage card       Eddga Card    ->  e**ga card
Osiris' Curse       ->  osiris' c**se     Ignite        ->  igni**
```

**46.1%** of 16,381 item and skill names are flagged. **69.0%** of all 81,303
localized strings. **37.1%** of an ordinary English dictionary.

And it is worse outside English. Same list, same method, each locale's own
content:

| locale | own names flagged |
|---|---|
| **Portuguese** | **52.1%** |
| Indonesian | 48.0% |
| English | 46.1% |
| Thai | 30.0% |
| Vietnamese | 9.7% |
| Chinese (Trad) | 9.7% |
| Chinese (Simp) | 8.4% |
| Korean | 0.0% |

The list is **95,660 entries, 93.4% Chinese** — a market-compliance list
(political terms, regional gambling domains, precursor chemicals), appropriate
for the market it was written for. Rebirth launched in China in December 2025
and globally in July 2026, and the list appears to have travelled with the build.
It damages the newer markets roughly **five times more than its home market**.

**11,872 entries are two characters long and 497 are a single character.** Those
are romanized abbreviations and common Han characters. As substrings they sit
inside thousands of ordinary words: `te` inside *ignite*, `ll` inside *skills*,
`ur` inside *curse*, `日` inside *日光*.

## This is not a request to filter less

The same design **fails in the other direction too**. Against ten common
obfuscation strategies the list catches **22.9%**; spaced-out text, full-width
characters and homoglyphs pass untouched. Of 25 common English profanity terms
tested, **6** are present at all.

So the filter blocks `cucumber` and passes `f u c k`. Both symptoms are the same
root cause. Fixing it makes the filter **more** accurate in both directions, not
more permissive.

## One caveat, stated plainly

The list we analysed is the copy **shipped in the client**. It does not fully
match what the server enforces: `cucumber` is blocked live, but the fragment
responsible is not in the client copy, and `ka` *is* in the client copy while
`okay` passes fine. The server list is a different, evolving revision.

**So do not act on our specific rows — run the tools on your own list.** They
take a word list and your own localization export and produce the answer for
whatever you are actually running. The class of defect is proven; the exact rows
are yours to generate.

## What would fix it

Three things, smallest first. Each is independently useful.

**1 — Run the self-test. (~40 lines, no dependencies, no library to adopt.)**

```sh
python3 tools/selftest_filter.py --list <your filter list> \
                                 --strings <your en localization>
```

It enforces one invariant: *no string we authored may be flagged by our own
filter*. If `Freezing` trips your filter, the filter is wrong — there is no
reading in which that is profanity. It has a `--max-failures` ratchet so it can
go into CI today at whatever level is currently true, then be tightened.

**2 — Rank your own entries by damage, and fix the worst.**

```sh
python3 tools/remediate.py --list <your list> --game-corpus <your localization> \
                           --out remediation.csv
```

On the client copy, false positives were extremely concentrated: **20 entries
caused 89%** of them, and fixing those 20 took own-content false positives from
46.1% to 6.2%. Only 191 of 5,695 entries needed any change. The tool emits a CSV
with, per entry, its measured blast radius, a worked example, and a recommended
action — `scope to zh` (keeps the entry, restricts it to the market it was
written for — **deletes nothing**), `whole-word only`, or `delete`.

**3 — Fix the matching.**

Word boundaries plus a rescue allowlist. Same vocabulary, no new words:
English-dictionary false positives drop **37.1% → 0.0%**. With a domain lexicon
generated from your own localization, false positives on your own item names go
**46.1% → 0.0%** while obfuscation recall rises **22.9% → 84.3%**.

On the cases you can verify yourself:

| input | filter today | with the fix |
|---|---|---|
| `cucumber` | blocked | **allowed** |
| `Heisenberg` | blocked | **allowed** |
| `thank` | was blocked | **allowed** |
| `okkk` | blocked | **still blocked** |
| `kkk` | blocked | **still blocked** |
| `f u c k` | passes | **caught** |

The engine is MIT-licensed, dependency-free, ~650 lines, and ships with a
shadow mode that runs beside your existing filter and changes nothing until you
choose to switch.

## Nothing here requires a client update

The filter check is already a server round trip — the client sends the candidate
text and receives a masked string back. Everything above changes only what
happens on the server side of that call. No client build, no store review.

## Reproduce everything

```sh
python3 tests/test_all.py          # 51 tests
python3 tools/conformance.py       # 25 conformance vectors
```

Repository: tools, engine, spec, and the full measurement method, including the
caveats. Nothing proprietary is redistributed — the allowlists ship as
*generators* you run on your own data.
