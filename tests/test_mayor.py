"""
Null's Addons -- tests for Mayor/Election economics and the market-movers radar.
Network-free.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import (
    mayor,  # noqa: E402
    mechanics,  # noqa: E402
)
from nulladdons.economy import EvalParams  # noqa: E402
from nulladdons.history import PriceHistory  # noqa: E402


class TestMayorEffects(unittest.TestCase):
    def test_neutral_mayor(self):
        payload = {"mayor": {"name": "Diana",
                             "perks": [{"name": "Huntress' Intuition",
                                        "description": "tracking"}]},
                   "current": {"candidates": [
                       {"name": "Cole", "perks": [{"name": "Prospection",
                                                   "description": "mining xp"}]},
                       {"name": "Marina", "perks": [{"name": "Fishing Festival"}]},
                       {"name": "Finnegan", "perks": [{"name": "Blooming Business"}]},
                   ]}}
        ctx = mayor.build_context(payload)
        self.assertEqual(ctx.name, "Diana")
        self.assertEqual(ctx.tax_multiplier, 1.0)
        self.assertFalse(ctx.tax_free)
        tags = dict(ctx.candidates)
        self.assertIn("mining", tags["Cole"])
        self.assertIn("fishing", tags["Marina"])
        self.assertIn("farming", tags["Finnegan"])
        line = mayor.candidates_line(ctx)
        self.assertIn("Cole", line)

    def test_derpy_removes_tax(self):
        payload = {"mayor": {"name": "Derpy",
                             "perks": [{"name": "Tax Evasion",
                                        "description": "You pay no tax."}]}}
        ctx = mayor.build_context(payload)
        self.assertEqual(ctx.tax_multiplier, 0.0)
        self.assertTrue(ctx.tax_free)
        self.assertTrue(any("TAX" in n.upper() for n in ctx.notes))

    def test_simulate(self):
        self.assertTrue(mayor.simulate("derpy").tax_free)
        cole = mayor.simulate("cole")
        self.assertEqual(cole.tax_multiplier, 1.0)
        self.assertTrue(any("Mining" in n for n in cole.notes))
        self.assertTrue(mayor.simulate("").notes)          # no crash, has a note
        self.assertTrue(mayor.simulate("Unknownguy").simulated)

    def test_none_payload_safe(self):
        ctx = mayor.build_context(None)
        self.assertEqual(ctx.name, "Unknown")
        self.assertEqual(ctx.tax_multiplier, 1.0)

    def test_tax_multiplier_applies_to_params(self):
        # The CLI multiplies params.tax by the mayor multiplier; verify the maths.
        params = EvalParams(tax=mechanics.BASE_BAZAAR_TAX)
        params.tax *= mayor.simulate("derpy").tax_multiplier
        self.assertEqual(params.tax, 0.0)


class TestMovers(unittest.TestCase):
    def test_movers_pct_change(self):
        h = PriceHistory({"A": [100, 110, 120], "B": [100, 50], "C": [100]})
        m = h.movers(min_samples=2)
        self.assertAlmostEqual(m["A"], 0.20)      # 100 -> 120
        self.assertAlmostEqual(m["B"], -0.50)     # 100 -> 50
        self.assertNotIn("C", m)                  # too few samples

    def test_movers_window(self):
        h = PriceHistory({"A": [10, 10, 10, 20]})  # last-2 window: 10 -> 20
        self.assertAlmostEqual(h.movers(window=2, min_samples=2)["A"], 1.0)

    def test_empty_history(self):
        self.assertEqual(PriceHistory({}).movers(), {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
