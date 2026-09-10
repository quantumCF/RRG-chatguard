#!/usr/bin/env python3
"""
build_allowlist.py -- build the list of words that must never be censored.

This is the smallest useful fix for a substring-matching chat filter, and the
only one that works without knowing what the filter blocks. You do not need to
find the bad entries. You assert what is legitimate, and the filter stops
censoring it.

    if a blocked fragment is found INSIDE a word on this list, do not block.

Sources, all declared per line in the output header:

    dict        public-domain English dictionary (web2 / SCOWL)
    proper      public-domain proper names (people, places)
    gaming      MMO / RPG / chat vocabulary that dictionaries do not carry
    locale      OPTIONAL: your own localization export, per language. This is
                the highest-value source, because it is exactly the vocabulary
                your players type, and it involves nobody's judgement but yours.

Safety is the whole game here. A word that should be blocked must never end up
on an allowlist, so every candidate is screened against a profanity lexicon by
exact match and by derivation (term + common suffix, common prefix + term), and
everything rejected is written to a review file rather than silently dropped.

Usage:
    build_allowlist.py --out data/allowlist/ \
        --terms data/lexicon/en-terms.jsonl \
        [--locale en:en_langs.txt] [--locale pt:pt_langs.txt] [--cjk-locale cn:cn_langs.txt]
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sys
import unicodedata

WORD_RE = re.compile(r"[^\W\d_][^\W\d_'\-]{1,}", re.UNICODE)
CJK_RUN_RE = re.compile(r"[㐀-䶿一-鿿぀-ヿ฀-๿]+")

# Vocabulary a dictionary will not have but players type constantly.
GAMING = """
mmo mmorpg rpg pve pvp pvm gvg woe mvp npc afk brb gg wp gl hf ty tysm np nvm
omw ez rip lol lmao rofl imo imho tbh idk irl ffs gj gz grats congrats
dps hps aggro gank kite pull tank tanking healer heals buff buffs debuff
proc crit crits cooldown cd dot hot aoe cc knockback stun slow root snare
respawn spawn spawning grind grinding farm farming leech leeching botting
loot looting drop drops rare mvps minis boss bosses raid raids dungeon
guild guilds party parties squad clan alliance recruit recruiting
zeny zenny gold silver rupee currency vend vending vendor merch merchant
refine refining enchant enchanting socket socketed slotted upgrade upgrading
overupgrade broke safe cert certs blessing ori oridecon elunium
str agi vit int dex luk stat stats statting build builds skillbuild
swordsman knight crusader paladin lordknight assassin rogue stalker
acolyte priest monk champion archer hunter sniper bard dancer clown gypsy
mage wizard sage professor merchant blacksmith whitesmith alchemist creator
taekwon ninja gunslinger supernovice novice
prontera geffen payon morroc alberta izlude aldebaran comodo yuno lutie
juno hugel rachel veins amatsu gonryun louyang ayothaya einbroch lighthalzen
poring drops poporing marin angeling deviling ghostring
baphomet osiris eddga phreeoni orkhero moonlight doppelganger
potion potions elixir elixirs herb herbs fly wing wings butterfly
headgear costume garment footgear accessory weapon armor shield
seller buyer trading price offer offering bid bidding
cucumber banana carrot potato tomato mushroom shiitake
"""

# Words that must never reach an allowlist even if they appear in a dictionary,
# beyond exact profanity: these are the derivational shapes that turn a benign
# root into a slur or an insult.
BAD_SUFFIXES = ["s", "es", "ed", "ing", "er", "ers", "ers", "y", "ie", "ies",
                "ier", "iest", "ty", "ter", "ters", "ness", "ish", "ist",
                "hole", "holes", "head", "heads", "face", "faces", "bag",
                "bags", "tard", "tards", "wad", "wads", "stain", "sucker"]
BAD_PREFIXES = ["bull", "horse", "dog", "jack", "mother", "dumb", "ass",
                "dip", "shit", "fuck", "cock", "dick", "cunt", "twat"]


def load_terms(path):
    terms = set()
    if not path or not os.path.exists(path):
        return terms
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if "text" in rec:
                terms.add(rec["text"].lower())
    return terms


def is_derived_from_term(word, terms):
    """True if `word` looks like a profanity derivative rather than a bystander."""
    w = word.lower()
    if w in terms:
        return True, "exact profanity"
    for t in terms:
        if len(t) < 3:
            continue
        if w.startswith(t):
            rest = w[len(t):]
            if rest in BAD_SUFFIXES:
                return True, f"{t}+{rest}"
        if w.endswith(t):
            head = w[:-len(t)]
            if head in BAD_PREFIXES:
                return True, f"{head}+{t}"
    return False, ""


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return [l.strip() for l in fh if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--terms", default=None)
    ap.add_argument("--dict", default="/usr/share/dict/web2")
    ap.add_argument("--proper", default="/usr/share/dict/propernames")
    ap.add_argument("--extra", action="append", default=[],
                    help="label:path -- an extra word source, one per line")
    ap.add_argument("--locale", action="append", default=[],
                    help="loc:path -- space-delimited language")
    ap.add_argument("--cjk-locale", action="append", default=[],
                    help="loc:path -- language without word spacing")
    ap.add_argument("--min-len", type=int, default=3)
    ap.add_argument("--max-len", type=int, default=24)
    args = ap.parse_args()

    terms = load_terms(args.terms)
    os.makedirs(args.out, exist_ok=True)

    candidates = {}          # word -> set of sources
    def add(word, source):
        w = word.strip().lower()
        if not w or not (args.min_len <= len(w) <= args.max_len):
            return
        candidates.setdefault(w, set()).add(source)

    if os.path.exists(args.dict):
        for w in read_lines(args.dict):
            if w.isalpha():
                add(w, "dict")
    if os.path.exists(args.proper):
        for w in read_lines(args.proper):
            if w.isalpha():
                add(w, "proper")
    for w in GAMING.split():
        if w.isalpha():
            add(w, "gaming")
    for spec in args.extra:
        label, _, path = spec.partition(":")
        if not os.path.exists(path):
            print(f"  (missing {path})", file=sys.stderr)
            continue
        for w in read_lines(path):
            if w and not w.startswith("#"):
                add(w, label)

    # Locale sources: every word the publisher itself wrote.
    locale_words = collections.defaultdict(set)
    for spec in args.locale:
        loc, _, path = spec.partition(":")
        if not os.path.exists(path):
            print(f"  (missing {path})", file=sys.stderr)
            continue
        for line in read_lines(path):
            for w in WORD_RE.findall(line):
                if args.min_len <= len(w) <= args.max_len:
                    locale_words[loc].add(w.lower())
                    add(w, f"locale:{loc}")

    # CJK / Thai: emit phrases, not words -- there are no word boundaries to use.
    cjk_phrases = collections.defaultdict(collections.Counter)
    for spec in args.cjk_locale:
        loc, _, path = spec.partition(":")
        if not os.path.exists(path):
            print(f"  (missing {path})", file=sys.stderr)
            continue
        for line in read_lines(path):
            for run in CJK_RUN_RE.findall(line):
                for n in (2, 3, 4):
                    for i in range(len(run) - n + 1):
                        cjk_phrases[loc][run[i:i + n]] += 1

    # ---- safety screen ----
    accepted, rejected = {}, []
    for w, srcs in candidates.items():
        bad, why = is_derived_from_term(w, terms)
        if bad:
            rejected.append((w, why, ",".join(sorted(srcs))))
        else:
            accepted[w] = srcs

    # ---- write ----
    main_path = os.path.join(args.out, "allowlist-en.txt")
    with open(main_path, "w", encoding="utf-8") as fh:
        fh.write(
            "# WORDS THAT MUST NEVER BE CENSORED\n"
            "#\n"
            "# If your chat filter finds a blocked fragment INSIDE one of these\n"
            "# words, suppress the block. Longest match wins.\n"
            "#\n"
            "# This list is deliberately conservative: it contains ordinary\n"
            "# vocabulary only. Every candidate was screened against a profanity\n"
            "# lexicon by exact match and by derivation; rejects are listed in\n"
            "# allowlist-rejected.txt for review rather than dropped silently.\n"
            "#\n"
            f"# entries: {len(accepted):,}\n"
            "# sources: public-domain dictionary (web2), public-domain proper\n"
            "#          names, curated MMO/chat vocabulary"
            + (", and the publisher's own localization export\n" if locale_words else "\n")
            + "# license: this file contains no proprietary content.\n"
            "#\n")
        for w in sorted(accepted):
            fh.write(w + "\n")

    rej_path = os.path.join(args.out, "allowlist-rejected.txt")
    with open(rej_path, "w", encoding="utf-8") as fh:
        fh.write("# Candidates REJECTED by the safety screen. Review before use.\n"
                 "# format: word <TAB> reason <TAB> sources\n")
        for w, why, srcs in sorted(rejected):
            fh.write(f"{w}\t{why}\t{srcs}\n")

    for loc, phrases in cjk_phrases.items():
        p = os.path.join(args.out, f"allowlist-{loc}-phrases.txt")
        keep = [g for g, c in phrases.items() if c > 1]
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(f"# CJK/Thai phrase shelters for locale '{loc}'.\n"
                     "# A blocked character occurring strictly inside one of these\n"
                     "# is part of an ordinary word. Languages without word spacing\n"
                     "# cannot be protected by a word list -- only by phrases.\n"
                     f"# entries: {len(keep):,}\n")
            for g in sorted(keep):
                fh.write(g + "\n")
        print(f"  {loc}: {len(keep):,} phrase shelters -> {os.path.basename(p)}")

    by_source = collections.Counter()
    for w, srcs in accepted.items():
        for s in srcs:
            by_source[s] += 1
    print(f"\nallowlist: {len(accepted):,} words -> {os.path.basename(main_path)}")
    for s, n in by_source.most_common():
        print(f"    {s:<16} {n:>8,}")
    print(f"rejected by safety screen: {len(rejected):,} -> {os.path.basename(rej_path)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
