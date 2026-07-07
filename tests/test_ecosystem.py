"""
Null's Addons -- tests for the ecosystem (income projections + status) and for
crash-resistance against malformed / newly-added items.  Network-free.
"""

import math
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import (accessories, auction, commands, craft, economy,  # noqa: E402
                        flip, projection)
from nulladdons.accounts import AccountContext  # noqa: E402
from nulladdons.bazaar import Market, Product, parse_product  # noqa: E402
from nulladdons.economy import EvalParams  # noqa: E402


def make_product(pid, bid, ask, demand=10_000_000, supply=10_000_000):
    return Product(pid, bid, ask, 5000, 5000, ask, bid, demand, supply,
                   100_000, 100_000, 20, 20)


class TestProjection(unittest.TestCase):
    def _portfolio(self):
        return [SimpleNamespace(coins_per_hour=1_000_000, capital_required=10_000_000),
                SimpleNamespace(coins_per_hour=500_000, capital_required=5_000_000)]

    def test_income_projection(self):
        p = projection.project_bazaar_income(self._portfolio(), active_hours=6)
        self.assertEqual(p.coins_per_hour, 1_500_000)
        self.assertEqual(p.capital_deployed, 15_000_000)
        self.assertEqual(p.per_day, 9_000_000)
        self.assertEqual(p.per_week, 63_000_000)

    def test_eta_and_afford(self):
        self.assertEqual(projection.eta_to_coins(100, 100, 50), 0.0)     # reached
        self.assertEqual(projection.eta_to_coins(0, 500, 100), 5.0)      # hours
        self.assertEqual(projection.hours_to_earn(300, 100), 3.0)
        self.assertEqual(projection.hours_to_earn(300, 0), math.inf)     # no income

    def test_human_duration(self):
        self.assertEqual(projection.human_duration(0), "already reached")
        self.assertEqual(projection.human_duration(math.inf), "never (no income)")
        self.assertIn("min", projection.human_duration(0.5))
        self.assertIn("days", projection.human_duration(30, active_hours=6))


class TestStatusRender(unittest.TestCase):
    def _account(self, **kw):
        base = dict(name="Acc", username="acc", budget=50_000_000, risk="balanced",
                    params=EvalParams(), live=True, active_hours=6,
                    coin_goal=500_000_000, mp_goal=1500)
        base.update(kw)
        return AccountContext(**base)

    def test_status_with_and_without_positions(self):
        acc = self._account()
        recomb = SimpleNamespace(label="Recomb Rare", mp_gain=4, cost=11_000_000,
                                 coins_per_mp=2_750_000)
        mp_plan = {"picks": [], "recombs": [recomb], "owned_count": 3}
        # Empty portfolio must not crash.
        s0 = commands.render_status(acc, [], mp_plan, ah={"recent_sales": []})
        self.assertIn("ECOSYSTEM STATUS", s0)
        # With a real flip in the portfolio.
        market = Market({"E": make_product("E", 100, 140)})
        params = EvalParams(min_liquidity=0, min_coins_per_hour=0, min_confidence=0)
        plans = flip.find_flips(market, params, 10**9)
        s1 = commands.render_status(acc, plans, mp_plan,
                                    ah={"recent_sales": [("HYPERION", 10**9)],
                                        "listings": None})
        self.assertIn("Do this now", s1)
        self.assertIn("income potential", s1)


class TestCrashResistance(unittest.TestCase):
    def test_garbage_bazaar_payload(self):
        payload = {"lastUpdated": 1, "products": {
            "GOOD": {"quick_status": {"buyPrice": 10, "sellPrice": 8,
                                      "buyMovingWeek": 1e6, "sellMovingWeek": 1e6},
                     "buy_summary": [{"pricePerUnit": 10, "amount": 100}],
                     "sell_summary": [{"pricePerUnit": 8, "amount": 100}]},
            "NULLS": {"quick_status": {"buyPrice": None, "sellPrice": None},
                      "buy_summary": [{"pricePerUnit": None, "amount": None}],
                      "sell_summary": [{"pricePerUnit": None}]},
            "STRS": {"buy_summary": [{"pricePerUnit": "x", "amount": "y"}],
                     "sell_summary": [{"pricePerUnit": "z"}]},
            "NEWKEYS": {"quick_status": {"buyPrice": 12, "sellPrice": 9, "brand": {}},
                        "buy_summary": [{"pricePerUnit": 12, "amount": 5, "new": 1}],
                        "sell_summary": [{"pricePerUnit": 9, "amount": 5}],
                        "top_new_key": [1, 2]},
            "BADSUMMARY": {"buy_summary": "oops", "sell_summary": None},
            "ITEMNOTDICT": {"buy_summary": [42], "sell_summary": [["x"]]},
            "NOTADICT": "string",
        }}
        market = Market.from_api(payload)     # must not raise
        self.assertIn("GOOD", market.products)
        self.assertIn("NEWKEYS", market.products)
        self.assertNotIn("NULLS", market.products)   # invalid price -> dropped
        # Downstream engines run clean on the survivors.
        flip.find_flips(market, EvalParams(min_liquidity=0, min_coins_per_hour=0,
                                           min_confidence=0), 10**9)

    def test_parse_product_never_raises_on_weird_input(self):
        for bad in [None, "x", 5, {}, {"buy_summary": [None], "sell_summary": [None]}]:
            self.assertIsNone(parse_product("X", bad))

    def test_loaders_skip_malformed(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            rp, ap = os.path.join(d, "r.json"), os.path.join(d, "a.json")
            with open(rp, "w") as fh:
                json.dump({"recipes": [
                    {"output": "ENCHANTED_X", "inputs": [["Y", 160]]},
                    {"output": "", "inputs": []}, {"inputs": [["Z", 1]]},
                    {"output": "B", "inputs": [["Q", "notint"]]}, "str", 9,
                ]}, fh)
            with open(ap, "w") as fh:
                json.dump({"accessories": [
                    {"id": "OK", "family": "f", "rarity": "epic"},
                    {"id": "", "rarity": "epic"}, {"id": "NR"}, "s", 3,
                ]}, fh)
            self.assertEqual([r.output for r in craft.load_recipes(rp)], ["ENCHANTED_X"])
            self.assertEqual([a.id for a in accessories.load_accessories(ap)], ["OK"])

    def test_extract_stats_survives_weird_types(self):
        from nulladdons import progress
        prof = {"banking": {"balance": {"weird": 1}}}          # bank is a dict
        member = {"coin_purse": "notnum",                       # purse a string
                  "collection": {"X": {"obj": 1}, "Y": 5},      # a dict value
                  "player_data": {"experience": {"SKILL_COMBAT": {"bad": 1}}},
                  "slayer_bosses": {"zombie": {"xp": "NaN"}},
                  "pets": 123,                                   # not a list
                  "dungeons": {"dungeon_types": {"catacombs": {"experience": None}}}}
        s = progress.extract_stats(prof, member, None)           # must not raise
        self.assertEqual(s["coins"], 0)
        self.assertIsInstance(s["collections_sum"], int)
        self.assertEqual(s["pets"], 0)
        self.assertEqual(s["catacombs_xp"], 0)

    def test_malformed_auctions_dont_crash(self):
        self.assertEqual(auction.sales_from_ended(
            [{"auction_id": "a", "price": None, "item_bytes": "garbage"},
             {"item_bytes": 123}]), [])
        summ = auction.player_listing_summary(
            [{"end": None, "item_bytes": "x"}, "notadict",
             {"highest_bid_amount": None, "starting_bid": None, "end": "bad"}])
        self.assertIsInstance(summ.active, int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
