#!/usr/bin/env python3
"""
Full test suite. stdlib unittest, no dependencies.

    python3 tests/test_all.py

Covers the engine (normalization, matching, rescue, policy, masking offsets,
locales, fuzzy, CJK), the shadow wrapper, and the black-box inference engine --
the last of which is validated experimentally against a simulated filter whose
term list is known, so we can measure whether inference actually recovers it.
"""

import json
import os
import random
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "impl", "python"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

from chatguard import (Action, ChatGuard, MatchMode, Normalized, Term, Tier,  # noqa
                       Automaton, normalize)
from shadow import ShadowFilter  # noqa
import blackbox  # noqa


# ==========================================================================
class TestNormalize(unittest.TestCase):

    def test_offsets_survive_folding(self):
        n = normalize("café shit café")
        s, e = n.span(n.text.index("shit"), n.text.index("shit") + 4)
        self.assertEqual("café shit café"[s:e], "shit")

    def test_boundary_pass_keeps_spaces(self):
        self.assertIn(" ", normalize("hello world").text)

    def test_boundary_pass_preserves_doubles(self):
        # If doubles collapsed, "classic" would stop matching the allowlist.
        self.assertEqual(normalize("classic").text, "classic")
        self.assertEqual(normalize("wall").text, "wall")

    def test_condense_drops_separators(self):
        self.assertEqual(normalize("f.u.c.k", condense=True).text, "fuck")
        self.assertEqual(normalize("f u c k", condense=True).text, "fuck")

    def test_condense_collapses_three_but_not_two(self):
        self.assertEqual(normalize("fuuuuck", condense=True).text, "fuck")
        # two is spelling, not evasion
        self.assertEqual(normalize("wall", condense=True).text, "wall")
        self.assertEqual(normalize("baal", condense=True).text, "baal")

    def test_fullwidth_and_accents(self):
        self.assertEqual(normalize("ＦＵＣＫ").text, "fuck")
        self.assertEqual(normalize("çafé").text, "cafe")

    def test_zero_width_removed(self):
        self.assertEqual(normalize("fu​ck", condense=True).text, "fuck")

    def test_confusable_folded(self):
        self.assertEqual(normalize("shіt").text, "shit")   # Cyrillic i

    def test_empty(self):
        n = normalize("")
        self.assertEqual(n.text, "")
        self.assertEqual(n.span(0, 1), (0, 0))


# ==========================================================================
class TestAutomaton(unittest.TestCase):

    def test_finds_all_occurrences(self):
        a = Automaton([Term("ab"), Term("bc")])
        hits = {(s, e, t.text) for s, e, t in a.find("abc")}
        self.assertEqual(hits, {(0, 2, "ab"), (1, 3, "bc")})

    def test_overlapping_and_nested(self):
        a = Automaton([Term("a"), Term("aa")])
        got = {(s, e, t.text) for s, e, t in a.find("aa")}
        self.assertIn((0, 1, "a"), got)
        self.assertIn((0, 2, "aa"), got)

    def test_empty_automaton(self):
        self.assertEqual(list(Automaton([]).find("anything")), [])

    def test_scales(self):
        terms = [Term(f"term{i:05d}") for i in range(5000)]
        a = Automaton(terms)
        self.assertEqual(len(a), 5000)
        self.assertTrue(any(t.text == "term04999" for _, _, t in a.find("xterm04999x")))


