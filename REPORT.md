# Chat Filter Accuracy Report

**Ragnarok: Rebirth Global**
Independent measurement against the live service · 12 September 2026

---

## Summary

The chat filter matches its blocked terms as **unanchored substrings**. A term
is refused wherever its letters appear, including in the middle of unrelated
words.

Separately, the term list is predominantly **Brazilian Portuguese**. Several
entries are two to four characters long — `cu`, `pau`, `pica`, `vaca`, `anta`,
`rola`, `japa` — which are ordinary vulgarities in Portuguese and ordinary
letter sequences everywhere else.

The two together are the defect. Short Portuguese terms matched as substrings
against all eight shipped locales censor common vocabulary in every language
the game runs in.

**15,307 messages** were sent through the ordinary game client. **342 ordinary
words were confirmed refused** and **10,627 were confirmed to pass**. The
confirmed rules affect **8,414 ordinary English dictionary words**, 3.6% of the
language.

Examples, each verified live: `thanks`, `attacks`, `tasks`, `books`, `works`,
`weeks`, `banks`, `links`, `document`, `discuss`, `security`, `focus`,
`culture`, `accurate`, `difficult`, `advantage`, `typical`, `tropical`,
`parameter`, `diameter`, `campus`, `vacation`, `reputation`, `cucumber`,
`circus`, `vacuum`.

`thank` is delivered. `thanks` is refused.

---

## 1. Method

Messages were sent through the game client into a private party channel, one at
a time, at human pace. Each message was read back from the chat history to
determine whether the server accepted or refused it. No client modification, no
packet injection, and no access to server code or configuration was involved;
the measurement sees exactly what a player sees.

Three properties of the measurement are worth stating because the conclusions
depend on them.

**A substring is only called blocked once it is isolated.** Observing that
`cucumber` is refused does not establish which part is responsible. Every rule
in this report was confirmed by sending the candidate substring inside inert
padding — `xxcuxx` — and by confirming that neither neighbouring letter fires
alone. A candidate that failed this test was dropped regardless of how
suggestive the surrounding evidence looked.

**A single observation is not a result.** Detection is imperfect. Its error
rate was measured directly rather than assumed: 250 words the sweep recorded as
clean were re-probed twice, producing 6 spurious blocks in 491 observations, a
per-probe false-positive rate of **1.2%**. Every word in the findings therefore
requires at least two independent blocked observations, which reduces the
chance of a spurious entry to roughly 0.015%.

**Words that were never actually sent are not counted as passing.** The harness
verifies that text reached the input box before sending. When that check fails
the message is not sent, and such a word is untested rather than clean. All but
**15** of these were retried until they produced a real verdict.

---

## 2. Findings

### 2.1 Matching is unanchored

`cu` and `ks` were isolated completely:

| probe | result | probe | result |
|---|---|---|---|
| `cu` | refused | `ks` | refused |
| `xxcuxx` | refused | `xxksxx` | refused |
| `xxcxx` | delivered | `xxkxx` | delivered |
| `xxuxx` | delivered | `xxsxx` | delivered |
| `xxucxx` | delivered | `xxskxx` | delivered |

Both sequences are refused bare and inside padding, at the start, middle and
end of a carrier, under two unrelated paddings. Neither constituent letter is
refused alone and neither reversed pair is refused. The filter is matching two
literal characters anywhere in the message.

Across **10,627 words the filter accepted, not one contains `cu` or `ks`.**
There are no exceptions in either direction.

### 2.2 The term list is Portuguese

Twenty-seven Portuguese profanity terms were tested. All twenty-seven are
refused, including uncommon ones:

`puta` · `porra` · `caralho` · `buceta` · `merda` · `foda` · `viado` · `veado`
· `corno` · `babaca` · `otario` · `piroca` · `bosta` · `cuzao` · `arrombado`

The short entries driving most of the damage are the same language: `cu`
(anus), `pau` / `pica` / `rola` (penis), `vaca` (a slur for a woman), `anta`
(idiot), `japa` (an ethnic slur), `meter` (a sexual sense of "to insert"),
`sexo` (sex).

### 2.3 Common English profanity is not on the list

Tested under the same conditions and **delivered**:

`bitch` · `rape` · `sex` · `slut` · `whore`

This is reported because it bears on priority. The filter is not
over-aggressive in general; it is aggressive about one language's vocabulary
and largely absent for another's. Both halves are the same root cause — a term
list that has not been reviewed against the locales it is applied to.

### 2.4 Confirmed rules and their reach

Each rule below was isolated in padding and corroborated. "Measured" counts
words confirmed refused in testing; "dictionary" counts ordinary English words
containing it that were therefore not all individually tested.

