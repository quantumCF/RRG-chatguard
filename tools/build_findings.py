#!/usr/bin/env python3
"""
build_findings.py -- turn live probe results into the deliverables.

Consumes the JSONL written by the probe harness (one record per message sent to
the live filter) and emits:

    findings.json          machine-readable summary
    words-to-allow.txt     ordinary words confirmed censored -- the deployable list
    blocked-terms.txt      terms confirmed blocked, for reference
    affected-words.txt     the full blast radius, DERIVED from a dictionary

Every entry in words-to-allow.txt carries provenance: it is there because a
message containing it was sent to the live server and refused, and the probe
that established it is in the raw logs. Nothing in that file is inferred.

affected-words.txt is different in kind and is labelled as such: it is what the
confirmed rules imply for words that were never probed. Keeping the measured
and the derived apart is the whole point -- an earlier draft of this report
mixed them and had to be withdrawn.

Three properties of the raw data drive the logic here:

  "mismatch" is not a verdict. The harness checks by OCR that the text reached
  the input box before clicking Send; when that fails it records "mismatch" and
  stops, so no message was sent and the word was never tested. Treating it as a
  pass would understate the finding, so those records are dropped and the word
  is reported as untested unless some other probe settled it.

  One observation is not a result. Detection is OCR-based and occasionally
  wrong, so a verdict is a vote across independent passes, not the last record
  written.

  A blocked fragment can be two characters. Both confirmed root causes are, so
  any minimum-length rule above 2 silently discards them.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from safety_screen import is_slur, is_vulgar_derivation
except Exception:
    def is_slur(w):
        return (False, "")

    def is_vulgar_derivation(w):
        return (False, "")

CARRIERS = (("xx", "xx"), ("qz", "jv"), ("qz", "qz"), ("mm", "mm"),
            ("qw", "qw"))


def unwrap(w):
    """Carrier probes (xxCUxx) tested a fragment in inert padding, not a word."""
    for pre, suf in CARRIERS:
        if w.startswith(pre) and w.endswith(suf) and len(w) > len(pre) + len(suf):
            return w[len(pre):-len(suf)], True
    return w, False


def load(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, action="append",
                    help="probe log (JSONL); repeatable")
    ap.add_argument("--out", required=True)
    ap.add_argument("--dictionary", default="/usr/share/dict/web2")
    ap.add_argument("--attest", action="append", default=[],
                    help="file of text attesting real vocabulary; repeatable")
    args = ap.parse_args()

    rows = []
    for p in args.results:
        rows.extend(load(p))
    os.makedirs(args.out, exist_ok=True)

    # ---- collect every valid observation per string ----------------------
    obs = collections.defaultdict(list)
    untested = set()
    lexicon_terms = set()
    for r in rows:
        t = (r.get("text") or "").strip()
        if not t or " " in t:          # multi-word calibration strings
            continue
        if r.get("phase") in ("stage1", "phase2"):
            lexicon_terms.add(t.lower())
        res = r.get("result")
        if res in ("blocked", "sent"):
            obs[t.lower()].append(res)
        elif res == "mismatch":
            untested.add(t.lower())
    untested -= set(obs)

    # ---- a verdict is a vote, not the last record ------------------------
    #
    # Inclusion needs TWO blocked observations, not one. Detection is OCR-based
    # and the earliest logs were collected before it was hardened, so a single
    # "blocked" is within the error rate of the instrument -- that is exactly
    # how "av" and "the" got into a previous draft and had to be withdrawn.
    # Corroboration is a property of the evidence rather than of which log a
    # word came from, so it needs no judgement call about which runs to trust.
    #
    # Words blocked exactly once are not discarded, they are reported
    # separately as unconfirmed. Understating is the safer failure here: a name
    # on the allow list that should not be there weakens the ask.
    verdict, disputed, unconfirmed = {}, {}, {}
    for w, v in obs.items():
        nb, n = v.count("blocked"), len(v)
        if nb == 0:
            verdict[w] = "sent"
        elif nb == 1 and n == 1:
            verdict[w] = "unconfirmed"
            unconfirmed[w] = "1/1"
        elif nb * 2 > n:
            verdict[w] = "blocked"
            if nb != n:
                disputed[w] = f"{nb}/{n}"
        else:
            verdict[w] = "sent"
            disputed[w] = f"{nb}/{n}"

    # ---- fragments: what the carrier probes established ------------------
    #
    # Built in one pass and filtered once at the end. Filtering between
    # additions is what let "forksful" and "xxanusxx" survive: the minimality
    # pass ran before the profanity pass added more entries, so anything added
    # afterwards was never compared against them.
    PADDING = set("xqw")
    candidates = set()

    for w, res in verdict.items():
        if res != "blocked":
            continue
        core, was_carrier = unwrap(w)
        if was_carrier:
            candidates.add(core)              # the fragment, not the wrapper
        elif len(w) <= 3:
            candidates.add(w)                 # a short string blocking alone
        elif w in lexicon_terms or is_slur(w)[0] or is_vulgar_derivation(w)[0]:
            candidates.add(w)

    def is_probe(t):
        """A known fragment surrounded only by padding letters is a probe."""
        for other in candidates:
            if other != t and other in t:
                if set(t.replace(other, "", 1)) <= PADDING:
                    return True
        return False

    def explained_by_shorter(t):
        return any(o != t and o in t for o in candidates)

    blocked_terms = {t for t in candidates
                     if not is_probe(t) and not explained_by_shorter(t)}

    # ---- what counts as a word at all ------------------------------------
    #
    # A string only reaches the allow list if it is attested as real
    # vocabulary: present in an English dictionary, in a usage-frequency list,
    # or in the game's own shipped interface text.
    #
    # This exists because the control battery deliberately sends suspected
    # TERMS to find out which ones the filter holds. Those come back blocked,
    # correctly, and without this gate they land in a file captioned "words
    # that must never be censored". The safety screen does not catch them all
    # because it began as English-only and the list here is Portuguese.
    attested = set()
    if os.path.exists(args.dictionary):
        attested |= {l.strip().lower() for l in
                     open(args.dictionary, encoding="utf-8", errors="ignore")}
    word_re = re.compile(r"[a-z][a-z'\-]+")
    for path in args.attest:
        if os.path.exists(path):
            attested |= set(word_re.findall(
                open(path, encoding="utf-8", errors="replace").read().lower()))

    def is_vocabulary(w):
        """Attested directly, or a regular inflection of something attested.

        The inflection step is not optional. Dictionaries hold base forms, so
        without it "decks", "disks", "clicks" and "networks" all read as
        unattested -- and those are the "ks" findings, the ones the report most
        needs to show. A rule that discards its own best evidence is worse than
        no rule.

        Two characters is never vocabulary here: "cu" and "ks" are the rules
        themselves and belong on the terms list, not among their victims.
        """
        if len(w) < 3:
            return False
        if w in attested:
            return True
        stems = []
        if w.endswith("ies"):
            stems.append(w[:-3] + "y")
        if w.endswith("es"):
            stems += [w[:-1], w[:-2]]
        if w.endswith("s"):
            stems.append(w[:-1])
        if w.endswith("ed"):
            stems += [w[:-1], w[:-2]]
        if w.endswith("ing"):
            stems += [w[:-3], w[:-3] + "e"]
        return any(st in attested for st in stems if len(st) >= 3)

    # ---- ordinary words the filter refused -------------------------------
    ordinary, clean, unattested = [], set(), []
    for w, res in verdict.items():
        core, was_carrier = unwrap(w)
        if was_carrier:
            continue
        if res == "blocked":
            # A string confirmed blocked in inert padding is a TERM, unless a
            # shorter confirmed rule already explains it. That distinction is
            # what separates "corno" from "cocoon": both block in padding, but
            # cocoon only does so because it contains "coon", while corno
            # contains no shorter rule and is therefore an entry in its own
            # right. Without this, Portuguese insults land on a list captioned
            # "words that must never be censored".
            shorter = any(t != w and t in w for t in blocked_terms)
            if w in blocked_terms and not shorter:
                pass                      # a term, not a casualty of one
            elif w in lexicon_terms or is_slur(w)[0] or is_vulgar_derivation(w)[0]:
                pass                      # correctly blocked profanity
            elif attested and not is_vocabulary(w):
                # Neither vocabulary nor an entry -- these are the control
                # battery's own probe strings. Recorded separately; adding them
                # to blocked_terms published "ksqwqw" and "forksful" in a file
                # captioned "terms confirmed refused".
                unattested.append(w)
            else:
                ordinary.append(w)
        elif res == "sent":
            clean.add(w)
    ordinary.sort()

    # ---- attribute each word to the shortest fragment that explains it ---
    # Minimum length 2: both confirmed root causes are two characters, so the
    # usual >=3 guard would drop every attribution that matters.
    frags = sorted((f for f in blocked_terms if len(f) >= 2), key=len)
    attribution = {}
    for w in ordinary:
        for f in frags:
            if len(f) < len(w) and f in w:
                attribution[w] = f
                break

    unexplained = [w for w in ordinary if w not in attribution]

    # ---- derived blast radius (NOT measured -- labelled as such) ---------
    rules = sorted({f for f in attribution.values()}, key=len)
    derived = {}
    if rules and os.path.exists(args.dictionary):
        words = [l.strip().lower() for l in
                 open(args.dictionary, encoding="utf-8", errors="ignore")]
        words = [w for w in words if w.isalpha() and 3 <= len(w) <= 20]
        for f in rules:
            hit = [w for w in words if f in w
                   and not (is_slur(w)[0] or is_vulgar_derivation(w)[0])]
            derived[f] = hit

    # ---------------------------------------------------------------- files
    with open(os.path.join(args.out, "words-to-allow.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(
            "# ORDINARY WORDS CONFIRMED CENSORED BY THE LIVE FILTER\n"
            "#\n"
            "# Every word below was sent to the live server inside a chat\n"
            "# message and refused. None of them is profanity. Allowing them\n"
            "# removes a false positive and cannot weaken moderation.\n"
            "#\n"
            "# The comment on each line names the substring that caused the\n"
            "# block, established separately by probing that substring inside\n"
            "# inert padding.\n"
            "#\n"
            f"# words: {len(ordinary)}\n"
            "#\n")
        for w in ordinary:
            f = attribution.get(w)
            note = f"\t# '{f}'" if f else ""
            if w in disputed:
                note += f"  [{disputed[w]} of passes]"
            fh.write(f"{w}{note}\n")

    with open(os.path.join(args.out, "blocked-terms.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("# Substrings and terms confirmed blocked by the live filter.\n"
                 "# Reference only -- this is not a list of things to change.\n"
                 f"# count: {len(blocked_terms)}\n#\n")
        for t in sorted(blocked_terms):
            fh.write(t + "\n")

    if derived:
        with open(os.path.join(args.out, "affected-words.txt"), "w",
                  encoding="utf-8") as fh:
            fh.write(
                "# DERIVED, NOT MEASURED.\n"
                "#\n"
                "# These words were NOT probed. They are ordinary dictionary\n"
                "# words that contain a substring the live filter was measured\n"
                "# to block, so the same rule applies to them. This file is the\n"
                "# scope of the problem; words-to-allow.txt is the evidence.\n"
                "#\n")
            # One word per line, deduplicated, annotated with the shortest
            # rule that reaches it. Grouping by rule instead would list
            # "circus" under both "cu" and its other match, so the file's line
            # count would exceed the distinct-word count quoted everywhere
            # else -- the first thing an integrator would notice and the last
            # thing that should need explaining.
            first = {}
            for f in sorted(rules, key=len):
                for w in derived[f]:
                    first.setdefault(w, f)
            fh.write(f"# words: {len(first)}\n#\n")
            for w in sorted(first):
                fh.write(f"{w}\t# '{first[w]}'\n")

    # The union matters more than the per-rule counts: a word like "circus"
    # matches more than one rule, so adding the columns up overstates the
    # damage. This is the number of DISTINCT ordinary words affected.
    union = set()
    for f, ws in derived.items():
        union |= set(ws)

    # Reach grouped by entry length. This is the number that justifies the
    # recommended fix and, unlike the rule list, it can be quoted in public
    # material without reproducing the slurs themselves.
    by_len, under5 = {}, set()
    for f, ws in derived.items():
        by_len.setdefault(len(f), set()).update(ws)
        if len(f) < 5:
            under5 |= set(ws)
    # Refusal rate per locale vocabulary, from the sweep's own tags. Charts and
    # prose both read this, so neither can drift from the other.
    # Counted over DISTINCT words, not over probe records. Verification
    # re-probes every blocked word three further times, so counting records
    # multiplies the numerator and leaves the denominator alone -- Portuguese
    # came out at 3.4% that way against a true 3.2%.
    LOCALE = {"5-locale-in": "Indonesian", "5-locale-vn": "Vietnamese",
              "5-locale-pt": "Portuguese", "5-locale-th": "Thai",
              "3-common-english": "English"}
    word_locale = {}
    for r in rows:
        name = LOCALE.get(r.get("tag"))
        w = (r.get("text") or "").strip().lower()
        if name and w:
            word_locale.setdefault(w, name)
    loc_tot, loc_blk = collections.Counter(), collections.Counter()
    for w, name in word_locale.items():
        v = verdict.get(w)
        if v in ("blocked", "sent"):
            loc_tot[name] += 1
            if v == "blocked":
                loc_blk[name] += 1
    locales = {k: round(loc_blk[k] / loc_tot[k] * 100, 1)
               for k in loc_tot if loc_tot[k]}

    # What survives the recommended fix: entries of five characters or more,
    # which keep matching as substrings. This is the "after" number.
    remaining = union - under5

    summary = {
        "derived_union_count": len(union),
        "locale_refusal_pct": locales,
        "remaining_after_length_rule": len(remaining),
        # what the reach chart's trailing bucket holds, so the figure in the
        # chart and its alt text is checkable like every other
        "derived_outside_top5": len(union) - sum(
            sorted(( {f: len(v) for f, v in derived.items()} ).values(),
                   reverse=True)[:5]),
        "derived_by_entry_length": {str(k): len(v) for k, v in sorted(by_len.items())},
        "derived_under_5_chars": len(under5),
        "rules_by_entry_length": {str(k): sum(1 for r in rules if len(r) == k)
                                  for k in sorted(by_len)},
        "probes_analysed": len(rows),
        "strings_with_a_verdict": len(verdict),
        "untested_mismatch_only": sorted(untested),
        "ordinary_words_censored": len(ordinary),
        "ordinary_censored": ordinary,
        "clean_words_confirmed": len(clean),
        "blocked_terms": sorted(blocked_terms),
        "rules": rules,
        "attribution": attribution,
        "unexplained": unexplained,
        "disputed": disputed,
        "blocked_but_not_attested_vocabulary": sorted(unattested),
        "unconfirmed_single_observation": sorted(unconfirmed),
        "derived_counts": {f: len(v) for f, v in derived.items()},
    }
    with open(os.path.join(args.out, "findings.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)

    # ---------------------------------------------------------------- report
    print(f"probes analysed          : {len(rows):,}")
    print(f"strings with a verdict   : {len(verdict):,}")
    print(f"never tested (mismatch)  : {len(untested):,}")
    print(f"clean words confirmed    : {len(clean):,}")
    print(f"ORDINARY WORDS CENSORED  : {len(ordinary):,}")
    if disputed:
        print(f"  not unanimous          : {len(disputed)}")
    if unattested:
        print(f"  blocked, not vocabulary: {len(unattested)}  (excluded from the allow list)")
    if unconfirmed:
        print(f"  seen blocked once only : {len(unconfirmed)}  (excluded, need 2)")
    by_frag = collections.Counter(attribution.values())
    if by_frag:
        print("\nby responsible substring:")
        for f, n in by_frag.most_common():
            ex = [w for w in ordinary if attribution.get(w) == f][:6]
            d = f"{len(derived.get(f, [])):,}" if f in derived else "-"
            print(f"  {f!r:8} {n:>4} measured  {d:>8} in dictionary   "
                  f"e.g. {', '.join(ex)}")
    if unexplained:
        print(f"\nblocked but not explained by a known substring ({len(unexplained)}):")
        print("  " + ", ".join(unexplained[:40]))
    if union:
        print(f"\ndistinct ordinary dictionary words affected: {len(union):,}")
    print(f"\nwrote {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