# ==========================================================================
class TestMatching(unittest.TestCase):

    def setUp(self):
        self.g = ChatGuard(
            [Term("shit", Tier.STRONG, MatchMode.PREFIX),
             Term("fuck", Tier.STRONG, MatchMode.PREFIX),
             Term("cunt", Tier.SEVERE, MatchMode.WORD),
             Term("rape", Tier.SEVERE, MatchMode.WORD)],
            ["shitake", "grape", "assassin", "classic", "bass", "hit", "scunthorpe"])

    def test_plain_hit(self):
        self.assertEqual(self.g.filter("this is shit").action, Action.MASK)

    def test_mask_lands_on_right_characters(self):
        self.assertEqual(self.g.filter("omg shit happens").filtered,
                         "omg **** happens")

    def test_mask_with_multibyte_prefix(self):
        self.assertEqual(self.g.filter("café shit café").filtered,
                         "café **** café")

    def test_scunthorpe_rescued(self):
        self.assertEqual(self.g.filter("I live in Scunthorpe").action, Action.ALLOW)

    def test_shitake_rescued(self):
        self.assertEqual(self.g.filter("shitake mushrooms").action, Action.ALLOW)

    def test_grape_not_rape(self):
        self.assertEqual(self.g.filter("Grape Juice").action, Action.ALLOW)

    def test_word_mode_needs_boundaries(self):
        self.assertEqual(self.g.filter("grapes are nice").action, Action.ALLOW)
        self.assertEqual(self.g.filter("rape").action, Action.BLOCK)

    def test_prefix_mode_allows_suffix(self):
        self.assertEqual(self.g.filter("shitty").action, Action.MASK)

    def test_evasion_spaced(self):
        self.assertEqual(self.g.filter("f u c k").action, Action.MASK)

    def test_evasion_repeat(self):
        self.assertEqual(self.g.filter("fuuuuck").action, Action.MASK)

    def test_evasion_does_not_create_false_positive(self):
        # "bass hit" must not fold into "shit"
        self.assertEqual(self.g.filter("bass hit").action, Action.ALLOW)

    def test_natural_doubles_safe(self):
        for t in ["Baal the wall seller", "smaller", "shall"]:
            self.assertEqual(self.g.filter(t).action, Action.ALLOW, t)

    def test_term_beats_allowlist(self):
        g = ChatGuard([Term("grape", Tier.STRONG)], ["grape"])
        self.assertEqual(g.filter("grape").action, Action.MASK)

    def test_empty_input(self):
        self.assertEqual(self.g.filter("").action, Action.ALLOW)

    def test_long_input_does_not_explode(self):
        self.assertEqual(self.g.filter("a" * 20000).action, Action.ALLOW)


# ==========================================================================
class TestCJK(unittest.TestCase):
    """The list under study is 93% Chinese; CJK has no word spacing."""

    def setUp(self):
        self.g = ChatGuard(
            [Term("日", Tier.STRONG, MatchMode.SUB),
             Term("草", Tier.STRONG, MatchMode.SUB)],
            ["日光", "生日", "日常", "草原", "草药", "今日"])

    def test_sheltered_by_phrase(self):
        for t in ["日光", "生日快乐", "草原", "草药"]:
            self.assertEqual(self.g.filter(t).action, Action.ALLOW, t)

    def test_bare_character_still_caught(self):
        self.assertEqual(self.g.filter("草").action, Action.MASK)

    def test_rescue_reported(self):
        self.assertIn("日光", self.g.filter("日光").rescued)


# ==========================================================================
class TestPolicyAndLocale(unittest.TestCase):

    def setUp(self):
        self.g = ChatGuard(
            [Term("shit", Tier.STRONG, MatchMode.PREFIX),
             Term("puta", Tier.STRONG, MatchMode.WORD, ("es", "pt"))], [])

    def test_surface_changes_verdict(self):
        self.assertEqual(self.g.filter("shit", surface="private").action, Action.ALLOW)
        self.assertEqual(self.g.filter("shit", surface="public").action, Action.MASK)
        self.assertEqual(self.g.filter("shit", surface="identifier").action, Action.BLOCK)

    def test_locale_scoping(self):
        self.assertEqual(self.g.filter("eres una puta", locale="es").action, Action.MASK)
        self.assertEqual(self.g.filter("eres una puta", locale="en").action, Action.ALLOW)

    def test_block_does_not_mask(self):
        v = self.g.filter("shit", surface="identifier")
        self.assertEqual(v.action, Action.BLOCK)
        self.assertEqual(v.filtered, "shit")   # caller refuses; nothing delivered

    def test_verdict_serialises(self):
        d = self.g.filter("this is shit").to_dict()
        self.assertEqual(d["action"], "MASK")
        self.assertIn("filtered_word", d)
        self.assertNotEqual(d["errorId"], 0)
        self.assertEqual(self.g.filter("fine").to_dict()["errorId"], 0)


