#!/usr/bin/env python3
"""
build_lexicon.py -- generate the domain allowlist from a title's OWN localization.

This is the step that makes the filter fit the game rather than fighting it.
Item names, skill names, NPC names, map names and UI strings are text the
publisher authored; nothing in them should ever be censored. Extracting them
into an allowlist means the filter can never again mangle the game's own nouns.

It is also the answer to "we don't trust an outsider's judgement about which
words are acceptable" -- nobody's judgement is involved. The allowlist is
derived mechanically from the publisher's own shipped strings.

Two products per locale:

    <loc>-allow.txt     word tokens (Latin scripts: space-delimited)
    <loc>-phrases.txt   whole name phrases and CJK n-grams (script-agnostic;
                        these shelter hits that no token rule could reach,
                        which is the only way to rescue Chinese, Japanese and
                        Thai text where words are not space-separated)

Usage:
    build_lexicon.py --locale en --strings en_langs.txt --out data/domain/
    build_lexicon.py --locale cn --strings cn_langs.txt --out data/domain/ --cjk
"""

from __future__ import annotations

import argparse
import collections
import os
import re
import sys

WORD_RE = re.compile(r"[^\W\d_]{2,}", re.UNICODE)
CJK_RE = re.compile(r"[㐀-䶿一-鿿぀-ヿ฀-๿]+")


def read_strings(paths):
    out = []
    for p in paths:
        with open(p, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", required=True)
    ap.add_argument("--strings", required=True, action="append")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cjk", action="store_true",
                    help="also emit CJK n-grams (needed for zh/ja/th)")
    ap.add_argument("--min-ngram", type=int, default=2)
    ap.add_argument("--max-ngram", type=int, default=4)
    ap.add_argument("--max-phrases", type=int, default=200000)
    args = ap.parse_args()

    lines = read_strings(args.strings)
    if not lines:
        print("no strings read", file=sys.stderr)
        return 1

    tokens = collections.Counter()
    phrases = set()
    for line in lines:
        phrases.add(line)
        for w in WORD_RE.findall(line):
            if len(w) >= 2:
                tokens[w.lower()] += 1

    ngrams = collections.Counter()
    if args.cjk:
        # Every contiguous run of CJK/Thai characters is a candidate phrase, and
        # every n-gram inside it is a candidate shelter. A single blocked
        # character inside an ordinary word is exactly the CJK form of the
        # Scunthorpe problem, and only a phrase-level shelter can rescue it.
        for line in lines:
            for run in CJK_RE.findall(line):
                for n in range(args.min_ngram, args.max_ngram + 1):
                    for i in range(len(run) - n + 1):
                        ngrams[run[i:i + n]] += 1

    os.makedirs(args.out, exist_ok=True)
    tok_path = os.path.join(args.out, f"{args.locale}-allow.txt")
    with open(tok_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Domain word lexicon for locale '{args.locale}'.\n"
                 f"# AUTO-GENERATED from {len(lines):,} of the title's own strings.\n"
                 f"# These are the game's own nouns. They must never be censored.\n")
        for w in sorted(tokens):
            fh.write(w + "\n")

    phr_path = os.path.join(args.out, f"{args.locale}-phrases.txt")
    items = sorted(phrases)
    if args.cjk:
        # Keep n-grams seen more than once: a repeated n-gram is a real word or
        # a real compound, a hapax is usually an arbitrary slice.
        items += [g for g, c in ngrams.items() if c > 1]
    items = items[:args.max_phrases]
    with open(phr_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Domain phrase lexicon for locale '{args.locale}'.\n"
                 f"# Shelters: a blocked term occurring strictly inside one of\n"
                 f"# these is a fragment of the game's own content, not abuse.\n")
        for p in items:
            if p.strip():
                fh.write(p.strip() + "\n")

    print(f"  {args.locale}: {len(tokens):,} tokens -> {os.path.basename(tok_path)}")
    print(f"  {args.locale}: {len(items):,} phrases"
          + (f" (incl. {sum(1 for g, c in ngrams.items() if c > 1):,} CJK n-grams)"
             if args.cjk else "")
          + f" -> {os.path.basename(phr_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
