"""
Null's Addons -- tests for the Auction House, progress, Gemini and brief modules.
Network-free.  Run with: python3 -m unittest discover -s tests
"""

import base64
import gzip
import os
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import auction, brief, llm, progress  # noqa: E402


def item_bytes(item_id, count=1, name=None):
    """Synthesise an auction item's base64 gzipped NBT."""
    def s(n):
        b = n.encode(); return struct.pack(">H", len(b)) + b

    def tstr(nm, val):
        v = val.encode(); return b"\x08" + s(nm) + struct.pack(">H", len(v)) + v

    extra = b"\x0a" + s("ExtraAttributes") + tstr("id", item_id) + b"\x00"
    disp = b"\x0a" + s("display") + tstr("Name", name or item_id) + b"\x00"
    tag = b"\x0a" + s("tag") + extra + disp + b"\x00"
    item_payload = b"\x01" + s("Count") + struct.pack(">b", count) + tag + b"\x00"
    lst = b"\x0a" + struct.pack(">i", 1) + item_payload
    root = b"\x0a" + s("") + b"\x09" + s("i") + lst + b"\x00"
    return base64.b64encode(gzip.compress(root)).decode()


class TestAuction(unittest.TestCase):
    def test_decode_item(self):
        info = auction.decode_item(item_bytes("HYPERION", 1, "§dHyperion"))
        self.assertEqual(info["id"], "HYPERION")
        self.assertEqual(info["count"], 1)

    def test_sales_and_index(self):
        ended = [
            {"auction_id": "a1", "price": 1000, "bin": True,
             "timestamp": 1, "item_bytes": item_bytes("FOO")},
            {"auction_id": "a2", "price": 2000, "bin": True,
             "timestamp": 2, "item_bytes": item_bytes("FOO")},
            {"auction_id": "a3", "price": 3000, "bin": False,
             "timestamp": 3, "item_bytes": item_bytes("FOO")},
        ]
        sales = auction.sales_from_ended(ended)
        self.assertEqual(len(sales), 3)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sales.jsonl")
            self.assertEqual(auction.record_sales(sales, path), 3)
            self.assertEqual(auction.record_sales(sales, path), 0)  # deduped
            idx = auction.SalePriceIndex.load(path)
            st = idx.stats("FOO")
            self.assertEqual(st["count"], 3)
            self.assertEqual(st["median"], 2000)

    def test_find_bin_flips(self):
        # index: FOO recently sells around 1,000,000 (5 samples)
        idx = auction.SalePriceIndex({"FOO": [1_000_000] * 5})

        def fetch_page(n):
            return {"totalPages": 1, "auctions": [
                {"bin": True, "starting_bid": 500_000, "item_bytes": item_bytes("FOO")},
                {"bin": True, "starting_bid": 990_000, "item_bytes": item_bytes("FOO")},
                {"bin": False, "starting_bid": 1, "item_bytes": item_bytes("FOO")},
            ]}
        flips = auction.find_bin_flips(fetch_page, idx, max_pages=1,
                                       min_samples=4, min_discount=0.15,
                                       min_profit=100_000)
        self.assertEqual(len(flips), 1)          # only the 500k BIN qualifies
        self.assertEqual(flips[0].item_id, "FOO")
        self.assertGreater(flips[0].profit, 0)

    def test_player_listing_summary(self):
        au = [
            {"item_bytes": item_bytes("SWORD"), "starting_bid": 1000,
             "highest_bid_amount": 5000, "end": 1, "bids": [{"amount": 5000}]},
            {"item_bytes": item_bytes("BOW"), "starting_bid": 2000,
             "highest_bid_amount": 0, "end": 10**15, "bids": []},
        ]
        summ = auction.player_listing_summary(au, now_ms=1000)
        self.assertEqual(summ.sold_claimable, 1)
        self.assertEqual(summ.active, 1)


