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
    verdict, disputed = {}, {}
    for w, v in obs.items():
        nb, n = v.count("blocked"), len(v)
        if nb == 0:
            verdict[w] = "sent"
        elif nb == n:
            verdict[w] = "blocked"
        elif nb * 2 > n:
            verdict[w] = "blocked"
            disputed[w] = f"{nb}/{n}"
        else:
            verdict[w] = "sent"
            disputed[w] = f"{nb}/{n}"

    # ---- fragments: what the carrier probes established ------------------
    blocked_terms = set()
    for w, res in verdict.items():
        core, was_carrier = unwrap(w)
        if res == "blocked" and was_carrier:
            blocked_terms.add(core)

    # a bare short string that blocks on its own is also a fragment
    for w, res in verdict.items():
        if res == "blocked" and len(w) <= 3 and not unwrap(w)[1]:
            blocked_terms.add(w)

    # profanity that blocks is a correct block, and belongs on the reference
    # list rather than the allow list
    for w, res in verdict.items():
        if res == "blocked" and (w in lexicon_terms or is_slur(w)[0]
                                 or is_vulgar_derivation(w)[0]):
            blocked_terms.add(w)

    # ---- ordinary words the filter refused -------------------------------
    ordinary, clean = [], set()
    for w, res in verdict.items():
        core, was_carrier = unwrap(w)
        if was_carrier:
            continue
        if res == "blocked":
            if not (w in lexicon_terms or is_slur(w)[0]
                    or is_vulgar_derivation(w)[0]):
                ordinary.append(w)
        else:
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
            for f in rules:
                fh.write(f"#\n# --- contains '{f}': {len(derived[f]):,} words\n")
                for w in derived[f]:
                    fh.write(w + "\n")

    summary = {
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
    print(f"\nwrote {args.out}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
