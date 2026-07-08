"""
Null's Addons -- tests for the grounded `ask` AI: retrieval, the local answerer,
the anti-hallucination "I don't know" behaviour, and the Gemini grounding.
Network-free.
"""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import ask, llm, mayor, projection  # noqa: E402
from nulladdons.bazaar import Market, Product  # noqa: E402


def make_product(pid, bid, ask_, demand=10_000_000, supply=10_000_000):
    return Product(pid, bid, ask_, 5000, 5000, ask_, bid, demand, supply,
                   100_000, 100_000, 20, 20)


def make_market():
    return Market({
        "DIAMOND": make_product("DIAMOND", 7.0, 7.5),
        "ENCHANTED_DIAMOND": make_product("ENCHANTED_DIAMOND", 1342.0, 1400.0),
        "ENCHANTED_DIAMOND_BLOCK": make_product("ENCHANTED_DIAMOND_BLOCK",
                                                203_000.0, 210_000.0),
    })


def make_ctx(market, items=None, with_proj=True):
    acct = SimpleNamespace(name="Acc", username="acc", budget=50_000_000,
                           risk="balanced", live=False, coin_goal=500_000_000,
                           mp_goal=1500, active_hours=6)
    proj = None
    if with_proj:
        proj = projection.project_bazaar_income(
            [SimpleNamespace(coins_per_hour=1_000_000, capital_required=10_000_000)], 6)
    return ask.AskContext(
        account=acct, market=market, tax=0.0125,
        mayor=mayor.simulate("diana"),
        items=items or [], projection=proj,
        flips=[SimpleNamespace(product_id="ENCHANTED_MITHRIL", quantity=100,
                               buy_order_price=1, sell_offer_price=2,
                               total_profit=2_000_000, margin=0.15,
                               coins_per_hour=11_000_000, confidence=0.84)],
        crafts=[], mp_plan={"picks": [], "recombs": []}, ah_recent=[])


class TestRetrieval(unittest.TestCase):
    def test_matches_items(self):
        m = make_market()
        self.assertIn("ENCHANTED_DIAMOND",
                      ask.find_items("profit flipping enchanted diamond", m))
        self.assertIn("DIAMOND", ask.find_items("price of diamond", m))

    def test_longest_match_wins(self):
        m = make_market()
        got = ask.find_items("is enchanted diamond block worth crafting", m)
        self.assertIn("ENCHANTED_DIAMOND_BLOCK", got)
        self.assertNotIn("ENCHANTED_DIAMOND", got)  # sub-phrase consumed

    def test_no_items_for_offtopic(self):
        self.assertEqual(ask.find_items("how do I beat Necron in dungeons",
                                        make_market()), [])


class TestLocalAnswer(unittest.TestCase):
    def test_flip_question(self):
        m = make_market()
        ctx = make_ctx(m, items=[("ENCHANTED_DIAMOND", m.get("ENCHANTED_DIAMOND"))])
        ans = ask.local_answer("how much profit flipping enchanted diamond", ctx)
        self.assertIn("Flip Enchanted Diamond", ans)
        self.assertNotIn("I don't know", ans)

    def test_price_question(self):
        m = make_market()
        ctx = make_ctx(m, items=[("DIAMOND", m.get("DIAMOND"))])
        ans = ask.local_answer("what is the price of diamond", ctx)
        self.assertIn("instant-buy", ans)

    def test_mayor_question(self):
        ctx = make_ctx(make_market())
        self.assertIn("Diana", ask.local_answer("who is the mayor", ctx))

    def test_income_question(self):
        ctx = make_ctx(make_market())
        ans = ask.local_answer("how much money can I make per day", ctx)
        self.assertIn("/day", ans)

    def test_budget_question(self):
        ctx = make_ctx(make_market())
        self.assertIn("50.00M", ask.local_answer("how much capital do i have", ctx))

    def test_unanswerable_says_dont_know(self):
        ctx = make_ctx(make_market())
        ans = ask.local_answer("what is the best pet for enchanting xp", ctx)
        self.assertTrue(ans.startswith(ask.DONT_KNOW))


class TestFactsAndGrounding(unittest.TestCase):
    def test_build_facts_has_account_and_mayor(self):
        m = make_market()
        facts = ask.build_facts(make_ctx(
            m, items=[("ENCHANTED_DIAMOND", m.get("ENCHANTED_DIAMOND"))]))
        self.assertIn("FACTS", facts)
        self.assertIn("Mayor: Diana", facts)
        self.assertIn("Enchanted Diamond", facts)
        self.assertIn("Income potential", facts)

    def test_answer_uses_gemini_when_available_and_grounds(self):
        ctx = make_ctx(make_market())
        with mock.patch("nulladdons.ask.llm.gemini_generate",
                        return_value="Grounded reply.") as gm:
            text, via = ask.answer("what should I flip?", ctx, gemini_key="k")
        self.assertTrue(via)
        self.assertEqual(text, "Grounded reply.")
        prompt = gm.call_args.args[0]
        self.assertIn("FACTS", prompt)                 # facts were sent
        self.assertIn("what should I flip?", prompt)   # question was sent
        self.assertEqual(gm.call_args.kwargs["system"], llm.ANSWER_SYSTEM)

    def test_answer_falls_back_to_local_on_llm_failure(self):
        ctx = make_ctx(make_market())
        with mock.patch("nulladdons.ask.llm.gemini_generate", return_value=None):
            text, via = ask.answer("who is the mayor", ctx, gemini_key="k")
        self.assertFalse(via)
        self.assertIn("Diana", text)

    def test_answer_local_without_key(self):
        ctx = make_ctx(make_market())
        text, via = ask.answer("random nonsense question xyz", ctx, gemini_key=None)
        self.assertFalse(via)
        self.assertTrue(text.startswith(ask.DONT_KNOW))


if __name__ == "__main__":
    unittest.main(verbosity=2)
