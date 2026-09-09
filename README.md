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

**Reporting a filter defect to a developer?** → [`docs/REPORT.md`](docs/REPORT.md)
— one page, evidence first, three concrete fixes ordered smallest to largest.

**You own a chat filter and want to know if it has this problem?** → run one
command, no dependencies, nothing to install:

```sh
python3 tools/selftest_filter.py --list <your word list> --strings <your localization>
```

It enforces a single invariant: *no string you authored may be flagged by your
own filter.* If `Freezing` trips it, the filter is wrong.

**Want to know which of your entries cause the damage?**

```sh
python3 tools/remediate.py --list <your list> --game-corpus <your localization> \
                           --out remediation.csv
```

In the case measured, **20 entries caused 89% of all false positives** and
191 of 5,695 needed any change at all. The CSV gives per-entry blast radius, a
worked example, and a recommended action.

**Can't see the list, only the behaviour?**

```sh
python3 tools/blackbox.py infer  --obs observations/live-2026-09-09.jsonl
python3 tools/blackbox.py design --obs observations/live-2026-09-09.jsonl
```

`infer` turns "these strings were blocked, these were fine" into the smallest set
of terms that explains it. `design` picks the next probes to type. Useful because
the list inside a client is often **not** the list the server enforces — that was
true here.

---

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
docs/REPORT.md        the one-page defect report            <- start here
docs/EVIDENCE.md      all measurements, method, caveats
docs/RESEARCH.md      what a 2026 moderation stack looks like
docs/ADOPTION.md      three adoption tiers, objections answered
docs/SPEC.md          normative behaviour, written to port from

impl/python/          the engine + shadow wrapper
tools/                selftest, remediate, audit, blackbox, build_lexicon, conformance
data/lexicon/         starter terms + public-domain rescue allowlist
vectors/golden.jsonl  25 conformance vectors -- the contract for any port
tests/test_all.py     51 tests
observations/         live filter behaviour, as recorded
```

## Verify

```sh
python3 tests/test_all.py       # 51 passed
python3 tools/conformance.py    # 25 passed, 0 failed
```

Any port in any language is conformant exactly when it reproduces
`vectors/golden.jsonl`. No shared code required.

## Clean-room

No code from any client was copied here, and no proprietary word list is
redistributed. The English allowlist derives from the public-domain web2/SCOWL
dictionary. Domain lexicons are **not shipped** — `tools/build_lexicon.py`
generates them from your own localization export, which is also why the allowlist
protecting your content involves no outsider's judgement about your language.

MIT.
