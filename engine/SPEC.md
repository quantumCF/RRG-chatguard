# Specification

Normative behaviour, written to be ported from. An implementation is conformant
when it reproduces `vectors/golden.jsonl`.

Keywords MUST / SHOULD / MAY are used in the RFC 2119 sense.

---

## 1. Data model

### 1.1 Term

```json
{"text": "fuck", "tier": 2, "mode": "prefix", "locales": ["en"]}
```

| field | required | meaning |
|---|---|---|
| `text` | yes | the term, normalized per §2 at load time |
| `tier` | no, default 2 | 1 mild, 2 strong, 3 severe, 4 illegal |
| `mode` | no, default `word` | `word`, `prefix`, or `sub` |
| `locales` | no, default all | locales this term applies to |

Implementations MUST normalize `text` through the §2 boundary pass at load time
and remove interior spaces. A term that normalizes to empty MUST be discarded.

### 1.2 Allowlist

A set of normalized word forms. An entry that is also a term MUST be removed
from the allowlist at load time — a term always outranks the allowlist, so that
adding a word to the blocklist cannot silently do nothing.

### 1.3 Policy

Maps tier → action for a named surface. Actions: `ALLOW`, `MASK`, `BLOCK`,
`REVIEW`. Three surfaces SHOULD be provided:

| surface | intent |
|---|---|
| `private` | party / guild / whisper — permissive |
| `public` | world / shout / trade — masked |
| `identifier` | character, guild, pet, stall names — permanent and public, strict |

---

## 2. Normalization

Two passes over the input. Both MUST produce, alongside the folded string, a map
from each output character to a half-open `[start, end)` range in the **original**
string. All masking happens through that map.

### 2.1 Per-character folding (both passes)

In order:

1. Drop zero-width and soft-hyphen characters.
2. Apply Unicode **NFKC**.
3. Decompose **NFD** and drop combining marks (category `Mn`).
4. Lowercase.
5. Map confusables to their Latin skeleton (UTS #39). A production build SHOULD
   load the full confusables table; a minimal build MUST cover Cyrillic and
   Greek lookalikes.
6. Optionally map leetspeak: `4@→a 8→b 3→e 6 9→g 1 ! |→i 0→o 5 $→s 7 +→t 2→z`.

### 2.2 Boundary pass (`condense = false`)

* Any run of separator characters collapses to a **single space**.
* Repeated letters are **preserved**.

This pass drives word/prefix matching and allowlist rescue. Preserving doubles
is required, or `classic` folds to `clasic` and stops matching the allowlist.

### 2.3 Evasion pass (`condense = true`)

* Separator characters are **removed entirely**.
* A run of **three or more** identical characters collapses to one.

The threshold of three is normative. Collapsing doubles folds `wall→wal`,
`Baal→bal` and `seller→seler`, which invents matches inside ordinary words and
proper nouns. English orthography effectively never triples a letter, so 3+ is a
genuine obfuscation signal and 2 is just spelling.

Separator set: space, tab, and ``. _ - * ' " ` ^ ~ , ; : ( ) [ ] { } < > / \ |``

---

## 3. Matching

Both passes are searched with the same automaton (Aho–Corasick is RECOMMENDED;
any exact multi-pattern matcher is acceptable).

### 3.1 Boundary-pass hits

A hit at `[i, j)` is kept only if its `mode` boundary condition holds against
the normalized text:

| mode | condition |
|---|---|
| `word` | `i == 0 or !isalnum(n[i-1])` **and** `j == len or !isalnum(n[j])` |
| `prefix` | left condition only |
| `sub` | always |

### 3.2 Evasion-pass hits

A hit is kept only if the **original** span shows an obfuscation signature.
Let `span = original[start:end]` and `term` be the matched term:

1. If `len(span) <= len(term)` → **reject**. The span is the plain term, and the
   boundary pass already adjudicated it. This is what stops `grape` matching
   `rape` via the back door.
2. Else if `span` contains no separator → **accept**. Length grew only through a
   collapsed 3+ run, i.e. `fuuuuck`.
3. Else split `span` on separators; **accept** only if every resulting run is
   ≤ 2 characters. Spaced-out obfuscation writes one or two characters between
   separators (`f u c k`, `fu ck`). This rejects `bass hit`, whose run `hit` is
   three characters and therefore ordinary prose.

### 3.3 Fuzzy stage (OPTIONAL)

Edit distance ≤ 1 against terms whose tier is in a configured high-severity set
and whose length ≥ 5 (both configurable). Candidates are whole tokens from the
boundary pass; tokens present in the allowlist MUST be skipped.

This stage is deliberately narrow. Applied to the whole vocabulary it is a false
positive generator.

---

## 4. Rescue

Two rules, applied in order. Both are longest-match-wins.

### 4.1 Phrase shelter (REQUIRED, script-agnostic)

Run a second automaton over the allowlist to find every allowlisted phrase
occurring in the text. A hit whose original span is **strictly contained** in
such an occurrence is discarded, and the sheltering phrase SHOULD be reported in
`rescued`.

"Strictly" is normative: a phrase identical to the term must not rescue it, or
adding a word to the blocklist that also appears in the allowlist would silently
do nothing.

This rule is required rather than optional because it is the **only** rescue that
works for Chinese, Japanese and Thai. Those scripts do not separate words with
spaces, so a token rule can never fire: a single blocked Han character inside an
ordinary two-character word has no token boundary to appeal to. Phrase shelters
handle `日` inside `日光` and `shit` inside `shitake` with the same mechanism.

### 4.2 Token shelter

For each remaining hit, find the boundary-pass token whose original span contains
it. If that token is not itself the term and is in the allowlist, discard the hit.

Together these fix the Scunthorpe class of false positive and its CJK equivalent.

---

## 5. Decision

1. Discard hits whose term does not apply to the request locale.
2. Deduplicate by `(start, end, term)`.
3. Map each remaining hit's tier through the surface policy to an action.
4. Drop hits whose action is `ALLOW`.
5. The message action is the **maximum** action over remaining hits.
6. If the action is `BLOCK`, `filtered` MUST equal the original text — the caller
   is refusing the message, not delivering a masked one.
7. Otherwise every `MASK` hit's original span is overwritten with the mask
   character, one per original character.

---

## 6. Output

```json
{
  "filtered_word": "this is ****",
  "action": "MASK",
  "errorId": 1,
  "hits": [{"start": 8, "end": 12, "tier": 2, "action": "MASK"}],
  "rescued": []
}
```

`errorId` is `0` for `ALLOW` and the numeric action otherwise, so the shape can
be returned directly by servers whose existing contract is an error code plus a
filtered string.

---

## 7. Conformance

```sh
python3 tools/conformance.py     # must print: 25 passed, 0 failed
```

Port authors SHOULD begin by hardcoding the fixture in `tools/conformance.py`
(six terms, eleven allowlist entries) and working until all vectors pass. No
code needs to be shared between implementations; the vectors are the contract.
