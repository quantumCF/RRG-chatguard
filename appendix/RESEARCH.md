# What a good chat moderation system looks like in 2026

Background for the recommendations in `REPORT.md`. The short version: the
industry has converged on a **layered** design, and the layer that is broken
here is the cheapest and most deterministic one. Adding machine learning without
fixing it would leave `cucumber` blocked.

---

## The consensus architecture

Every serious production system now looks approximately like this:

```
 1  normalize        Unicode NFKC, confusable folding, case, diacritics,
                     leet, repeats, separators        ~microseconds
 2  deterministic    multi-pattern match against a curated lexicon,
                     with boundaries + an allowlist   ~microseconds
 3  classifier       small supervised model for context, harassment,
                     scams, grooming                  ~1-50 ms
 4  LLM judge        only for genuinely ambiguous cases  ~100-1000 ms
 5  human review     queue, appeals, and the feedback loop
```

The ordering is a cost and latency cascade: layer 2 handles the overwhelming
majority of traffic, and each subsequent layer sees only what the previous one
could not resolve. The current practical guidance is explicitly to *layer* them —
use classifiers for throughput and reserve LLM judges for cases classifiers
cannot settle.

**The filter under discussion is layer 2, implemented without the normalization
of layer 1 or the boundary/allowlist logic that makes layer 2 safe.** That is
why it fails in both directions at once. No amount of layer 3 or 4 compensates:
a substring bug needs a substring fix.

## Layer 1 — normalization, and one subtlety worth knowing

The standard reference is **Unicode UTS #39, Unicode Security Mechanisms**, which
defines the *skeleton* algorithm: normalize, strip ignorable characters, map
confusables to a representative form, normalize again. Two strings with the same
skeleton are confusable.

The subtlety, and it is a real one: **`confusables.txt` is designed for
detection, not for silent normalization.** The intended use for identifiers is
to notice that a submitted string is confusable with something else and reject
or flag it — not to quietly rewrite it and let it through. Blind remapping can
also mis-handle legitimate non-Latin text.

Practical resolution used here: fold for *matching* only, never mutate what is
stored or displayed, and keep an offset map so masking lands on the original
characters. For permanent identifiers — character and guild names — the stricter
UTS #39 posture applies: mixed-script and confusable names should be refused
outright, not silently accepted.

Note also that `confusables.txt` and NFKC **disagree** on a number of characters,
so applying both requires deciding the order deliberately rather than by accident.

## Layer 2 — the deterministic matcher

**Aho–Corasick** is the standard choice: it finds all patterns in one pass, in
time linear in the message and independent of the number of patterns. Optimized
implementations reach multi-GB/s throughput with DFA compilation and SIMD
prefilters. The important property for this case is asymptotic, not peak: a naive
substring scan is O(list × message) and degrades every time a moderator adds a
term, while Aho–Corasick does not.

What separates a good layer 2 from a bad one is not the algorithm but three
pieces of policy around it:

1. **Per-term match modes.** Whole-word by default; substring only where the
   term has no legitimate host word. Applying substring matching uniformly is
   precisely the defect measured here.
2. **An allowlist that outranks the blocklist**, longest-match-wins. This is the
   documented, decades-old fix for the Scunthorpe problem — a false positive
   named for the 1996 AOL incident that blocked residents of an English town
   from registering accounts. It remains the canonical example because it keeps
   recurring.
3. **Severity tiers and per-surface policy.** A permanent public character name
   warrants a stricter threshold than a whisper to a friend.

`rustrict` (Rust) is a good reference implementation of the evasion-handling
side: leet, repeats, spacing, separators, diacritics, and an explicit `EVASIVE`
classification rather than a plain boolean.

## Layer 3 — classifiers, and where they actually help

This is where the last two years moved fastest, and it is worth being precise
about what it buys you.

**Open-weight guard models**, roughly current:

| model | notes |
|---|---|
| **Qwen3Guard** | 0.6B / 4B / 8B, **119 languages**, and a streaming variant with a token-level head for incremental detection. The strongest fit for multilingual game chat. |
| Llama Guard (2/3) | the original taxonomy-driven LLM guard; broad, well documented |
| ShieldGemma / 2 | Gemma-family safety tuning; ShieldGemma 2 adds image moderation |
| Granite Guardian | strong on prompt injection and groundedness |
| WildGuard | highest precision on benign traffic — i.e. it over-blocks least |
| PolyGuard | 17-language corpus (PolyGuardMix, 1.91M samples) |

The consistent finding in 2026 benchmark work is that **no single open-weight
model wins across categories**, and that the practical pattern is two models with
non-overlapping strengths, ensembled with OR for high-severity categories only.

For a game specifically, the classifier's job is **not** profanity — a lexicon
does that better, faster and more predictably. It is the things a lexicon
structurally cannot see:

* harassment and targeted abuse that uses no banned word
* RMT / gold-selling and account trading
* phishing and off-platform solicitation
* grooming patterns
* context: the same word between friends and at a stranger

