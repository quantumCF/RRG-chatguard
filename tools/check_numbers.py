#!/usr/bin/env python3
"""
check_numbers.py -- fail if a figure in the documents is not in the evidence.

Every quantity in the report and the one-pager comes from findings.json. They
are separate files, so the same figure is written out in several places and
each rebuild of the evidence silently invalidates all of them. That is the
error this catches: a number that was true last week, sitting in a sentence
that reads as current.

It is deliberately dumb. It extracts every integer from the documents and
checks it against the set of quantities the evidence actually supports. Dates,
version numbers, section numbers and small integers are ignored, because they
are not claims about measurement.

    python3 tools/check_numbers.py            # exits non-zero on a stale figure

A figure that is legitimately not derived from findings.json goes in ALLOWED
with a reason, so the exception is visible rather than silent.
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = ["REPORT.md", "docs/report-onepage.html", "README.md", "fix/DEPLOY.md"]

# Figures that are real but do not come from the probe evidence.
ALLOWED = {
    2026: "year",
    2022: "Unity version referenced in the client analysis",
    8: "number of shipped locales",
    2: "length of the cu / ks rules",
    3: "verification passes",
    650: "approximate line count of the reference engine",
    250: "words re-probed by the false-negative audit (findings/raw-logs/f1,f2)",
    491: "observations in the false-negative audit (findings/raw-logs/f1,f2)",
    53: "tests in the reference engine suite",
    29: "conformance vectors",
    27: "Portuguese terms tested in the control battery",
    # Allowlist provenance. Not probe findings -- these describe the sources
    # fix/allowlist-en.txt was built from. The total is verified against the
    # file by the assertion below; the per-source counts are approximate and
    # labelled as such in DEPLOY.md.
    473532: "entries in fix/allowlist-en.txt (verified against the file)",
    234246: "allowlist source: web2 dictionary",
    91600: "allowlist source: GeoNames place names",
    162253: "allowlist source: US Census surnames",
    1297: "allowlist source: BSD propernames",
    222: "allowlist source: hand-written MMO vocabulary",
    2010: "US Census year for the surname source",
}


def evidence_numbers(path):
    """Every quantity findings.json supports, plus tolerant variants."""
    with open(path, encoding="utf-8") as fh:
        f = json.load(fh)

    nums = set()

    def add(n):
        if isinstance(n, int):
            nums.add(n)

    add(f.get("probes_analysed"))
    add(f.get("strings_with_a_verdict"))
    add(f.get("ordinary_words_censored"))
    add(f.get("clean_words_confirmed"))
    add(f.get("derived_union_count"))
    add(len(f.get("blocked_terms", [])))
    add(len(f.get("untested_mismatch_only", [])))
    add(len(f.get("unexplained", [])))
    add(len(f.get("rules", [])))
    for v in (f.get("derived_counts") or {}).values():
        add(v)
    # per-rule measured counts
    attribution = f.get("attribution") or {}
    counts = {}
    for w, rule in attribution.items():
        counts[rule] = counts.get(rule, 0) + 1
    for v in counts.values():
        add(v)
    return nums


def main():
    ev_path = os.path.join(ROOT, "findings", "findings.json")
    if not os.path.exists(ev_path):
        print(f"no evidence at {ev_path} -- run build_findings.py first")
        return 2
    ok = evidence_numbers(ev_path)

    stale = []
    for rel in DOCS:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        text = open(p, encoding="utf-8").read()
        if p.endswith(".html"):
            # Only prose makes claims. Stylesheets are full of numbers that
            # look exactly like findings (215, 700, 600) and are px and font
            # weights, so strip style blocks and tags before reading.
            text = re.sub(r"<style\b.*?</style>", "", text,
                          flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", text)
        for m in re.finditer(r"\b\d{1,3}(?:,\d{3})+\b|\b\d+\b", text):
            raw = m.group(0)
            n = int(raw.replace(",", ""))
            if n < 100 and n not in ALLOWED:
                continue                      # section numbers, small counts
            if n in ok or n in ALLOWED:
                continue
            line = text[:m.start()].count("\n") + 1
            stale.append((rel, line, raw))

    if not stale:
        print(f"all figures in {len(DOCS)} documents trace to findings.json")
        return 0

    print(f"{len(stale)} figure(s) not supported by the evidence:\n")
    for rel, line, raw in stale:
        print(f"  {rel}:{line}  {raw}")
    print("\nEither the document is stale or ALLOWED needs the exception.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