class TestProgress(unittest.TestCase):
    RES = {"skills": {"COMBAT": {"levels": [
        {"level": 1, "totalExpRequired": 50},
        {"level": 2, "totalExpRequired": 175}]}}}

    def test_level_from_xp(self):
        levels = self.RES["skills"]["COMBAT"]["levels"]
        self.assertEqual(progress.level_from_xp(40, levels), 0)
        self.assertEqual(progress.level_from_xp(180, levels), 2)

    def test_extract_both_shapes(self):
        prof = {"cute_name": "P", "banking": {"balance": 100}}
        newer = {"currencies": {"coin_purse": 50},
                 "player_data": {"experience": {"SKILL_COMBAT": 175}}}
        older = {"coin_purse": 50, "experience_skill_combat": 175}
        for member in (newer, older):
            s = progress.extract_stats(prof, member, self.RES)
            self.assertEqual(s["coins"], 150)
            self.assertEqual(s["skills"]["COMBAT"]["level"], 2)

    def test_diff_and_previous(self):
        a = {"ts": 0, "date": "2026-07-06", "coins": 100, "skills": {},
             "skill_average": 1.0, "slayer_total": 0, "catacombs_xp": 0,
             "collections_sum": 0, "pets": 1, "fairy_souls": 0}
        b = dict(a, ts=86400, date="2026-07-07", coins=250, pets=2)
        d = progress.diff(a, b)
        self.assertTrue(d["baseline"])
        self.assertEqual(d["coins_delta"], 150)
        self.assertTrue(any("Coins" in ln for ln in d["lines"]))
        self.assertIs(progress.previous_snapshot([a, b], b), a)
        self.assertFalse(progress.diff(None, b)["baseline"])


class TestLLMAndBrief(unittest.TestCase):
    def test_extract_text(self):
        payload = {"candidates": [{"content": {"parts": [
            {"text": "hello "}, {"text": "world"}]}}]}
        self.assertEqual(llm._extract_text(payload), "hello world")
        self.assertIsNone(llm._extract_text({"candidates": []}))

    def test_gemini_no_key(self):
        self.assertIsNone(llm.gemini_generate("x", api_key=None))

    def _ctx(self):
        acc = SimpleNamespace(name="Acc", username="acc", live=False, mp_goal=0)
        flip = SimpleNamespace(product_id="ENCHANTED_DIAMOND", quantity=100,
                               buy_order_price=1.0, sell_offer_price=2.0,
                               total_profit=1_000_000, margin=0.2,
                               coins_per_hour=5_000_000, confidence=0.8)
        craft = SimpleNamespace(output_id="ENCHANTED_IRON", quantity=10,
                                total_profit=500_000, margin=0.5)
        mpbuy = SimpleNamespace(label="Recomb Rare", mp_gain=4, cost=11_000_000,
                                coins_per_mp=2_750_000)
        return brief.build_context(
            acc, stats={"coins": 5_000_000, "skill_average": 30, "pets": 3,
                        "date": "2026-07-07", "purse": 4_000_000, "bank": 1_000_000},
            prog_diff={"baseline": True, "days": 1, "lines": ["Coins: +2,000,000"]},
            flips=[flip], crafts=[craft],
            mp_plan={"picks": [], "recombs": [mpbuy]},
            ah={"recent_sales": [("HYPERION", 900_000_000)], "listings": None})

    def test_facts_and_local_brief(self):
        ctx = self._ctx()
        facts = brief.facts_text(ctx)
        self.assertIn("ENCHANTED", facts.upper())
        self.assertIn("PROGRESS", facts)
        local = brief.local_brief(ctx)
        self.assertIn("Best flip", local)

    def test_summarize_falls_back_without_key(self):
        ctx = self._ctx()
        text, via = brief.summarize(ctx, gemini_key=None, model="x")
        self.assertFalse(via)
        self.assertIn("Best flip", text)
        rendered = brief.render_brief(ctx, text, via)
        self.assertIn("DAILY BRIEF", rendered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
