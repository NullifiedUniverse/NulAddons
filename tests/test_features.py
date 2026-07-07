"""
Null's Addons -- tests for the second-wave features: congestion-aware fill,
blacklist filtering, the Magical Power engine, NBT decoding and Discord alerts.
Network-free.  Run with: python3 -m unittest discover -s tests
"""

import base64
import gzip
import os
import struct
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import accessories, craft, economy, flip, nbt, notify  # noqa: E402
from nulladdons.bazaar import Market, Product  # noqa: E402
from nulladdons.economy import EvalParams  # noqa: E402


def make_product(pid, bid, ask, demand=10_000_000, supply=10_000_000,
                 bid_amt=5000, ask_amt=5000, bid_orders=20, ask_orders=20,
                 bid_volume=100_000, ask_volume=100_000):
    return Product(
        product_id=pid, best_bid=bid, best_ask=ask,
        best_bid_amount=bid_amt, best_ask_amount=ask_amt,
        insta_buy_price=ask, insta_sell_price=bid,
        demand_per_week=demand, supply_per_week=supply,
        ask_volume=ask_volume, bid_volume=bid_volume,
        ask_orders=ask_orders, bid_orders=bid_orders,
    )


class TestCongestion(unittest.TestCase):
    def test_congested_book_lowers_capture(self):
        calm = make_product("X", 100, 110, supply=10_000_000, bid_volume=1_000)
        busy = make_product("Y", 100, 110, supply=10_000_000, bid_volume=10_000_000)
        c_calm = economy.effective_capture(calm, 0.5, "buy")
        c_busy = economy.effective_capture(busy, 0.5, "buy")
        self.assertLess(c_busy, c_calm)
        self.assertGreater(c_busy, 0.0)
        self.assertLessEqual(c_calm, 0.5)


class TestBlacklist(unittest.TestCase):
    def test_blacklist_excludes_product(self):
        market = Market({
            "A": make_product("A", 100, 130),
            "B": make_product("B", 100, 130),
        })
        params = EvalParams(min_liquidity=0, min_coins_per_hour=0,
                            min_confidence=0)
        allp = flip.find_flips(market, params, 10**9)
        ids = {p.product_id for p in allp}
        self.assertIn("A", ids)
        blocked = flip.find_flips(market, params, 10**9, blacklist={"A"})
        self.assertNotIn("A", {p.product_id for p in blocked})

    def test_whitelist_restricts(self):
        market = Market({
            "A": make_product("A", 100, 130),
            "B": make_product("B", 100, 130),
        })
        params = EvalParams(min_liquidity=0, min_coins_per_hour=0, min_confidence=0)
        only = flip.find_flips(market, params, 10**9, whitelist={"B"})
        self.assertEqual({p.product_id for p in only}, {"B"})


