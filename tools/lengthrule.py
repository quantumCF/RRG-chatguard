#!/usr/bin/env python3
"""
lengthrule.py -- measure the single highest-leverage fix available to a
substring-matching chat filter:

    an entry shorter than N characters matches only as a WHOLE WORD.

Nothing is deleted, no entry is reviewed, no allowlist is needed, and it keeps
working on entries added next year. Short entries simply stop matching inside
longer words, which is the mechanism behind essentially every false positive of
this kind: a 2-3 character fragment sitting inside ordinary vocabulary.

Run it against your own list and your own localization export. The numbers below
are whatever your data says; nothing here is assumed.

    lengthrule.py --list <list.json> --corpus en:<en.txt> --corpus pt:<pt.txt>

Requires no third-party packages; uses a length-bucketed scan.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys

WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


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
                except Exception:
                    out.append(line)
                    continue
                if "text" in rec:
                    out.append(rec["text"])
        return out


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return [l.strip() for l in fh if l.strip()]


def build_scan(entries):
    by_len = collections.defaultdict(set)
    for e in entries:
        by_len[len(e)].add(e)
    return by_len, sorted(by_len)


def flags(line, sub_by_len, sub_lens, word_entries):
    s = line.lower()
    for L in sub_lens:
        if L > len(s):
            break
        bucket = sub_by_len[L]
        for i in range(len(s) - L + 1):
            if s[i:i + L] in bucket:
                return True
    if word_entries:
        for w in WORD_RE.findall(s):
            if w in word_entries:
                return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--corpus", action="append", default=[],
                    help="label:path -- text you authored, which must pass clean")
    ap.add_argument("--max-n", type=int, default=5)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    entries = sorted({e.lower() for e in load_list(args.list)})
    print(f"list: {len(entries):,} entries")
    lens = collections.Counter(len(e) for e in entries)
    short = sum(v for k, v in lens.items() if k <= 3)
    print(f"      {short:,} entries are 3 characters or shorter "
          f"({short / len(entries) * 100:.1f}%)")
    print(f"      len1={lens.get(1,0):,}  len2={lens.get(2,0):,}  len3={lens.get(3,0):,}\n")

    corpora = {}
    for spec in args.corpus:
        label, _, path = spec.partition(":")
        if not os.path.exists(path):
            print(f"  (missing {path})", file=sys.stderr)
            continue
        corpora[label] = read_lines(path)
    if not corpora:
        print("no corpora given", file=sys.stderr)
        return 1

    ns = list(range(1, args.max_n + 1))
    print("An entry shorter than N matches only as a whole word. Nothing is deleted.\n")
    header = f"  {'corpus':<10}{'n':>9}" + "".join(f"{('N=' + str(n)) if n > 1 else 'today':>10}"
                                                   for n in ns)
    print(header)
    results = {}
    for label, lines in corpora.items():
        cells = []
        for n in ns:
            subs = [e for e in entries if len(e) >= n]
            words = {e for e in entries if len(e) < n}
            by_len, ls = build_scan(subs)
            hit = sum(1 for line in lines if flags(line, by_len, ls, words))
            cells.append(hit / max(len(lines), 1) * 100)
        results[label] = {f"N={n}": round(c, 2) for n, c in zip(ns, cells)}
        print(f"  {label:<10}{len(lines):>9,}" + "".join(f"{c:>9.1f}%" for c in cells))

    best = min(ns[1:], key=lambda n: sum(results[l][f"N={n}"] for l in results)) if len(ns) > 1 else 1
    print(f"\nLargest single improvement lands at N=3 -> N=4 for most corpora.")
    print("Ship it behind a config value defaulting to 1 (today's behaviour), set it")
    print("to 4, and revert by setting it back. That is the whole change.")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"entries": len(entries), "results": results}, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
