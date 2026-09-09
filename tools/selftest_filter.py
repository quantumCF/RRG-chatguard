#!/usr/bin/env python3
"""
selftest_filter.py -- a CI guard that makes this class of bug impossible to
ship again. Roughly 40 lines of logic, no dependencies, no chatguard required.

The invariant:

    No string the publisher itself authored may be flagged by the publisher's
    own chat filter.

That is unarguable. If your own item name, skill name, NPC name or UI string
trips your own filter, the filter is wrong -- there is no interpretation in
which "Freezing" is profanity. Wire this into CI next to the localization
export and the filter list, and the next person who adds a two-character entry
finds out in the build instead of from players.

    python3 selftest_filter.py --list filter.json --strings en_langs.txt
    -> exit 0 clean, exit 1 with the offending pairs listed

Optionally --allow exempts specific known-and-accepted collisions, so the test
can be adopted at whatever level is currently true and ratcheted down from
there rather than blocking the first build it touches.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys

WORD_RE = re.compile(r"[a-z][a-z']*")


def load_list(path):
    with open(path, encoding="utf-8") as fh:
        head = fh.read(1)
        fh.seek(0)
        if head == "[":
            return [t for t in json.load(fh) if isinstance(t, str)]
        out = []
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                rec = json.loads(line)
                if "text" in rec:
                    out.append(rec["text"])
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True, help="the chat filter word list")
    ap.add_argument("--strings", required=True, action="append",
                    help="your own authored strings, one per line")
    ap.add_argument("--allow", help="file of accepted collisions, one per line")
    ap.add_argument("--mode", choices=["substring", "word"], default="substring",
                    help="how your filter matches (default: substring)")
    ap.add_argument("--max-failures", type=int, default=0,
                    help="ratchet: tolerate up to N while you burn the list down")
    ap.add_argument("--show", type=int, default=25)
    args = ap.parse_args()

    terms = {t.lower() for t in load_list(args.list) if t.isascii() and t.isalpha()}
    allow = set()
    if args.allow:
        with open(args.allow, encoding="utf-8") as fh:
            allow = {l.strip().lower() for l in fh
                     if l.strip() and not l.startswith("#")}

    by_len = collections.defaultdict(set)
    for t in terms:
        by_len[len(t)].add(t)
    lens = sorted(by_len)

    def offending_term(text):
        s = text.lower()
        if args.mode == "word":
            for w in WORD_RE.findall(s):
                if w in terms and w not in allow:
                    return w
            return None
        for L in lens:
            if L > len(s):
                break
            for i in range(len(s) - L + 1):
                frag = s[i:i + L]
                if frag in by_len[L] and frag not in allow:
                    return frag
        return None

    total = 0
    failures = []
    for path in args.strings:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                total += 1
                hit = offending_term(line)
                if hit:
                    failures.append((line, hit))

    print(f"checked {total:,} authored strings against {len(terms):,} filter "
          f"entries ({args.mode} matching)")

    if not failures:
        print("PASS -- the filter flags none of your own content")
        return 0

    print(f"\nFAIL -- {len(failures):,} authored strings are flagged by your own "
          f"filter ({len(failures) / total * 100:.1f}%)\n")
    worst = collections.Counter(h for _, h in failures)
    for text, hit in failures[:args.show]:
        print(f"  {text[:56]:58} <- entry {hit!r}")
    if len(failures) > args.show:
        print(f"  ... and {len(failures) - args.show:,} more")
    print("\n  worst entries: " + ", ".join(
        f"{t!r}({n:,})" for t, n in worst.most_common(10)))

    if len(failures) <= args.max_failures:
        print(f"\n  within the configured ratchet of {args.max_failures:,}; "
              f"passing, but lower it once these are fixed")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
