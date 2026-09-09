#!/usr/bin/env python3
"""
blackbox.py -- identify what a chat filter actually blocks, without seeing its list.

Written because the list shipped inside a game client is not necessarily the
list the server enforces, and because that list changes over time. Anything
built on a stale copy is guesswork. This tool works from observed behaviour
only, so it stays correct whatever the server is really running.

Two capabilities:

  infer   Given observations of the form "this string was blocked / was fine",
          compute the substrings that could be responsible, eliminate the
          impossible ones, and report the smallest set of blocked terms that
          explains everything seen so far.

  design  Propose the next probes to type, chosen so each one eliminates as
          much of the remaining hypothesis space as possible. A handful of
          well-chosen probes pins an exact term; typing random words does not.

The core inference is one observation used twice:

    * If a string was NOT blocked, then NO substring of it is a blocked term.
      This is the powerful direction -- a single clean string can eliminate
      hundreds of candidates at once.
    * If a string WAS blocked, then AT LEAST ONE of its substrings is a term.

Together those turn probing into constraint solving rather than guesswork.

Usage:
    blackbox.py infer  --obs observations.jsonl
    blackbox.py design --obs observations.jsonl [--budget 12]

observations.jsonl:  {"text": "cucumber", "blocked": true}
                     {"text": "okay",     "blocked": false}
"""

from __future__ import annotations

import argparse
import collections
import json
import string
import sys

MIN_LEN = 2
MAX_LEN = 12

# Words so common that if any substring of them were a blocked term, the game
# would be visibly unusable and the player would have said so. Treating them as
# clean observations is an ASSUMPTION, but a well-founded one, and it removes
# absurd hypotheses like "be" or "er" that a pure hitting-set search will
# otherwise prefer simply because they are short and appear everywhere.
# Disable with --no-assume-common if you want the raw hypothesis space.
COMMON = """
a an the and or but if then than that this these those there here it its is are
was were be been being am do does did done doing have has had having will would
can could should shall may might must not no yes ok okay
i you he she we they me him her us them my your his our their mine yours
of in on at to from with without by for about into over under up down out off
again once more most some any all each every few many much other another same
what which who whom whose when where why how
go goes went going come comes came get gets got give gives gave take takes took
make makes made see sees saw look looks looked want wants wanted need needs
say says said tell tells told ask asks asked know knows knew think thinks
use uses used find finds found work works worked play plays played
good bad best better worse great nice cool fine okay sure right wrong true false
new old first last long short high low big small large little
time day days week month year today tomorrow yesterday now soon later never always
one two three four five six seven eight nine ten hundred thousand
hello hi hey thanks thank please sorry welcome bye goodbye congrats
buy buys sell sells selling trade trades price cheap cost free
party guild team group friend friends member members player players
level up quest quests item items gear weapon armor skill skills
help helps helping join joins joined leave leaves left start starts stop stops
where when what how why who anyone someone everyone nobody
lets let us we our been being have has
"""


def common_words():
    return {w for w in COMMON.split() if len(w) >= 2}



def substrings(s, lo=MIN_LEN, hi=MAX_LEN):
    s = s.lower()
    out = set()
    for L in range(lo, min(hi, len(s)) + 1):
        for i in range(len(s) - L + 1):
            out.add(s[i:i + L])
    return out


def load_obs(path):
    obs = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            rec = json.loads(line)
            obs.append((rec["text"], bool(rec["blocked"])))
    return obs


def analyse(obs, assume_common=True):
    """Return (candidates_per_blocked, eliminated, unexplained)."""
    clean = set()
    for text, blocked in obs:
        if not blocked:
            clean |= substrings(text)
    if assume_common:
        for w in common_words():
            clean |= substrings(w)

    per_blocked = {}
    unexplained = []
    for text, blocked in obs:
        if not blocked:
            continue
        cands = substrings(text) - clean
        per_blocked[text] = cands
        if not cands:
            unexplained.append(text)
    return per_blocked, clean, unexplained


def minimal_explanation(per_blocked):
    """
    Smallest set of terms explaining every blocked observation.

    Greedy hitting set: repeatedly take the candidate that explains the most
    still-unexplained blocked strings. Ties break toward the SHORTER candidate,
    because short entries are both likelier in these lists and the ones that do
    the damage.
    """
    remaining = dict(per_blocked)
    chosen = []
    while remaining:
        freq = collections.Counter()
        for cands in remaining.values():
            for c in cands:
                freq[c] += 1
        if not freq:
            break
        best = max(freq.items(), key=lambda kv: (kv[1], -len(kv[0])))[0]
        chosen.append(best)
        remaining = {k: v for k, v in remaining.items() if best not in v}
    return chosen


