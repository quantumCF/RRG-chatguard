# Adoption

Written for the engineer who has to say yes or no to this, and for the manager
who has to sign off on the risk.

The ask is deliberately tiered. **Tier 1 requires no code and no dependency.**
Most of the player-visible damage is fixed there. Tiers 2 and 3 exist if you
want them, not because Tier 1 is a trap that requires them later.

One thing to establish first, because it changes what you should trust here: the
word list shipped inside a game client is **not necessarily the list the server
enforces**. In the case measured, it demonstrably was not — see `REPORT.md` §3.
So no specific row named in these documents should be actioned directly. Run
`tools/remediate.py` against your own list and act on that. The tools take your
data as input precisely so that this caveat does not matter.

---

## Tier 1 — data only. No code, no dependency, no build. Hours, not sprints.

Two changes to the list you already have:

1. **Scope it by locale.** A market-compliance list written for one region is
   currently being evaluated against players typing another language. Nothing
   gets deleted — the list keeps applying, in full, to the locales it was
   written for. This is one field on a term and one condition at match time.

2. **Drop or re-scope the short entries.** Two-character entries are the single
   biggest source of false positives under substring matching: they appear
   inside thousands of ordinary words. In the list we measured, 53 entries were
   1–2 characters, and the worst single one appeared inside 21,144 English
   dictionary words.

Expected effect, measured on the real list and the real content: game-name
false positives fall from **46.1% to roughly 2.5%** — that is the gap between
substring matching on an unscoped list and whole-word matching, before any
engine change at all.

A third change costs nothing and is worth doing at the same time: under
substring matching, **59.6% of the list cannot affect any outcome**, because a
shorter entry already matches inside each of those entries. Dropping all 57,051
leaves behaviour bit-identical. That is worth sitting with — substring matching
has collapsed a 95,660-entry list into the behaviour of its shortest ~38,000
entries. Moving to word-boundary matching does not weaken the list; it **restores
the other 57,051 entries to usefulness**.

If you stop reading here, this is still worth doing.

---

## Tier 2 — vendor the engine. ~600 lines, zero dependencies, MIT.

Fixes the rest: word-boundary matching, the rescue allowlist, Unicode and leet
normalization, per-surface policy. On identical vocabulary this takes
English-dictionary false positives from **37.1% to 0.0%**.

Roll it out through `engine/shadow.py`, which is designed so the decision is made by
your production traffic rather than by this document. See *Rollout* below.

---

## Tier 3 — improve the vocabulary.

The engine cannot invent coverage. If the list is 93% one language, abuse in
another language gets through no matter how good the matcher is. Adding a
proper per-locale term table takes obfuscated-abuse recall from **23.2% to
84.3%**.

This is the tier that needs your trust-and-safety judgment, not ours, which is
why it is last and separable.

---

## Rollout: how this ships without anyone taking a risk

`engine/shadow.py` wraps your existing filter:

```python
shadow = ShadowFilter(incumbent=your_existing_filter, guard=chatguard)
flagged, filtered = shadow.filter(text)   # ALWAYS the incumbent's answer
```

The incumbent stays authoritative. chatguard runs beside it and records every
disagreement, classified as either `over_block_fixed` (the incumbent censored
something legitimate) or `new_catch` (chatguard flagged something the incumbent
missed). A guard exception can never reach the live path — it is caught, counted,
and the incumbent's answer is returned.

After a week you have a ledger from your own traffic. Flipping `authority` to
`"chatguard"` is one config value. Rolling back is the same value. No deploy,
no client build.

A shadow run over 4,004 of one game's own item and skill names produced:

```
agreement            55.9%
over_block_fixed     1,763     <- incumbent censored its own content
new_catch                1
guard_errors             0
```

---

## Objections, answered

**"This needs a client update and an app-store re-cert."**
No. In the architecture we examined, the filter check is already a server round
trip: the client sends the candidate text and receives a masked string back.
Replacing what happens on the server side of that call changes no client code,
no protocol field, and no binary. Nothing goes to Apple or Google.

