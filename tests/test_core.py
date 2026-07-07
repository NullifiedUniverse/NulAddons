"""
Null's Addons -- unit tests for the pure logic (no network, no live data).

Run with:  python3 -m unittest discover -s tests   (or pytest)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import craft, economy, mechanics  # noqa: E402
from nulladdons.bazaar import Market, Product, parse_product  # noqa: E402
from nulladdons.economy import EvalParams  # noqa: E402


def make_product(pid, bid, ask, demand=10_000_000, supply=10_000_000,
                 bid_amt=5000, ask_amt=5000, bid_orders=20, ask_orders=20):
    return Product(
        product_id=pid, best_bid=bid, best_ask=ask,
        best_bid_amount=bid_amt, best_ask_amount=ask_amt,
        insta_buy_price=ask, insta_sell_price=bid,
        demand_per_week=demand, supply_per_week=supply,
        ask_volume=100_000, bid_volume=100_000,
        ask_orders=ask_orders, bid_orders=bid_orders,
    )


class TestMechanics(unittest.TestCase):
    def test_net_sell_unit_applies_tax(self):
        self.assertAlmostEqual(mechanics.net_sell_unit(100, 0.0125), 98.75)

    def test_flip_prices_front_of_queue(self):
        buy, sell = mechanics.flip_prices(100.0, 110.0)
        self.assertAlmostEqual(buy, 100.1)   # one increment above best bid
        self.assertAlmostEqual(sell, 109.9)  # one increment below best ask

    def test_flip_unit_economics_profit_and_margin(self):
        e = mechanics.flip_unit_economics(100.0, 110.0, tax=0.0125)
        # revenue = 109.9 * 0.9875 = 108.52625 ; cost = 100.1
        self.assertAlmostEqual(e["unit_revenue_net"], 109.9 * 0.9875)
        self.assertGreater(e["unit_profit"], 0)
        self.assertAlmostEqual(e["margin"], e["unit_profit"] / 100.1)

    def test_tight_book_is_unprofitable(self):
        # Spread smaller than 2 increments => negative profit.
        e = mechanics.flip_unit_economics(100.0, 100.1, tax=0.0125)
        self.assertLess(e["unit_profit"], 0)

    def test_orders_needed_ceils_by_limit(self):
        self.assertEqual(mechanics.orders_needed(mechanics.ORDER_UNIT_LIMIT), 1)
        self.assertEqual(mechanics.orders_needed(mechanics.ORDER_UNIT_LIMIT + 1), 2)

    def test_cookie_lowers_tax(self):
        self.assertGreater(mechanics.sell_tax(cookie_buffed=False),
                           mechanics.sell_tax(cookie_buffed=True))


class TestBazaarModel(unittest.TestCase):
    def test_parse_skips_one_sided_market(self):
        blob = {"quick_status": {}, "buy_summary": [], "sell_summary": []}
        self.assertIsNone(parse_product("X", blob))

    def test_parse_disambiguates_hypixel_fields(self):
        blob = {
            "quick_status": {"buyPrice": 7.6, "sellPrice": 7.1,
                             "buyMovingWeek": 5, "sellMovingWeek": 9},
            "buy_summary": [{"amount": 100, "pricePerUnit": 7.5, "orders": 2}],
            "sell_summary": [{"amount": 200, "pricePerUnit": 7.1, "orders": 3}],
        }
        p = parse_product("DIAMOND", blob)
        self.assertEqual(p.best_ask, 7.5)   # from buy_summary (asks)
        self.assertEqual(p.best_bid, 7.1)   # from sell_summary (bids)
        self.assertEqual(p.demand_per_week, 5)   # buyMovingWeek
        self.assertEqual(p.supply_per_week, 9)   # sellMovingWeek
        self.assertTrue(p.has_two_sided_market)

    def test_liquidity_is_thinner_side(self):
        p = make_product("X", 100, 110, demand=3, supply=9)
        self.assertEqual(p.liquidity, 3)


class TestEconomy(unittest.TestCase):
    def test_fill_time_scales_with_quantity(self):
        p = make_product("X", 100, 110, demand=10_080, supply=10_080)  # 1/min each
        f1 = economy.fill_minutes(p, 100, capture=1.0)
        f2 = economy.fill_minutes(p, 200, capture=1.0)
        self.assertAlmostEqual(f2["total_minutes"], 2 * f1["total_minutes"])

    def test_zero_flow_is_infinite(self):
        p = make_product("X", 100, 110, demand=0, supply=10_000)
        self.assertEqual(economy.fill_minutes(p, 10, 1.0)["sell_minutes"],
                         float("inf"))

    def test_size_position_binds_on_smallest_cap(self):
        p = make_product("X", 100, 110, demand=10**9, supply=10**9)
        params = EvalParams(max_fill_minutes=1000, impact_fraction=1.0,
                            max_orders_per_flip=100)
        qty, binding = economy.size_position(p, unit_cost=100.1, params=params,
                                             budget=1000.0)  # tiny budget binds
        self.assertEqual(binding, "capital")
        self.assertEqual(qty, 9)  # floor(1000/100.1)

    def test_confidence_is_bounded(self):
        p = make_product("X", 100, 110)
        score, parts = economy.confidence(p, margin=0.1, history=None)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertIn("spread", parts)


class TestCraftRecursion(unittest.TestCase):
    def build_market(self):
        return Market({
            "DIAMOND": make_product("DIAMOND", 7.0, 7.5),
            "ENCHANTED_DIAMOND": make_product("ENCHANTED_DIAMOND", 1342.0, 1379.0),
            "ENCHANTED_DIAMOND_BLOCK": make_product(
                "ENCHANTED_DIAMOND_BLOCK", 203_000.0, 204_600.0,
                demand=1_000_000, supply=1_000_000),
        })

    def recipes(self):
        return [
            craft.Recipe("ENCHANTED_DIAMOND", (("DIAMOND", 160),)),
            craft.Recipe("ENCHANTED_DIAMOND_BLOCK", (("ENCHANTED_DIAMOND", 160),)),
        ]

    def test_acquisition_prefers_crafting_when_cheaper(self):
        engine = craft.CraftEngine(self.build_market(), self.recipes(),
                                   EvalParams())
        # Crafting an enchanted diamond from 160 diamond (@7.1) beats buying it.
        cost = engine.acquisition_cost("ENCHANTED_DIAMOND")
        self.assertAlmostEqual(cost, 160 * 7.1)
        self.assertEqual(engine._method_memo["ENCHANTED_DIAMOND"], "craft")

    def test_two_step_chain_resolved(self):
        engine = craft.CraftEngine(self.build_market(), self.recipes(),
                                   EvalParams())
        # Block cost = 160 * (160 * 7.1) via the recursive cheapest path.
        cost = engine.acquisition_cost("ENCHANTED_DIAMOND_BLOCK")
        self.assertAlmostEqual(cost, 160 * 160 * 7.1)

    def test_manipulation_ceiling_rejects_absurd_margin(self):
        # Enchanted item "sells" for 100k while raws cost ~1 each -> absurd.
        market = Market({
            "COAL": make_product("COAL", 1.0, 2.0),
            "ENCHANTED_COAL": make_product("ENCHANTED_COAL", 100_000.0, 101_000.0),
        })
        recipes = [craft.Recipe("ENCHANTED_COAL", (("COAL", 160),))]
        plans = craft.find_crafts(market, recipes, EvalParams(max_margin=3.0),
                                  budget=10**9)
        self.assertEqual(plans, [])  # ceiling filters the fake profit

    def test_guaranteed_requires_instant_profit(self):
        # Patient-only craft: buy-order on raws profits (~60% margin, under the
        # absurdity ceiling), but instant-buying the raws at the wide ask loses.
        market = Market({
            "COAL": make_product("COAL", 6.0, 12.0),   # wide raw spread
            "ENCHANTED_COAL": make_product("ENCHANTED_COAL", 1500.0, 1600.0),
        })
        recipes = [craft.Recipe("ENCHANTED_COAL", (("COAL", 160),))]
        patient = craft.find_crafts(market, recipes,
                                    EvalParams(require_instant_profit=False),
                                    budget=10**9)
        strict = craft.find_crafts(market, recipes,
                                   EvalParams(require_instant_profit=True),
                                   budget=10**9)
        self.assertTrue(patient)          # profitable with patient orders
        # instant: 160*12=1920 cost vs ~1481 revenue => loss => filtered
        self.assertEqual(strict, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
