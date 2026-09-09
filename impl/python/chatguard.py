"""
chatguard - reference implementation.

A drop-in replacement for substring blocklist chat filters, designed to sit at
the exact seam an existing `check(text) -> bool` / `filter(text) -> masked`
server API already occupies.

Pipeline:
    0 policy    resolve (surface, channel, locale) -> policy
    1 normalize NFKC, confusable fold, diacritic strip, leet map, run collapse,
                separator strip, zero-width strip -- with an offset map back to
                the original string so masking lands on the right characters
    2 match     Aho-Corasick over the normalized form; each term carries a match
                mode (word | prefix | sub) and a severity tier
    3 rescue    allowlist longest-match override; a hit inside an allowlisted
                token is dropped. This is what fixes the Scunthorpe problem.
    4 fuzzy     bounded edit-distance<=1, tier-3 core terms only, len>=5
    5 decide    tier x channel -> allow | mask | block | review
    6 emit      masked string via the offset map, plus a structured verdict

No third-party dependencies. Python 3.8+.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


# --------------------------------------------------------------------------
# tiers and actions
# --------------------------------------------------------------------------

class Tier(IntEnum):
    """Severity. Policy maps tier -> action per channel; nothing is hardcoded."""
    NONE = 0
    MILD = 1      # crude but not harmful
    STRONG = 2    # clear profanity
    SEVERE = 3    # slurs, threats, sexual content involving minors
    ILLEGAL = 4   # RMT, phishing, off-platform solicitation


class Action(IntEnum):
    ALLOW = 0
    MASK = 1      # replace the span, deliver the message
    BLOCK = 2     # refuse to deliver, tell the sender
    REVIEW = 3    # deliver, but queue for a human


# --------------------------------------------------------------------------
# normalization
# --------------------------------------------------------------------------

# Homoglyph folds. A real deployment loads the full Unicode UTS#39 confusables
# table; this covers the classes that actually appear in game chat evasion.
_CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "ѕ": "s", "і": "i", "ј": "j", "к": "k", "м": "m", "н": "h", "т": "t",
    "ο": "o", "ε": "e", "ι": "i", "κ": "k", "ν": "v", "ρ": "p", "τ": "t",
    "α": "a", "β": "b", "γ": "y", "σ": "o", "υ": "u", "χ": "x",
}

_LEET = {
    "4": "a", "@": "a", "8": "b", "3": "e", "6": "g", "9": "g",
    "1": "i", "!": "i", "|": "i", "0": "o", "5": "s", "$": "s",
    "7": "t", "+": "t", "2": "z",
}

# Characters used to break up a word: f.u.c.k / f-u-c-k / f u c k
_SEPARATORS = set(" \t._-*'\"`^~,;:()[]{}<>/\\|")

_ZERO_WIDTH = {"​", "‌", "‍", "﻿", "⁠", "­"}


@dataclass
class Normalized:
    """Normalized text plus a map from each normalized char to its source span."""
    text: str
    # src[i] == (start, end) half-open range in the ORIGINAL string
    src: List[Tuple[int, int]]

    def span(self, i: int, j: int) -> Tuple[int, int]:
        """Map a normalized [i, j) match back to an original [start, end)."""
        if not self.src or i >= len(self.src):
            return (0, 0)
        j = min(j, len(self.src))
        return (self.src[i][0], self.src[j - 1][1])


def _fold_char(ch: str, fold_leet: bool) -> str:
    """NFKC + strip accents + lowercase + confusables + optional leet."""
    folded = unicodedata.normalize("NFKC", ch)
    folded = "".join(c for c in unicodedata.normalize("NFD", folded)
                     if unicodedata.category(c) != "Mn")
    if not folded:
        return ""
    folded = folded.lower()
    folded = "".join(_CONFUSABLES.get(c, c) for c in folded)
    if fold_leet:
        folded = "".join(_LEET.get(c, c) for c in folded)
    return folded


def normalize(text: str, *, condense: bool = False,
              fold_leet: bool = True) -> Normalized:
    """
    Fold text to a matching form, preserving a map back to the original.

    Two modes, and the distinction matters:

    * condense=False (the BOUNDARY pass) keeps separators as a single space, so
      word boundaries survive and repeated letters are left alone. "classic"
      stays "classic" and the allowlist can still match it. This pass drives
      word/prefix matching and allowlist rescue.

    * condense=True (the EVASION pass) drops separators entirely and collapses
      runs of THREE OR MORE identical letters to one, so "f u c k", "f.u.c.k"
      and "fuuuuck" all fold onto the same form.

      The 3-or-more threshold is load-bearing. Collapsing mere doubles would
      fold "wall" -> "wal", "Baal" -> "bal" and "seller" -> "seler", inventing
      matches inside ordinary words and game proper nouns. English almost never
      writes the same letter three times in a row, so 3+ is a genuine evasion
      signal while 2 is just spelling.

    Hits from the evasion pass are additionally gated by _evasion_ok, which
    requires the original span to actually show obfuscation.
    """
    # Phase 1: fold every source character, keeping its origin.
    folded: List[Tuple[str, int]] = []
    for idx, ch in enumerate(text):
        if ch in _ZERO_WIDTH:
            continue
        for c in _fold_char(ch, fold_leet):
            folded.append((c, idx))

    # Phase 2: emit, applying separator and run policy.
    out: List[str] = []
    src_map: List[Tuple[int, int]] = []

    i = 0
    n = len(folded)
    while i < n:
        c, idx = folded[i]
        if c in _SEPARATORS or c.isspace():
            if not condense and out and out[-1] != " ":
                out.append(" ")
                src_map.append((idx, idx + 1))
            i += 1
            continue

        # Measure the run of this character.
        j = i
        while j < n and folded[j][0] == c:
            j += 1
        run = j - i

        if condense and run >= 3:
            out.append(c)
            src_map.append((idx, folded[j - 1][1] + 1))
        else:
            for k in range(i, j):
                ck, ik = folded[k]
                out.append(ck)
                src_map.append((ik, ik + 1))
        i = j

    return Normalized("".join(out), src_map)


# --------------------------------------------------------------------------
# term table
# --------------------------------------------------------------------------

class MatchMode:
    WORD = "word"      # must be bounded by non-letters on both sides
    PREFIX = "prefix"  # bounded on the left only
    SUB = "sub"        # anywhere -- use sparingly, this is the FP engine


@dataclass(frozen=True)
class Term:
    text: str
    tier: Tier = Tier.STRONG
    mode: str = MatchMode.WORD
    locales: Optional[Tuple[str, ...]] = None   # None == all locales

    def applies_to(self, locale: str) -> bool:
        return self.locales is None or locale in self.locales


# --------------------------------------------------------------------------
# Aho-Corasick
# --------------------------------------------------------------------------

class _Node:
    __slots__ = ("next", "fail", "out")

    def __init__(self) -> None:
        self.next: Dict[str, "_Node"] = {}
        self.fail: Optional["_Node"] = None
        self.out: List[Term] = []


class Automaton:
    """Multi-pattern matcher. O(n) in the text, independent of pattern count."""

    def __init__(self, terms: Iterable[Term]) -> None:
        self.root = _Node()
        self._count = 0
        for t in terms:
            self._add(t)
        self._build()

    def _add(self, term: Term) -> None:
        node = self.root
        for ch in term.text:
            node = node.next.setdefault(ch, _Node())
        node.out.append(term)
        self._count += 1

    def _build(self) -> None:
        q: deque = deque()
        self.root.fail = self.root
        for child in self.root.next.values():
            child.fail = self.root
            q.append(child)
        while q:
            node = q.popleft()
            for ch, child in node.next.items():
                f = node.fail
                while f is not self.root and ch not in f.next:
                    f = f.fail
                child.fail = f.next.get(ch, self.root)
                if child.fail is child:
                    child.fail = self.root
                child.out.extend(child.fail.out)
                q.append(child)

    def __len__(self) -> int:
        return self._count

    def find(self, text: str) -> List[Tuple[int, int, Term]]:
        """Yield (start, end, term) for every occurrence, in text order."""
        hits: List[Tuple[int, int, Term]] = []
        node = self.root
        for i, ch in enumerate(text):
            while node is not self.root and ch not in node.next:
                node = node.fail
            node = node.next.get(ch, self.root)
            for term in node.out:
                hits.append((i - len(term.text) + 1, i + 1, term))
        return hits


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------

@dataclass
class Policy:
    """
    What to do about each tier, on a given surface.

    Surfaces differ: a character name is permanent and visible to everyone, so
    it warrants BLOCK where the same word in guild chat warrants MASK or ALLOW.
    """
    name: str = "default"
    actions: Dict[Tier, Action] = field(default_factory=lambda: {
        Tier.MILD: Action.ALLOW,
        Tier.STRONG: Action.MASK,
        Tier.SEVERE: Action.BLOCK,
        Tier.ILLEGAL: Action.BLOCK,
    })
    mask_char: str = "*"

    def action_for(self, tier: Tier) -> Action:
        return self.actions.get(tier, Action.ALLOW)


DEFAULT_POLICIES: Dict[str, Policy] = {
    # Private-ish: friends, party, guild. Adults talking to adults.
    "private": Policy("private", {
        Tier.MILD: Action.ALLOW, Tier.STRONG: Action.ALLOW,
        Tier.SEVERE: Action.MASK, Tier.ILLEGAL: Action.BLOCK,
    }),
    # Broadcast: world/shout/trade. Everyone sees it.
    "public": Policy("public", {
        Tier.MILD: Action.ALLOW, Tier.STRONG: Action.MASK,
        Tier.SEVERE: Action.BLOCK, Tier.ILLEGAL: Action.BLOCK,
    }),
    # Permanent + public: character, guild, pet, stall names.
    "identifier": Policy("identifier", {
        Tier.MILD: Action.BLOCK, Tier.STRONG: Action.BLOCK,
        Tier.SEVERE: Action.BLOCK, Tier.ILLEGAL: Action.BLOCK,
    }),
}


# --------------------------------------------------------------------------
# verdict
# --------------------------------------------------------------------------

@dataclass
class Hit:
    start: int          # offset in the ORIGINAL string
    end: int
    term: str
    tier: Tier
    action: Action


@dataclass
class Verdict:
    original: str
    filtered: str
    action: Action
    hits: List[Hit] = field(default_factory=list)
    rescued: List[str] = field(default_factory=list)  # what the allowlist saved

    @property
    def blocked(self) -> bool:
        return self.action == Action.BLOCK

    @property
    def clean(self) -> bool:
        return self.action == Action.ALLOW and not self.hits

    def to_dict(self) -> dict:
        return {
            "filtered_word": self.filtered,
            "action": self.action.name,
            "errorId": 0 if self.action == Action.ALLOW else int(self.action),
            "hits": [
                {"start": h.start, "end": h.end, "tier": int(h.tier),
                 "action": h.action.name}
                for h in self.hits
            ],
            "rescued": self.rescued,
        }


# --------------------------------------------------------------------------
# the guard
# --------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-z0-9]+")
_SEP_SPLIT_RE = re.compile("[" + re.escape("".join(_SEPARATORS)) + r"\s]+")


class ChatGuard:
    """
    Build once at startup, call per message. Thread-safe for reads.

    >>> g = ChatGuard(terms=[Term("badword", Tier.STRONG, MatchMode.WORD)])
    >>> g.filter("that is a badword here").filtered
    'that is a ******* here'
    >>> g.check("perfectly fine")
    False
    """

    def __init__(self,
                 terms: Sequence[Term],
                 allowlist: Optional[Iterable[str]] = None,
                 policies: Optional[Dict[str, Policy]] = None,
                 fuzzy_tiers: Tuple[Tier, ...] = (Tier.SEVERE, Tier.ILLEGAL),
                 fuzzy_min_len: int = 5) -> None:
        # Terms must live in the same normalized space as the input, or a term
        # written "sh1t" would never match input "shit" (and vice versa).
        self.terms = [
            Term(normalize(t.text).text.replace(" ", ""), t.tier, t.mode, t.locales)
            for t in terms
        ]
        self.terms = [t for t in self.terms if t.text]
        self.allow: Set[str] = {w.strip().lower() for w in (allowlist or ())
                                if w.strip() and not w.startswith("#")}
        # A term always beats the allowlist -- otherwise adding a dictionary
        # word to the blocklist would silently do nothing.
        self._term_texts = {t.text for t in self.terms}
        self.allow -= self._term_texts
        self.policies = dict(policies or DEFAULT_POLICIES)
        self.automaton = Automaton(self.terms)
        self.fuzzy_tiers = fuzzy_tiers
        self.fuzzy_min_len = fuzzy_min_len
        self._fuzzy_terms = [t for t in self.terms
                             if t.tier in fuzzy_tiers
                             and len(t.text) >= fuzzy_min_len]

    # -- public API, shaped to match an existing server filter seam -------

    def check(self, text: str, *, surface: str = "public",
              locale: str = "en") -> bool:
        """True if the text should be acted on at all. Mirrors CheckBlockWord."""
        return self.evaluate(text, surface=surface, locale=locale).action != Action.ALLOW

    def filter(self, text: str, *, surface: str = "public",
               locale: str = "en") -> Verdict:
        """Masked text + verdict. Mirrors FilterBlockWord -> filtered_word."""
        return self.evaluate(text, surface=surface, locale=locale)

    # -- the pipeline ------------------------------------------------------

    def evaluate(self, text: str, *, surface: str = "public",
                 locale: str = "en") -> Verdict:
        if not text:
            return Verdict(text, text, Action.ALLOW)

        policy = self.policies.get(surface, DEFAULT_POLICIES["public"])

        # Pass A: boundaries intact. Drives word/prefix matching and rescue.
        norm = normalize(text, condense=False)
        tokens = [(m.start(), m.end(), m.group(0))
                  for m in _WORD_RE.finditer(norm.text)]

        candidates = []
        for s_i, e_i, term in self.automaton.find(norm.text):
            if not self._boundary_ok(norm.text, s_i, e_i, term.mode):
                continue
            o = norm.span(s_i, e_i)
            candidates.append((o[0], o[1], term))

        # Pass B: separators dropped, repeats collapsed. Catches deliberate
        # evasion only -- a hit is kept solely when the original span carries an
        # evasion signature, so this cannot resurrect substring false positives.
        cond = normalize(text, condense=True)
        for s_i, e_i, term in self.automaton.find(cond.text):
            o = cond.span(s_i, e_i)
            if self._evasion_ok(text, o[0], o[1], term.text):
                candidates.append((o[0], o[1], term))

        if self._fuzzy_terms:
            candidates.extend(self._fuzzy_find(norm, tokens))

        # Rescue + locale gate.
        kept = []
        rescued = []
        seen = set()
        for o_start, o_end, term in candidates:
            if not term.applies_to(locale):
                continue
            key = (o_start, o_end, term.text)
            if key in seen:
                continue
            seen.add(key)
            host = self._host_token(norm, tokens, o_start, o_end)
            if host is not None and host != term.text and host in self.allow:
                rescued.append(host)
                continue
            kept.append((o_start, o_end, term))

        if not kept:
            return Verdict(text, text, Action.ALLOW, [], sorted(set(rescued)))

        hits = []
        worst = Action.ALLOW
        for o_start, o_end, term in kept:
            action = policy.action_for(term.tier)
            if action == Action.ALLOW:
                continue
            hits.append(Hit(o_start, o_end, term.text, term.tier, action))
            if int(action) > int(worst):
                worst = action

        if not hits:
            return Verdict(text, text, Action.ALLOW, [], sorted(set(rescued)))

        filtered = text if worst == Action.BLOCK else self._mask(text, hits, policy)
        return Verdict(text, filtered, worst, hits, sorted(set(rescued)))

    @staticmethod
    def _evasion_ok(text: str, start: int, end: int, term: str) -> bool:
        """
        True when the original span looks like deliberate obfuscation rather
        than an innocent substring.

        Accepts  "f u c k", "f.u.c.k", "fu ck", "fuuuck"
        Rejects  "bass hit" (the run "hit" is too long to be spaced-out
                 obfuscation) and "grape" (span equals the term, so pass A
                 already had its chance and correctly declined on boundaries).
        """
        span = text[start:end]
        if len(span) <= len(term):
            return False
        has_sep = any(c in _SEPARATORS or c.isspace() for c in span)
        if not has_sep:
            # No separators: the span grew only through repeated letters.
            return True
        # Spaced-out obfuscation writes 1-2 characters between separators.
        parts = re.split(_SEP_SPLIT_RE, span)
        return all(len(p) <= 2 for p in parts)

    @staticmethod
    def _host_token(norm, tokens, o_start, o_end):
        """The pass-A word that contains this original span, if any."""
        for t_start, t_end, t_text in tokens:
            ts, te = norm.span(t_start, t_end)
            if ts <= o_start and o_end <= te:
                return t_text
        return None

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _boundary_ok(n: str, start: int, end: int, mode: str) -> bool:
        if mode == MatchMode.SUB:
            return True
        left_ok = start == 0 or not n[start - 1].isalnum()
        if mode == MatchMode.PREFIX:
            return left_ok
        right_ok = end >= len(n) or not n[end].isalnum()
        return left_ok and right_ok

    @staticmethod
    def _token_containing(tokens: Sequence[Tuple[int, int, str]],
                          start: int, end: int) -> Optional[Tuple[int, int, str]]:
        for t_start, t_end, t_text in tokens:
            if t_start <= start and end <= t_end:
                return (t_start, t_end, t_text)
        return None

    def _fuzzy_find(self, norm, tokens):
        """Edit-distance<=1 against a small high-severity core only."""
        out = []
        for t_start, t_end, tok in tokens:
            if len(tok) < self.fuzzy_min_len or tok in self.allow:
                continue
            for term in self._fuzzy_terms:
                if abs(len(tok) - len(term.text)) > 1:
                    continue
                if tok == term.text:
                    continue
                if _within_one_edit(tok, term.text):
                    o = norm.span(t_start, t_end)
                    out.append((o[0], o[1], term))
                    break
        return out

    @staticmethod
    def _mask(text: str, hits: Sequence[Hit], policy: Policy) -> str:
        chars = list(text)
        for h in hits:
            if h.action != Action.MASK:
                continue
            for i in range(h.start, min(h.end, len(chars))):
                chars[i] = policy.mask_char
        return "".join(chars)

    # -- loading -----------------------------------------------------------

    @classmethod
    def from_files(cls, terms_path: str, allow_paths: Sequence[str] = (),
                   policy_path: Optional[str] = None) -> "ChatGuard":
        terms: List[Term] = []
        with open(terms_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                rec = json.loads(line)
                if "text" not in rec:
                    continue          # documentation rows carry only _comment
                terms.append(Term(
                    text=rec["text"].lower(),
                    tier=Tier(rec.get("tier", int(Tier.STRONG))),
                    mode=rec.get("mode", MatchMode.WORD),
                    locales=tuple(rec["locales"]) if rec.get("locales") else None,
                ))
        allow: List[str] = []
        for p in allow_paths:
            with open(p, encoding="utf-8") as fh:
                allow.extend(l.strip() for l in fh
                             if l.strip() and not l.startswith("#"))
        policies = dict(DEFAULT_POLICIES)
        if policy_path:
            with open(policy_path, encoding="utf-8") as fh:
                for name, spec in json.load(fh).items():
                    policies[name] = Policy(
                        name=name,
                        actions={Tier[k]: Action[v] for k, v in spec["actions"].items()},
                        mask_char=spec.get("mask_char", "*"),
                    )
        return cls(terms, allow, policies)


def _within_one_edit(a: str, b: str) -> bool:
    """True if a and b differ by at most one insert, delete or substitution."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = sum(1 for x, y in zip(a, b) if x != y)
        return diff <= 1
    if la > lb:
        a, b, la, lb = b, a, lb, la
    i = j = 0
    skipped = False
    while i < la and j < lb:
        if a[i] != b[j]:
            if skipped:
                return False
            skipped = True
            j += 1
            continue
        i += 1
        j += 1
    return True
