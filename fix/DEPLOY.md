# Deploy

Three fixes, smallest first. **Fix 1 is one line of code and needs no data.**
They compose, but each works alone.

Every figure here derives from the 16 rules confirmed against the live service
in the audit. Earlier versions of this file gave percentages for each language. Those came
from reading the word list inside the game client. We withdrew that analysis:
live testing showed the client's list is not the list the server uses.

---

## Fix 1 — minimum fragment length. One line. No data. No list review.

> An entry shorter than N characters matches only as a **whole word**,
> not as a sequence of letters.

Nothing is deleted. Every entry keeps working. Short entries simply stop
matching inside longer words.

| threshold | entries still matching inside longer words | ordinary English words still censored |
|---|---|---|
| today, no rule | 16 | 8,414 |
| N = 3 | 13 | 2,100 |
| N = 4 | 10 | 1,672 |
| **N = 5** | **2** | **745** |
| N = 6 | 0 | 0 |

**N = 5 is the recommendation.** It leaves only two entries matching as
sequences of letters, and both are long enough that an accidental collision has to
reconstruct five specific letters. N = 6 would remove the remainder, but it
also stops every entry from matching inside a compound, which is a real loss
against deliberate evasion.

Computed by projecting the 16 confirmed rules across an English dictionary of
235,357 ordinary words. The audit's own measurement of the live service is in
`../REPORT.md`; these are the same rules applied to untested vocabulary, and
are labelled derived for that reason.

In your matcher, where you currently accept any hit:

```
if (entry.length < MIN_SUBSTRING_LEN && !isWholeWord(text, matchStart, matchEnd))
    continue;                       // short entries must stand alone
```

`isWholeWord` means the characters immediately before and after the span are not
letters or digits.

**N=4 is the recommendation.** It fixes `cucumber` (3-letter fragment), every
two-letter romanized entry, and the single-character Han entries that damage the
Chinese build. N=5 additionally fixes `Freezing` (`free`, 4 letters).

Why this is the first fix: it needs no list review, no new data, no judgement
calls about individual entries, and it works on entries added tomorrow. The
open-set problem — surnames, place names, new slang — is closed by a rule, not
by listing.

---

## Fix 2 — the allowlist. One file. ~20 lines of glue.

`allowlist-en.txt` — **473,532 words that must never be censored.**

Sources (counts approximate; the file itself is authoritative):

| source | entries | license |
|---|---|---|
| public-domain English dictionary (web2) | 234,246 | public domain |
| place names, world cities + countries (GeoNames) | ~91,600 | CC BY 4.0 |
| surnames (US Census 2010) | 162,253 | public domain |
| given names (BSD `propernames`) | 1,297 | public domain |
| MMO / RPG / chat vocabulary (hand-written here) | 222 | MIT |

Wire it in immediately before your filter returns "blocked":

```python
from rescue import Rescue
rescue = Rescue("allowlist-en.txt")            # once, at startup

if rescue.is_rescued(text, match_start, match_end):
    pass          # ordinary word — let it through
else:
    block()       # your existing behaviour, unchanged
```

The rule: suppress the block when the span sits **strictly inside** an
allowlisted word. Strictly — a word identical to the blocked term never rescues
itself, so adding a term to your blocklist cannot silently stop working.

Measured: 76 MB resident, 0.08 s load, **0.35 µs per check**. Not measurable
against a network round trip.

Reference implementations, all with the same semantics and the same tests:
`rescue.py`, and one per language in this directory.

### Regenerate it with your own vocabulary

The highest-value source is your own localization export — it is exactly the
vocabulary your players type, and it involves nobody's judgement but yours:

```sh
python3 ../tools/build_allowlist.py --out . \
    --terms ../engine/lexicon/lexicon/en-terms.jsonl \
    --locale en:your_en_export.txt --locale pt:your_pt_export.txt \
    --cjk-locale cn:your_cn_export.txt
```

Everything the safety screen rejects is written to `allowlist-rejected.txt` for
review rather than dropped silently.

### CJK

Chinese, Japanese and Thai do not put spaces between words, so there is no word
for a token rule to find — a blocked single character sits inside an ordinary
two-character word with no boundary to appeal to. `--cjk-locale` emits phrase
shelters instead, and `Rescue(phrases_path=...)` consumes them.

---

## Fix 3 — replace the matcher.

`../engine/chatguard.py`, 676 lines, no dependencies, MIT.

Word boundaries, per-term match modes, a rescue allowlist, Unicode/confusable/
leet normalization, bounded fuzzy matching, severity tiers, per-surface policy
(a permanent character name is judged more strictly than a whisper), and
per-locale scoping so one market's list stops being applied to another's players.

We measured this against the audit's own results. We loaded the engine with the
38 entries we confirmed are on the live filter. It blocked **0 of the 343**
ordinary words that the live filter blocks. It still blocked **all 38** entries
when they were typed as words. Same word list, nothing added, nothing
removed.

`python3 engine/tests/test_all.py` reproduces that check.

Roll it out with `../engine/shadow.py`: it runs beside your existing filter
and returns **your** filter's answer every time, recording only where the two
disagree. Flip authority when your own traffic says to. Rollback is the same
config value.

---

## Rollout

1. Ship **Fix 1** behind a config value (`MIN_SUBSTRING_LEN`, default 1 = today's
   behaviour). Set it to 4. Watch. Revert by setting it back to 1.
2. Add **Fix 2**. It is additive — it can only ever *unblock*, never block more.
3. Consider **Fix 3** when there is appetite for it.

None of this needs a client update. The filter check is already a server round
trip, so all of it lands server-side. No store review.

## Verify before you trust any of it

```sh
python3 ../tools/selftest_filter.py --list <your list> --strings <your localization>
python3 ../tools/testbattery.py generate --out battery --margin 0.05
python3 ../tests/test_all.py
```

`tools/selftest_filter.py` enforces one invariant — *no string we authored may be
flagged by our own filter* — and belongs in CI next to the localization export.
It has a `--max-failures` ratchet so it can be adopted today at whatever level is
currently true, then tightened.

## Known limitation, stated plainly

An allowlist cannot close an open set. `Heisenberg` is in no public-domain
dictionary, gazetteer or census list, so Fix 2 alone does not rescue it — which
is exactly why Fix 1 comes first: a length rule covers every proper noun that
will ever exist, including the ones nobody has listd yet.
