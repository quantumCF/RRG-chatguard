# Chat Filter Accuracy Report

**Ragnarok: Rebirth Global**
Independent measurement against the live service · 12 September 2026

---

> **Content notice.** This report audits a profanity filter. Establishing what
> the filter does requires naming the terms it holds, so the sections below
> quote profanity and slurs. They appear as evidence, not as commentary.

---

## Summary

The chat filter searches for each banned word **anywhere in a message,
including inside longer words**. When the letters of a banned word appear in
the middle of an ordinary word, the filter blocks the whole message.

The word list is also mostly **Brazilian Portuguese**. Several entries are only
two to four characters long. In Portuguese they are rude words. In other
languages the same letters are an ordinary part of many words.

These two facts together cause the problem. The filter applies the short
Portuguese entries to all eight languages the game ships in, and searches for
them inside longer words. As a result it blocks common words in every one of
those languages.

We sent **15,307 messages** through the normal game client. The filter blocked
**343 ordinary words**, and delivered **10,627**. Applying the confirmed
entries to an English dictionary gives **8,414 ordinary words** affected, which
is 3.6% of that dictionary.

Examples, each verified live: `thanks`, `attacks`, `tasks`, `books`, `works`,
`weeks`, `banks`, `links`, `document`, `discuss`, `security`, `focus`,
`culture`, `accurate`, `difficult`, `advantage`, `typical`, `tropical`,
`parameter`, `diameter`, `campus`, `vacation`, `reputation`, `cucumber`,
`circus`, `vacuum`.

The filter delivers `thank`. The filter blocks `thanks`.

---

## 1. Method

Messages were sent through the game client into a private party channel, one at
a time, at human pace. Each message was read back from the chat history to
determine whether the server delivered or blocked it. The audit used a normal
player account and the retail client, nothing else, so it sees exactly what a
player sees.

Three properties of the measurement are worth stating because the conclusions
depend on them.

**We report a group of letters only after testing it on its own.** The filter
blocks `cucumber`, but that alone does not show which part of the word caused
it. For every entry in this report we sent the letters inside a made-up word,
such as `xxcuxx`. We also sent each letter on its own. If a single letter was
blocked as well, we dropped the candidate.

**One test is not a result.** Our own reading of the result is sometimes wrong.
We measured how often: we re-tested 250 words that had looked fine, and got 6
wrong readings out of 491 tests. That is an error rate of **1.2%** per test.
For this reason, every word in this report was blocked in at least two separate
tests. The chance that a word reached the list through two wrong readings is
about 0.015%.

**A message that was never sent does not count as delivered.** Before sending,
our tool checks that the text reached the input box. When that check failed, no
message went out. We treated those words as untested, and retried them. Only
**15** words were left unresolved.

---

## 2. Findings

### 2.1 The filter matches inside longer words

We tested `cu` and `ks` on their own. Each test message was built so that a
block could only be caused by those letters:

| probe | result | probe | result |
|---|---|---|---|
| `cu` | blocked | `ks` | blocked |
| `xxcuxx` | blocked | `xxksxx` | blocked |
| `xxcxx` | delivered | `xxkxx` | delivered |
| `xxuxx` | delivered | `xxsxx` | delivered |
| `xxucxx` | delivered | `xxskxx` | delivered |

The filter blocked both pairs of letters on their own, and blocked them again
when we surrounded them with meaningless letters. It blocked them at the start,
in the middle, and at the end of the surrounding word, using two different sets
of surrounding letters. It delivered each single letter on its own, and
delivered the same two letters in the opposite order. The filter is searching
for these two characters anywhere in the message.

The filter delivered 10,627 words during this audit. **None of those 10,627
words contains `cu` or `ks`.** Every word we tested that contains those letters
was blocked.

### 2.2 The term list is Portuguese

Twenty-seven Portuguese profanity terms were tested. All twenty-seven are
blocked, including uncommon ones:

`puta` · `porra` · `caralho` · `buceta` · `merda` · `foda` · `viado` · `veado`
· `corno` · `babaca` · `otario` · `piroca` · `bosta` · `cuzao` · `arrombado`

The short entries driving most of the damage are the same language: `cu`
(anus), `pau` / `pica` / `rola` (penis), `vaca` (a slur for a woman), `anta`
(idiot), `japa` (an ethnic slur), `meter` (a sexual sense of "to insert"),
`sexo` (sex).

### 2.3 Common English profanity is not on the list

Tested under the same conditions and **delivered**:

`bitch` · `rape` · `sex` · `slut` · `whore`

We report this because it affects which fix you choose first. The filter is not
over-aggressive in general; it is aggressive about one language's vocabulary
and largely absent for another's. Both halves are the same root cause — a term
list that has not been reviewed against the locales it is applied to.

