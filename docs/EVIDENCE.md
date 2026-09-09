# Evidence

Every figure here was produced by `tools/audit.py` from a shipped game client's
own data. Nothing is estimated and nothing is extrapolated. The method is at the
bottom so you can re-run it against your own list.

---

## The list under audit

| | |
|---|---|
| Entries | **95,660** |
| Chinese (Han / fullwidth) | **89,378 — 93.4%** |
| ASCII | 6,205 (5,695 alphabetic) |
| Entries of 1–2 characters | **53** |
| Entries using the wildcard syntax the format supports | 26 — **0.03%** |

The composition matters more than the size. This is a market-compliance list —
political terms, regional gambling domains, drug-precursor chemical names — and
it is being applied to players typing English, Spanish and Portuguese.

The two-character entries are romanized abbreviations. They are meaningless in
English and catastrophic as substrings: the worst single one occurs inside
**21,144** English dictionary words.

Confirmed as **exact** entries in the list, by direct string match:

```
the   party   tank   priest   banana   country
master   freedom   four   iii   lantern   pancake
```

`priest` is one of the game's own character classes. `party` and `tank` are core
MMO vocabulary. `the` is the most common word in the English language.

---

## Over-blocking

Lines that should pass clean, but get flagged.

| corpus | n | blocklist / substring | blocklist / whole-word | chatguard, same vocab | chatguard |
|---|---|---|---|---|---|
| game item & skill names | 16,381 | **7,545 (46.1%)** | 415 (2.5%) | 3,234 (19.7%) | **3 (0.0%)** |
| all localized strings | 81,303 | **56,066 (69.0%)** | 24,020 (29.5%) | 44,007 (54.1%) | **47 (0.1%)** |
| English dictionary | 235,616 | **87,481 (37.1%)** | 104 (0.0%) | 104 (0.0%) | 77 (0.0%) |

Read the **same vocab** column carefully — it is the honest one. It gives
chatguard's matcher the identical 5,695-term vocabulary the baseline has, so
every difference is attributable to matching strategy alone and not to a
friendlier word list.

On the English dictionary that column is decisive: **37.1% → 0.0%** with no
vocabulary change whatsoever. That is the Scunthorpe problem, eliminated by word
boundaries plus a rescue allowlist.

On the game's own strings the same column stays high (54.1%), and that is the
finding, not a failure: **no matcher can rescue a list that contains the word
`the`.** That residue is a vocabulary defect, and it is what Tier 1 and Tier 3
address.

---

## Under-blocking

Obfuscated abuse that should be caught. Same terms, ten obfuscation strategies.

| variant | substring | whole-word | chatguard, same vocab | chatguard |
|---|---|---|---|---|
| plain | 35.7% | 21.4% | 21.4% | **89.3%** |
| spaced `f u c k` | 0.0% | 0.0% | 35.7% | **89.3%** |
| dotted `f.u.c.k` | 0.0% | 0.0% | 35.7% | **89.3%** |
| dashed | 0.0% | 0.0% | 35.7% | **89.3%** |
| repeated `fuuuck` | 57.1% | 0.0% | 21.4% | **85.7%** |
| leetspeak `sh1t` | 14.3% | 3.6% | 21.4% | **89.3%** |
| fullwidth `ｆｕｃｋ` | 0.0% | 0.0% | 21.4% | **89.3%** |
| Cyrillic homoglyph | 14.3% | 7.1% | 21.4% | **89.3%** |
| letter swap `fvck` | 28.6% | 0.0% | 0.0% | 42.9% |
| padded | 78.6% | 0.0% | 17.9% | **89.3%** |
| **all** | **22.9%** | **3.2%** | 23.2% | **84.3%** |

The `plain` row is the quiet indictment: only **21.4%** of common English
profanity appears in the list as an exact entry at all. The list simultaneously
censors 37% of the dictionary and misses four fifths of the words it is
nominally for.

---

## The decomposition

The two failure directions have **different causes and different fixes**:

* Over-blocking is an **engine** defect — 37.1% → 0.0% on identical vocabulary.
* Under-blocking is a **vocabulary** defect — 23.2% → 84.3% needs new terms, and
  no matcher change produces it.

They are independent. Each can ship on its own. This is why `docs/ADOPTION.md`
is tiered rather than all-or-nothing.

---

## Shadow run

`impl/python/shadow.py` against 4,004 of the game's own item and skill names,
with the incumbent substring filter authoritative throughout:

```
calls                4,004
agreement             55.9%
over_block_fixed      1,763      incumbent censored its own content
new_catch                 1
guard_errors              0
```

A sample of what the incumbent does to the game's own names:

```
Freezing                  ->  ****zing
Immunity Control          ->  i**unity control
Osiris' Curse             ->  osiris' c**se
Savage Card               ->  **vage card
Card Skills               ->  card ski**s
Downpour                  ->  downpo**
Invisibility              ->  invisibili**
Ignite                    ->  igni**
```

---

## Latency

Per message, single core, 5,695 terms, Python reference implementation:

| engine | µs/message |
|---|---|
| blocklist / substring | 65.2 |
| blocklist / whole-word | 0.9 |
| chatguard, same vocab | 100.4 |
| chatguard | 96.7 |

chatguard is slower than a bare hash-set lookup, and stating otherwise would be
dishonest. ~97 µs is roughly 10,000 messages/sec on one core in **interpreted
Python**, before any compiled port — comfortably inside the budget for a chat
round trip that is already crossing a network.

The asymptotics run the other way, which matters more over time: substring
scanning is O(list × message) and degrades every time a moderator adds a term,
while Aho–Corasick is O(message) and does not.

---

## Method, so you can reproduce it

```sh
# both failure directions, any list, any corpora
python3 tools/audit.py --list your-list.json --ascii-only \
        --corpus your-item-names.txt \
        --corpus your-localized-strings.txt \
        --corpus /usr/share/dict/words \
        --json results.json
```

* `--list` takes a JSON array of strings or a chatguard `.jsonl` term table.
* `--ascii-only` restricts the audited list to ASCII alphabetic entries, which
  is the fair scope when the corpora are English.
* The over-blocking corpora are text that *should* pass. Using the game's own
  localized content is the strongest possible choice: it is text the publisher
  authored, so any flag on it is unambiguously a false positive.
* The under-blocking corpus is generated in-tool by applying ten obfuscation
  transforms to known terms.

### Caveats, stated plainly

1. The audited list is the copy **shipped in the client**. Whether the live
   server list is identical is not verifiable from the client side. It was
   byte-identical across a full content patch, and nothing in the client loads
   it, which is consistent with it being an export of the same source data — but
   that is inference, not proof.
2. The `substring` and `whole-word` columns are **models** of the incumbent, not
   the incumbent itself. The real matcher runs server-side and was not observed.
   Both bounds are reported precisely because the true behaviour sits somewhere
   between them, and the argument holds at either bound.
3. The `plain` recall figures depend on which terms the evasion corpus is built
   from; they measure coverage of common English profanity, not of all abuse.
4. False positives here are measured against *published game content and
   dictionary words*, which is a proxy for player chat, not a sample of it.
   A shadow run on real traffic is the only way to measure the real rate — which
   is exactly what `shadow.py` is for.
