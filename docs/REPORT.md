# Chat filter: accuracy defect, and a 20-row fix

Sent by a player. Everything below is reproducible from files already shipped in
the client; two commands are given at the end.

## What players are hitting

Your own item and skill names, run through your own filter list:

```
Freezing            ->  ****zing          Card Skills   ->  card ski**s
Immunity Control    ->  i**unity control  Downpour      ->  downpo**
Savage Card         ->  **vage card       Eddga Card    ->  e**ga card
Osiris' Curse       ->  osiris' c**se     Safety Wall   ->  flagged
```

**46.1%** of your 16,381 English item and skill name strings are flagged by your
own filter. Across all 81,303 localized strings it is **69.0%**. On an ordinary
English dictionary, **37.1%**.

## Why

The list is **95,660 entries, 93.4% Chinese** — a market-compliance list
(political terms, regional gambling domains, precursor chemicals). It is sound
for the market it was written for. It is being evaluated against players typing
English, Spanish and Portuguese.

**53 entries are one or two characters.** They are romanized abbreviations —
meaningful in their origin market, and inside thousands of ordinary English
words. `te` sits inside *ignite*. `ll` inside *skills*. `ur` inside *curse*.
`sa` inside *savage*. `dd` inside *Eddga*.

## This is not a request to filter less

The same list is also **failing in the other direction**. Measured against ten
common obfuscation strategies, it catches **22.9%** — and of 25 common English
profanity terms tested, only **6** appear in it as exact entries at all.
Spaced-out text, full-width characters and Cyrillic look-alikes pass untouched.

So the filter currently censors *Freezing* while passing actual abuse. Both
symptoms have the same root cause: matching raw substrings against a list built
for a different language.

## The ask: 20 rows

Fixing the twenty highest-impact entries removes **86.5%** of the false
positives. Forty rows removes **92.7%**. Only **191 of 5,695** ASCII entries
need any change at all — the other 5,504 are fine.

| entry | action | own strings broken | example |
|---|---|---|---|
| `te` | scope to zh | 349 | ignite |
| `ll` | scope to zh | 182 | skills |
| `ur` | scope to zh | 171 | curse |
| `sa` | scope to zh | 111 | savage |
| `av` | scope to zh | 79 | savage |
| `rr` | scope to zh | 67 | parry |
| `ty` | scope to zh | 67 | immunity |
| `tt` | scope to zh | 58 | attack |
| `mm` | scope to zh | 48 | immunity |
| `ui` | scope to zh | 45 | squid |
| `ka` | scope to zh | 44 | sakaba |
| `the` | delete | 40 | withering |
| `sm` | scope to zh | 39 | smoked |
| `sw` | scope to zh | 32 | sword |
| `dd` | scope to zh | 19 | eddga |
| `xi` | scope to zh | 18 | maximum |
| `roc` | whole-word only | 15 | rocker |
| `cia` | whole-word only | 14 | crucian |
| `ntr` | whole-word only | 13 | control |
| `net` | delete | 8 | nether |

**"Scope to zh" deletes nothing.** The entry keeps working, in full, for the
locale it was written for. It simply stops being applied to players typing
Latin script. Thirteen of these twenty are that change.

Full table with per-entry evidence and rationale: `remediation.csv`, 191 rows.

Also worth knowing: `free`, `the`, `master`, `priest`, `party`, `tank`, `wall`,
`cult`, `corona`, `banana`, `country`, `freedom`, `lantern` and `pancake` are
**exact** entries — each verified by direct string match. `free` is what turns
*Freezing* into `****zing`. `priest` is one of your classes and `Safety Wall`
one of your skills. These are flagged under any matching mode, substring or not.

## Verify it in two commands

```sh
# does your own filter flag your own content?
python3 selftest_filter.py --list <filter list> --strings <en localization>

# which entries cause the damage, and what should happen to each?
python3 remediate.py --list <filter list> --game-corpus <en localization> \
        --out remediation.csv
```

`selftest_filter.py` is ~40 lines with no dependencies. It is worth running in
CI next to the localization export: *no string we authored may be flagged by our
own filter* is an invariant that would have caught this before players did, and
it has a `--max-failures` ratchet so it can be adopted today at whatever level
is currently true.

## If you want more than the 20 rows

There is a complete, MIT-licensed, dependency-free matching engine that fixes
the underlying behaviour — word boundaries, a rescue allowlist generated from
your own localization, Unicode and leet normalization, per-surface policy, and a
shadow mode that runs beside your existing filter and changes nothing until you
choose to switch. On identical vocabulary it takes English-dictionary false
positives from 37.1% to 0.0% and obfuscation recall from 22.9% to 84.3%.

That is offered, not asked for. **The 20 rows are the ask**, they need no code,
and they are most of the benefit.
