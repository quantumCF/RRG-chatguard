#!/usr/bin/env python3
"""
audit.py -- measure any blocklist against any corpus, and compare it to chatguard.

This is the tool that turns "the filter feels bad" into numbers a reviewer can
check. It reports both failure directions, because a blocklist typically fails
in both at once:

    over-blocking   legitimate text that gets censored   (false positives)
    under-blocking  obfuscated abuse that sails through  (false negatives)

Usage:
    audit.py --list <terms.json> --corpus <file> [--corpus ...] [--json out.json]

--list accepts a JSON array of strings (a raw blocklist) OR a .jsonl term table
in chatguard format. Corpora are newline-delimited text, one candidate per line.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "impl", "python"))
from chatguard import ChatGuard, MatchMode, Term, Tier  # noqa: E402


# --------------------------------------------------------------------------
# the two baselines we are replacing
# --------------------------------------------------------------------------

class SubstringBaseline:
    """`if term in text` over the whole list. The classic broken filter."""

    name = "blocklist / substring"

    def __init__(self, terms):
        self.by_len = collections.defaultdict(set)
        for t in terms:
            self.by_len[len(t)].add(t)
        self.lens = sorted(self.by_len)

    def hits(self, text):
        s = text.lower()
        out = set()
        for L in self.lens:
            if L > len(s):
                break
            for i in range(len(s) - L + 1):
                frag = s[i:i + L]
                if frag in self.by_len[L]:
                    out.add(frag)
        return out

    def flags(self, text):
        return bool(self.hits(text))


class WholeWordBaseline:
    """The charitable reading: the same list, but only on word boundaries."""

    name = "blocklist / whole-word"
    _WORD = re.compile(r"[a-z0-9']+")

    def __init__(self, terms):
        self.terms = set(terms)

    def hits(self, text):
        return {w for w in self._WORD.findall(text.lower()) if w in self.terms}

    def flags(self, text):
        return bool(self.hits(text))


class GuardSameVocab:
    """
    chatguard running the AUDITED list as its own vocabulary.

    This is the honest comparison. Giving chatguard a different (smaller) word
    list would flatter it for reasons that have nothing to do with the engine.
    Here both arms know exactly the same words, so every difference is
    attributable to matching strategy alone: word boundaries, the rescue
    allowlist, and normalization.
    """

    name = "chatguard / same vocab"

    def __init__(self, terms, allow, surface="public"):
        table = [Term(t, Tier.STRONG, MatchMode.WORD) for t in terms]
        self.g = ChatGuard(table, allow)
        self.surface = surface

    def flags(self, text):
        return self.g.check(text, surface=self.surface)


class GuardAdapter:
    name = "chatguard"

    def __init__(self, guard, surface="public", locale="en"):
        self.g = guard
        self.surface = surface
        self.locale = locale

    def flags(self, text):
        return self.g.check(text, surface=self.surface, locale=self.locale)


# --------------------------------------------------------------------------
# corpora
# --------------------------------------------------------------------------

EVASIONS = [
    ("plain", lambda w: w),
    ("spaced", lambda w: " ".join(w)),
    ("dotted", lambda w: ".".join(w)),
    ("dashed", lambda w: "-".join(w)),
    ("repeat", lambda w: w[0] + w[1] * 3 + w[2:]),
    ("leet", lambda w: w.replace("a", "4").replace("e", "3")
                        .replace("i", "1").replace("o", "0").replace("s", "5")),
    ("fullwidth", lambda w: "".join(chr(ord(c) - 0x21 + 0xFF01)
                                    if "!" <= c <= "~" else c for c in w)),
    ("cyrillic", lambda w: w.replace("a", "а").replace("e", "е")
                            .replace("o", "о").replace("c", "с")),
    ("swap", lambda w: w[:1] + "v" + w[2:] if len(w) > 2 else w),
    ("padded", lambda w: w + w[-1] * 2),
]


def build_evasion_corpus(terms):
    """Generate obfuscated variants of real terms. Measures under-blocking."""
    rows = []
    for t in terms:
        if len(t) < 4:
            continue
        for label, fn in EVASIONS:
            try:
                rows.append((label, fn(t)))
            except Exception:
                pass
    return rows


def load_list(path):
    with open(path, encoding="utf-8") as fh:
        head = fh.read(1)
        fh.seek(0)
        if head == "[":
            data = json.load(fh)
            return [t.lower() for t in data if isinstance(t, str)]
        terms = []
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rec = json.loads(line)
            if "text" in rec:
                terms.append(rec["text"].lower())
        return terms


def load_terms_table(path):
    terms = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rec = json.loads(line)
            if "text" not in rec:
                continue
            terms.append(Term(
                text=rec["text"].lower(),
                tier=Tier(rec.get("tier", 2)),
                mode=rec.get("mode", MatchMode.WORD),
                locales=tuple(rec["locales"]) if rec.get("locales") else None,
            ))
    return terms


def load_allow(paths):
    out = []
    for p in paths:
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as fh:
            out.extend(l.strip().lower() for l in fh
                       if l.strip() and not l.startswith("#"))
    return out


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", required=True,
                    help="the blocklist under audit (JSON array or .jsonl)")
    ap.add_argument("--corpus", action="append", default=[],
                    help="newline-delimited text that SHOULD pass clean")
    ap.add_argument("--ascii-only", action="store_true",
                    help="restrict the audited list to ASCII alphabetic terms")
    ap.add_argument("--json", help="write machine-readable results here")
    args = ap.parse_args()

    root = os.path.join(os.path.dirname(__file__), "..")
    audited = load_list(args.list)
    if args.ascii_only:
        audited = [t for t in audited if t.isascii() and t.isalpha()]

    guard = ChatGuard(
        load_terms_table(os.path.join(root, "data/lexicon/en-terms.jsonl")),
        load_allow([os.path.join(root, "data/lexicon/en-allow.txt"),
                    os.path.join(root, "data/domain/game-terms.txt")]),
    )

    allow = load_allow([os.path.join(root, "data/lexicon/en-allow.txt"),
                        os.path.join(root, "data/domain/game-terms.txt")])
    engines = [SubstringBaseline(audited), WholeWordBaseline(audited),
               GuardSameVocab(audited, allow), GuardAdapter(guard)]

    results = {"list_size": len(audited), "corpora": {}, "evasion": {}}

    print(f"\naudited list: {len(audited):,} terms")
    print(f"chatguard   : {len(guard.automaton):,} terms, "
          f"{len(guard.allow):,} allowlisted words\n")

    # ---- over-blocking ----
    print("OVER-BLOCKING  (lines that SHOULD pass clean but get flagged)")
    print(f"  {'corpus':<24}{'n':>8}" + "".join(f"{e.name:>24}" for e in engines))
    for path in args.corpus:
        if not os.path.exists(path):
            print(f"  {os.path.basename(path):<24}  MISSING")
            continue
        lines = [l.rstrip("\n") for l in open(path, encoding="utf-8",
                                              errors="replace") if l.strip()]
        row = []
        for e in engines:
            n = sum(1 for l in lines if e.flags(l))
            row.append((n, n / len(lines) * 100 if lines else 0.0))
        results["corpora"][os.path.basename(path)] = {
            e.name: {"flagged": r[0], "pct": round(r[1], 2)}
            for e, r in zip(engines, row)
        }
        cells = "".join(f"{n:>12,} ({p:5.1f}%)" for n, p in row)
        print(f"  {os.path.basename(path):<24}{len(lines):>8,}{cells}")

    # ---- under-blocking ----
    real = [t.text for t in guard.terms if t.tier >= Tier.STRONG and len(t.text) >= 4]
    corpus = build_evasion_corpus(real)
    print(f"\nUNDER-BLOCKING  (obfuscated abuse that SHOULD be caught, n={len(corpus)})")
    print(f"  {'variant':<24}" + "".join(f"{e.name:>24}" for e in engines))
    by_variant = collections.defaultdict(list)
    for label, text in corpus:
        by_variant[label].append(text)
    for label, texts in by_variant.items():
        cells = []
        for e in engines:
            n = sum(1 for t in texts if e.flags(t))
            cells.append((n, n / len(texts) * 100))
        results["evasion"][label] = {
            e.name: {"caught": c[0], "pct": round(c[1], 1)}
            for e, c in zip(engines, cells)
        }
        print(f"  {label:<24}" + "".join(f"{n:>12,} ({p:5.1f}%)" for n, p in cells))
    totals = []
    for e in engines:
        n = sum(1 for _, t in corpus if e.flags(t))
        totals.append((n, n / len(corpus) * 100))
    print(f"  {'ALL':<24}" + "".join(f"{n:>12,} ({p:5.1f}%)" for n, p in totals))
    results["evasion_total"] = {
        e.name: {"caught": t[0], "pct": round(t[1], 1)}
        for e, t in zip(engines, totals)
    }

    # ---- latency ----
    sample = ["hello there, selling +7 gear in prontera, whisper me"] * 2000
    print("\nLATENCY  (per message, single core)")
    for e in engines:
        t0 = time.perf_counter()
        for s in sample:
            e.flags(s)
        dt = (time.perf_counter() - t0) / len(sample) * 1e6
        results.setdefault("latency_us", {})[e.name] = round(dt, 1)
        print(f"  {e.name:<24}{dt:>9.1f} us")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
