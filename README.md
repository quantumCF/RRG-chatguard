# chatguard

**An accuracy audit of the Ragnarok: Rebirth Global chat filter, and a fix.**

The filter censors thousands of ordinary words. `thanks`, `document`,
`security`, `number`, `advantage`, `parameter`, `campus`, `vacation` and
`reputation` are all refused by the live service.

```
thank      delivered
thanks     refused        ← one letter apart
```

> **Content notice.** This repository audits a profanity filter, so the report
> and the evidence files under `findings/` necessarily quote profanity and
> slurs. This README, the fix, and the integration instructions do not. Nothing
> below contains offensive language.

| | |
|---|---|
| Messages sent through the retail client | **15,307** |
| Ordinary words confirmed censored | **342** |
| Ordinary words confirmed delivered | **10,627** |
| Ordinary English words the rules reach | **8,414** |

**[→ Read the audit report](docs/chat-filter-audit-report.pdf)** · 6 pages ·
[one-page summary](docs/chat-filter-defect-report.pdf) ·
[markdown](REPORT.md)

---

## Why it happens

Two facts combine. Neither is a problem alone.

**1. Blocked terms are matched as unanchored substrings.** A term fires
wherever its letters appear, including inside unrelated words. Demonstrated
with `ks`, one of the blocked entries, probed inside inert padding:

| probe | result | | probe | result |
|---|---|---|---|---|
| `ks` | refused | | `xxkxx` | delivered |
| `xxksxx` | refused | | `xxsxx` | delivered |
| `qwksqw` | refused | | `xxskxx` | delivered |

Refused bare and inside padding, at any position, under two different
paddings. Neither letter fires alone, and the reversed pair does not fire. The
filter is matching two literal characters anywhere in the message — which is
why the plural of `thank` is refused.

**2. The term list is predominantly Brazilian Portuguese, and several entries
are two to four characters long.** Words that are ordinary vulgarities in
Portuguese are ordinary letter sequences in English, Indonesian, Thai and
Vietnamese. The specific entries are listed in the report.

### Short entries cause almost all of it

| entry length | entries | ordinary English words reached |
|---|---|---|
| 2 characters | 3 | **6,355** |
| 3 characters | 3 | 428 |
| 4 characters | 8 | 928 |
| 5 characters | 2 | 745 |

**7,675 of the 8,414 affected words — 91% — come from entries shorter than
five characters.** That single fact is what makes the recommended fix a
one-line change rather than a list review.

---

## Fix it

None of these removes anything from the block list. They remove false
positives only.

| | Change | Removes | Effort |
|---|---|---|---|
| **A** | Ship [`findings/words-to-allow.txt`](findings/words-to-allow.txt) | The 342 confirmed words | Hours, no code |
| **B** | Add [`fix/rescue.py`](fix/rescue.py) at one call site | Substring false positives generally | 1 day |
| **C** | Minimum-length rule in the matcher | 91% of the damage, at the cause | 1–2 days |
| **D** | Replace the matcher with [`engine/`](engine/) | This class of defect entirely | 1–2 weeks |

**Option C** — the recommended one — is a single condition:

> Entries shorter than five characters match only as whole words.
> Entries of five characters or more are unchanged.

Short entries still match as whole words, so nothing stops being blocked when
someone actually types it. Entries of five characters and longer are untouched,
so every substantial term behaves exactly as it does today.

**Option B** is three lines where your filter already decides to block:

```python
from rescue import Rescue
rescue = Rescue("allowlist-en.txt")        # once, at startup

if rescue.is_rescued(text, match_start, match_end):
    pass          # ordinary word — deliver it
else:
    block()       # unchanged behaviour
```

Your matching logic, word list, severity rules and protocol stay as they are.

---

## Assessing the code before you adopt it

Adopting code from outside the studio is a risk. Rather than ask you to take
that on trust, this repository is built so the claim can be checked:

```sh
python3 tools/verify_safe.py
```

It parses the AST of every file you would deploy and reports the dependency and
capability surface. On this tree it returns:

| check | result |
|---|---|
| third-party dependencies | none — Python standard library only |
| network access | none |
| process execution | none |
| dynamic evaluation (`eval`/`exec`) | none |
| unsafe deserialisation (`pickle`) | none |
| file writes | one, in `ShadowFilter.dump(path)`, which you call with a path you supply |

Total shipped code is **961 lines** across three files — small enough to read
in a sitting:

| file | lines | purpose |
|---|---|---|
| [`fix/rescue.py`](fix/rescue.py) | 138 | Option B. The whole fix. |
| [`engine/chatguard.py`](engine/chatguard.py) | 676 | Option D. The replacement matcher. |
| [`engine/shadow.py`](engine/shadow.py) | 147 | Runs a new filter beside the current one, comparing without changing behaviour. |

**Option A requires no code from this repository at all** — it is a text file
of 342 words. If your review process makes vendoring third-party code slow,
that path is available immediately and independently.

Everything is MIT licensed. The term list is deliberately *not* shipped: the
vocabulary is yours, and what this audit identifies as defective is the
matching, not the words.

---

## Rolling it out safely

1. **Shadow first.** `engine/shadow.py` evaluates the new decision alongside
   the current one and records where they differ, without changing what players
   see.
2. **Check the direction of every difference.** All differences must be
   messages previously refused that would now be delivered. A message newly
   *refused* means a wiring error — none of these options adds blocking.
3. **Enable.** A and B are independent and can ship in either order.

---

## Repository

```
REPORT.md      the audit report
docs/          PDFs, adoption notes, background research
findings/      the evidence  ⚠ contains profanity, by necessity
  words-to-allow.txt    342 ordinary words confirmed refused — measured
  affected-words.txt    8,414 words the rules reach — derived
  blocked-terms.txt     terms confirmed refused
  findings.json         machine-readable summary
  raw-logs/             all 15,307 probes, one JSON record each
fix/           rescue.py, the 473,532-word allowlist, deploy notes
engine/        optional replacement matcher, tests, conformance vectors
tools/         everything used to produce and verify the above
```

## Verify

```sh
python3 tools/verify_safe.py       # dependency and capability surface
python3 engine/tests/test_all.py   # 53 tests
python3 tools/conformance.py       # 29 language-agnostic vectors
python3 tools/check_numbers.py     # every figure in the docs traces to findings.json
```

To confirm the defect itself, send `thank` in game and then `thanks`. It takes
ten seconds and needs nothing from this repository.

## Method

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

Findings describe the service on 11–12 September 2026.

---

MIT licensed. Every figure traces to `findings/findings.json`; every claim
traces to a record in `findings/raw-logs/`.