def cmd_infer(args):
    obs = load_obs(args.obs)
    per_blocked, clean, unexplained = analyse(
        obs, assume_common=not args.no_assume_common)
    nb = sum(1 for _, b in obs if b)
    print(f"observations: {len(obs)}  ({nb} blocked, {len(obs) - nb} clean)")
    print(f"substrings eliminated as impossible: {len(clean):,}"
          + ("" if args.no_assume_common else "  (incl. common-word assumption)"))

    if unexplained:
        print("\nCONTRADICTION -- these were blocked but every substring of them "
              "also appears in something that was NOT blocked:")
        for t in unexplained:
            print(f"    {t!r}")
        print("  The filter is therefore not pure substring matching on a fixed "
              "list.\n  Likely causes: normalization before matching, a fuzzy or "
              "phonetic rule,\n  a rule on the whole string, or the list changed "
              "between the two probes.")

    print("\nper blocked string, surviving candidate terms:")
    for text, cands in sorted(per_blocked.items(), key=lambda kv: len(kv[1])):
        short = sorted(cands, key=lambda c: (len(c), c))[:12]
        print(f"  {text!r:16} {len(cands):>5} candidates   shortest: "
              + ", ".join(repr(c) for c in short))

    chosen = minimal_explanation(per_blocked)
    print(f"\nSMALLEST TERM SET EXPLAINING EVERYTHING SEEN ({len(chosen)}):")
    for c in chosen:
        covers = [t for t, cd in per_blocked.items() if c in cd]
        print(f"  {c!r:14} explains {covers}")
    print("\n  (smallest, not proven -- run `design` for probes that discriminate)")
    return 0


def cmd_design(args):
    obs = load_obs(args.obs)
    per_blocked, clean, unexplained = analyse(
        obs, assume_common=not args.no_assume_common)
    if not per_blocked:
        print("no blocked observations yet; nothing to narrow")
        return 0

    # Rank candidates by how many blocked strings they could explain. Probing a
    # high-frequency candidate is worth the most: a clean result kills it for
    # every string at once, a blocked result nearly confirms it.
    freq = collections.Counter()
    for cands in per_blocked.values():
        for c in cands:
            freq[c] += 1

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))
    seen_probe = set()
    probes = []
    filler = "qzjv"          # letters unlikely to collide with anything real

    for cand, n in ranked:
        if len(probes) >= args.budget:
            break
        if cand in seen_probe:
            continue
        seen_probe.add(cand)
        # A carrier that contains the candidate and as little else as possible.
        carrier = f"{filler[:2]}{cand}{filler[2:]}"
        probes.append((carrier, cand, n))

    print("TYPE THESE, IN ORDER, AND RECORD blocked / not blocked")
    print("Each is a nonsense carrier around one suspect fragment, so a block "
          "means\nthe fragment itself is a term rather than anything around it.\n")
    print(f"  {'probe':<20}{'tests':<14}{'would explain'}")
    for carrier, cand, n in probes:
        print(f"  {carrier:<20}{cand!r:<14}{n} blocked observation(s)")

    print("\nalso worth typing, to bound the mechanism:")
    extra = [
        ("cum", "is the bare fragment itself a term?"),
        ("qzcumqz", "same fragment, nonsense carrier"),
        ("kk", "two -- does it take three to fire?"),
        ("kkk", "three"),
        ("kkkk", "four"),
        ("c u c u m b e r", "does spacing evade it?"),
        ("cucumb3r", "does leetspeak evade it?"),
        ("ｃｕｃｕｍｂｅｒ", "does full-width evade it?"),
        ("CUCUMBER", "is it case sensitive?"),
    ]
    for t, why in extra:
        print(f"  {t:<20}{why}")

    print("\nappend results to the observations file as:")
    print('  {"text": "qzcumqz", "blocked": true}')
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("infer")
    p1.add_argument("--obs", required=True)
    p1.add_argument("--no-assume-common", action="store_true",
                    help="do not treat very common English words as clean")
    p1.set_defaults(fn=cmd_infer)
    p2 = sub.add_parser("design")
    p2.add_argument("--obs", required=True)
    p2.add_argument("--no-assume-common", action="store_true",
                    help="do not treat very common English words as clean")
    p2.add_argument("--budget", type=int, default=12)
    p2.set_defaults(fn=cmd_design)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