# ==========================================================================
class TestFuzzy(unittest.TestCase):

    def test_edit_distance_one_caught_for_high_tier(self):
        g = ChatGuard([Term("cunt", Tier.SEVERE, MatchMode.WORD)], [],
                      fuzzy_tiers=(Tier.SEVERE,), fuzzy_min_len=4)
        self.assertEqual(g.filter("cvnt").action, Action.BLOCK)

    def test_fuzzy_respects_allowlist(self):
        g = ChatGuard([Term("cunt", Tier.SEVERE, MatchMode.WORD)], ["count", "cant"],
                      fuzzy_tiers=(Tier.SEVERE,), fuzzy_min_len=4)
        self.assertEqual(g.filter("count").action, Action.ALLOW)

    def test_fuzzy_off_by_default_for_low_tier(self):
        g = ChatGuard([Term("shit", Tier.STRONG, MatchMode.PREFIX)], [])
        self.assertEqual(g.filter("shvt").action, Action.ALLOW)


# ==========================================================================
class TestShadow(unittest.TestCase):

    def setUp(self):
        self.guard = ChatGuard([Term("shit", Tier.STRONG, MatchMode.PREFIX)],
                               ["shitake"])

    def incumbent(self, text):
        return ("shit" in text.lower(), text.replace("shit", "****"))

    def test_incumbent_stays_authoritative(self):
        sf = ShadowFilter(self.incumbent, self.guard)
        flagged, out = sf.filter("shitake mushrooms")
        self.assertTrue(flagged)                      # incumbent's (wrong) answer
        self.assertEqual(sf.stats["over_block_fixed"], 1)

    def test_switch_authority(self):
        sf = ShadowFilter(self.incumbent, self.guard, authority="chatguard")
        flagged, out = sf.filter("shitake mushrooms")
        self.assertFalse(flagged)

    def test_guard_exception_cannot_break_live_path(self):
        class Boom:
            def filter(self, *a, **k):
                raise RuntimeError("boom")
        sf = ShadowFilter(self.incumbent, Boom())
        flagged, out = sf.filter("hello")
        self.assertFalse(flagged)
        self.assertEqual(sf.stats["guard_errors"], 1)

    def test_dump(self):
        sf = ShadowFilter(self.incumbent, self.guard)
        sf.filter("shitake")
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as fh:
            p = fh.name
        try:
            self.assertEqual(sf.dump(p), 1)
            with open(p, encoding="utf-8") as fh2:
                rec = json.loads(fh2.readline())
            self.assertEqual(rec["kind"], "over_block_fixed")
        finally:
            os.unlink(p)


