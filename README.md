# RRG-chatguard

Accuracy audit of the **Ragnarok: Rebirth Global** chat filter, and a fix.

```
thank      delivered
thanks     refused     ← one letter apart
```

The filter matches blocked terms as **unanchored substrings**, so they fire
inside unrelated words. `thanks`, `document`, `security`, `number`,
`advantage`, `parameter`, `campus` and `vacation` are all refused by the live
service.

**15,307** messages tested · **342** ordinary words confirmed censored ·
**8,414** ordinary English words affected

**[→ Read the 6-page report](docs/chat-filter-audit-report.pdf)**  ·
[one-pager](docs/chat-filter-defect-report.pdf) · [markdown](REPORT.md)

> **Content notice** — this repository audits a profanity filter. The report
> and `findings/` quote slurs as evidence. This README does not.

---

## The fix

> **Entries shorter than five characters match only as whole words.**

That one condition removes **91%** of the affected words. Short entries still
match when typed as words; entries of five characters or more are untouched.

| | Option | Effort |
|---|---|---|
| **A** | Ship [`findings/words-to-allow.txt`](findings/words-to-allow.txt) — 342 words, no code | Hours |
| **B** | Add [`fix/rescue.py`](fix/rescue.py) at one call site | 1 day |
| **C** | The length rule above | 1–2 days |
| **D** | Replace the matcher with [`engine/`](engine/) | 1–2 weeks |

None of these removes anything from the block list. They remove false
positives only.

**Option B**, in full:

```python
from rescue import Rescue
rescue = Rescue("allowlist-en.txt")        # once, at startup

if rescue.is_rescued(text, match_start, match_end):
    pass          # ordinary word — deliver it
else:
    block()       # unchanged behaviour
```

---

## Why it happens

`ks` is a blocked entry. Probed inside inert padding:

| probe | | probe | |
|---|---|---|---|
| `ks` | refused | `xxkxx` | delivered |
| `xxksxx` | refused | `xxsxx` | delivered |
| `qwksqw` | refused | `xxskxx` | delivered |

Two literal characters, matched anywhere, with no word boundary — which is why
the plural of `thank` is refused. The term list is predominantly Brazilian
Portuguese, and its shortest entries are two characters long.

**Short entries cause nearly all of it:**

| entry length | entries | words reached |
|---|---|---|
| 2 characters | 3 | **6,355** |
| 3 characters | 3 | 428 |
| 4 characters | 8 | 928 |
| 5 characters | 2 | 745 |

---

## Before you adopt the code

```sh
python3 tools/verify_safe.py
```

Parses the AST of every shipped file and reports what it can do. On this tree:
**no third-party dependencies, no network, no process execution, no `eval`, no
`pickle`** — Python standard library only, **961 lines** across three files.
The one file write is `ShadowFilter.dump(path)`, which you call with a path you
supply.

**Option A needs no code from here at all** — it is a text file of 342 words.

MIT licensed. The term list is deliberately not shipped: the vocabulary is
yours; what is defective is the matching.

---

## Repository

| | |
|---|---|
| [`findings/`](findings/) | the evidence — word lists, `findings.json`, all 15,307 probe records ⚠ contains profanity |
| [`fix/`](fix/) | `rescue.py`, the 473,532-word allowlist, deploy notes |
| [`engine/`](engine/) | optional replacement matcher, 53 tests, 29 conformance vectors |
| [`tools/`](tools/) | everything used to produce and verify the above |
| [`docs/`](docs/) | PDFs, adoption notes, background research |

```sh
python3 tools/verify_safe.py       # dependency and capability surface
python3 engine/tests/test_all.py   # 53 tests
python3 tools/conformance.py       # 29 conformance vectors
python3 tools/check_numbers.py     # every published figure traces to the evidence
```

To confirm the defect, send `thank` in game and then `thanks`. Ten seconds, and
it needs nothing from this repository.

<details>
<summary><b>Method and limitations</b></summary>

<br>

Messages were sent through the retail client into a private party channel, one
at a time, and read back from chat history. No client modification, no packet
injection, no server or source access — the audit observes exactly what a
player observes.

- **A substring is not reported until isolated.** Every rule was confirmed
  inside inert padding, with neither neighbouring letter firing alone.
  Candidates that failed were dropped.
- **One observation is not a result.** The detection error rate was measured,
  not assumed: 6 spurious refusals in 491 observations, 1.2% per probe. Every
  reported word required two independent refused observations.
- **An unsent probe is not a passing probe.** All but 15 were retried to a real
  verdict. A false-negative audit over 250 words returned zero misses.

**Limitations.** The rule set is a lower bound — entries whose letters did not
occur in the 11,868 strings tested would not have surfaced. The 8,414 figure is
derived by projecting confirmed rules across a dictionary; the 342 measured
words are kept in a separate file. Korean, Chinese and Japanese vocabularies
were not swept. Findings describe the service on 11–12 September 2026.

</details>
