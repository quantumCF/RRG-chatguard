# Evidence

> **CORRECTION — 2026-09-10**
>
> Figures in this document derived from the client's copy of the filter list are
> **withdrawn**. Live behaviour shows the server does not enforce that list: `ka`,
> `ll`, `ui`, `ur`, `te` and `the` are all present in the client copy, yet `okay`,
> `skill`, `guild`, `your` and `they` are not blocked in game. Conversely `cum`
> fires (`cucumber` is blocked) but is absent from the client copy.
>
> The client list is legacy data — nothing in the client loads it, and it stayed
> byte-identical across a full content patch. Treating it as live was an error.
>
> **What still stands:** substring matching is proven directly (`okkk` blocked,
> `okay` passes), the observed blocks are real (`cucumber`, `Heisenberg`,
> `thank`), and every tool here takes the operator's own list as input and is
> unaffected. **What is withdrawn:** all per-locale percentages, the
> words-to-unblock counts, and the evasion-recall figure.


Two independent bodies of evidence, deliberately kept apart because they have
very different strengths:

* **§1 Live observation** — a handful of data points from the running game.
  Small, but authoritative: it is the actual server.
* **§2 Static analysis** — the filter list shipped inside the client, measured
  against the game's own localized content in eight languages. Large and fully
  reproducible, but one step removed from what the server enforces.

§3 states plainly where the two disagree, because they do.

---

## 1. Live observation

Typed in game, 2026-09-09.

| input | result |
|---|---|
| `cucumber` | blocked |
| `Heisenberg` | blocked |
| `thank` | blocked earlier; no longer |
| `okkk` | blocked |
| `kkk` | blocked |
| `okay` | fine |

Three conclusions follow, and they are the load-bearing ones:

**Matching is substring-based.** `okkk` is blocked while `okay` is fine. The only
difference is the run of `k`s, so the filter is matching a fragment inside the
word rather than the word itself.

**Ordinary words are collateral.** `cucumber` and `Heisenberg` contain no
profanity. They contain fragments of it.

**The list changes over time.** `thank` was blocked and is not any more, which
means remediation is already happening and confirms the list is server-side
configuration rather than something baked into a client build.

`tools/blackbox.py` turns observations like these into constraints. Given the
six above it eliminates 1,133 candidate fragments and reports the smallest term
set consistent with all of them, then designs the next probes to narrow further.
It is the right instrument here precisely because it needs no access to the list.

---

## 2. Static analysis of the shipped client list

### 2.1 What the list is

| | |
|---|---|
| Entries | **95,660** |
| Chinese (Han + fullwidth) | **89,378 — 93.4%** |
| ASCII | 6,205 (5,695 alphabetic) |
| Korean / Thai entries | **0** |
| Single-character entries | **497** (433 Han) |
| Two-character entries | **11,872** (11,812 Han) |
| Three-character entries | 17,893 |
| Entries using the wildcard syntax the format supports | 37 — 0.04% |

Composition is market-compliance material: political terms, regional gambling
domains, precursor chemical names. Rebirth launched in China in December 2025 and
globally in July 2026; the list appears to have travelled with the build.

**59.6% of the list — 57,051 entries — cannot change any outcome**, because a
shorter entry already matches inside each of them. Dropping all 57,051 leaves
measured behaviour bit-for-bit identical (46.1% → 46.1%). This is worth reading
twice: substring matching collapses a 95,660-entry list into the behaviour of
its ~38,000 shortest entries. Moving to word-boundary matching would *restore*
the expressiveness of the other 57,051 rather than reduce it.

### 2.2 Over-blocking, per locale

Each locale's own authored content, measured against the full list, substring
matching. These are unambiguous false positives: the publisher wrote this text.

| locale | own names | flagged | rate | all strings | rate |
|---|---|---|---|---|---|
| **Portuguese** | 17,244 | 8,985 | **52.1%** | 83,068 | 67.9% |
| Indonesian | 16,280 | 7,821 | 48.0% | 81,083 | 71.2% |
| English | 16,381 | 7,547 | 46.1% | 81,303 | 69.0% |
| Thai | 16,377 | 4,915 | 30.0% | 81,260 | 20.1% |
| Vietnamese | 17,345 | 1,684 | 9.7% | 83,426 | 21.1% |
| Chinese (Trad) | 16,381 | 1,594 | 9.7% | 81,395 | 14.2% |
| Chinese (Simp) | 15,732 | 1,320 | 8.4% | 79,508 | 10.3% |
| Korean | 15,409 | 7 | 0.0% | 79,011 | 0.3% |