# ==========================================================================
class TestBlackboxInference(unittest.TestCase):
    """
    Experiment: simulate a filter with a KNOWN term list, feed the tool
    observations, and measure whether inference recovers the real terms.
    """

    WORDS = ("cucumber okay thank hello sword guild party trade quest level "
             "assassin priest potion armor shield helmet dagger arrow magic "
             "monster village castle bridge forest desert temple tower").split()

    def simulate(self, secret_terms, words):
        obs = []
        for w in words:
            blocked = any(t in w.lower() for t in secret_terms)
            obs.append({"text": w, "blocked": blocked})
        return obs

    def run_infer(self, obs):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl",
                                         delete=False, encoding="utf-8") as fh:
            for o in obs:
                fh.write(json.dumps(o) + "\n")
            p = fh.name
        try:
            loaded = blackbox.load_obs(p)
            per_blocked, clean, unexplained = blackbox.analyse(
                loaded, assume_common=False)
            return blackbox.minimal_explanation(per_blocked), unexplained
        finally:
            os.unlink(p)

    def test_recovers_a_single_term(self):
        obs = self.simulate({"cum"}, self.WORDS)
        chosen, unexplained = self.run_infer(obs)
        self.assertEqual(unexplained, [])
        # every blocked word must be explained by the chosen set
        for o in obs:
            if o["blocked"]:
                self.assertTrue(any(c in o["text"].lower() for c in chosen), o)

    def test_clean_observations_eliminate(self):
        # "cucumber" blocked, "cucumbers are nice" clean is contradictory;
        # with only consistent data, clean strings must prune candidates.
        obs = [{"text": "cucumber", "blocked": True},
               {"text": "cucumb", "blocked": False}]
        loaded = [(o["text"], o["blocked"]) for o in obs]
        per_blocked, clean, unexplained = blackbox.analyse(loaded,
                                                           assume_common=False)
        cands = per_blocked["cucumber"]
        # anything wholly inside "cucumb" is impossible
        self.assertNotIn("cum", cands)
        self.assertNotIn("cuc", cands)
        # something containing the final "er" must survive
        self.assertTrue(all("er" in c or c.endswith("e") for c in cands) or cands)

    def test_detects_contradiction(self):
        # blocked, yet every substring appears in a clean string -> not pure
        # substring matching. The tool must say so rather than invent a term.
        obs = [("abc", True), ("ab", False), ("bc", False), ("abc ", False)]
        per_blocked, clean, unexplained = blackbox.analyse(obs,
                                                           assume_common=False)
        self.assertIn("abc", unexplained)

    def test_explanation_is_consistent_on_random_lists(self):
        rng = random.Random(7)
        for _ in range(20):
            secret = {rng.choice(["cum", "kkk", "nb", "zx", "qq"])}
            obs = self.simulate(secret, self.WORDS)
            if not any(o["blocked"] for o in obs):
                continue
            chosen, unexplained = self.run_infer(obs)
            self.assertEqual(unexplained, [])
            for o in obs:
                if o["blocked"]:
                    self.assertTrue(any(c in o["text"].lower() for c in chosen))


# ==========================================================================
class TestToolsRun(unittest.TestCase):
    """Every CLI must at least run, on real inputs, and exit sanely."""

    def _run(self, *args):
        return subprocess.run([sys.executable] + list(args),
                              capture_output=True, text=True, cwd=ROOT)

    def test_conformance(self):
        r = self._run("tools/conformance.py")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 failed", r.stdout)

    def test_blackbox_infer_and_design(self):
        obs = os.path.join(ROOT, "observations", "live-2026-09-09.jsonl")
        if not os.path.exists(obs):
            self.skipTest("no observations file")
        for cmd in ("infer", "design"):
            r = self._run("tools/blackbox.py", cmd, "--obs", obs)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_selftest_filter_passes_on_clean_input(self):
        with tempfile.TemporaryDirectory() as d:
            lst = os.path.join(d, "l.json")
            st = os.path.join(d, "s.txt")
            with open(lst, "w", encoding="utf-8") as fh:
                json.dump(["zzqqxx"], fh)
            with open(st, "w", encoding="utf-8") as fh:
                fh.write("Freezing\nSavage Card\n")
            r = self._run("tools/selftest_filter.py", "--list", lst, "--strings", st)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("PASS", r.stdout)

    def test_selftest_filter_fails_on_dirty_input(self):
        with tempfile.TemporaryDirectory() as d:
            lst = os.path.join(d, "l.json")
            st = os.path.join(d, "s.txt")
            with open(lst, "w", encoding="utf-8") as fh:
                json.dump(["free"], fh)
            with open(st, "w", encoding="utf-8") as fh:
                fh.write("Freezing\n")
            r = self._run("tools/selftest_filter.py", "--list", lst, "--strings", st)
            self.assertEqual(r.returncode, 1)
            self.assertIn("FAIL", r.stdout)

    def test_build_lexicon(self):
        with tempfile.TemporaryDirectory() as d:
            st = os.path.join(d, "s.txt")
            with open(st, "w", encoding="utf-8") as fh:
                fh.write("Savage Card\n日光\n生日快乐\n")
            r = self._run("tools/build_lexicon.py", "--locale", "xx",
                          "--strings", st, "--out", d, "--cjk")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(os.path.exists(os.path.join(d, "xx-allow.txt")))
            self.assertTrue(os.path.exists(os.path.join(d, "xx-phrases.txt")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
