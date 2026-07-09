"""
Null's Addons -- tests for the flair (personality) engine. Network-free.
Verifies the golden rule: serious mode is fully neutral, and flair never leaks
into data/answers it shouldn't.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import flair  # noqa: E402


class TestFlair(unittest.TestCase):
    def tearDown(self):
        flair.set_serious(None)   # reset override so other tests aren't affected

    # --- serious mode is completely neutral ---------------------------------
    def test_serious_mode_is_neutral(self):
        flair.set_serious(True)
        self.assertEqual(flair.tagline(seed=1), "")
        self.assertEqual(flair.empty_flips(), "No flips clear this risk floor. Try --risk aggressive.")
        self.assertIsNone(flair.easter_egg("are you sentient"))
        self.assertEqual(flair.mayor_quip("tax_free"), "")
        real, quip = flair.resolve_risk_alias("yolo")
        self.assertEqual(real, "aggressive")   # alias still resolves...
        self.assertIsNone(quip)                # ...but no quip in serious mode

    # --- fun mode -----------------------------------------------------------
    def test_taglines_and_determinism(self):
        flair.set_serious(False)
        self.assertTrue(flair.tagline(seed=2))
        self.assertEqual(flair.tagline(seed=2), flair.tagline(seed=2))  # stable per seed

    def test_easter_eggs_match_memes_not_market(self):
        flair.set_serious(False)
        self.assertIn("spreadsheet", flair.easter_egg("are you sentient?").lower())
        self.assertIsNotNone(flair.easter_egg("derpy"))
        self.assertIsNotNone(flair.easter_egg("hello"))
        # Real market questions must NOT trigger an egg.
        self.assertIsNone(flair.easter_egg("how much is enchanted diamond"))
        self.assertIsNone(flair.easter_egg("what should i flip right now"))
        self.assertIsNone(flair.easter_egg(""))

    def test_risk_aliases(self):
        flair.set_serious(False)
        self.assertEqual(flair.resolve_risk_alias("yolo")[0], "aggressive")
        self.assertEqual(flair.resolve_risk_alias("scared")[0], "conservative")
        self.assertIsNotNone(flair.resolve_risk_alias("degen")[1])   # has a quip
        # A real profile passes through untouched, no quip.
        self.assertEqual(flair.resolve_risk_alias("balanced"), ("balanced", None))
        # An unknown value is left as-is for the normal validator to reject.
        self.assertEqual(flair.resolve_risk_alias("xyzzy"), ("xyzzy", None))

    def test_lore_exists(self):
        self.assertIn("bazaar", flair.lore().lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
