#!/usr/bin/env python3
"""
make_charts.py -- generate the report's charts from findings.json.

Three charts, chosen because each answers a question the prose cannot answer as
quickly:

  reach    where the damage concentrates -- one two-character entry accounts
           for more than half of it, which is why the fix is a length rule and
           not a list review
  impact   what the recommended fix actually removes, as a before and after
  locales  whether this is an English-only problem (it is not)

Anything else would be decoration. A chart that restates a sentence costs the
reader time and earns nothing.

Written as plain SVG with an explicit white background: GitHub strips <style>
from embedded SVG and renders READMEs on a dark ground for many users, so a
transparent chart with dark text becomes unreadable for them. Figures come from
findings.json so a rebuild of the evidence cannot leave a chart behind.
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs")

INK = "#14181c"
ACCENT = "#c0392b"
MUTED = "#aeb6bd"
GREY = "#5d666e"
TRACK = "#eef1f4"
FONT = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, "
        "sans-serif")


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=13, fill=INK, weight="400", anchor="start", mono=False):
    fam = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" if mono else FONT
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
            f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}">'
            f'{esc(s)}</text>')


def frame(w, h, body, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
            f'<rect width="{w}" height="{h}" fill="#ffffff" rx="8"/>'
            f'{body}</svg>')


def bar_chart(rows, title, subtitle, value_fmt="{:,}", accent_first=True,
              label_w=96, width=840, mono_labels=True):
    """rows: [(label, value, note)] -- horizontal bars, largest first."""
    pad, top = 26, 74
    row_h, bar_h = 34, 17
    chart_x = pad + label_w
    note_w = 250
    track_w = width - chart_x - pad - note_w
    peak = max(v for _, v, _ in rows) or 1

    parts = [text(pad, 32, title, 16, INK, "700"),
             text(pad, 52, subtitle, 12, GREY)]
    for i, (label, value, note) in enumerate(rows):
        y = top + i * row_h
        fill = ACCENT if (accent_first and i == 0) else INK if value >= peak * 0.08 else MUTED
        w = max(2, round(track_w * value / peak))
        parts.append(text(chart_x - 10, y + bar_h - 4, label, 12.5, INK, "600",
                          "end", mono=mono_labels))
        parts.append(f'<rect x="{chart_x}" y="{y}" width="{track_w}" '
                     f'height="{bar_h}" fill="{TRACK}" rx="2.5"/>')
        parts.append(f'<rect x="{chart_x}" y="{y}" width="{w}" height="{bar_h}" '
                     f'fill="{fill}" rx="2.5"/>')
        vx = chart_x + w + 8
        parts.append(text(vx, y + bar_h - 4, value_fmt.format(value), 12,
                          INK, "700"))
        if note:
            parts.append(text(width - pad, y + bar_h - 4, note, 11.5, GREY,
                              anchor="end"))
    h = top + len(rows) * row_h + 12
    return frame(width, h, "".join(parts), title)


def main():
    f = json.load(open(os.path.join(ROOT, "findings", "findings.json"),
                       encoding="utf-8"))
    dc = f["derived_counts"]
    total = f["derived_union_count"]
    after = f["remaining_after_length_rule"]
    removed = total - after

    # ---- 1. where the damage concentrates ---------------------------------
    top5 = sorted(dc.items(), key=lambda kv: -kv[1])[:5]
    examples = {
        "cu": "document · security · circus",
        "nb": "number · inbox · unbind",
        "meter": "parameter · diameter",
        "anta": "advantage · santa · fantastic",
        "ks": "thanks · tasks · books · works",
    }
    rows = [(k, v, examples.get(k, "")) for k, v in top5]
    rest = total - sum(v for _, v in top5)
    rows.append(("11 others", rest, ""))
    svg = bar_chart(
        rows,
        "One two-character entry causes most of the damage",
        f"Ordinary English words censored, by blocked entry "
        f"({total:,} distinct words in total)")
    open(os.path.join(OUT, "chart-reach.svg"), "w", encoding="utf-8").write(svg)

    # ---- 2. what the fix removes ------------------------------------------
    width, h, pad = 840, 210, 26
    bar_w, bx = 560, 150
    parts = [
        text(pad, 32, "A one-line rule removes 91% of it", 16, INK, "700"),
        text(pad, 52, "Ordinary English words still censored, before and after "
                      "“entries under five characters match only as whole "
                      "words”", 12, GREY),
    ]
    for i, (label, value, fill) in enumerate(
            [("before", total, ACCENT), ("after", after, INK)]):
        y = 84 + i * 52
        w = max(3, round(bar_w * value / total))
        parts.append(text(bx - 12, y + 24, label, 13, INK, "600", "end"))
        parts.append(f'<rect x="{bx}" y="{y}" width="{bar_w}" height="32" '
                     f'fill="{TRACK}" rx="3"/>')
        parts.append(f'<rect x="{bx}" y="{y}" width="{w}" height="32" '
                     f'fill="{fill}" rx="3"/>')
        inside = w > 90
        parts.append(text(bx + w - 10 if inside else bx + w + 10, y + 22,
                          f"{value:,}", 15, "#ffffff" if inside else INK, "700",
                          "end" if inside else "start"))
    parts.append(text(bx, 196, f"{removed:,} words recovered — no entry removed "
                               f"from the block list", 12, GREY))
    open(os.path.join(OUT, "chart-impact.svg"), "w", encoding="utf-8").write(
        frame(width, h, "".join(parts), "Impact of the length rule"))

    # ---- 3. not an English-only problem -----------------------------------
    loc = sorted(f["locale_refusal_pct"].items(), key=lambda kv: -kv[1])
    rows = [(k, v, "") for k, v in loc]
    svg = bar_chart(rows,
                    "Every market, not only English",
                    "Share of each locale's common vocabulary refused by the "
                    "live filter",
                    value_fmt="{}%", accent_first=False, label_w=96,
                    mono_labels=False)
    open(os.path.join(OUT, "chart-locales.svg"), "w", encoding="utf-8").write(svg)

    for name in ("chart-reach.svg", "chart-impact.svg", "chart-locales.svg"):
        p = os.path.join(OUT, name)
        print(f"  {name:22} {os.path.getsize(p):>6,} bytes")


if __name__ == "__main__":
    main()