| rule | measured | English words affected | example ordinary words |
|---|---|---|---|
| `cu` | 160 | 5,016 | document, discuss, security, focus, accurate, circus |
| `nb` | 17 | 956 | number, inbox, unbind, sunburst |
| `meter` | 5 | 695 | parameter, diameter, kilometer |
| `anta` | 11 | 419 | advantage, santa, atlanta, fantastic |
| `ks` | 70 | 408 | thanks, attacks, tasks, books, works, weeks |
| `pus` | 5 | 230 | campus, octopus, push |
| `pica` | 4 | 227 | typical, tropical, topical |
| `pau` | 4 | 134 | pause, paused, paul |
| `puta` | 1 | 95 | reputation, computation, amputation |
| `nub` | 3 | 65 | snub, anubis, nubian |
| `crack` | 4 | 50 | cracked, firecracker, nutcracker |
| `anus` | 16 | 47 | cyanus, dhanush, elanus |
| `japa` | 2 | 28 | japan, japanese |
| `vaca` | 3 | 21 | vacation, vacate |
| `coon` | 8 | 20 | cocoon, raccoon, tycoon |

Distinct ordinary words affected across all rules: **8,414**. This is the
union, not the sum — `circus` matches more than one rule, and adding the
columns would double-count.

### 2.5 Scope across locales

The measured refusal rate was uniform across the vocabularies tested:
Indonesian 5.2%, Vietnamese 3.6%, English 3.4%, Portuguese 3.2%, Thai 3.2%.
This is not an English-only problem. The game's own Portuguese interface text
contains words its own filter refuses.

---

## 3. Remediation

Three options, in increasing order of effort. They are independent; the first
requires no code change at all.

### Option 1 — Allow the confirmed words

`findings/words-to-allow.txt` lists **342 ordinary words** confirmed refused by
the live service, each annotated with the rule responsible. If the filter
already supports an exception list, this is a data change and nothing more.

This is the smallest possible fix and the one with the least risk. It does not
reduce what is blocked; it removes false positives only.

`findings/affected-words.txt` extends the same list to the full **8,414**
dictionary words the confirmed rules reach. These were not individually tested,
and the file says so at the top. Use it to judge scope, or as a broader
starting set.

### Option 2 — Require a word boundary for short terms

The behaviour that causes the damage is matching entries of two to four
characters inside longer words. A minimum-length rule fixes the majority of it:

> Entries shorter than five characters match only as whole words.

Under this rule `cu` still refuses `cu`, and stops refusing `document`,
`discuss`, `security` and `circus`. `ks` still refuses `ks`, and stops refusing
`thanks` and `books`. Entries of five characters and longer are unaffected, so
`caralho` and `arrombado` continue to match exactly as they do now.

This is the highest ratio of damage removed to change made.

### Option 3 — Replace the matcher

`appendix/reference-engine/` contains a drop-in matcher: per-term match modes
(whole word, prefix, substring), a severity tier per term, allowlist rescue
that resolves longest-match-wins, and normalisation that folds evasion
(`f u c k`, `fuuuck`, `sh1t`, homoglyphs) without folding ordinary words. No
dependencies, MIT licensed, and it sits at the same `check(text) -> bool` seam
the current filter occupies.

It ships with 53 tests and 29 language-agnostic conformance vectors so a port
to another language can be verified against the same expectations. Against the
cases in this report it allows all ordinary words tested and catches the
evasions.

The term list is deliberately not shipped. The vocabulary is yours; what this
report identifies as broken is the matching, not the words.

---

## 4. Limitations

**Rule set is a lower bound.** Only substrings implicated by a tested word
could be isolated. Entries whose letters did not appear in the 11,868 strings
tested would not have surfaced.

**Dictionary counts are derived, not measured.** The 8,414 figure counts
dictionary words containing a confirmed rule. Those specific words were not
each sent to the server. They are labelled as derived wherever they appear, and
the 342 measured words are kept in a separate file.

**Point-in-time.** Everything here reflects the service as it behaved on 11–12
September 2026. If the list is edited, these results describe the previous
state.

**Non-Latin locales are under-covered.** Korean, Chinese and Japanese
vocabularies were not swept; conclusions about them would not be supported.

---

## 5. Evidence

```
findings/words-to-allow.txt   342 ordinary words confirmed refused, with the
                              rule responsible for each
findings/affected-words.txt   8,414 dictionary words the confirmed rules reach
                              (derived, not individually tested)
findings/blocked-terms.txt    terms and substrings confirmed refused
findings/findings.json        machine-readable summary
findings/raw-logs/            all 15,307 probes, one JSON record each
```

Every claim traces to a record in `raw-logs/`. Each record carries the exact
string sent, the verdict, and the timestamp.

To reproduce any single result, send the string in game and observe whether it
appears in chat history. `thank` against `thanks` takes ten seconds and
demonstrates the defect without any tooling.
