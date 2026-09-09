"""
shadow.py -- run chatguard beside an existing filter without changing behaviour.

The single largest obstacle to replacing a live moderation filter is not
technical quality, it is risk: nobody wants to be the engineer who shipped the
change that let a slur through, and no amount of benchmark data fully removes
that fear. Shadow mode removes the risk instead of arguing about it.

    verdict = shadow.filter(text)     # returns the INCUMBENT's answer, always

The incumbent stays authoritative. chatguard runs beside it, and every
disagreement is recorded. After a week of real traffic you have a decision
based on your own production data rather than on anyone's benchmark:

    * cases where chatguard would have stopped censoring a legitimate word
    * cases where chatguard would have caught abuse the incumbent missed
    * cases where chatguard would have been WRONG   <- the ones that matter

Only when that ledger looks right do you flip `authority` to "chatguard".
Rollback is one config value, with no deploy.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class Disagreement:
    text: str
    incumbent_flagged: bool
    guard_flagged: bool
    guard_action: str
    guard_filtered: str
    rescued: List[str]
    surface: str
    locale: str
    ts: float = field(default_factory=time.time)

    @property
    def kind(self) -> str:
        """
        over_block_fixed  incumbent censored it, chatguard would not
        new_catch         chatguard flags it, incumbent did not
        """
        if self.incumbent_flagged and not self.guard_flagged:
            return "over_block_fixed"
        return "new_catch"

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "text": self.text, "surface": self.surface,
            "locale": self.locale, "incumbent_flagged": self.incumbent_flagged,
            "guard_flagged": self.guard_flagged, "guard_action": self.guard_action,
            "guard_filtered": self.guard_filtered, "rescued": self.rescued,
            "ts": round(self.ts, 3),
        }


class ShadowFilter:
    """
    Wrap an existing filter. Behaviour is unchanged until you say otherwise.

    Args:
        incumbent: your current filter. Callable(text) -> (flagged, filtered).
        guard:     a configured ChatGuard.
        authority: "incumbent" (default, zero behaviour change) or "chatguard".
        sink:      called with each Disagreement. Default keeps an in-memory
                   ring buffer; in production point this at your log pipeline.
        sample:    fraction of AGREEMENTS to record too (for a denominator).
    """

    def __init__(self,
                 incumbent: Callable[[str], "tuple[bool, str]"],
                 guard,
                 authority: str = "incumbent",
                 sink: Optional[Callable[[Disagreement], None]] = None,
                 ring_size: int = 10000) -> None:
        self.incumbent = incumbent
        self.guard = guard
        self.authority = authority
        self._lock = threading.Lock()
        self.ring: List[Disagreement] = []
        self.ring_size = ring_size
        self.sink = sink or self._default_sink
        self.stats: Dict[str, int] = {
            "calls": 0, "agree": 0, "over_block_fixed": 0, "new_catch": 0,
            "guard_errors": 0,
        }

    def _default_sink(self, d: Disagreement) -> None:
        self.ring.append(d)
        if len(self.ring) > self.ring_size:
            del self.ring[: len(self.ring) - self.ring_size]

    def filter(self, text: str, *, surface: str = "public",
               locale: str = "en") -> "tuple[bool, str]":
        """Returns (flagged, filtered) from whichever side holds authority."""
        inc_flagged, inc_filtered = self.incumbent(text)

        try:
            v = self.guard.filter(text, surface=surface, locale=locale)
            g_flagged = v.action.name != "ALLOW"
            g_filtered = v.filtered
            g_action = v.action.name
            rescued = v.rescued
        except Exception:
            # A shadow evaluation must NEVER be able to break the live path.
            with self._lock:
                self.stats["guard_errors"] += 1
            return (inc_flagged, inc_filtered)

        with self._lock:
            self.stats["calls"] += 1
            if inc_flagged == g_flagged:
                self.stats["agree"] += 1
            else:
                d = Disagreement(text, inc_flagged, g_flagged, g_action,
                                 g_filtered, rescued, surface, locale)
                self.stats[d.kind] += 1
                self.sink(d)

        if self.authority == "chatguard":
            return (g_flagged, g_filtered)
        return (inc_flagged, inc_filtered)

    # -- reporting ---------------------------------------------------------

    def report(self) -> dict:
        with self._lock:
            s = dict(self.stats)
        total = max(s["calls"], 1)
        s["agreement_pct"] = round(s["agree"] / total * 100, 2)
        return s

    def dump(self, path: str, limit: int = 1000) -> int:
        """Write recorded disagreements as JSONL for review. Returns count."""
        with self._lock:
            rows = list(self.ring)[-limit:]
        with open(path, "w", encoding="utf-8") as fh:
            for d in rows:
                fh.write(json.dumps(d.to_dict(), ensure_ascii=False) + "\n")
        return len(rows)