**The list damages the newer markets about five times more than its home market.**
Latin-script locales are worst, and Portuguese — a launch market — worst of all.

What causes it, per locale:

```
en  te(2,003)  ll(1,552)  ur(852)  sa(688)  rr(410)  sm(372)  ty(370)
pt  te(3,265)  ur(1,726)  sa(1,438)  rr(859)  xa(703)  av(616)  sf(600)
in  ka(2,033)  te(1,831)  sa(1,287)  ll(1,261)  ur(1,097)
th  te(1,339)  ll(872)  ur(507)  sa(450)  rr(356)
cn  日(438)  士兵(73)  草(51)  大师(51)  犬(41)  庇护(40)
tw  日(433)  無(210)  士兵(73)  大師(69)  草(52)  藥水(42)
```

Every Latin-script locale is damaged **100% by ASCII entries** — the romanized
two-letter fragments. Chinese is damaged **99% by Han entries**, overwhelmingly
single common characters: `日` (sun/day) fires 438 times inside the game's own
Chinese names. That is the same defect in another script, and it means fixing
this helps the Chinese build too.

Korean and Thai deserve a separate note: the list contains **zero** Hangul and
**zero** Thai entries. Those players receive no filtering in their own script
while still absorbing collateral flags from other scripts' entries.

### 2.3 Concentration — the reason the fix is small

False positives are not spread across the list. On the ASCII subset:

```
top  5 entries  ->  57.8% of all false positives
top 20 entries  ->  89.0%
top 40 entries  ->  96.0%
```

Simulated remediation, measured on the game's own English names:

| | flagged | rate |
|---|---|---|
| today | 7,545 | 46.1% |
| after the top 5 rows | 3,899 | 23.8% |
| after the top 10 rows | 2,635 | 16.1% |
| **after the top 20 rows** | **1,016** | **6.2%** |
| after the top 40 rows | 550 | 3.4% |

**191 of 5,695 ASCII entries need any change at all.** Recommended actions split
31 delete / 53 scope-to-locale / 107 whole-word-only. Scoping deletes nothing.

Globally, dropping just the **59 romanized entries of ≤2 characters**:

| locale | today | after |
|---|---|---|
| en | 46.1% | **6.2%** |
| pt | 52.1% | **8.0%** |
| in | 48.0% | **5.0%** |
| th | 30.0% | **3.3%** |
| vn | 9.7% | **2.8%** |

Scoping the 433 single-Han-character entries takes cn 8.4% → 4.3% and
tw 9.7% → 4.7%.

### 2.4 The minimum-fragment-length rule

The single highest-leverage change measured. An entry shorter than N characters
matches only as a whole word; nothing is deleted and no entry is reviewed.

Measured on each locale's own authored item and skill names:

| locale | today | N=2 | N=3 | **N=4** | N=5 |
|---|---|---|---|---|---|
| English | 46.1% | 46.1% | 7.6% | **4.0%** | 3.0% |
| Portuguese | 52.1% | 52.1% | 8.2% | **0.9%** | 0.5% |
| Indonesian | 48.0% | 48.0% | 6.2% | **3.1%** | 2.2% |
| Thai | 30.0% | 30.0% | 4.3% | **2.4%** | 1.9% |
| Vietnamese | 9.7% | 9.7% | 3.4% | **2.5%** | 2.4% |
| Korean | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| Chinese (Simp) | 8.4% | 5.9% | 2.5% | **2.3%** | 2.1% |
| Chinese (Trad) | 9.7% | 6.7% | 2.9% | **2.7%** | 2.6% |

Two things are worth reading carefully.

**N=2 changes almost nothing.** The 497 single-character entries barely matter
for Latin scripts; the damage is done by the 11,872 two-character and 17,893
three-character entries. The step from N=3 to N=4 is where the collapse happens.

**It beats the allowlist on coverage, structurally.** An allowlist is an
enumeration and proper nouns are an open set. `Heisenberg` appears in no
public-domain dictionary, gazetteer or census file we could find, so a 473,841-word
allowlist still does not rescue it. A length rule rescues every proper noun that
will ever exist. This is why the report leads with the rule and treats the
allowlist as the second option rather than the first.

Reproduce with `tools/lengthrule.py`.

### 2.5 Under-blocking

Ten obfuscation strategies applied to known terms.