### 2.4 Confirmed rules and their reach

Each rule below was isolated in padding and confirmed. "Measured" counts
words confirmed blocked in testing; "dictionary" counts ordinary English words
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

### 2.5 Entry length, not entry count, drives the damage

| entry length | entries | ordinary English words reached |
|---|---|---|
| 2 characters | 3 | 6,355 |
| 3 characters | 3 | 428 |
| 4 characters | 8 | 928 |
| 5 characters | 2 | 745 |

**7,675 of the 8,414 affected words — 91% — are reached by entries shorter
than five characters.** This is the measured basis for the fix recommended in Section 3. A rule about
entry length removes most of the problem, and nobody has to review the word
list to apply it. The problem comes from how short the entries are, not from
which entries they are.

### 2.6 Scope across locales

The measured block rate is comparable across every vocabulary tested:
Indonesian 4.8%, Thai 3.0%, English 2.8%, Portuguese 2.8%, Vietnamese 2.2%. This is not an English-only problem. The game's own
Portuguese and Indonesian interface text contains words its own filter blocks.

These percentages count each word once, not each test. Counting tests inflates
them, because verification re-tests every blocked word three further times and
so multiplies the numerator while leaving the denominator alone.

---

## 3. Remediation

Three options, in increasing order of effort. They are independent; the first
requires no code change at all.

### Option 1 — Allow the confirmed words

`findings/words-to-allow.txt` lists **343 ordinary words** confirmed blocked by
the live service, each annotated with the rule responsible. If the filter
already supports an exception list, this is a data change and nothing more.

Option 1 is the smallest fix and has the lowest risk. It does not reduce what
the filter blocks. It only stops the filter blocking ordinary words.

`findings/affected-words.txt` extends the same list to the full **8,414**
dictionary words the confirmed rules reach. These were not individually tested,
and the file says so at the top. Use it to judge scope, or as a broader
starting set.

### Option 2 — Require a word boundary for short terms

The behaviour that causes the damage is matching entries of two to four
characters inside longer words. A minimum-length rule fixes the majority of it:

> Entries shorter than five characters match only as whole words.

With this rule in place, the filter still blocks a message that is only the
word `cu`. It stops blocking `document`, `discuss`, `security` and `circus`.
The filter still blocks a message that is only the word `ks`, and stops
blocking `thanks` and `books`. Entries of five characters or more are not
affected: they match exactly as they do now.

Option 2 removes the most problems for the least change.

### Option 3 — Replace the matcher

`engine/` contains a replacement matcher. Each entry can be set to match as a
whole word, at the start of a word, or anywhere inside a word. Each entry has a
severity level. An exception list protects ordinary words, and the longest
match wins. The matcher also recognises disguised spellings such as `f u c k`,
`fuuuck` and `sh1t`, and it does not affect ordinary words. It has no outside
dependencies, is MIT licensed, and uses the same `check(text) -> bool` call
that the current filter uses.

The engine ships with 55 tests and 29 conformance vectors. A team rewriting it
in another programming language can check their version against the same
expected results. Against the
cases in this report it allows all ordinary words tested and catches the
evasions.

The term list is deliberately not shipped. The vocabulary is yours; what this
report identifies as broken is the matching, not the words.

---

## 4. Limitations

**Rule set is a lower bound.** Only sequences of letters implicated by a tested word
could be isolated. Entries whose letters did not appear in the 11,868 strings
tested would not have surfaced.

**Dictionary counts are derived, not measured.** The 8,414 figure counts
dictionary words containing a confirmed rule. Those specific words were not
each sent to the server. They are labelled as derived wherever they appear, and
the 343 measured words are kept in a separate file.

**Point-in-time.** Everything here reflects the service as it behaved on 11–12
September 2026. If the list is edited, these results describe the previous
state.

**Non-Latin locales are under-covered.** Korean, Chinese and Japanese
vocabularies were not swept; conclusions about them would not be supported.

---

## 5. Evidence

```
findings/words-to-allow.txt   343 ordinary words confirmed blocked, with the
                              rule responsible for each
findings/affected-words.txt   8,414 dictionary words the confirmed rules reach
                              (derived, not individually tested)
findings/blocked-terms.txt    terms and sequences of letters confirmed blocked
findings/findings.json        machine-readable summary
findings/raw-logs/            all 15,307 probes, one JSON record each
```

Every claim in this report comes from a record in `findings/raw-logs/`. Each
record holds the exact text we sent, the result, and the time.

To reproduce any single result, send the string in game and observe whether it
appears in chat history. `thank` against `thanks` takes ten seconds and
demonstrates the defect without any tooling.
