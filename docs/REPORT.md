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

Three options, smallest first. Each works alone; they compose.

### 1 — One line. No data, no list review.

> **A blocked entry shorter than N characters matches only as a whole word,
> never inside a longer one.**

```
if (entry.length < 4 && !isWholeWord(text, matchStart, matchEnd))
    continue;               // short entries must stand alone
```

Measured on your own localized item and skill names:

| locale | today | N=3 | **N=4** | N=5 |
|---|---|---|---|---|
| English | 46.1% | 7.6% | **4.0%** | 3.0% |
| Portuguese | 52.1% | 8.2% | **0.9%** | 0.5% |
| Indonesian | 48.0% | 6.2% | **3.1%** | 2.2% |
| Thai | 30.0% | 4.3% | **2.4%** | 1.9% |
| Vietnamese | 9.7% | 3.4% | **2.5%** | 2.4% |
| Chinese (Simp) | 8.4% | 2.5% | **2.3%** | 2.1% |
| Chinese (Trad) | 9.7% | 2.9% | **2.7%** | 2.6% |
| Korean | 0.0% | 0.0% | 0.0% | 0.0% |

**Nothing is deleted.** Every entry keeps working; short ones simply stop
matching inside longer words. No entry needs reviewing, no new data is required,
and — the part that matters most — it covers vocabulary nobody has enumerated.
Surnames, place names, next year's slang, and the proper nouns that no
dictionary contains are all protected by a rule rather than by a list.

Ship it behind a config value defaulting to 1 (today's behaviour), set it to 4,
revert by setting it back. Reproduce the table with:

```sh
python3 tools/lengthrule.py --list <your list> --corpus en:<your en export>
```

### 2 — An allowlist of words that must never be censored.

`deploy/allowlist-en.txt` — **473,841 words**, assembled from the public-domain
web2 dictionary, GeoNames world cities and countries, US Census 2010 surnames,
BSD given names, and hand-written MMO vocabulary.

Wire it in immediately before your filter returns "blocked":

```python
if rescue.is_rescued(text, match_start, match_end):
    pass          # ordinary word — let it through
else:
    block()       # your existing behaviour, unchanged
```

Suppress the block when the span sits **strictly inside** an allowlisted word.
Strictly: a word identical to the blocked term never rescues itself, so adding a
term to your blocklist cannot silently stop working. Measured 76 MB resident,
0.08 s load, **0.35 µs per check**.

This is purely additive — it can only ever unblock, never block more — and
`tools/build_allowlist.py` regenerates it from your own localization export, so
the list protecting your content involves nobody's judgement but yours.

### 3 — Replace the matcher.

`impl/python/chatguard.py`, ~650 lines, no dependencies, MIT. Word boundaries,
per-term match modes, rescue allowlist, Unicode/confusable/leet normalization,
bounded fuzzy matching, severity tiers, per-surface policy, per-locale scoping.

Same vocabulary, no new words: English-dictionary false positives **37.1% → 0.0%**.
With a domain lexicon generated from your own localization, false positives on
your own content go **46.1% → 0.0%** while obfuscation recall rises
**22.9% → 84.3%**.

`impl/python/shadow.py` runs it beside your existing filter and returns **your**
filter's answer every time, recording only the disagreements. Flip authority when
your own traffic says to; rollback is the same config value.

On the cases you can check yourself:

| input | filter today | with the fix |
|---|---|---|
| `cucumber` | blocked | **allowed** |
| `Heisenberg` | blocked | **allowed** |
| `thank` | was blocked | **allowed** |
| `okkk` | blocked | **still blocked** |
| `kkk` | blocked | **still blocked** |
| `f u c k` | passes | **caught** |

## Measure it properly rather than trusting our numbers

`tools/testbattery.py` generates a standardized, seeded, stratified probe set —
401 probes across nine strata — and scores results with Wilson 95% confidence
intervals:

```sh
python3 tools/testbattery.py generate --out battery --margin 0.05
# type the probes, fill in the result column, then:
python3 tools/testbattery.py score --results battery/battery.csv
```

Three of the nine strata are honesty controls: obfuscated profanity (so the
result cannot be read as "filter less"), nonsense strings (so a broken harness
is not mistaken for a broken filter), and plain profanity (so a disabled filter
is not mistaken for a well-behaved one). Pooled precision at the default size is
±4.9%.

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
