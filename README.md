# chatguard

Measurement of the **Ragnarok: Rebirth Global** chat filter, and a fix.

The filter matches its blocked terms as unanchored substrings, and its term
list is predominantly Brazilian Portuguese. Short Portuguese entries applied to
all eight shipped locales censor ordinary vocabulary in every language the game
runs in.

```
thank    delivered
thanks   refused        one letter apart; the plural creates "ks"
```

`cu`, `ks`, `nb`, `anta`, `pica`, `meter`, `pau`, `puta` and nine others are
refused wherever their letters appear. That reaches **8,414 ordinary English
dictionary words** — 3.6% of the language — including `document`, `discuss`,
`security`, `focus`, `number`, `advantage`, `parameter`, `typical`, `campus`,
`vacation`, `reputation`, `thanks`, `tasks`, `books`, `works`.

Measured live: **15,307 messages** through the ordinary game client, **342
ordinary words confirmed refused**, **10,627 confirmed delivered**.

---

## Start here

| | |
|---|---|
| **[REPORT.md](REPORT.md)** | the full report: method, findings, remediation, limitations |
| **[docs/chat-filter-defect-report.pdf](docs/chat-filter-defect-report.pdf)** | the same thing on one page |
| **[findings/words-to-allow.txt](findings/words-to-allow.txt)** | 342 ordinary words confirmed refused, each annotated with the rule responsible |

---

## The fix, in increasing order of effort

**1 — Allow the confirmed words.** `findings/words-to-allow.txt` is a plain
list. If the filter already supports an exception list, this is a data change
and nothing else. It removes false positives only; it does not reduce what is
blocked. `findings/affected-words.txt` extends the same idea to all 8,414
dictionary words the confirmed rules reach, and is labelled as derived rather
than measured.

**2 — Require a word boundary for short terms.** One rule:

> Entries shorter than five characters match only as whole words.

`cu` still refuses `cu` and stops refusing `document`. Entries of five
characters or more are untouched, so `caralho` matches exactly as it does
today. This is the highest ratio of damage removed to change made.

**3 — Replace the matcher.** `appendix/reference-engine/` — per-term match
modes (whole word, prefix, substring), a severity tier per term, allowlist
rescue with longest-match-wins, and normalisation that folds evasion
(`f u c k`, `fuuuck`, `sh1t`, homoglyphs) without folding ordinary words. No
dependencies, MIT, and it sits at the same `check(text) -> bool` seam the
current filter occupies.

The term list is deliberately not shipped. The vocabulary is yours; what is
broken is the matching, not the words.

---

## How the measurement was done

Messages were sent through the game client into a private party channel, one at
a time, at human pace, and read back from chat history to see whether the
server accepted them. No client modification, no packet injection, no server
access.

Three rules govern what reached the report:

- **A substring is not a rule until it is isolated.** Every rule was confirmed
  by sending it inside inert padding (`xxcuxx`) and confirming neither
  neighbouring letter fires alone. Candidates that failed were dropped, however
  suggestive the surrounding evidence.
- **One observation is not a result.** The detection error rate was measured,
  not assumed: 250 words recorded clean were re-probed, giving 6 spurious
  blocks in 491 observations — 1.2% per probe. Every finding therefore needs
  two independent blocked observations.
- **A word that was never sent is not a word that passed.** Probes where the
  text could not be confirmed in the input box are counted as untested, not
  clean. All but 15 were retried to a real verdict.

---

## Layout

```
REPORT.md                     the report
findings/                     evidence and the deployable word list
  words-to-allow.txt            342 words, measured
  affected-words.txt            8,414 words, derived from the confirmed rules
  blocked-terms.txt             terms and substrings confirmed refused
  findings.json                 machine-readable summary
  raw-logs/                     all 15,307 probes, one JSON record each
fix/                          allowlist + drop-in rescue shim, deploy notes
appendix/reference-engine/    the replacement matcher
tests/, vectors/              53 tests, 29 conformance vectors
tools/                        everything used to produce the above
archive/                      superseded drafts, kept for provenance
```

## Verify it

```sh
python3 tests/test_all.py        # 53 tests
python3 tools/conformance.py     # 29 language-agnostic vectors
python3 tools/check_numbers.py   # every figure in the docs traces to findings.json
```

To check the defect itself, send `thank` and then `thanks` in game. It takes
ten seconds and needs none of this repository.

---

MIT licensed. Findings are reproducible from `findings/raw-logs/`; each record
carries the exact string sent, the verdict, and the timestamp.
