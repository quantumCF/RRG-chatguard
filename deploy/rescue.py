"""
rescue.py -- the minimal fix. Reference implementation.

Drop this beside your existing chat filter. Call it immediately before the
filter returns "blocked". If the blocked fragment sits INSIDE a word that is on
the allowlist, suppress the block.

    from rescue import Rescue

    rescue = Rescue("allowlist-en.txt")          # once, at startup

    # ... inside your existing filter, where you were about to block:
    if rescue.is_rescued(text, match_start, match_end):
        pass          # ordinary word, let it through
    else:
        block()       # unchanged behaviour

That is the whole integration. Your matching logic, your word list, your
severity rules and your protocol all stay exactly as they are.

WHY THIS WORKS WITHOUT KNOWING YOUR LIST
The defect is that a blocked fragment matches inside ordinary words: "cucumber"
is censored for a fragment in the middle of it, "Freezing" becomes "****zing".
You do not have to find which entries are at fault. You assert what is
legitimate, and the filter stops censoring it. That holds whatever your list
contains and however often it changes.

COST
~234,000 words, about 12 MB resident as a Python set, loaded once. Lookup is a
single hash probe: the added latency is not measurable against a network round
trip. Nothing is written; the check is pure.

CJK NOTE
Chinese, Japanese and Thai do not separate words with spaces, so there is no
word for a token rule to find. Pass a phrase file to `phrases=` and the check
also suppresses a block whose span lies strictly inside a known-good phrase.
"""

from __future__ import annotations

import os
from typing import Iterable, Optional, Set

# A "word" is a maximal run of these. Apostrophe and hyphen are included so
# "don't" and "well-known" are single words rather than three.
_WORD_CHARS = set("abcdefghijklmnopqrstuvwxyz"
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
                  "0123456789'-")


def _is_word_char(ch: str) -> bool:
    # Any letter counts, so accented and non-Latin scripts behave sensibly.
    return ch in _WORD_CHARS or ch.isalpha()


class Rescue:
    def __init__(self, allowlist_path: Optional[str] = None,
                 phrases_path: Optional[str] = None,
                 words: Optional[Iterable[str]] = None) -> None:
        self.words: Set[str] = set()
        self.phrases: Set[str] = set()
        self._max_phrase = 0
        if allowlist_path:
            self.load(allowlist_path)
        if phrases_path:
            self.load_phrases(phrases_path)
        if words:
            self.words.update(w.strip().lower() for w in words if w.strip())

    # -- loading ---------------------------------------------------------

    def load(self, path: str) -> int:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    self.words.add(line.lower())
        return len(self.words)

    def load_phrases(self, path: str) -> int:
        if not os.path.exists(path):
            return 0
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    self.phrases.add(line)
                    self._max_phrase = max(self._max_phrase, len(line))
        return len(self.phrases)

    # -- the check -------------------------------------------------------

    def is_rescued(self, text: str, start: int, end: int) -> bool:
        """
        True if the block at [start, end) should be SUPPRESSED.

        Suppressed when the span is strictly inside an allowlisted word or
        phrase. "Strictly" is the important part: a word identical to the
        blocked term must never rescue itself, or adding a term to your
        blocklist would silently stop working.
        """
        if not text:
            return False
        n = len(text)
        if start < 0 or end > n or start >= end:
            return False

        # 1. The word containing the span.
        i = start
        while i > 0 and _is_word_char(text[i - 1]):
            i -= 1
        j = end
        while j < n and _is_word_char(text[j]):
            j += 1
        if j - i > end - start:
            if text[i:j].lower() in self.words:
                return True

        # 2. Phrase shelters, for scripts with no word spacing.
        if self.phrases:
            span_len = end - start
            lo = max(0, start - self._max_phrase + span_len)
            hi = min(n, end + self._max_phrase - span_len)
            window = text[lo:hi]
            for p_start in range(len(window)):
                for p_len in range(span_len + 1, self._max_phrase + 1):
                    if p_start + p_len > len(window):
                        break
                    abs_start = lo + p_start
                    abs_end = abs_start + p_len
                    if abs_start <= start and end <= abs_end and \
                            (abs_end - abs_start) > span_len:
                        if window[p_start:p_start + p_len] in self.phrases:
                            return True
        return False

    def __len__(self) -> int:
        return len(self.words)
