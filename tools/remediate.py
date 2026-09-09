#!/usr/bin/env python3
"""
remediate.py -- rank blocklist entries by how much damage each one causes, and
emit a decision-ready remediation table.

The premise: in a list of ~100k entries, false positives are not spread evenly.
A tiny minority of entries cause nearly all of them. Finding that minority turns
"your filter is bad" into "change these N rows", which is a ticket someone can
actually action without adopting anything.

For each entry we compute a blast radius: the number of legitimate strings it
breaks, split into

    game    the publisher's own localized content (unambiguous false positives,
            because they authored the text themselves)
    dict    ordinary English dictionary words

and then a recommended action:

    DELETE        an ordinary English word; blocking it is simply wrong
    SCOPE:<loc>   meaningful only in one market -- keep it, restrict it
    WHOLE-WORD    fine as a word, catastrophic as a substring
    KEEP          no measured false positives

Usage:
    remediate.py --list live.json --game-corpus names.txt [--dict /usr/share/dict/words]
                 --out remediation.csv
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import os
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


def load_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return [l.strip() for l in fh if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True)
    ap.add_argument("--game-corpus", action="append", default=[])
    ap.add_argument("--dict", default="/usr/share/dict/words")
    ap.add_argument("--out", default="remediation.csv")
    ap.add_argument("--top", type=int, default=60)
    args = ap.parse_args()

    raw = load_list(args.list)
    terms = sorted({t.lower() for t in raw if t.isascii() and t.isalpha()})
    tset = set(terms)
    by_len = collections.defaultdict(set)
    for t in terms:
        by_len[len(t)].add(t)
    lens = sorted(by_len)

    def substr_hits(word):
        """Every list entry occurring inside `word`, excluding word == entry."""
        out = set()
        for L in lens:
            if L > len(word):
                break
            for i in range(len(word) - L + 1):
                frag = word[i:i + L]
                if frag in by_len[L] and frag != word:
                    out.add(frag)
        return out

    # ---- blast radius over the publisher's own content ----
    game_break = collections.Counter()
    game_example = {}
    game_tokens = collections.Counter()
    for path in args.game_corpus:
        if not os.path.exists(path):
            print(f"  (missing corpus {path})", file=sys.stderr)
            continue
        for line in load_lines(path):
            for w in WORD_RE.findall(line.lower()):
                game_tokens[w] += 1
    for w, freq in game_tokens.items():
        if w in tset:
            continue                      # the whole word IS an entry: §2 below
        for frag in substr_hits(w):
            game_break[frag] += 1
            game_example.setdefault(frag, w)

    # ---- blast radius over the English dictionary ----
    dict_break = collections.Counter()
    dict_example = {}
    if os.path.exists(args.dict):
        for w in load_lines(args.dict):
            w = w.lower()
            if not w.isalpha() or len(w) < 3 or w in tset:
                continue
            for frag in substr_hits(w):
                dict_break[frag] += 1
                dict_example.setdefault(frag, w)

    # ---- entries that are themselves ordinary words ----
    english = set()
    if os.path.exists(args.dict):
        english = {w.strip().lower() for w in load_lines(args.dict)}
    own_word = sorted(t for t in terms if t in english)
    game_word = sorted(t for t in terms if game_tokens.get(t, 0) > 0)

    # ---- recommend ----
    rows = []
    for t in terms:
        g, d = game_break.get(t, 0), dict_break.get(t, 0)
        total = g + d
        # Order matters. Nothing is recommended for deletion unless the
        # publisher's OWN text uses the word -- that justification cannot be
        # argued with, and it means no recommendation here asks them to give up
        # coverage they deliberately wanted.
        if len(t) <= 2:
            action = "SCOPE:zh"
            why = ("1-2 characters: a romanized abbreviation. Meaningful in its "
                   "origin market, unusable as a substring in Latin text. "
                   "Keep it, restrict it to that locale.")
        elif t in game_tokens:
            action = "DELETE"
            why = (f"the game's own localized text uses this as a word "
                   f"({game_tokens[t]:,} occurrences)")
        elif t in english and total > 0:
            action = "WHOLE-WORD"
            why = "an ordinary English word; keep the word, stop the substring"
        elif total > 0:
            action = "WHOLE-WORD"
            why = f"substring false positives ({total:,} legitimate strings)"
        else:
            action, why = "KEEP", "no measured false positives"
        rows.append({
            "entry": t, "length": len(t), "game_strings_broken": g,
            "dict_words_broken": d, "blast_radius": total,
            "example_game": game_example.get(t, ""),
            "example_dict": dict_example.get(t, ""),
            "recommended_action": action, "rationale": why,
        })

    rows.sort(key=lambda r: (-r["blast_radius"], r["entry"]))
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- the Pareto result: how few rows carry the damage ----
    total_break = sum(r["blast_radius"] for r in rows)
    actionable = [r for r in rows if r["recommended_action"] != "KEEP"]
    print(f"\nlist: {len(terms):,} ASCII entries")
    print(f"entries with at least one measured false positive: "
          f"{sum(1 for r in rows if r['blast_radius'] > 0):,}")
    print(f"entries that are themselves ordinary words: "
          f"{len(own_word):,} English, {len(game_word):,} in the game's own text")
    print(f"\ntotal false-positive incidents attributable: {total_break:,}")

    cum = 0
    print("\nPARETO -- fixing the worst N entries removes this share of the damage")
    for n in (5, 10, 20, 40, 60, 100, 200):
        if n > len(rows):
            break
        cum = sum(r["blast_radius"] for r in rows[:n])
        print(f"  top {n:>4} entries  ->  {cum:>9,} of {total_break:,} "
              f"({cum / total_break * 100:5.1f}%)")

    print(f"\nrecommended actions: " + ", ".join(
        f"{k}={v}" for k, v in
        collections.Counter(r["recommended_action"] for r in rows).most_common()))
    print(f"\nwrote {args.out}  ({len(actionable):,} actionable rows)")

    # ---- simulate: apply the top-N recommendations, re-measure ----
    print("\nSIMULATION -- false positives on the publisher's own content")
    game_lines = []
    for path in args.game_corpus:
        if os.path.exists(path):
            game_lines.extend(load_lines(path))

    def fp_rate(active_sub, active_word):
        """active_sub: entries still matched as substrings. active_word: as words."""
        bl = collections.defaultdict(set)
        for t in active_sub:
            bl[len(t)].add(t)
        ls = sorted(bl)
        n = 0
        for line in game_lines:
            s = line.lower()
            hit = False
            for L in ls:
                if L > len(s):
                    break
                for i in range(len(s) - L + 1):
                    if s[i:i + L] in bl[L]:
                        hit = True
                        break
                if hit:
                    break
            if not hit and active_word:
                if any(w in active_word for w in WORD_RE.findall(s)):
                    hit = True
            if hit:
                n += 1
        return n

    base = fp_rate(set(terms), set())
    print(f"  {'today (every entry, substring)':<44}"
          f"{base:>8,} / {len(game_lines):,} ({base / len(game_lines) * 100:5.1f}%)")
    for n in (5, 10, 20, 40):
        fix = {r["entry"] for r in rows[:n] if r["recommended_action"] != "KEEP"}
        scoped = {r["entry"] for r in rows[:n] if r["recommended_action"] == "SCOPE:zh"}
        deleted = {r["entry"] for r in rows[:n] if r["recommended_action"] == "DELETE"}
        as_word = fix - scoped - deleted
        after = fp_rate(set(terms) - fix, as_word)
        print(f"  {'after applying the top ' + str(n) + ' rows':<44}"
              f"{after:>8,} / {len(game_lines):,} ({after / len(game_lines) * 100:5.1f}%)"
              f"   -{(base - after) / base * 100:4.1f}%")

    print(f"\nWORST {min(args.top, 25)} ENTRIES")
    print(f"  {'entry':<12}{'len':>4}{'game':>8}{'dict':>8}  {'action':<12} example")
    for r in rows[:min(args.top, 25)]:
        ex = r["example_game"] or r["example_dict"]
        print(f"  {r['entry']:<12}{r['length']:>4}{r['game_strings_broken']:>8,}"
              f"{r['dict_words_broken']:>8,}  {r['recommended_action']:<12} {ex}")


if __name__ == "__main__":
    main()
