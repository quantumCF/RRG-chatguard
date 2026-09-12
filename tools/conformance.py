#!/usr/bin/env python3
"""
conformance.py -- run the golden vectors against an implementation.

Any port of chatguard (C#, Java, Go, C++, TypeScript) is "correct" exactly when
it reproduces vectors/golden.jsonl. That is the whole contract: no shared code
required, no trust required, just a file both sides agree on.

Exit code 0 = all vectors pass. Non-zero = the count of failures.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))
from chatguard import ChatGuard, MatchMode, Term, Tier  # noqa: E402


# The fixture the vectors are written against. Kept tiny and explicit so a
# porter can hardcode it while bringing a new implementation up.
FIXTURE_TERMS = [
    Term("fuck", Tier.STRONG, MatchMode.PREFIX),
    Term("shit", Tier.STRONG, MatchMode.PREFIX),
    Term("bitch", Tier.STRONG, MatchMode.PREFIX),
    Term("cunt", Tier.SEVERE, MatchMode.WORD),
    Term("rape", Tier.SEVERE, MatchMode.WORD),
    Term("puta", Tier.STRONG, MatchMode.WORD, ("es", "pt")),
]

FIXTURE_ALLOW = [
    "shitake", "assassin", "classic", "grape", "analysis",
    "bass", "hit", "wall", "baal", "seller", "scunthorpe",
]


def main() -> int:
    path = os.path.join(os.path.dirname(__file__), "..", "engine", "vectors", "golden.jsonl")
    guard = ChatGuard(FIXTURE_TERMS, FIXTURE_ALLOW,
                      fuzzy_tiers=(Tier.SEVERE, Tier.ILLEGAL))

    passed = failed = 0
    failures = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            vec = json.loads(line)
            if "_comment" in vec:
                continue
            got = guard.filter(vec["text"],
                               surface=vec.get("surface", "public"),
                               locale=vec.get("locale", "en"))
            ok = got.action.name == vec["action"]
            if ok and "filtered" in vec:
                ok = got.filtered == vec["filtered"]
            if ok:
                passed += 1
            else:
                failed += 1
                failures.append((vec, got))

    for vec, got in failures:
        print(f"FAIL {vec['id']:16} {vec['text']!r}")
        print(f"     want action={vec['action']}"
              + (f" filtered={vec['filtered']!r}" if "filtered" in vec else ""))
        print(f"     got  action={got.action.name} filtered={got.filtered!r}")

    print(f"\n{passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(main())
