#!/usr/bin/env python3
"""
testbattery.py -- a standardized, reproducible test battery for a live chat filter.

Anecdotes do not measure a filter. "cucumber is blocked" proves a defect exists;
it does not tell you the false-positive RATE, and a publisher cannot prioritise
work from a handful of examples. This produces a stratified probe set with a
stated confidence interval, versioned and seeded so two people running it get
the same battery and comparable numbers.

    generate   emit the battery as a numbered checklist (CSV + Markdown)
    score      read the filled-in checklist and report per-stratum rates with
               Wilson 95% confidence intervals

Strata, and what each one measures:

    A common-en      everyday chat vocabulary            -> FP rate players feel
    B dict-sample    general English                     -> FP rate at large
    C game-vocab     the title's own nouns               -> FP rate on game topics
    D fp-prone       words containing profane fragments  -> the Scunthorpe class
    E proper-noun    names and places                    -> the "Heisenberg" class
    F locale         non-English market vocabulary       -> FP rate outside English
    G evasion        obfuscated real profanity           -> UNDER-blocking rate
    H control-clean  nonsense strings                    -> test's own false alarm
    I control-block  unambiguous profanity               -> is the filter on at all

G, H and I are the honesty controls. Without G the report reads as "stop
filtering"; without H a broken harness looks like a broken filter; without I you
cannot distinguish a well-behaved filter from a disabled one.

Usage:
    testbattery.py generate --out battery/ --margin 0.05 \
        --game-strings names.txt [--locale pt:pt.txt ...]
    testbattery.py score --results battery/battery-filled.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import re
import sys

BATTERY_VERSION = "1.0"
SEED = 20260910          # fixed: the battery must be reproducible

WORD_RE = re.compile(r"[^\W\d_]{3,}", re.UNICODE)

COMMON_EN = """
hello hi hey thanks thank please sorry welcome goodbye yes no maybe okay sure
what where when why how who which anyone someone everyone nobody
buy sell trade price cheap expensive offer deal gold money coin
party guild team friend group join leave invite kick recruit member
level quest item weapon armor shield potion skill spell magic attack defend
help helping need want looking find found lost win lose fight beat
today tomorrow tonight morning afternoon evening later soon now
good great nice cool awesome amazing terrible boring fun happy sad tired
before after during while until since between around through across
because although however therefore instead maybe perhaps probably
country city town village island mountain river forest desert castle
water fire earth wind light dark ice thunder poison holy
first second third last next previous another other same different
"""

EVASION_TEMPLATES = [
    ("spaced", lambda w: " ".join(w)),
    ("dotted", lambda w: ".".join(w)),
    ("repeat", lambda w: w[0] + w[1] * 3 + w[2:] if len(w) > 2 else w),
    ("leet", lambda w: w.replace("a", "4").replace("e", "3").replace("i", "1")
                        .replace("o", "0").replace("s", "5")),
    ("fullwidth", lambda w: "".join(chr(ord(c) - 0x21 + 0xFF01)
                                    if "!" <= c <= "~" else c for c in w)),
    ("upper", lambda w: w.upper()),
]

CONTROL_CLEAN = ["qzjvx", "wexbtn", "mlqrpd", "vbnxzq", "jkwmtz",
                 "zzqqxx", "pflmrv", "xcvbnm", "qwrtpl", "hjklzx"]


def wilson(k, n, z=1.96):
    """Wilson score interval -- correct at small n and at p near 0 or 1."""
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def sample_size(margin, p=0.5, z=1.96):
    """n for a proportion estimate at the given margin of error."""
    return int(math.ceil(z * z * p * (1 - p) / (margin * margin)))


def read_words(path, limit=None):
    if not path or not os.path.exists(path):
        return []
    out = set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            for w in WORD_RE.findall(line):
                out.add(w.lower())
                if limit and len(out) >= limit:
                    return sorted(out)
    return sorted(out)


def cmd_generate(args):
    rng = random.Random(SEED)
    os.makedirs(args.out, exist_ok=True)

    n_per = max(12, sample_size(args.margin) // 6)
    rows = []

    def add(stratum, text, expect, note=""):
        rows.append({"id": len(rows) + 1, "stratum": stratum, "probe": text,
                     "expected": expect, "note": note, "result": ""})

    # A -- everyday English
    common = sorted(set(COMMON_EN.split()))
    for w in rng.sample(common, min(n_per, len(common))):
        add("A common-en", w, "pass")

    # B -- general dictionary
    dic = [w for w in read_words(args.dict) if 4 <= len(w) <= 12]
    for w in rng.sample(dic, min(n_per, len(dic))):
        add("B dict-sample", w, "pass")

    # C -- the title's own vocabulary
    game = read_words(args.game_strings)
    if game:
        for w in rng.sample(game, min(n_per, len(game))):
            add("C game-vocab", w, "pass")

    # D -- the Scunthorpe class, the highest-yield stratum
    prone = read_words(args.fp_prone) if args.fp_prone else []
    if prone:
        for w in rng.sample(prone, min(n_per * 2, len(prone))):
            add("D fp-prone", w, "pass", "contains a profane fragment but is innocuous")

    # E -- proper nouns
    proper = [w for w in read_words(args.proper) if 4 <= len(w) <= 14]
    if proper:
        for w in rng.sample(proper, min(n_per, len(proper))):
            add("E proper-noun", w, "pass")

    # F -- other markets
    for spec in args.locale:
        loc, _, path = spec.partition(":")
        lw = [w for w in read_words(path) if 4 <= len(w) <= 14]
        if lw:
            for w in rng.sample(lw, min(n_per // 2 or 6, len(lw))):
                add(f"F locale:{loc}", w, "pass")

    # G -- under-blocking. Uses placeholders; the operator substitutes real terms.
    for label, fn in EVASION_TEMPLATES:
        add("G evasion", f"<PROFANITY:{label}>", "block",
            f"apply the '{label}' transform to a common profanity and type that")

    # H / I -- controls
    for w in CONTROL_CLEAN:
        add("H control-clean", w, "pass", "nonsense; if this is blocked the list is broken")
    add("I control-block", "<PROFANITY:plain>", "block",
        "an unambiguous profanity, typed plainly -- confirms the filter is switched on")

    csv_path = os.path.join(args.out, "battery.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "stratum", "probe", "expected",
                                           "note", "result"])
        w.writeheader()
        w.writerows(rows)

    md_path = os.path.join(args.out, "battery.md")
    strata = {}
    for r in rows:
        strata.setdefault(r["stratum"], []).append(r)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(f"# Chat filter test battery v{BATTERY_VERSION}\n\n")
        fh.write(f"{len(rows)} probes · seed {SEED} · reproducible\n\n")
        fh.write("Type each probe into **guild chat** (not world chat: avoid spamming\n"
                 "other players and tripping rate limits). Record `pass` if the message\n"
                 "went through unmodified, `block` if it was rejected or masked.\n\n")
        fh.write("Fill the `result` column in `battery.csv`, then:\n\n")
        fh.write("```sh\npython3 tools/testbattery.py score --results battery.csv\n```\n\n")
        fh.write("Probes shown as `<PROFANITY:...>` are placeholders — substitute a real\n"
                 "term yourself. They are deliberately not written out here.\n\n")
        for s, items in strata.items():
            fh.write(f"\n## {s}  ({len(items)} probes, expect `{items[0]['expected']}`)\n\n")
            if items[0]["note"]:
                fh.write(f"*{items[0]['note']}*\n\n")
            fh.write("| # | probe | result |\n|---|---|---|\n")
            for r in items:
                fh.write(f"| {r['id']} | `{r['probe']}` |  |\n")

    print(f"battery v{BATTERY_VERSION}: {len(rows)} probes -> {csv_path}")
    for s, items in strata.items():
        print(f"    {s:<22} {len(items):>4}")
    legit = sum(1 for r in rows if r["expected"] == "pass")
    per_stratum_margin = 1.96 * math.sqrt(0.25 / max(n_per, 1)) * 100
    pooled_margin = 1.96 * math.sqrt(0.25 / max(legit, 1)) * 100
    print(f"\nPrecision, worst case (p=0.5), 95% confidence:")
    print(f"    per stratum  n={n_per:<5} ±{per_stratum_margin:.1f}%")
    print(f"    pooled       n={legit:<5} ±{pooled_margin:.1f}%   <- the headline number")
    print("Per-stratum figures are indicative; the pooled over-blocking rate is the")
    print("one to quote. Wilson intervals are reported per stratum by `score` so the")
    print("uncertainty travels with every figure rather than being dropped.")
    return 0


def cmd_score(args):
    with open(args.results, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    filled = [r for r in rows if r.get("result", "").strip().lower() in ("pass", "block")]
    if not filled:
        print("no results filled in yet", file=sys.stderr)
        return 1

    print(f"scored {len(filled)}/{len(rows)} probes\n")
    print(f"{'stratum':<22}{'n':>5}{'unexpected':>12}{'rate':>9}{'95% CI':>18}")
    strata = {}
    for r in filled:
        strata.setdefault(r["stratum"], []).append(r)

    out = {}
    for s, items in sorted(strata.items()):
        n = len(items)
        bad = sum(1 for r in items
                  if r["result"].strip().lower() != r["expected"].strip().lower())
        p, lo, hi = wilson(bad, n)
        out[s] = {"n": n, "unexpected": bad, "rate": round(p * 100, 1),
                  "ci95": [round(lo * 100, 1), round(hi * 100, 1)]}
        print(f"{s:<22}{n:>5}{bad:>12}{p * 100:>8.1f}%"
              f"{f'[{lo * 100:.1f}, {hi * 100:.1f}]':>18}")

    fp = [r for r in filled if r["expected"] == "pass"]
    fn = [r for r in filled if r["expected"] == "block"]
    if fp:
        bad = sum(1 for r in fp if r["result"].strip().lower() != "pass")
        p, lo, hi = wilson(bad, len(fp))
        print(f"\nOVER-BLOCKING   {bad}/{len(fp)} legitimate probes censored "
              f"= {p * 100:.1f}%  [{lo * 100:.1f}, {hi * 100:.1f}]")
    if fn:
        bad = sum(1 for r in fn if r["result"].strip().lower() != "block")
        p, lo, hi = wilson(bad, len(fn))
        print(f"UNDER-BLOCKING  {bad}/{len(fn)} abusive probes passed "
              f"= {p * 100:.1f}%  [{lo * 100:.1f}, {hi * 100:.1f}]")

    ctrl = strata.get("H control-clean", [])
    if ctrl:
        bad = sum(1 for r in ctrl if r["result"].strip().lower() != "pass")
        if bad:
            print(f"\n  WARNING: {bad} nonsense control(s) were blocked. Either the "
                  f"filter blocks arbitrary strings, or the harness is wrong. "
                  f"Investigate before trusting the rest.")
    ctrl_b = strata.get("I control-block", [])
    if ctrl_b:
        bad = sum(1 for r in ctrl_b if r["result"].strip().lower() != "block")
        if bad:
            print(f"\n  WARNING: plain profanity was NOT blocked. The filter may be "
                  f"off for this channel; over-blocking numbers above are not "
                  f"comparable to a run where it is on.")

    if args.json:
        with open(args.json, "w") as fh:
            json.dump({"version": BATTERY_VERSION, "strata": out}, fh, indent=2)
        print(f"\nwrote {args.json}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate")
    g.add_argument("--out", required=True)
    g.add_argument("--margin", type=float, default=0.10,
                   help="target margin of error, e.g. 0.05 for +/-5%%")
    g.add_argument("--dict", default="/usr/share/dict/web2")
    g.add_argument("--proper", default="/usr/share/dict/propernames")
    g.add_argument("--game-strings", default=None)
    g.add_argument("--fp-prone", default=None,
                   help="words containing profane fragments (the Scunthorpe class)")
    g.add_argument("--locale", action="append", default=[])
    g.set_defaults(fn=cmd_generate)

    s = sub.add_parser("score")
    s.add_argument("--results", required=True)
    s.add_argument("--json", default=None)
    s.set_defaults(fn=cmd_score)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
