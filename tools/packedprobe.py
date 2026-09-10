#!/usr/bin/env python3
"""
packedprobe.py -- screen many candidate fragments per chat message.

Typing one word at a time is the slow way to interrogate a filter. Two
properties of this protocol make it much faster:

  1. The server returns a MASKED STRING, not a boolean. `filtered_word` shows
     which characters were starred, so a single response reveals exactly which
     fragments fired and at what offset.

  2. A message can carry many candidates at once. Padding each candidate with
     inert filler and concatenating them turns one message into a parallel test
     of everything in it.

Together that is classical group testing. Screening 400 candidate fragments
costs roughly 30 messages instead of 400, and the mask tells you the answer
directly rather than by elimination.

    pack    build probe messages from a candidate list
    read    parse the masked replies and report which candidates fired

Workflow:

    packedprobe.py pack --candidates frags.txt --out probes.txt
    # paste each line into guild chat, copy what actually appeared, save to replies.txt
    packedprobe.py read --probes probes.txt --replies replies.txt --out fired.json

The filler is chosen so it cannot itself match: 'qzjvx' style consonant runs do
not occur in English or in romanized CJK, so any mask that appears is caused by
the candidate it surrounds.

NOTE ON RATE. This is deliberately built for tens of messages typed by a person,
not thousands driven by a script. Automated bulk querying of a live game server
is unsolicited load on someone else's production system, it looks like an attack,
and it puts the account at risk. Group testing removes the need for volume:
that is the point of the tool.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

FILLER = "qzjvx"
SEP = " "


def make_slots(candidates, max_len, pad=2):
    """Pack candidates into messages, each wrapped in inert filler."""
    msgs, cur, cur_len = [], [], 0
    for c in candidates:
        token = f"{FILLER[:pad]}{c}{FILLER[pad:pad + pad]}"
        if cur and cur_len + len(token) + 1 > max_len:
            msgs.append(cur)
            cur, cur_len = [], 0
        cur.append((c, token))
        cur_len += len(token) + 1
    if cur:
        msgs.append(cur)
    return msgs


def cmd_pack(args):
    cands = []
    with open(args.candidates, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#"):
                cands.append(line.lower())
    seen, uniq = set(), []
    for c in cands:
        if c not in seen:
            seen.add(c)
            uniq.append(c)

    msgs = make_slots(uniq, args.max_len, args.pad)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(f"# {len(uniq)} candidates packed into {len(msgs)} messages\n")
        fh.write(f"# filler={FILLER!r} pad={args.pad} max_len={args.max_len}\n")
        fh.write("# Type each PROBE line in guild chat. Copy EXACTLY what appears\n")
        fh.write("# (including any *** masking) into the replies file, one per line,\n")
        fh.write("# in the same order. A refused message: write REFUSED.\n#\n")
        for i, m in enumerate(msgs):
            fh.write(f"MAP\t{i}\t" + "\t".join(c for c, _ in m) + "\n")
        fh.write("#\n# ---- type these ----\n")
        for m in msgs:
            fh.write(SEP.join(t for _, t in m) + "\n")

    print(f"{len(uniq):,} candidates -> {len(msgs)} messages "
          f"({len(uniq) / max(len(msgs), 1):.1f} per message)")
    print(f"wrote {args.out}")
    print("\nfirst message:")
    if msgs:
        print("   " + SEP.join(t for _, t in msgs[0])[:120])
    return 0


def cmd_read(args):
    mapping, sent = [], []
    with open(args.probes, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("MAP\t"):
                parts = line.rstrip("\n").split("\t")
                mapping.append(parts[2:])
            elif line.strip() and not line.startswith("#"):
                sent.append(line.rstrip("\n"))

    replies = []
    with open(args.replies, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.strip():
                replies.append(line)

    if len(replies) != len(sent):
        print(f"WARNING: {len(sent)} probes sent but {len(replies)} replies given. "
              f"Pairing by position; check for skipped lines.", file=sys.stderr)

    fired, clean, refused = [], [], []
    for i, (out_line, cands) in enumerate(zip(sent, mapping)):
        reply = replies[i] if i < len(replies) else ""
        if reply.strip().upper() == "REFUSED":
            refused.extend(cands)
            continue
        tokens_sent = out_line.split(SEP)
        tokens_back = reply.split(SEP)
        if len(tokens_back) != len(tokens_sent):
            # Masking changed the shape; fall back to whole-message verdict.
            if reply != out_line:
                fired.extend(cands)
            else:
                clean.extend(cands)
            continue
        for cand, a, b in zip(cands, tokens_sent, tokens_back):
            (fired if a != b else clean).append(cand)

    print(f"messages: {len(sent)}   candidates: {sum(len(m) for m in mapping)}")
    print(f"  FIRED   {len(fired):>6}")
    print(f"  clean   {len(clean):>6}")
    if refused:
        print(f"  refused {len(refused):>6}  (message rejected outright, not masked)")
    if fired:
        print("\nfragments the live filter acts on:")
        for c in sorted(set(fired)):
            print(f"    {c}")

    if args.out:
        json.dump({"fired": sorted(set(fired)), "clean": sorted(set(clean)),
                   "refused": sorted(set(refused))},
                  open(args.out, "w"), indent=1)
        print(f"\nwrote {args.out}")

    if args.obs_out:
        with open(args.obs_out, "w", encoding="utf-8") as fh:
            for c in sorted(set(fired)):
                fh.write(json.dumps({"text": c, "blocked": True}) + "\n")
            for c in sorted(set(clean)):
                fh.write(json.dumps({"text": c, "blocked": False}) + "\n")
        print(f"wrote {args.obs_out}  (feed to blackbox.py infer)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack")
    p.add_argument("--candidates", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-len", type=int, default=80,
                   help="chat message length limit; lower it if messages truncate")
    p.add_argument("--pad", type=int, default=2)
    p.set_defaults(fn=cmd_pack)

    r = sub.add_parser("read")
    r.add_argument("--probes", required=True)
    r.add_argument("--replies", required=True)
    r.add_argument("--out", default=None)
    r.add_argument("--obs-out", default=None,
                   help="write blackbox.py observations")
    r.set_defaults(fn=cmd_read)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