class TestMagicalPower(unittest.TestCase):
    def test_mp_table_and_recomb(self):
        self.assertEqual(accessories.mp_for("LEGENDARY"), 16)
        self.assertEqual(accessories.next_rarity("EPIC"), "LEGENDARY")
        self.assertIsNone(accessories.next_rarity("MYTHIC"))
        self.assertEqual(accessories.recomb_delta("RARE"), 4)   # 12 - 8
        self.assertEqual(accessories.recomb_delta("LEGENDARY"), 6)  # 22 - 16

    def market(self):
        return Market({
            "NECRO": make_product("NECRO", 1000, 60000),
            "RECOMBOBULATOR_3000": make_product("RECOMBOBULATOR_3000",
                                                11_000_000, 12_000_000),
            "ENCHANTED_STRING": make_product("ENCHANTED_STRING", 1000, 1100),
        })

    def accs(self):
        return [
            accessories.Accessory("NECRO", "Necro Brooch", "necro", "LEGENDARY",
                                  {"bazaar": "NECRO"}),
            accessories.Accessory("STR_TAL", "String Talisman", "string", "COMMON",
                                  {"craft": [["ENCHANTED_STRING", 20]]}),
            accessories.Accessory("NPC_TAL", "Npc Talisman", "npc_fam", "UNCOMMON",
                                  {"npc": 5000}),
        ]

    def test_pricing_sources(self):
        eng = accessories.AccessoryEngine(self.market(), self.accs(), [])
        cost_b, m_b, _ = eng.price(self.accs()[0])
        self.assertAlmostEqual(cost_b, 1000.1)         # buy-order price
        self.assertEqual(m_b, "buy")
        cost_c, m_c, _ = eng.price(self.accs()[1])
        self.assertAlmostEqual(cost_c, 20 * 1000.1)     # 20 * mat buy-order
        self.assertEqual(m_c, "craft")
        cost_n, m_n, _ = eng.price(self.accs()[2])
        self.assertEqual((cost_n, m_n), (5000.0, "npc"))

    def test_buy_options_dedup_and_owned(self):
        eng = accessories.AccessoryEngine(self.market(), self.accs(), [])
        opts = eng.buy_options(owned_ids=set(), owned_families=set())
        fams = [o.family for o in opts]
        self.assertEqual(len(fams), len(set(fams)))     # one per family
        self.assertEqual(opts, sorted(opts, key=lambda o: o.coins_per_mp))
        # Owned family is excluded.
        opts2 = eng.buy_options(owned_ids=set(), owned_families={"necro"})
        self.assertNotIn("necro", {o.family for o in opts2})

    def test_plan_reaches_goal_and_lists_recombs(self):
        eng = accessories.AccessoryEngine(self.market(), self.accs(), [])
        plan = accessories.plan_magic_power(eng, self.accs(), set(), set(),
                                            mp_goal=0, top=10)
        self.assertTrue(plan["picks"])
        self.assertTrue(plan["recombs"])   # generic recomb table present
        self.assertEqual(plan["recombs"][0].kind, "recomb")


class TestNBT(unittest.TestCase):
    def _bag(self, ids):
        def s(n):
            b = n.encode(); return struct.pack(">H", len(b)) + b

        def tag_string(name, val):
            v = val.encode()
            return b"\x08" + s(name) + struct.pack(">H", len(v)) + v

        def item_payload(iid):  # unnamed compound payload
            extra = b"\x0a" + s("ExtraAttributes") + tag_string("id", iid) + b"\x00"
            return extra + b"\x00"
        lst = b"\x0a" + struct.pack(">i", len(ids)) + b"".join(
            item_payload(i) for i in ids)
        root = b"\x0a" + s("") + b"\x09" + s("i") + lst + b"\x00"
        return base64.b64encode(gzip.compress(root)).decode()

    def test_roundtrip(self):
        blob = self._bag(["TITANIUM_ARTIFACT", "NECROMANCER_BROOCH"])
        self.assertEqual(nbt.item_ids_from_bag({"data": blob}),
                         {"TITANIUM_ARTIFACT", "NECROMANCER_BROOCH"})

    def test_graceful_failure(self):
        self.assertEqual(nbt.item_ids_from_bag("not base64 @@@"), set())
        self.assertEqual(nbt.item_ids_from_bag(None), set())


class TestNotify(unittest.TestCase):
    def _plan(self, profit, cph, conf):
        return SimpleNamespace(product_id="X", buy_order_price=1.0,
                               total_profit=profit, coins_per_hour=cph,
                               confidence=conf, quantity=10,
                               sell_offer_price=2.0, margin=0.1,
                               total_minutes=10.0)

    def test_crucial_threshold(self):
        alert = {"min_profit": 1_000_000, "min_coins_per_hour": 5_000_000,
                 "min_confidence": 0.6}
        good = self._plan(2_000_000, 6_000_000, 0.8)
        weak = self._plan(500_000, 6_000_000, 0.8)      # profit too low
        self.assertTrue(notify.is_crucial(good, alert))
        self.assertFalse(notify.is_crucial(weak, alert))
        self.assertEqual(len(notify.crucial([good, weak], alert)), 1)

    def test_opportunity_key_stable(self):
        p = self._plan(1, 1, 1)
        self.assertEqual(notify.opportunity_key(p), notify.opportunity_key(p))

    def test_embed_shape(self):
        acct = SimpleNamespace(name="Acc", risk="balanced", budget=1e6)
        embed = notify.opportunities_embed(acct, [self._plan(2e6, 6e6, 0.8)], [], 10)
        self.assertIn("title", embed)
        self.assertEqual(embed["color"], notify._GREEN)
        self.assertTrue(embed["fields"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