**"We can't take an external dependency."**
Then don't. Tier 1 is a change to data you already own. Tier 2 is vendoring a
single dependency-free file into your tree, under MIT, which you then own
outright. There is no package to track and no upstream to trust.

**"It's the wrong language for our stack."**
The contract is `engine/vectors/golden.jsonl` — 25 cases — not code. Any implementation
that reproduces those vectors is conformant. `engine/SPEC.md` is written to be
ported from. The algorithm is Aho–Corasick plus a hash-set lookup; it is a day
of work in any language, and the vectors tell you when you are done.

**"Removing our compliance list creates legal exposure."**
Nothing is removed. The existing list is preserved verbatim as a locale-scoped
pack and keeps applying, unchanged, to the markets it was written for. The
defect is not that the list exists — it is that it is being evaluated against
players it was never written for.

**"We can't risk a regression on a live service."**
That is what shadow mode is for. The incumbent stays authoritative until your
own traffic says otherwise. This is a strictly smaller risk than the status quo,
which is already producing player-visible defects every day.

**"How do we know it's actually better?"**
Run `tools/audit.py` against your list and your corpora. It reports both failure
directions, because reporting only false positives would be marketing. Every
figure in `REPORT.md` was produced by that tool and is reproducible from
data you already have.

**"Our moderation team needs to be able to retune it."**
The lexicon is data: one JSON line per term carrying tier, match mode and
locale. It hot-reloads exactly like your current list. It is strictly more
tunable than a flat array of strings, because a term can now be scoped rather
than only added or removed.

**"Latency."**
Aho–Corasick is O(message length) and independent of list size. The Python
reference does ~97 µs per message against 5,695 terms — about 10,000
messages/sec on one core, before any compiled port. Your current substring scan
is O(list × message): it gets measurably slower every time someone adds a word.
chatguard does not.

**"We don't trust an outsider's judgment about which words are acceptable."**
You shouldn't have to, and you don't. The allowlist protecting your content is
generated from **your own localization tables** — your item, skill, equipment
and NPC names. Regenerate it from your data and it is yours.

**"Legal / IP."**
Clean-room. No code was taken from any client. No proprietary word list is
redistributed. The English allowlist derives from a public-domain dictionary and
the domain lexicon from your own shipped strings. MIT, so there is no copyleft
obligation to review.

**"Who maintains it?"**
You do, and that is the point. ~600 lines, no dependencies, 25 conformance
vectors that fail loudly if someone breaks it.

**"We don't have engineering bandwidth this quarter."**
Tier 1 is a configuration change. It needs a trust-and-safety decision, not a
sprint.

**"We can't see our own server list from where you sit, so how would you know?"**
We don't, and we say so. That is what `tools/blackbox.py` is for: it infers the
responsible terms from observed behaviour alone — "this string was blocked, this
one was fine" — eliminates impossible candidates, reports the smallest consistent
explanation, and designs the next probes. It is correct whatever your list
actually contains.

**"Players are exaggerating; the filter is mostly fine."**
`cucumber` is blocked in the live game. So is `Heisenberg`. `thank` was.
Separately, measured on the shipped list against the game's own English content:
**46.1%** of item and skill name strings are flagged under substring matching,
and **69.0%** of all localized strings — rising to **52.1%** for Portuguese.
`Freezing` becomes `****zing`. That is not a perception problem.

**"We should use an ML classifier instead."**
Different problem, and worth doing — later, on top. A classifier addresses
harassment, context and intent. It does not fix `Freezing → ****zing`, because
that is a string-matching bug and needs a string-matching fix. Deterministic
matching is the layer a classifier sits on; you want both, in that order.

---

## What this repository deliberately does not ship

A tier-3 slur inventory. You already have a vocabulary your trust-and-safety
team owns and stands behind, and importing an outsider's list would be the
wrong kind of change to ask for. What was broken was the **matching**, not the
words. Bring your own vocabulary; the engine is the contribution.
