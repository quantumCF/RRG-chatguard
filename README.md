# chatguard

A drop-in replacement for substring-blocklist chat filtering.

It exists because blocklists fail in **both** directions at once — they censor
ordinary words while letting obvious evasion straight through — and because the
fix is unglamorous, deterministic, and about 600 lines long.

```
Freezing                 ->  ****zing
Immunity Control         ->  i**unity control
Savage Card              ->  **vage card
Card Skills              ->  card ski**s
Downpour                 ->  downpo**
```

Those are not hypotheticals. They are a live game's own item and skill names,
run through that same game's own shipped filter list. Meanwhile `f u c k`,
`ｆｕｃｋ` and `sh1t` all pass it untouched.

## What it does

| | |
|---|---|
| **Fixes over-blocking** | Word boundaries + a longest-match rescue allowlist. On the same vocabulary, English-dictionary false positives drop from **37.1% to 0.0%**. |
| **Fixes under-blocking** | Unicode/confusable/leet normalization + bounded fuzzy matching. Obfuscated-abuse recall rises from **22.9% to 84.3%**. |
| **Scopes by locale** | A term table carries a `locales` field, so one market's compliance list stops being applied to another market's players. |
| **Grades by surface** | The same word can be fine in guild chat, masked in world chat, and refused in a permanent character name. |
| **Ships without risk** | Shadow mode runs it beside your existing filter and changes nothing until you say so. |

## The two problems are independent

This is the most useful thing the measurements showed, and it decides how you
adopt:

* **Over-blocking is an engine problem.** Give chatguard's matcher the *exact
  same word list* and dictionary false positives go 37.1% → 0.0%.
* **Under-blocking is a vocabulary problem.** A list that is 93% one language
  will not catch abuse in another, whatever the matcher does.

They are fixed by different changes, and **each ships on its own**. You do not
have to do both at once, and Tier 1 below requires no code at all.

## Use it

```python
from chatguard import ChatGuard

guard = ChatGuard.from_files("data/lexicon/en-terms.jsonl",
                             ["data/lexicon/en-allow.txt",
                              "data/domain/game-terms.txt"])

guard.check("Assassin Cross build")          # False  - not flagged
guard.filter("this is shit").filtered        # 'this is ****'
guard.filter("f u c k").action.name          # 'MASK'
guard.filter("shit", surface="identifier")   # BLOCK - names are stricter
```

The API is deliberately shaped like the one you already have: a boolean check
and a masked-string filter. If your server exposes something like
`check_block_word(text) -> bool` and `filter_block_word(text) -> filtered`,
chatguard slots in at that exact seam with no protocol change.

## Layout

```
impl/python/chatguard.py   the engine, no dependencies
impl/python/shadow.py      run beside an existing filter, change nothing
data/lexicon/              terms (tier + match mode + locale) and allowlist
data/domain/               game nouns, auto-generated from your localization
vectors/golden.jsonl       25 conformance vectors -- the contract for any port
tools/audit.py             measure any list against any corpus, both directions
tools/conformance.py       run the vectors
docs/ADOPTION.md           three adoption tiers and every objection, answered
docs/EVIDENCE.md           the measurements, and how to reproduce them
docs/SPEC.md               normative behaviour, for porting
```

## Verify it yourself

```sh
python3 tools/conformance.py                       # 25 passed, 0 failed
python3 tools/audit.py --list YOUR_LIST.json \
        --corpus your_strings.txt --ascii-only     # both failure directions
```

Every number in `docs/EVIDENCE.md` came out of `tools/audit.py`. Point it at
your own list and your own corpora and check.

## License

MIT. No dependencies. Clean-room: no third-party code was copied into this
repository, and no proprietary word list is redistributed by it.
