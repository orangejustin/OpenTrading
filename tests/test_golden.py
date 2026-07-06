#!/usr/bin/env python3
"""
Golden-file regression tests (P1-2) — the numbers that drive real sizing.

Everything here is pure math on FIXED inputs: no network, no keys, no LLM.
If a refactor changes any of these outputs, a decision the desk would have
made changes with it — that is exactly what these tests exist to catch.

    python3 -m unittest discover tests -v
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("tools/options", "tools/quant", "tools/china", "tools/macro", "tools/web"):
    sys.path.insert(0, str(ROOT / sub))

import cn            # noqa: E402
import opt           # noqa: E402
import quant         # noqa: E402


class TestOccAndGamma(unittest.TestCase):
    TODAY = date(2026, 7, 3)

    def test_parse_occ(self):
        root, exp, cp, strike = opt.parse_occ("SPY260615C00500000")
        self.assertEqual((root, exp, cp, strike), ("SPY", "2026-06-15", "C", 500.0))
        root, exp, cp, strike = opt.parse_occ("NVDA260710P00190500")
        self.assertEqual((root, exp, cp, strike), ("NVDA", "2026-07-10", "P", 190.5))

    def _chain(self):
        # fixed 6-row chain: 2 near calls, 1 near put, 1 far call (excluded by
        # dte), 1 expired (excluded), 1 unparsable (skipped)
        return [
            {"option": "TST260710C00100000", "open_interest": 1000, "volume": 50, "gamma": 0.02},
            {"option": "TST260710C00110000", "open_interest": 500, "volume": 20, "gamma": 0.01},
            {"option": "TST260710P00090000", "open_interest": 800, "volume": 40, "gamma": 0.015},
            {"option": "TST261218C00120000", "open_interest": 9999, "volume": 1, "gamma": 0.5},
            {"option": "TST260601C00100000", "open_interest": 7777, "volume": 1, "gamma": 0.5},
            {"option": "garbage", "open_interest": 1, "volume": 1, "gamma": 1.0},
        ]

    def test_aggregate_golden(self):
        call_oi, put_oi, call_vol, put_vol, gex, cw, pw = \
            opt.aggregate(self._chain(), 30, self.TODAY, spot=100.0)
        self.assertEqual((call_oi, put_oi, call_vol, put_vol), (1500, 800, 70, 40))
        # net gamma = 0.02*1000 + 0.01*500 - 0.015*800 = 13.0
        # $GEX = 13.0 * 100 * 100^2 * 0.01 = 130_000
        self.assertAlmostEqual(gex, 130_000.0, places=6)
        self.assertEqual((cw, pw), (100.0, 90.0))   # call wall = max +gamma, put wall = min

    def test_aggregate_negative_gex(self):
        rows = [{"option": "TST260710P00095000", "open_interest": 2000, "volume": 5, "gamma": 0.03}]
        *_, gex, cw, pw = opt.aggregate(rows, 30, self.TODAY, spot=100.0)
        self.assertAlmostEqual(gex, -0.03 * 2000 * 100 * 100 * 100 * 0.01, places=6)
        self.assertEqual(pw, 95.0)


class TestQuantMath(unittest.TestCase):
    # deterministic synthetic series: trending sawtooth, 60 sessions
    SERIES = [100 + 0.4 * i + (3 if i % 5 == 0 else -1 if i % 3 == 0 else 0)
              for i in range(60)]

    def test_features_shape_and_values(self):
        f = quant.features_at(self.SERIES, 40)
        self.assertEqual(len(f), 6)
        # golden values, frozen 2026-07-05 (update ONLY with a reviewed reason)
        expected = [0.017094, 0.072072, 0.174797, 0.017778, 0.020959, 0.5]
        for got, want in zip(f, expected):
            self.assertAlmostEqual(got, want, places=4)

    def test_logistic_deterministic_and_learns(self):
        X = [[0.1, 0.2], [0.9, 0.8], [0.15, 0.1], [0.85, 0.9], [0.2, 0.25], [0.8, 0.75]]
        y = [0, 1, 0, 1, 0, 1]
        b1, w1 = quant.train_logistic(X, y)           # returns (bias, weights)
        b2, w2 = quant.train_logistic(X, y)
        self.assertEqual((b1, w1), (b2, w2))          # no hidden randomness
        hi = quant._sigmoid(b1 + sum(w * x for w, x in zip(w1, [0.9, 0.9])))
        lo = quant._sigmoid(b1 + sum(w * x for w, x in zip(w1, [0.1, 0.1])))
        self.assertGreater(hi, 0.5)
        self.assertLess(lo, 0.5)


class TestMacroBias(unittest.TestCase):
    def test_bias_bands(self):
        sys.path.insert(0, str(ROOT / "tools/macro"))
        import macro
        self.assertIn("CALLS", macro.bias_from_score(3))
        self.assertIn("PUTS", macro.bias_from_score(-3))
        self.assertIn("NEUTRAL", macro.bias_from_score(0))


class TestCnNormalizer(unittest.TestCase):
    CASES = {
        "600519": "1.600519", "600519.SH": "1.600519", "600519.SS": "1.600519",
        "sh600519": "1.600519", "000001.SZ": "0.000001", "sz399001": "0.399001",
        "hk00700": "116.00700", "0700.HK": "116.00700", "HK.00700": "116.00700",
        "00700": "116.00700", "shcomp": "1.000001", "沪深300": "1.000300",
        "688008": "1.688008", "300394": "0.300394",
    }

    def test_all_spellings(self):
        for raw, want in self.CASES.items():
            self.assertEqual(cn.to_secid(raw), want, f"to_secid({raw!r})")


class TestFallbackAnalysis(unittest.TestCase):
    def test_rules(self):
        import server
        up_ctx = {"technicals": {"last": 100.0, "ma10": 99.0, "ma20": 96.0,
                                 "hi20": 104.0, "lo20": 92.0, "rsi14": 55.0}}
        r = server._fallback_analysis(up_ctx)
        self.assertEqual(r["action"], "BUY")
        self.assertTrue(r["fallback"])
        down_ctx = {"technicals": {"last": 88.0, "ma10": 93.0, "ma20": 96.0,
                                   "hi20": 104.0, "lo20": 87.0, "rsi14": 28.0}}
        self.assertEqual(server._fallback_analysis(down_ctx)["action"], "WATCH")
        hot_ctx = {"technicals": {"last": 110.0, "ma10": 105.0, "ma20": 100.0,
                                  "hi20": 111.0, "lo20": 95.0, "rsi14": 75.0}}
        self.assertEqual(server._fallback_analysis(hot_ctx)["action"], "REDUCE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
