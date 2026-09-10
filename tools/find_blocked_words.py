#!/usr/bin/env python3
"""
find_blocked_words.py -- find the ordinary words a filter currently censors.

This answers the question that actually matters to players: which normal words
can I not type? It takes a filter word list and a body of legitimate vocabulary,
and returns every legitimate word the filter would flag, together with the
fragment responsible.

The output is directly deployable. Each line is a word that is demonstrably a
real word (it came from a dictionary, a gazetteer or a census file) and is
demonstrably flagged (the offending fragment is recorded next to it). Adding
them to an allowlist requires no judgement call and no code redesign.

    find_blocked_words.py --list filter.json \
        --vocab dict:/usr/share/dict/web2 --vocab names:propernouns.txt \
        --out words-to-unblock.txt --evidence evidence.csv

A light safety screen runs last so the output never asks anyone to unblock
actual profanity: the point is to rescue bystanders, not to punch holes in
moderation.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from safety_screen import is_slur, is_vulgar_derivation
except Exception:                                    # screen is optional
    def is_slur(w):
        return (False, "")

    def is_vulgar_derivation(w):
        return (False, "")

WORD_RE = re.compile(r"[^\W\d_][^\W\d_'\-]*", re.UNICODE)


def load_list(path):
    with open(path, encoding="utf-8") as fh:
        head = fh.read(1)
        fh.seek(0)
        if head == "[":
            return [t for t in json.load(fh) if isinstance(t, str) and t]
        out = []
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    rec = json.loads(line)
                    if "text" in rec:
                        out.append(rec["text"])
                except Exception:
                    out.append(line)
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--vocab", action="append", required=True,
                    help="label:path -- legitimate words, one per line or free text")
    ap.add_argument("--out", required=True)
    ap.add_argument("--evidence", default=None)
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=24)
    ap.add_argument("--ascii-only", action="store_true")
    ap.add_argument("--no-safety-screen", action="store_true")
    ap.add_argument("--flags", default=None,
                    help="JSON from a human review pass; those words are excluded too")
    args = ap.parse_args()

    entries = {e.lower() for e in load_list(args.list) if e}
    if args.ascii_only:
        entries = {e for e in entries if e.isascii() and e.isalpha()}
    by_len = collections.defaultdict(set)
    for e in entries:
        by_len[len(e)].add(e)
    lens = sorted(by_len)
    print(f"filter list: {len(entries):,} entries")

    vocab = {}
    for spec in args.vocab:
        label, _, path = spec.partition(":")
        if not os.path.exists(path):
            print(f"  (missing {path})", file=sys.stderr)
            continue
        n0 = len(vocab)
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("#"):
                    continue
                for w in WORD_RE.findall(line):
                    wl = w.lower()
                    if args.min_len <= len(wl) <= args.max_len:
                        vocab.setdefault(wl, label)
        print(f"  vocab {label:<12} +{len(vocab) - n0:,}")
    print(f"legitimate vocabulary: {len(vocab):,} words\n")

    # Fast path: Aho-Corasick finds every entry inside a word in one pass.
    # The pure-Python fallback below is kept so this tool has no hard
    # dependency -- it is ~100x slower but produces identical output.
    automaton = None
    try:
        import ahocorasick
        automaton = ahocorasick.Automaton()
        for e in entries:
            automaton.add_word(e, e)
        automaton.make_automaton()
        print("  (using pyahocorasick fast path)")
    except ImportError:
        print("  (pyahocorasick not installed -- using the slow fallback)")

    def offender(word):
        """The longest list entry occurring strictly inside `word`."""
        best = None
        if automaton is not None:
            for _, frag in automaton.iter(word):
                if len(frag) < len(word) and (best is None or len(frag) > len(best)):
                    best = frag
            return best
        for L in lens:
            if L >= len(word):
                break
            for i in range(len(word) - L + 1):
                frag = word[i:i + L]
                if frag in by_len[L] and (best is None or L > len(best)):
                    best = frag
        return best

    reviewed = set()
    if args.flags and os.path.exists(args.flags):
        reviewed = {r["word"].lower() for r in json.load(open(args.flags, encoding="utf-8"))}
        print(f"  human-review exclusions loaded: {len(reviewed):,}")

    blocked, skipped = [], []
    for w, source in vocab.items():
        if w in entries:
            continue                     # the whole word IS a filter entry
        frag = offender(w)
        if not frag:
            continue
        if w in reviewed:
            skipped.append((w, "human-review", ""))
            continue
        if not args.no_safety_screen:
            slur, root = is_slur(w)
            if slur:
                skipped.append((w, "slur", root))
                continue
            vulgar, why = is_vulgar_derivation(w)
            if vulgar:
                skipped.append((w, "vulgar", why))
                continue
        blocked.append((w, frag, source))

    blocked.sort()
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("# ORDINARY WORDS CURRENTLY CENSORED BY THIS FILTER\n"
                 "#\n"
                 "# Every word below is a real word taken from a dictionary, a\n"
                 "# gazetteer or a census file, and is flagged by the filter list\n"
                 "# because a shorter entry occurs INSIDE it. None of them are\n"
                 "# profanity. Adding them to an allowlist requires no judgement.\n"
                 "#\n"
                 f"# words: {len(blocked):,}\n"
                 f"# generated from a filter list of {len(entries):,} entries\n"
                 "#\n")
        for w, _, _ in blocked:
            fh.write(w + "\n")

    if args.evidence:
        with open(args.evidence, "w", newline="", encoding="utf-8") as fh:
            wr = csv.writer(fh)
            wr.writerow(["word", "blocked_by_fragment", "vocabulary_source"])
            wr.writerows(blocked)

    by_frag = collections.Counter(f for _, f, _ in blocked)
    by_src = collections.Counter(s for _, _, s in blocked)
    print(f"ORDINARY WORDS CURRENTLY CENSORED: {len(blocked):,}"
          f"   ({len(blocked) / max(len(vocab), 1) * 100:.1f}% of the vocabulary tested)")
    print(f"  by source: " + ", ".join(f"{k}={v:,}" for k, v in by_src.most_common()))
    if not args.no_safety_screen:
        print(f"  withheld by the safety screen (actual profanity): {len(skipped):,}")
    print(f"\n  worst fragments — each number is how many ordinary words it breaks:")
    for frag, n in by_frag.most_common(15):
        ex = [w for w, f, _ in blocked if f == frag][:3]
        print(f"    {frag!r:<10} {n:>7,}   e.g. {', '.join(ex)}")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
