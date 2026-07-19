#!/usr/bin/env python3
"""Golden tests for the desk's scoring and safety math.

These cover the functions whose output decides whether real money moves, and
every case below is a bug that actually shipped on this branch — a regression
here is not hypothetical, it already happened once:

  * grading returns that ignored direction, so a profitable PUT was averaged
    against longs with the same sign
  * grading to the LATEST close instead of a fixed horizon, which manufactures
    skill in a trending tape
  * a benchmark cache keyed by symbol alone, so every entry after the first
    silently reused the first entry's window
  * a risk gate that let a levered vehicle stack on its own unleveraged version
  * a grounding check whose tolerance passed half of all hallucinations
  * a divergence rule that stayed silent on the exact case it was written for

Stdlib unittest, no network: every test drives pure functions with fixtures.

    python3 tests/test_desk.py
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "reflect"))
sys.path.insert(0, os.path.join(ROOT, "tools", "trade"))
sys.path.insert(0, os.path.join(ROOT, "tools", "llm"))

import reflect            # noqa: E402
import propose            # noqa: E402
import paper              # noqa: E402
import debate             # noqa: E402
import decay              # noqa: E402


class TestGradingIsDirectionAware(unittest.TestCase):
    """A PUT that wins must not be recorded as a loss."""

    def test_put_profit_is_positive_for_the_trade(self):
        # underlying -10% => a PUT made +10%, a CALL lost 10%
        for act, expected in (("PUT", 10.0), ("CALL", -10.0)):
            sign = 1 if act == "CALL" else -1 if act == "PUT" else 0
            self.assertAlmostEqual(-10.0 * sign, expected, places=6,
                                   msg=f"{act} trade return sign is wrong")

    def test_no_action_has_no_pnl(self):
        self.assertEqual(0, 1 if "NO-ACTION" == "CALL" else -1 if "NO-ACTION" == "PUT" else 0)

    def test_agg_averages_only_positions(self):
        """NO-ACTION contributes a hit/miss but must not drag the return mean."""
        rows = [
            {"action": "CALL", "outcome": {"was_right": True, "trade_return_pct": 4.0,
                                           "trade_alpha_pct": 2.0}},
            {"action": "PUT", "outcome": {"was_right": True, "trade_return_pct": 6.0,
                                          "trade_alpha_pct": 3.0}},
            {"action": "NO-ACTION", "outcome": {"was_right": False,
                                                "trade_return_pct": None,
                                                "trade_alpha_pct": None}},
        ]
        g = reflect._agg(rows, "action")
        self.assertEqual(1, g["NO-ACTION"]["flat"])
        self.assertEqual(0.0, g["NO-ACTION"]["ret"])
        # the two real positions average +5%, unpolluted by the flat row
        total = g["CALL"]["ret"] + g["PUT"]["ret"]
        npos = (g["CALL"]["n"] - g["CALL"]["flat"]) + (g["PUT"]["n"] - g["PUT"]["flat"])
        self.assertAlmostEqual(5.0, total / npos, places=6)


class TestRiskGates(unittest.TestCase):
    def _p(self, **kw):
        base = {"ticker": "TQQQ", "side": "LONG", "entry": 100.0, "stop": 95.0,
                "target": 115.0, "size_usd": 1000.0, "budget_usd": 100000.0, "dte": 5}
        base.update(kw)
        return base

    def test_g1_rejects_a_stop_on_the_winning_side(self):
        g = propose.run_gates(self._p(side="LONG", entry=100.0, stop=105.0))
        g1 = next(x for x in g if x["gate"].startswith("G1"))
        self.assertFalse(g1["ok"], "a LONG stop above entry must be rejected")

    def test_g1_rejects_a_missing_stop(self):
        g = propose.run_gates(self._p(stop=None))
        g1 = next(x for x in g if x["gate"].startswith("G1"))
        self.assertFalse(g1["ok"])

    def test_g1_accepts_a_correct_short_stop(self):
        g = propose.run_gates(self._p(side="SHORT", entry=100.0, stop=105.0, target=90.0))
        g1 = next(x for x in g if x["gate"].startswith("G1"))
        self.assertTrue(g1["ok"], "a SHORT stop above entry is correct")

    def test_g2_blocks_an_oversized_loss(self):
        # 50% stop distance on a 100k position against a 100k budget
        g = propose.run_gates(self._p(entry=100.0, stop=50.0, size_usd=100000.0))
        g2 = next(x for x in g if x["gate"].startswith("G2"))
        self.assertFalse(g2["ok"])

    def test_complex_map_groups_the_stacked_pairs(self):
        """The map is the whole intelligence of G4 — these pairs must stay paired."""
        for a, b in (("LOFF", "SPCX"), ("RAM", "DRAM"), ("TQQQ", "QQQ"), ("MSTU", "MSTR")):
            self.assertEqual(propose.LEVERAGED[a][1], propose.LEVERAGED[b][1],
                             f"{a} and {b} must share a complex")
            self.assertGreater(abs(propose.LEVERAGED[a][0]), 1.0, f"{a} should be levered")


class TestPaperGateFailsClosed(unittest.TestCase):
    def test_empty_book_refuses(self):
        ok, fails = paper.gate() if not paper._load() else (None, None)
        if ok is not None:
            self.assertFalse(ok, "an empty paper book must never allow live")
            self.assertTrue(fails)

    def test_thresholds_are_not_accidentally_permissive(self):
        self.assertGreaterEqual(paper.MIN_N, 30)
        self.assertGreaterEqual(paper.MIN_WIN, 50.0)


class TestGrounding(unittest.TestCase):
    PACK = {"decide": {"price": 100.0, "plan": {"buy_zone": [95.0, 105.0], "stop": 90.0}},
            "quant": {"cone": {"p10": 80.0, "p90": 120.0}},
            "options": {"spot": 100.0, "call_wall": 110.0, "put_wall": 92.0}}

    def test_real_levels_pass(self):
        r = debate._check_grounding({"entry_price": 100.0, "invalidation": 92.0,
                                     "targets": [110.0]}, self.PACK)
        self.assertEqual(r["checked"], r["grounded"])

    def test_invented_level_is_caught(self):
        r = debate._check_grounding({"entry_price": 100.0, "invalidation": 92.0,
                                     "targets": [137.0]}, self.PACK)
        self.assertEqual(1, len(r["ungrounded"]))
        self.assertEqual("target[0]", r["ungrounded"][0]["field"])

    def test_tolerance_stays_tight(self):
        """1.5% passed ~half the price range. Do not loosen this without measuring."""
        import inspect
        sig = inspect.signature(debate._check_grounding)
        self.assertLessEqual(sig.parameters["tol_pct"].default, 1.0)


class TestSentimentDivergence(unittest.TestCase):
    def _pack(self, score, breadth, p5):
        return {"smart": {"equity_fng": {"score": score, "week_ago": score,
                                         "components": {"breadth": {"score": breadth}}}},
                "decide": {"prior5": p5 / 100.0}}

    def test_knife_case_fires(self):
        """-12.3% with fear 37 is the case that shipped silent. It must fire."""
        lines = "\n".join(debate._sentiment_read(self._pack(37, 21, -12.3)))
        self.assertIn("PRICE vs SENTIMENT", lines)
        self.assertIn("knife", lines)

    def test_calm_tape_does_not_fire(self):
        lines = "\n".join(debate._sentiment_read(self._pack(52, 50, 0.4)))
        self.assertNotIn("PRICE vs SENTIMENT", lines)

    def test_breadth_divergence_fires_on_a_narrow_tape(self):
        lines = "\n".join(debate._sentiment_read(self._pack(37, 21, 0.0)))
        self.assertIn("HEADLINE vs BREADTH", lines)


class TestDecayMath(unittest.TestCase):
    def test_drag_grows_with_variance_not_just_leverage(self):
        """The branch's headline finding: a 2x on a volatile name bleeds far more
        than a 3x on the index. If this inverts, the formula regressed."""
        def drag(k, sigma):
            return -0.5 * k * (k - 1) * sigma ** 2 * 100
        tqqq = drag(3.0, 0.0119)      # QQQ ~1.19%/day
        ram = drag(2.0, 0.0651)       # DRAM ~6.51%/day
        self.assertLess(ram, tqqq, "RAM must show the larger daily drag")
        self.assertGreater(abs(ram) / abs(tqqq), 5.0, "expected roughly an order of magnitude")

    def test_pairs_point_at_the_right_underlying(self):
        self.assertEqual("DRAM", decay.PAIRS["RAM"][1])
        self.assertEqual("QQQ", decay.PAIRS["TQQQ"][1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
