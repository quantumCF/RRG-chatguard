# Probe set — determines what the live filter actually does

Type each line in **guild chat** (not world chat — avoids spamming players and
tripping rate limits). Record `pass` or `blocked`. Twenty messages settles it.

`qz`/`jv` are nonsense padding: if a probe is blocked, the fragment in the middle
is the cause, because nothing else in the string could be.

---

## A. Does fragment length matter?

This is the main question. `cucumber` is blocked (3-letter fragment fires) while
`okay` passes (2-letter `ka` does not). These confirm where the cutoff is.

| # | type this | tests | if blocked it means |
|---|---|---|---|
| 1 | `okay` | control | *(known: passes)* |
| 2 | `qzcumjv` | `cum` in isolation | 3-char fragments fire as substrings |
| 3 | `cum` | `cum` alone | the bare term is listed |
| 4 | `qzkajv` | `ka` in isolation | 2-char fragments fire too |
| 5 | `qzlljv` | `ll` in isolation | 2-char fragments fire too |
| 6 | `qzthejv` | `the` in isolation | the client list is live after all |

**Reading it:** if 2 and 3 block but 4, 5 and 6 pass, the server enforces an
English list with a minimum fragment length of 3. That is the single most useful
thing to learn, and it tells you exactly what `MIN_SUBSTRING_LEN` should be.

## B. Which ordinary words are actually affected?

Only worth running if section A shows 3-character fragments firing.

| # | type this | contains |
|---|---|---|
| 7 | `cucumber` | *(known: blocked)* |
| 8 | `circumvent` | `cum` |
| 9 | `document` | `cum` |
| 10 | `accumulate` | `cum` |
| 11 | `Scunthorpe` | a well-known case |
| 12 | `assassin` | `ass` |
| 13 | `classic` | `ass` |
| 14 | `analysis` | `anal` |
| 15 | `grape` | `rape` |
| 16 | `shiitake` | `shit` |

Every block here is a false positive you can hand to an engineer directly.

## C. Does it catch disguised abuse?

Substitute a common swear word for `WORD`. These measure the other failure
direction, and they matter: without them the report reads as a request to
moderate less.

| # | type this | tests |
|---|---|---|
| 17 | `W O R D` (letters spaced) | separator evasion |
| 18 | `W-O-R-D` | separator evasion |
| 19 | `WOOOORD` (letter repeated) | run collapsing |
| 20 | `W0RD` (zero for O) | leetspeak |
| 21 | `ＷＯＲＤ` (full-width) | Unicode normalization |
| 22 | `WORD` plain | control — confirms the filter is on |

**Probe 22 matters.** If plain profanity passes, the filter is off for that
channel and nothing else in the run is comparable.

## D. Is it the same everywhere?

| # | type this | where |
|---|---|---|
| 23 | `cucumber` | world / shout chat |
| 24 | `cucumber` | whisper |
| 25 | `Cucumber` | guild chat, capitalised — tests case sensitivity |

---

## Recording results

Append to `observations/live-2026-09-09.jsonl`, one per line:

```json
{"text": "qzcumjv", "blocked": true}
{"text": "qzkajv",  "blocked": false}
```

Then:

```sh
python3 tools/blackbox.py infer  --obs observations/live-2026-09-09.jsonl
python3 tools/blackbox.py design --obs observations/live-2026-09-09.jsonl
```

`infer` eliminates every fragment inconsistent with the results and reports the
smallest set that explains them. `design` proposes the next probes if the answer
is still ambiguous.

Once section A is answered, `tools/lengthrule.py` can be pointed at the real
behaviour and will give a false-positive rate that means something — unlike any
figure derived from the client's stale copy of the list.
