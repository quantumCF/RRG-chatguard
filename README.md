# chatguard

An accuracy audit of the **Ragnarok: Rebirth Global** chat filter, and a fix.

The filter matches blocked terms as **unanchored substrings**, and the term
list is **predominantly Brazilian Portuguese**. Two-letter Portuguese entries
applied across all eight locales censor ordinary vocabulary in every language
the game ships in.

```
thank     delivered
thanks    refused      ← one letter apart; the plural creates "ks"
```

`cu` (Portuguese for anus) and `ks` are matched anywhere in a message, with no
word boundary. So are `pica`, `pau`, `rola`, `vaca`, `anta`, `japa`, `puta` and
nine more.

**15,307 messages** sent through the retail client · **342 ordinary words
confirmed censored** · **10,627 confirmed delivered** · the confirmed rules
reach **8,414 ordinary English words**.

Meanwhile `bitch`, `rape`, `sex`, `slut` and `whore` are all delivered.

**[Read the audit report](docs/chat-filter-audit-report.pdf)** (6 pages) ·
[one-page summary](docs/chat-filter-defect-report.pdf) ·
[markdown](REPORT.md)

---

## Fix it

| | Change | Removes | Effort |
|---|---|---|---|
| **A** | Ship [`findings/words-to-allow.txt`](findings/words-to-allow.txt) | The 342 confirmed words | Hours, no code |
| **B** | Add [`fix/rescue.py`](fix/rescue.py) at one call site | Substring false positives generally | 1 day |
| **C** | Minimum-length rule in the matcher | The root cause for short terms | 1–2 days |
| **D** | Replace the matcher with [`engine/`](engine/) | This class of defect entirely | 1–2 weeks |

None of these removes anything from the block list. They remove false
positives only.

**Option B** is three lines where your filter already decides to block:

```python
from rescue import Rescue
rescue = Rescue("allowlist-en.txt")        # once, at startup

if rescue.is_rescued(text, match_start, match_end):
    pass          # ordinary word — deliver it
else:
    block()       # unchanged behaviour
```

**Option C** is one condition:

> Entries shorter than five characters match only as whole words.
> Entries of five characters or more are unchanged.

`cu` still refuses `cu` and stops refusing `document`. `caralho` behaves
exactly as it does today.

---

## Repository

```
REPORT.md      the audit report
docs/          PDFs, adoption notes, background research
findings/      the evidence
  words-to-allow.txt    342 ordinary words confirmed refused, measured
  affected-words.txt    8,414 words the rules reach, derived
  blocked-terms.txt     terms and substrings confirmed refused
  findings.json         machine-readable summary
  raw-logs/             all 15,307 probes, one JSON record each
fix/           rescue.py, the 473,532-word allowlist, deploy notes
engine/        optional replacement matcher, tests, conformance vectors
tools/         everything used to produce the above
```

## Verify

```sh
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
  inside inert padding (`xxcuxx`), with neither neighbouring letter firing
  alone. Candidates that failed were dropped.
- **One observation is not a result.** The detection error rate was measured,
  not assumed: 6 spurious refusals in 491 observations, 1.2% per probe. Every
  reported word required two independent refused observations.
- **An unsent probe is not a passing probe.** All but 15 were retried to a real
  verdict. A false-negative audit over 250 words returned zero misses.

Findings describe the service on 11–12 September 2026.

---

MIT licensed. Every figure traces to `findings/findings.json`; every claim
traces to a record in `findings/raw-logs/`.
