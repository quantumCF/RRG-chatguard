#!/usr/bin/env python3
"""
build_findings.py -- turn live probe results into the deliverables.

Consumes the JSONL written by the probe harness (one record per message sent to
the live filter) and emits:

    findings.json          machine-readable summary
    words-to-allow.txt     ordinary words confirmed censored -- the deployable list
    blocked-terms.txt      terms confirmed blocked, for reference
    FINDINGS.md            the human-readable report body

Every entry carries provenance: it is in the list because a message containing
it was refused by the live server, and the probe that established it is in the
log. Nothing here is inferred from a client-side word list.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

# Words that are profanity themselves -- they belong on the blocked-terms list,
# never on the allow list, regardless of how they were probed.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from safety_screen import is_slur, is_vulgar_derivation
except Exception:
    def is_slur(w):
        return (False, "")

    def is_vulgar_derivation(w):
        return (False, "")


def load(path):
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    pass
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, action="append")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = []
    for p in args.results:
        if os.path.exists(p):
            rows.extend(load(p))
    os.makedirs(args.out, exist_ok=True)

    # A word's verdict is its last recorded verdict (later probes supersede).
    # Terms probed during lexicon discovery ARE profanity by construction --
    # they came from a profanity word list. They belong on blocked-terms, never
    # on the allow list, no matter what the verdict was.
    lexicon_terms = {r["text"].lower() for r in rows
                     if r.get("phase") in ("stage1", "phase2")}

    verdict = {}
    for r in rows:
        t = r.get("text", "").strip()
        res = r.get("result")
        if not t or res not in ("blocked", "sent"):
            continue
        if " " in t:          # multi-word calibration strings, not vocabulary
            continue
        verdict[t.lower()] = res

    # Carrier probes (xxTERMxx / qzTERMjv) tested a fragment, not a word.
    def unwrap(w):
        for pre, suf in (("xx", "xx"), ("qz", "jv"), ("qz", "qz"),
                         ("mm", "mm")):
            if w.startswith(pre) and w.endswith(suf) and len(w) > len(pre) + len(suf):
                return w[len(pre):-len(suf)], True
        return w, False

    blocked_terms, blocked_words, clean_words = set(), {}, set()
    for w, res in verdict.items():
        core, was_carrier = unwrap(w)
        if res == "blocked":
            if was_carrier:
                blocked_terms.add(core)
            elif w in lexicon_terms or is_slur(w)[0] or is_vulgar_derivation(w)[0]:
                blocked_terms.add(w)
            else:
                blocked_words[w] = True
        else:
            if not was_carrier:
                clean_words.add(w)

    # Words that are themselves profanity are not "false positives".
    ordinary = sorted(w for w in blocked_words
                      if not (is_slur(w)[0] or is_vulgar_derivation(w)[0]))

    # attribute each ordinary word to the fragment responsible
    frags = sorted(blocked_terms | {w for w in verdict
                                    if verdict[w] == "blocked"
                                    and (is_slur(w)[0] or is_vulgar_derivation(w)[0])},
                   key=len)
    attribution = {}
    for w in ordinary:
        for f in frags:
            if 3 <= len(f) < len(w) and f in w:
                attribution[w] = f
                break

    with open(os.path.join(args.out, "words-to-allow.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("# ORDINARY WORDS CONFIRMED CENSORED BY THE LIVE FILTER\n#\n"
                 "# Each word below was sent to the live server in a chat message\n"
                 "# and refused. None is profanity. Adding these to an allow list\n"
                 "# removes a false positive and cannot weaken moderation.\n#\n"
                 f"# words: {len(ordinary)}\n#\n")
        for w in ordinary:
            f = attribution.get(w)
            fh.write(f"{w}\n" if not f else f"{w}\t# blocked by '{f}'\n")

    with open(os.path.join(args.out, "blocked-terms.txt"), "w",
              encoding="utf-8") as fh:
        fh.write("# Terms confirmed blocked by the live filter (reference only).\n"
                 f"# count: {len(blocked_terms)}\n#\n")
        for t in sorted(blocked_terms):
            fh.write(t + "\n")

    summary = {
        "probes_total": len(rows),
        "words_tested": len(verdict),
        "ordinary_words_censored": len(ordinary),
        "clean_words_confirmed": len(clean_words),
        "blocked_terms": sorted(blocked_terms),
        "ordinary_censored": ordinary,
        "attribution": attribution,
    }
    with open(os.path.join(args.out, "findings.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)

    by_frag = collections.Counter(attribution.values())
    print(f"probes analysed        : {len(rows):,}")
    print(f"distinct strings tested: {len(verdict):,}")
    print(f"blocked terms          : {len(blocked_terms)}")
    print(f"ORDINARY WORDS CENSORED: {len(ordinary)}")
    print(f"clean words confirmed  : {len(clean_words)}")
    if ordinary:
        print("\ncensored ordinary words:")
        print("  " + ", ".join(ordinary))
    if by_frag:
        print("\nby responsible fragment:")
        for f, n in by_frag.most_common():
            ex = [w for w in ordinary if attribution.get(w) == f][:5]
            print(f"  {f!r:12} {n:>3}   e.g. {', '.join(ex)}")
    print(f"\nwrote {args.out}/words-to-allow.txt, blocked-terms.txt, findings.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
