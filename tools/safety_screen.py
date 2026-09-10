#!/usr/bin/env python3
"""
safety_screen.py -- remove anything from an allowlist that must never be on one.

An allowlist is a list of words the filter will NEVER censor. That makes a bad
entry far more dangerous than a bad blocklist entry: a slur that reaches this
file becomes permanently uncensorable. This screen therefore errs toward
removal, and it treats two classes of term very differently.

  SLUR roots      remove any word CONTAINING the root.
                  Racial, ethnic and identity slurs have almost no legitimate
                  host words, and the few archaic ones ("niggerfish", a real
                  1913 dictionary entry for a fish) are worth nothing in chat
                  while handing players a free pass token. Containment is the
                  right test here.

  VULGAR roots    remove only the bare word and its derivations.
                  These DO have innocent hosts, and rescuing those hosts is the
                  entire point of the allowlist. "cum" must go; "cucumber",
                  "accumulate" and "documentation" must stay. "ass" must go;
                  "assassin", "class" and "Cassandra" must stay.

The distinction is the whole design. Applying containment to vulgar roots would
delete the words we are trying to protect; applying derivation-only rules to
slurs would leave slurs on the list.

Usage:
    safety_screen.py --allowlist deploy/allowlist-en.txt \
                     --flags audit-flags.json --out deploy/allowlist-en.txt
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# TIER 1 -- containment. Any word CONTAINING these is removed.
# Restricted to roots with no innocent English host word. Verified against the
# full dictionary: adding a root here that appears inside an ordinary word (as
# "coon" does inside raccoon, cocoon and tycoon) would exclude that word from
# the allowlist and therefore leave it censored -- the exact bug being fixed.
SLUR_ROOTS = [
    "nigger", "nigga", "niggr", "nigre",
    "kike", "gook", "wetback", "beaner", "jigaboo", "pickaninny",
    "faggot", "tranny", "shemale", "raghead", "towelhead", "redskin",
    "bhangi", "porn", "pedophil", "paedophil", "necrophil",
]

# TIER 2 -- slurs that DO have innocent host words. Screened only as the bare
# word or a close derivation, so the hosts survive:
#   coon    -> raccoon, cocoon, tycoon        kraut -> sauerkraut
#   squaw   -> squawk                         chink -> chink of light
#   gypsy   -> gypsum is unaffected           fag   -> fagotto
AMBIGUOUS_SLURS = [
    "coon", "wop", "dago", "kraut", "gyppo", "gypsy", "squaw", "injun",
    "chink", "chinky", "spick", "spic", "fag", "fagot", "sambo", "chamar",
    "nazi", "hitler", "klan", "kkk", "retard", "bestial",
]

# Derivation test. Only the bare word and close derivations are removed.
VULGAR_ROOTS = [
    "ass", "arse", "cum", "clit", "cock", "cunt", "dick", "fuck", "shit",
    "piss", "prick", "pussy", "puss", "slut", "twat", "whore", "hoe",
    "tit", "titty", "tittie", "boob", "penis", "vagina", "anal", "anus",
    "rape", "raper", "raping", "rapist", "molest", "incest", "pedo",
    "smut", "horny", "orgasm", "cumshot", "blowjob", "handjob",
    "turd", "fart", "bollock", "wank", "bugger", "bastard", "damn",
    "prostitute", "hooker", "nympho", "sodom", "felch", "queef",
]

SUFFIXES = ["", "s", "es", "ed", "ing", "er", "ers", "y", "ie", "ies", "ier",
            "iest", "ty", "ter", "ters", "ness", "ish", "ist", "ism", "dom",
            "like", "hood", "ship", "ery", "ary", "ous", "ful", "less",
            "head", "heads", "hole", "holes", "face", "faces", "bag", "bags",
            "wad", "wads", "tard", "tards", "stain", "sucker", "monger",
            "master", "masterly", "mastery", "monging", "son", "ant", "ard",
            "ate", "ation", "ish", "ishly", "ishness", "ikin", "a", "o"]

PREFIXES = ["", "un", "over", "under", "re", "de", "dis", "bull", "horse",
            "dog", "jack", "mother", "dumb", "dip", "ass", "shit", "cover",
            "philo", "un", "in"]


def is_slur(word):
    w = word.lower()
    for root in SLUR_ROOTS:
        if root in w:
            return True, root
    return False, ""


# Precomputed once at import. Building this eagerly turns the derivation test
# from O(roots x prefixes x suffixes) per word into a single set lookup -- the
# difference between scanning a 234,000-word dictionary in a second and in
# twenty billion string concatenations.
_DERIVATIONS = {}
for _root in VULGAR_ROOTS + AMBIGUOUS_SLURS:
    _DERIVATIONS[_root] = _root
    for _pre in PREFIXES:
        for _suf in SUFFIXES:
            _DERIVATIONS.setdefault(_pre + _root + _suf,
                                    f"{_pre}+{_root}+{_suf}".strip("+"))


def is_vulgar_derivation(word):
    w = word.lower()
    why = _DERIVATIONS.get(w)
    return (True, why) if why else (False, "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--allowlist", required=True)
    ap.add_argument("--flags", default=None,
                    help="JSON list of {word, severity} from a review pass")
    ap.add_argument("--out", required=True)
    ap.add_argument("--removed-out", default=None)
    ap.add_argument("--keep-borderline", action="store_true",
                    help="keep entries a reviewer marked 'borderline'")
    args = ap.parse_args()

    header, words = [], []
    with open(args.allowlist, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("#"):
                header.append(line)
            elif line.strip():
                words.append(line.strip().lower())

    reviewed = {}
    if args.flags and os.path.exists(args.flags):
        for rec in json.load(open(args.flags, encoding="utf-8")):
            sev = rec.get("severity", "should-remove")
            if sev == "borderline" and args.keep_borderline:
                continue
            reviewed[rec["word"].lower()] = (sev, rec.get("reason", ""))

    kept, removed = [], []
    for w in words:
        slur, root = is_slur(w)
        if slur:
            removed.append((w, "slur-containment", root))
            continue
        vulgar, why = is_vulgar_derivation(w)
        if vulgar:
            removed.append((w, "vulgar-derivation", why))
            continue
        if w in reviewed:
            sev, reason = reviewed[w]
            removed.append((w, f"reviewed:{sev}", reason[:80]))
            continue
        kept.append(w)

    with open(args.out, "w", encoding="utf-8") as fh:
        for h in header:
            if h.startswith("# entries:"):
                fh.write(f"# entries: {len(kept):,}\n")
            else:
                fh.write(h + "\n")
        fh.write(f"# safety screen: {len(removed):,} candidates removed "
                 f"(slur containment, vulgar derivation, human review)\n")
        for w in kept:
            fh.write(w + "\n")

    if args.removed_out:
        with open(args.removed_out, "w", encoding="utf-8") as fh:
            fh.write("# Removed by the safety screen. word <TAB> rule <TAB> detail\n")
            for w, rule, detail in sorted(removed):
                fh.write(f"{w}\t{rule}\t{detail}\n")

    by_rule = {}
    for _, rule, _ in removed:
        by_rule[rule.split(":")[0]] = by_rule.get(rule.split(":")[0], 0) + 1
    print(f"in:  {len(words):,}")
    print(f"out: {len(kept):,}   removed: {len(removed):,}")
    for r, n in sorted(by_rule.items(), key=lambda kv: -kv[1]):
        print(f"       {r:<22} {n:>6,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
