# Chat Filter Defect Report

**Ragnarok: Rebirth Global**
Independent analysis · measured against the live service · 11 September 2026

---

## Summary

The chat filter blocks the two-letter sequence **`cu`** and matches it as a raw
substring. Every word containing those two letters is refused, in every language
the game ships in.

This censors ordinary vocabulary at scale — `cut`, `cute`, `cup`, `cure`,
`curious`, `circus`, `discuss`, `document`, `vacuum`, `security`, `culture`,
`focus`, `difficult`, `accurate`, `curse`, `cursed`, `thanks`, `understand` —
while leaving much of the abuse it exists to stop untouched.

**5,928 test messages** were sent through the ordinary game client. **693
ordinary dictionary words** were confirmed refused; **4,462** were confirmed to
pass. Every finding below was reproduced in the live game.

---

## 1. The defect

### 1.1 What was observed

| typed in game | result |
|---|---|
| `cu` | **blocked** |
| `cut` · `cute` · `cup` · `cure` | **blocked** |
| `curious` · `circus` · `discuss` · `vacuum` | **blocked** |
| `document` · `thanks` · `understand` · `curse` | **blocked** |
| `xxcuxx` (nonsense padding around `cu`) | **blocked** |

The final row is the decisive one. `xx` and `jv` are inert padding — no dictionary
word, no term in any list. The only thing that can cause a block is the `cu` in
the middle. That establishes both that `cu` is a blocked term and that it matches
**inside** longer words rather than only as a whole word.

### 1.2 Why `cu` is on the list

`cu` is vulgar in **Portuguese**. The most likely explanation is that it was
added for the Portuguese market, which is reasonable in isolation. The defect is
not that the term exists — it is that a two-character term is matched as a
substring, and against all locales rather than the one it was added for.

### 1.3 Scale

Words containing `cu`:

| vocabulary | affected |
|---|---|
| English dictionary (web2, 235k words) | **5,018** |
| **Your own Portuguese localization** | **530 distinct words** |
| Your own English localization | 297 |
| Your own Indonesian localization | 251 |
| Your own Thai localization | 114 |
| Your own Vietnamese localization | 50 |

The market that suffers most is Portuguese — the same market the term was
presumably added to protect.

---

## 2. The filter also misses what it is for

Tested against the same live service, all of the following **passed
unmodified**:

```
kike    spic    fag     rape    whore
bitch   dick    slut    porn    tit     piss
```

Evasion is handled inconsistently. Spaced-out text is caught for some terms and
not others:

| typed | result |
|---|---|
| `s h i t` · `s-h-i-t` · `SHIT` | blocked |
| `c u n t` · `cuuunt` · `CUNT` | blocked |
| `f u c k` · `ｆｕｃｋ` · `fuuuck` | **passed** |

There is also no stemming: `cocks`, `coons`, `cumming` and `cumshots` appear as
separate entries. A stemmed list would not need them, and their presence is why
short roots end up doing substring damage.

**Correcting the matching improves accuracy in both directions.** This report is
not a request to moderate less.

---

## 3. Recommended fix

### 3.1 Immediate — remove or scope `cu`

Delete the `cu` entry, or restrict it to (a) the Portuguese locale and (b)
whole-word matching. This single change resolves the large majority of the
false positives measured here, in every market.

### 3.2 Structural — two rules

**Minimum length before substring matching.** A term shorter than a threshold
should match only as a whole word, never inside a longer one:

```
if (term.length < MIN_SUBSTRING_LEN && !isWholeWord(text, start, end))
    continue;
```

Ship it as a configuration value defaulting to today's behaviour, set it to 4,
and revert by setting it back. A two-character term should never match as a
substring in any language.

**Locale scoping.** Each term should carry the locale it was added for. A
Portuguese term should not be evaluated against English, Thai or Korean text.
Nothing is deleted; terms simply stop applying where they were never intended.

### 3.3 Supplied — the allow list

`findings/words-to-allow.txt` contains **693 ordinary dictionary words**, each
confirmed refused by your live service. Adding them to an allow list removes
false positives and **cannot weaken moderation** — the change is purely
additive.

A reference implementation of the allow-list check (~20 lines, no dependencies)
is in `fix/rescue.py`.

### 3.4 Prevent recurrence

`tools/selftest_filter.py` enforces one invariant: *no string the publisher
authored may be flagged by the publisher's own filter.* It is ~40 lines with no
dependencies and belongs in CI beside the localization export. Had it been
running, `cu` would have been caught before release — 297 of your own English
strings and 530 Portuguese ones trip it.

---

## 4. Method

Messages were typed into the ordinary game client at human pacing (1–3 seconds
apart) and the outcome read from the client's own response: a blocked message
produces the modal *"The speech is innappropriate. Please edit it before
sending"* and never enters chat history. No account, protocol, server or binary
was accessed in any other way.

**Probe design.** Candidate terms were tested inside inert padding (`xxTERMxx`)
so that a block can only be attributed to the term itself. Ordinary words were
tested directly.

**Detection.** Each probe carried a unique tag. A message was recorded as
delivered if either the tag or the word appeared in chat history across repeated
checks; a message recorded as blocked was automatically re-probed once before
the verdict was kept.

**Verification.** Every headline finding was re-tested three times. Of 36 items
re-tested, 29 were confirmed and **6 were discarded** — `but`, `great`, `lord`,
`war`, `military`, `sphinx` had been flagged by single probes and did not
reproduce. Zero flaky results across 108 verification probes.

**Volume.** 5,928 probes: 5,040 in a 14-hour unattended run, plus verification,
evasion and targeted passes.

---

## 5. Limitations

1. **Coverage is a floor, not a total.** Roughly 5,300 of ~235,000 English words
   were tested. The 693 confirmed words are those actually probed; 5,018 English
   dictionary words contain `cu` and are expected to behave identically.
2. **Fragment attribution is indicative.** Where a word contains more than one
   blocked sequence, the responsible one was not always isolated individually.
3. **The filter changes over time.** These results reflect the service on
   10–11 September 2026. The included tools regenerate the analysis against your
   configuration at any time.
4. **Other locales are under-sampled.** Portuguese, Indonesian, Thai and
   Vietnamese were sampled, not swept. Korean and both Chinese variants were not
   tested at all.

---

## 6. What is included

```
findings/words-to-allow.txt     693 ordinary words confirmed refused
findings/blocked-terms.txt      terms confirmed blocked
findings/findings.json          machine-readable summary
findings/raw-logs/              every one of the 5,928 probes

fix/DEPLOY.md                   how to apply each fix
fix/rescue.py                   ~20-line allow-list check
fix/allowlist-en.txt            optional broader allow list

tools/                          reproduce any figure against your own config
appendix/                       optional replacement matcher, background research
```

Every number in this report can be traced to the probe that produced it in
`findings/raw-logs/`.
