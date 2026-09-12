# Chat Filter Accuracy Audit — Ragnarok: Rebirth Global

The filter matches blocked terms as **unanchored substrings**, and the term
list is **predominantly Brazilian Portuguese**. Two-letter Portuguese entries
applied across all eight locales censor ordinary vocabulary in every language
the game ships in.

```
thank    delivered
thanks   refused      ← one letter apart; the plural creates "ks"
```

**15,307 messages** sent through the retail client. **342 ordinary words
confirmed censored**, **10,627 confirmed delivered**. The confirmed rules reach
**8,414 ordinary English words**.

---

## What's in this folder

| Folder | For | Contents |
|---|---|---|
| **1-report** | Everyone | 6-page audit report (PDF), one-page summary, markdown source |
| **2-quick-fix** | Engineering | The word list, the allowlist corpus, and a 3-line drop-in shim |
| **3-replacement-engine** | Engineering | Optional replacement matcher, tests and conformance vectors |
| **4-evidence** | Anyone verifying | All 15,307 probe records, one JSON line each |

---

## Fastest path to a fix

**If your filter already has an exception list** — ship
`2-quick-fix/words-to-allow.txt`. It is 342 words, one per line, each annotated
with the rule that caused it. No code change. This removes false positives
only; nothing is taken off the block list.

**If it does not** — add `2-quick-fix/rescue.py` at the one call site where
your filter decides to block:

```python
# once, at startup
from rescue import Rescue
rescue = Rescue("allowlist-en.txt")

# inside your filter, where you were about to block:
if rescue.is_rescued(text, match_start, match_end):
    pass          # ordinary word — deliver the message
else:
    block()       # unchanged behaviour
```

Your matching logic, word list, severity rules and protocol stay exactly as
they are. Cost is one hash-set lookup.

**To fix the cause rather than the symptoms** — one condition in the matcher:

> Entries shorter than five characters match only as whole words.
> Entries of five characters or more are unchanged.

`cu` still refuses `cu` and stops refusing `document`. `caralho` and
`arrombado` behave exactly as they do today. Section 04 of the report has the
language-agnostic implementation.

---

## Verify it

Confirm the defect in ten seconds, with nothing from this package: send
`thank` in game, then `thanks`.

After the fix, these must be **delivered** — every one was confirmed refused
by the live service:

```
thanks   document   number   advantage   parameter   reputation
```

And these must **stay refused** — no option here removes anything from the
block list, so if any becomes deliverable the change was wired wrong:

```
cu   ks   puta   caralho   arrombado
```

If you take the replacement engine:

```sh
cd 3-replacement-engine
python3 tests/test_all.py      # 53 tests
python3 conformance.py         # 29 language-agnostic vectors
```

---

## Notes on the numbers

- **342** is measured — each word was refused by the live service in at least
  two independent trials, against a measured 1.2% per-probe error rate.
- **8,414** is derived — the confirmed rules projected across a dictionary.
  Those specific words were not each sent. The two are kept in separate files
  on purpose.
- **16 rules** is a lower bound. Entries whose letters did not appear in the
  11,868 strings tested would not have surfaced.
- Everything reflects the service on **11–12 September 2026**.

No client modification, packet injection, or server access was used at any
point. The audit observes exactly what a player observes.
