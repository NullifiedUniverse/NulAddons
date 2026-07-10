"""
Tests for flavors and feature toggles (nulladdons.features). Both are pure
config/presentation; these verify the resolution order (override → env → config →
default) and that flavors each carry a distinct, non-empty voice. Network-free.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import features  # noqa: E402


class TestFlavors(unittest.TestCase):
    def tearDown(self):
        features.set_flavor(None)

    def test_every_flavor_has_a_nonempty_pool_and_label(self):
        for fid in features.flavor_ids():
            self.assertTrue(features.taglines(fid), f"{fid} has taglines")
            self.assertTrue(features.flavor_label(fid))

    def test_normalize_falls_back_to_default(self):
        self.assertEqual(features.normalize_flavor("PIRATE"), "pirate")
        self.assertEqual(features.normalize_flavor("nonsense"), features.DEFAULT_FLAVOR)
        self.assertEqual(features.normalize_flavor(None), features.DEFAULT_FLAVOR)

    def test_resolution_order(self):
        cfg = {"flavor": "zen"}
        self.assertEqual(features.active_flavor(cfg), "zen")          # config
        with mock.patch.dict(os.environ, {"NULLADDONS_FLAVOR": "pirate"}):
            self.assertEqual(features.active_flavor(cfg), "pirate")   # env beats config
            features.set_flavor("wallstreet")
            self.assertEqual(features.active_flavor(cfg), "wallstreet")  # override wins

    def test_flavors_are_distinct(self):
        firsts = {features.taglines(f)[0] for f in features.flavor_ids()}
        self.assertGreater(len(firsts), 1)


class TestFeatureToggles(unittest.TestCase):
    def test_defaults(self):
        self.assertTrue(features.enabled("animations"))
        self.assertTrue(features.enabled("mayor"))
        self.assertFalse(features.enabled("telemetry"))   # OFF by default (load-bearing)

    def test_config_override_wins(self):
        cfg = {"features": {"animations": False, "telemetry": True}}
        self.assertFalse(features.enabled("animations", cfg))
        self.assertTrue(features.enabled("telemetry", cfg))
        self.assertTrue(features.enabled("mayor", cfg))    # unspecified → default

    def test_unknown_feature_is_false(self):
        self.assertFalse(features.enabled("does_not_exist"))

    def test_default_features_covers_all_and_telemetry_off(self):
        d = features.default_features()
        self.assertEqual(set(d), set(features.FEATURES))
        self.assertFalse(d["telemetry"])


if __name__ == "__main__":
    unittest.main()