| variant | substring | whole-word | chatguard |
|---|---|---|---|
| plain | 35.7% | 21.4% | **89.3%** |
| spaced `f u c k` | 0.0% | 0.0% | **89.3%** |
| dotted / dashed | 0.0% | 0.0% | **89.3%** |
| repeated `fuuuck` | 57.1% | 0.0% | **85.7%** |
| leetspeak `sh1t` | 14.3% | 3.6% | **89.3%** |
| full-width | 0.0% | 0.0% | **89.3%** |
| Cyrillic homoglyph | 14.3% | 7.1% | **89.3%** |
| letter swap `fvck` | 28.6% | 0.0% | 42.9% |
| **all** | **22.9%** | **3.2%** | **84.3%** |

Of 25 common English profanity terms tested, **6** appear in the list at all.

### 2.6 What the fix measures

| corpus | n | substring | whole-word | chatguard | chatguard + domain lexicon |
|---|---|---|---|---|---|
| game names | 16,381 | 7,545 (46.1%) | 415 (2.5%) | 43 (0.3%) | **1 (0.0%)** |
| all localized strings | 81,303 | 56,066 (69.0%) | 24,020 (29.5%) | 695 (0.9%) | **42 (0.1%)** |
| English dictionary | 235,616 | 87,481 (37.1%) | 104 (0.0%) | 23 (0.0%) | **21 (0.0%)** |

"chatguard" uses only the public-domain allowlist shipped in this repository.
"+ domain lexicon" adds an allowlist generated from the game's own localization
via `tools/build_lexicon.py` — no judgement of ours is involved in it.

An earlier run of this table gave chatguard a *different, smaller* vocabulary
than the baseline, which flattered it for reasons unrelated to the engine. The
`same vocab` arm in `tools/audit.py` exists to prevent that: given the identical
5,695-term vocabulary, chatguard's matcher alone takes English-dictionary false
positives from **37.1% to 0.0%**.

### 2.7 Shadow run

`shadow.py` over 4,004 of the game's own names, incumbent authoritative:

```
agreement            55.9%
over_block_fixed     1,763
new_catch                1
guard_errors             0
```

---

## 3. Where the two bodies of evidence disagree

**The client's list is not the server's list.** Testing the live observations
against the shipped copy:

| observed | client list predicts | |
|---|---|---|
| `kkk` blocked | flagged (`kk`, `kkk` present) | ✅ |
| `okkk` blocked | flagged via `kkk` | ✅ |
| `cucumber` blocked | **would pass** | ❌ |
| `Heisenberg` blocked | **would pass** | ❌ |
| `thank` was blocked | **would pass** | ❌ |
| `okay` fine | **would be flagged** (`ka` present) | ❌ |

So the server has entries the client copy lacks, and lacks entries it has. The
two overlap but are different revisions, and the server's changes over time.

**What this does and does not invalidate:**

* **Invalidated:** any specific row we name. Our 20-row table describes the
  client copy, not what you are running. Do not action it — regenerate it with
  `tools/remediate.py` against your list.
* **Not invalidated:** the class of defect, which the live observations
  independently confirm. Substring matching is proven by `okkk` vs `okay`.
  Ordinary-word collateral is proven by `cucumber`. The static analysis shows how
  much damage that design does at scale, and that conclusion does not depend on
  the two lists being identical.

This is also the reason the tools matter more than the tables. Every tool here
takes *your* list and *your* content as input.

---

## 4. Method and caveats

```sh
python3 tools/audit.py --list <list.json> --ascii-only \
        --corpus <names.txt> --corpus <all-strings.txt> --corpus /usr/share/dict/words
python3 tools/remediate.py --list <list.json> --game-corpus <names.txt> --out remediation.csv
python3 tools/selftest_filter.py --list <list.json> --strings <localization.txt>
python3 tools/blackbox.py infer --obs observations/live-2026-09-09.jsonl
python3 tests/test_all.py       # 51 tests
python3 tools/conformance.py    # 25 vectors
```

1. The audited list is the client copy. §3 covers this.
2. The `substring` and `whole-word` columns are **models** of the server's
   matcher, which was never observed directly. Both bounds are reported; the
   argument holds at either.
3. False positives are measured against published game content and dictionary
   words — a proxy for player chat, not a sample of it. Only a shadow run on real
   traffic measures the true rate.
4. Under-blocking recall depends on which terms the evasion corpus is built from;
   it measures coverage of common English profanity, not of all abuse.
5. The per-locale figures use each locale's own localization as the clean corpus.
   Strings mixing scripts (English fragments inside Thai names) are attributed to
   whichever entry matched.
6. `blackbox.py`'s common-word assumption is an assumption. `--no-assume-common`
   disables it.
