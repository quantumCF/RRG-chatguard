#!/usr/bin/env python3
"""
screen_language.py -- flag wording that is easy to misread.

The audience is an engineering team at a Korean publisher working on a
Brazilian-Portuguese term list, reading English. Wording that is merely elegant
in English is a liability there. This flags the constructions that cause
trouble, so they can be rewritten rather than noticed by accident.

    python3 tools/screen_language.py            # report
    python3 tools/screen_language.py --strict   # exit 1 if anything is flagged

What it looks for, in rough order of how badly each one misleads:

  actor     "cu refuses cu" -- an entry cannot refuse anything. Only the
            filter acts. A reader has to already understand the system to
            decode it, which defeats the sentence.
  idiom     figurative language with no literal reading
  long      over 28 words; the subject is usually lost by the end
  jargon    terms with a plain-English equivalent
  negation  two negatives in one clause
  vague     "it", "this", "that" opening a sentence with no clear referent

Nothing here is a grammar checker. Every rule targets a way a sentence can be
read to mean something other than what it says.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCS = ["README.md", "REPORT.md", "fix/DEPLOY.md", "tools/package-readme.md",
        "docs/audit-report.html", "docs/report-onepage.html",
        "docs/ADOPTION.md", "docs/SUGGESTIONS.md"]

# An entry, a rule or a word cannot refuse, block, censor or allow. The filter
# does. These read as shorthand to someone who wrote the system and as a
# category error to everyone else.
ACTOR = re.compile(
    r"`?\b(cu|ks|nb|anta|meter|pica|pau|puta|entry|entries|rule|rules|term|terms)\b`?\s+"
    r"(still\s+)?(refuses|refuse|blocks|block|censors|censor|allows|allow|"
    r"delivers|deliver)\b", re.I)

IDIOM = [
    "blast radius", "wearing .* hats", "earns its place", "carries the",
    "in one sitting", "on its own feet", "bears on", "load-bearing",
    "worse than useless", "side door", "front door", "the whole point",
    "costs the reader", "pays for itself", "a fight", "picks a fight",
    "falls away", "fell through", "slipped past", "waved through",
    "wearing", "by the side door", "at a glance", "in a sitting",
]

JARGON = {
    "unanchored": "not limited to whole words",
    "substring": "a sequence of letters inside a word",
    "inert padding": "meaningless surrounding letters",
    "carrier": "a test word built around the letters",
    "casualty": "ordinary word affected",
    "casualties": "ordinary words affected",
    "victim": "ordinary word affected",
    "victims": "ordinary words affected",
    "scunthorpe": "the class of error where a word contains a banned sequence",
    "corroborat": "confirm",
    "adjudicat": "decide",
    "vacuous": "empty",
    "morpholog": "word-form",
    "provenance": "origin",
    "attested": "found in a dictionary or in the game's own text",
    "derivation": "word built from",
    "enumerat": "list",
    "orthogonal": "independent",
    "conflat": "mix up",
    "obviat": "remove the need for",
}

NEGATION = re.compile(
    r"\b(not|never|no|cannot|can't|without)\b[^.;]{0,40}?\b"
    r"(not|never|no|nothing|none|nor|un\w+|in\w+valid)\b", re.I)

# Only a pronoun that opens a PARAGRAPH is genuinely ambiguous: mid-paragraph
# the referent is the sentence before it, which is how English works. Flagging
# every "This ..." produced fifty findings and hid the handful that matter.
VAGUE_OPEN = re.compile(r"\n\n\s*(It|This|That|These|Those|They)\s+(?!is the|are the)")

MAX_WORDS = 28


def sentences(text):
    """Yield prose sentences only.

    Headings, list markers, table rows and horizontal rules end a sentence as
    surely as a full stop does. Without that, a heading merges with the
    paragraph beneath it and the result is reported as one 30-word sentence
    that nobody wrote -- noise that buries the sentences actually worth fixing.
    """
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\|[^\n]*\|", "\n", text)         # tables
    out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if (not stripped or stripped.startswith(("#", "-", "*", ">", "|", "==="))
                or re.match(r"^\d+\.", stripped)):
            out.append(".")                           # hard break
            stripped = re.sub(r"^[#>*\-]+\s*|^\d+\.\s*", "", stripped)
        out.append(stripped)
    text = re.sub(r"\s+", " ", " ".join(out))
    for m in re.finditer(r"[^.!?]+[.!?]", text):
        s = m.group(0).strip(" .")
        if len(s.split()) >= 4:
            yield s


def main():
    strict = "--strict" in sys.argv
    findings = []

    for rel in DOCS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        raw = open(p, encoding="utf-8").read()
        # Code is not prose. Identifiers, snippets and CSS are read as code by
        # the audience too, so flagging MIN_SUBSTRING_LEN as jargon is noise
        # that hides the real findings.
        raw = re.sub(r"```.*?```", " ", raw, flags=re.S)
        raw = re.sub(r"<pre\b.*?</pre>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"<style\b.*?</style>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"`[^`]*`", " CODE ", raw)
        raw = re.sub(r"\b[A-Z][A-Z0-9_]{3,}\b", " CONST ", raw)
        # Markup between words hides the very phrases this screens for:
        # "<code>cu</code> still refuses" did not match the actor rule because
        # of the tags, and sat in the published one-pager as a result.
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"&nbsp;|&rarr;|&amp;", " ", raw)

        for m in ACTOR.finditer(raw):
            findings.append((rel, "actor", m.group(0).strip()))

        low = raw.lower()
        for word, better in JARGON.items():
            if word in low:
                n = low.count(word)
                findings.append((rel, "jargon", f"{word} x{n}  -> {better}"))

        for phrase in IDIOM:
            for m in re.finditer(phrase, low):
                findings.append((rel, "idiom", m.group(0)))

        for s in sentences(raw):
            n = len(s.split())
            if n > MAX_WORDS:
                findings.append((rel, "long", f"{n} words: {s[:70]}..."))
            if NEGATION.search(s):
                findings.append((rel, "negation", s[:70] + "..."))

        for m in VAGUE_OPEN.finditer(raw):
            findings.append((rel, "vague", m.group(0).strip()))

    order = ["actor", "idiom", "jargon", "negation", "long", "vague"]
    by_kind = {k: [f for f in findings if f[1] == k] for k in order}

    print("LANGUAGE SCREEN — constructions that invite misreading\n")
    for kind in order:
        hits = by_kind[kind]
        print(f"  {kind:<10} {len(hits)}")
    print()
    for kind in order:
        hits = by_kind[kind]
        if not hits:
            continue
        print(f"\n=== {kind.upper()} ({len(hits)}) ===")
        seen = set()
        for rel, _, detail in hits:
            key = (rel, detail)
            if key in seen:
                continue
            seen.add(key)
            print(f"  {rel:<28} {detail}")

    total = len(findings)
    print(f"\ntotal flagged: {total}")
    return 1 if (strict and total) else 0


if __name__ == "__main__":
    sys.exit(main())
