# chatguard

Tools and a reference engine for chat filters that block `cucumber`.

That is not a joke example. It is a live, reproducible defect in a shipping MMO:
`cucumber` is blocked, `Heisenberg` is blocked, `thank` was blocked — while
`f u c k` passes untouched. All of it has one cause. Blocklists matched as raw
substrings fail in **both** directions at once.

```
Freezing            ->  ****zing          Card Skills   ->  card ski**s
Immunity Control    ->  i**unity control  Downpour      ->  downpo**
Savage Card         ->  **vage card       Ignite        ->  igni**
```

Those are a game's own item and skill names, run through that game's own filter.

---

## Start here

**Reporting a filter defect to a developer?**
→ [`docs/report-onepage.pdf`](docs/Ragnarok-Rebirth-chat-filter-report.pdf) (one page)
or [`docs/REPORT.md`](docs/REPORT.md) (full).

**You own a chat filter?** The highest-leverage change is one conditional:

> An entry shorter than N characters matches only as a **whole word**,
> never inside a longer one.

Measure it on your own list and your own content:

```sh
python3 tools/lengthrule.py --list <your list> --corpus en:<your localization>
```

On the case measured, N=4 took own-content false positives from **46.1% to 4.0%**
in English and **52.1% to 0.9%** in Portuguese. Nothing deleted, no entry
reviewed, no new data — and it covers proper nouns nobody has enumerated, which
no allowlist can.

**Everything ready to deploy** lives in [`deploy/`](deploy/): a 473,841-word
allowlist of terms that must never be censored, a ~20-line rescue check, and
deployment notes.

**Does your filter censor your own content?** One command, no dependencies:

```sh
python3 tools/selftest_filter.py --list <your list> --strings <your localization>
```

It enforces one invariant — *no string you authored may be flagged by your own
filter* — and belongs in CI. If `Freezing` trips it, the filter is wrong.

**Want a real measurement instead of anecdotes?**

```sh
python3 tools/testbattery.py generate --out battery --margin 0.05
python3 tools/testbattery.py score --results battery/battery.csv
```

401 stratified probes, Wilson confidence intervals, and three honesty controls so
the result cannot be misread as "filter less" and a disabled filter cannot be
mistaken for a well-behaved one.

**Can't see the list, only the behaviour?**

```sh
python3 tools/blackbox.py infer  --obs observations/live-2026-09-09.jsonl
python3 tools/blackbox.py design --obs observations/live-2026-09-09.jsonl
```

Turns "these were blocked, these were fine" into the smallest set of terms that
explains it, then picks the next probes. Useful because the list inside a client
is often **not** the list the server enforces — that was true here.

## The engine

If you want to fix the matching rather than patch the list:

```python
from chatguard import ChatGuard

guard = ChatGuard.from_files("data/lexicon/en-terms.jsonl",
                             ["data/lexicon/en-allow.txt"])

guard.check("Assassin Cross build")          # False
guard.filter("this is shit").filtered        # 'this is ****'
guard.filter("f u c k").action.name          # 'MASK'
guard.filter("shit", surface="identifier")   # BLOCK - names are stricter
```

| | |
|---|---|
| **Over-blocking** | word boundaries + longest-match rescue allowlist. Same vocabulary: dictionary false positives **37.1% → 0.0%** |
| **Under-blocking** | NFKC, confusable, leet, repeat and separator normalization + bounded fuzzy. Obfuscation recall **22.9% → 84.3%** |
| **CJK** | rescue by allowlist *phrase* containment, so `日` inside `日光` is safe — languages without word spacing need this and token rules cannot provide it |
| **Locale** | terms carry a `locales` field; one market's list stops hitting another's players |
| **Surface** | `private` / `public` / `identifier` — permanent public names get stricter treatment |
| **Rollout** | `shadow.py` runs it beside your existing filter and changes nothing until you flip one value |

~650 lines, no dependencies, MIT.

## Layout

```
docs/  Ragnarok-Rebirth-chat-filter-report.pdf   one page, for sending
       REPORT.md      the full report
       EVIDENCE.md    every measurement, method and caveat
       RESEARCH.md    what a 2026 moderation stack looks like
       ADOPTION.md    adoption tiers, objections answered
       SPEC.md        normative behaviour, written to port from

deploy/                 <- self-contained drop-in
       allowlist-en.txt  473,841 words that must never be censored
       rescue.py         ~20-line integration
       README.md         deployment notes

tools/ lengthrule.py     measure the one-line fix
       selftest_filter.py CI guard: no self-authored string may be flagged
       testbattery.py    stratified live test battery + Wilson CIs
       remediate.py      rank your entries by measured blast radius
       blackbox.py       infer the list from behaviour alone
       build_allowlist.py / build_lexicon.py / audit.py / conformance.py

impl/python/            the replacement matcher + shadow-mode wrapper
tests/test_all.py       51 tests
vectors/golden.jsonl    25 conformance vectors -- the contract for any port
observations/           live filter behaviour, as recorded
```

## Verify

```sh
python3 tests/test_all.py       # 51 passed
python3 tools/conformance.py    # 25 passed, 0 failed
```

Any port in any language is conformant exactly when it reproduces
`vectors/golden.jsonl`. No shared code required.

## Provenance and licensing

No code from any client was copied here, and no proprietary word list is
redistributed. Everything shipped is public-domain, permissively licensed, or
written for this repository.

| component | source | license |
|---|---|---|
| English dictionary words | web2 (Webster's 1913, via BSD `/usr/share/dict`) | public domain |
| given names | BSD `propernames` | public domain |
| surnames | US Census Bureau, 2010 Surname File | public domain (US Gov) |
| cities and countries | [GeoNames](https://www.geonames.org/) | **CC BY 4.0** |
| MMO / chat vocabulary | written here | MIT |
| all code | written here | MIT |

**Attribution:** place-name data in `deploy/allowlist-en.txt` is derived from
[GeoNames](https://www.geonames.org/), used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). If you redistribute
that file, carry this attribution with it. `tools/build_allowlist.py` can
regenerate the list without the GeoNames sources if you would rather not take on
the attribution requirement — omit `--extra`.

Domain lexicons derived from a publisher's own localization are **not shipped**;
`tools/build_lexicon.py` and `tools/build_allowlist.py` generate them from your
own export. That keeps this repository clean-room, and it is also why the
allowlist protecting your content involves no outsider's judgement about your
language.

Code: MIT.
