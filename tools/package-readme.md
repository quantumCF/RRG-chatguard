# Chat Filter Accuracy Audit — Ragnarok: Rebirth Global

The filter matches blocked terms as **letters found anywhere inside a word**, and the term
list is **predominantly Brazilian Portuguese**. Two-letter Portuguese entries
applied across all eight locales censor ordinary vocabulary in every language
the game ships in.

```
thank    delivered
thanks   blocked      one letter apart
```

> **Content notice.** This package audits a profanity filter. The report and
> the files in `4-evidence/` quote profanity and slurs as evidence. This
> summary and the integration instructions do not.

**15,307 messages** sent through the retail client. **343 ordinary words
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
`2-quick-fix/words-to-allow.txt`. It is 343 words, one per line, each annotated
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

Short entries still match as whole words. Nothing stops being blocked when a
player actually types it. Entries of five characters or more work exactly as
they do today. This removes 91% of the affected words, and nobody has to review
the word list. Section 04 of the report has the language-agnostic
implementation.

---

## Verify it

Confirm the defect in ten seconds, with nothing from this package: send
`thank` in game, then `thanks`.

After the fix, these must be **delivered** — every one was confirmed blocked
by the live service:

```
thanks   document   number   advantage   parameter   reputation
```

And the filter's actual terms must **stay blocked** — no option here removes
anything from the block list, so if any becomes deliverable the change was
wired wrong. Section 05 of the report lists them as explicit regression
vectors.

If you take the replacement engine:

```sh
cd 3-replacement-engine
python3 tests/test_all.py      # 53 tests
python3 conformance.py         # 29 language-agnostic vectors
```

---

## What you would be installing

Three files, 961 lines in total. Python standard library only, no outside
packages, MIT licensed.

| file | lines | what it does |
|---|---|---|
| `2-quick-fix/rescue.py` | 138 | Option B. The whole fix. |
| `3-replacement-engine/chatguard.py` | 676 | Option D. The replacement matcher. |
| `3-replacement-engine/shadow.py` | 147 | Runs a new filter next to your current one and compares the two answers. Your filter stays in charge. |

**Option A installs nothing at all.** It is a text file of 343 words, so it is
available immediately even if adding outside code is slow to clear review.

If your review process wants it, `python3 verify_safe.py` lists the imports and
file operations in each of the three files.

## Notes on the numbers

- **343** is measured — each word was blocked by the live service in at least
  two independent trials, against a measured 1.2% per-probe error rate.
- **8,414** is derived — the confirmed rules projected across a dictionary.
  Those specific words were not each sent. The two are kept in separate files
  on purpose.
- **16 rules** is a lower bound. Entries whose letters did not appear in the
  11,868 strings tested would not have surfaced.
- Everything reflects the service on **11–12 September 2026**.

No client modification, packet injection, or server access was used at any
point. The audit observes exactly what a player observes.