A 0.6B model at a few milliseconds is affordable per message; a 8B LLM judge is
not, which is why it belongs at layer 4 on a sampled or escalated basis.

**Deployment shape.** Streaming architectures (Kafka/Flink with a local model per
event) are the common production pattern, and there is now credible on-device
work — NPU-resident moderation with ~120 MB footprints and sub-second decisions.
Self-hosting is entirely practical at 0.6B–4B.

## Layer 5 — the part that is usually missing

Trust-and-safety practice is unambiguous that **appeals are a core component**,
not a nicety: they are how false positives get discovered and corrected, and two
metrics matter operationally.

* **Appeal overturn rate.** If a large share of appeals succeed, the system has
  an accuracy problem. If almost none do, the appeals process is too strict.
* **Appeal volume spikes**, which indicate over-removal after a config change.

For this game the cheapest possible version costs no client work: a support
ticket category for "a normal word was blocked", routed to whoever owns the list.
Today a player who hits `cucumber` has nowhere to put that information, which is
why the defect survived launch.

## Regulatory context, briefly

Worth knowing because it changes who cares internally. The EU **Digital Services
Act** is in active enforcement, with harmonized transparency reporting from early
2026 and penalties up to 6% of global turnover. It is process-based: it regulates
*how* moderation decisions are made, notified and appealed, rather than dictating
outcomes. It requires accessible notice-and-action tools and effective means to
**challenge moderation decisions** — and the Commission's preliminary findings
against Meta centred precisely on inadequate mechanisms for contesting them.

A filter that silently censors ordinary words with no appeal path is a poor fit
for that direction of travel, independent of player sentiment.

## What we would actually recommend here, in order

1. **Fix layer 2.** Boundaries, an allowlist, per-term modes, locale scoping. This
   is the entire reported defect and it needs no ML.
2. **Add the CI invariant.** No self-authored string may be flagged by the filter.
   Cheap, permanent, prevents recurrence.
3. **Add an appeal path.** A support category is enough to start.
4. **Then** consider layer 3, scoped to RMT, scams and harassment — the categories
   a lexicon genuinely cannot cover. Qwen3Guard-0.6B is the obvious first
   candidate for a title shipping in eight languages.
5. Keep layer 4 for sampled review and policy calibration, not the hot path.

The ordering matters. Adding a classifier on top of a broken layer 2 would add
cost and latency, and `cucumber` would still be blocked.

---

### Sources

Aho–Corasick and multi-pattern matching: [cp-algorithms](https://cp-algorithms.com/string/aho_corasick.html),
[Toptal](https://www.toptal.com/algorithms/aho-corasick-algorithm),
[a 6 GB/s Go implementation](https://dev.to/kolkov/aho-corasick-in-go-multi-pattern-string-matching-at-6-gbs-with-zero-allocations-2jog) ·
Scunthorpe problem: [Wikipedia](https://en.wikipedia.org/wiki/Scunthorpe_problem) ·
Unicode security: [UTS #39](https://www.unicode.org/reports/tr39/),
[confusables vs NFKC disagreement](https://paultendo.github.io/posts/unicode-confusables-nfkc-conflict/),
[confusable detection primer](https://www.namesilo.com/blog/en/brand-protection/confusable-detection-101-unicode-skeletons-and-mixed-script-checks-for-your-brands) ·
Evasion-handling reference implementation: [rustrict](https://github.com/finnbear/rustrict) ·
Guard models: [Qwen3Guard](https://github.com/QwenLM/Qwen3Guard) and its
[technical report](https://arxiv.org/html/2510.14276v1),
[benchmarking open-source safety guards](https://arxiv.org/html/2605.28830v1),
[guardian model overview](https://www.turingpost.com/p/guardianmodels),
[X-Guard multilingual](https://arxiv.org/pdf/2504.08848) ·
Game deployment patterns: [real-time toxicity detection](https://www.confluent.io/blog/confluent-databricks-detecting-gaming-toxicity/),
[gaming-chat toxicity model comparison](https://arxiv.org/pdf/2510.17924),
[on-device NPU moderation](https://www.amd.com/en/blogs/2026/amd-ryzen-ai-powers-on-device-voice-chat-moderation.html) ·
Appeals and QA practice: [TSPA on user appeals](https://www.tspa.org/curriculum/ts-fundamentals/content-moderation-and-operations/user-appeals/),
[moderation QA](https://www.tspa.org/curriculum/ts-fundamentals/content-moderation-and-operations/content-moderation-quality-assurance/) ·
Regulation: [DSA two-year review](https://commission.europa.eu/news-and-media/news/two-years-digital-services-act-ensuring-safer-online-spaces-2026-02-17_en),
[2026 enforcement outlook](https://www.taylorwessing.com/en/interface/2025/predictions-2026/enhancement-and-enforcement),
[player-safety regulation summary](https://aiba.ai/moderation-vendor-compliance-2026-dsa-osa-coppa/)
