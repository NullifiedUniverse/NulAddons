"""
Null's Addons -- tests for onboarding: config resolution, config builders, the
UI prompts (via piped stdin) and the doctor (with the network mocked out).
Network-free.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import accounts as A  # noqa: E402
from nulladdons import onboarding, ui  # noqa: E402


class TestConfigResolution(unittest.TestCase):
    def test_load_missing_and_bad_returns_default(self):
        self.assertEqual(A.load_config("/no/such/file.json").get("accounts"), {})
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{ not json ]")
            bad = fh.name
        try:
            self.assertEqual(A.load_config(bad).get("accounts"), {})
        finally:
            os.unlink(bad)

    def test_config_path_env_override(self):
        with mock.patch.dict(os.environ, {"NULLADDONS_CONFIG": "/x/y.json"}):
            self.assertEqual(A.config_path(), "/x/y.json")

    def test_save_roundtrip_and_helpers(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "accounts.json")
            cfg = A.default_config()
            onboarding.apply_account(cfg, "Me", username="Me", budget=5_000_000,
                                     risk="aggressive", coin_goal=10_000_000)
            saved = A.save_config(cfg, path)
            self.assertEqual(saved, path)
            back = A.load_config(path)
            self.assertEqual(A.account_names(back), ["Me"])
            self.assertEqual(A.first_account(back), "Me")
            self.assertEqual(back["accounts"]["Me"]["budget"], 5_000_000)
            # 0600 permissions on POSIX
            if os.name == "posix":
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)


class TestConfigBuilders(unittest.TestCase):
    def test_apply_account_normalises(self):
        cfg = A.default_config()
        onboarding.apply_account(cfg, "X", username="X", risk="not-a-risk",
                                 budget="ignored" if False else 100, active_hours=8)
        acc = cfg["accounts"]["X"]
        self.assertEqual(acc["risk"], "balanced")   # bad risk -> default
        self.assertEqual(acc["active_hours"], 8.0)
        # A round-trip through build_context must succeed.
        ctx = A.build_context("X", cfg)
        self.assertEqual(ctx.budget, 100)

    def test_apply_globals(self):
        cfg = A.default_config()
        onboarding.apply_globals(cfg, hypixel_api_key="k", gemini_api_key="",
                                 discord_webhook_url="http://x")
        self.assertEqual(cfg["hypixel_api_key"], "k")
        self.assertIsNone(cfg["gemini_api_key"])       # empty -> None
        self.assertEqual(cfg["discord_webhook_url"], "http://x")


class TestUIPrompts(unittest.TestCase):
    def setUp(self):
        self._stdin, self._stdout = sys.stdin, sys.stdout
        sys.stdout = io.StringIO()          # swallow prompt echoes
        os.environ["NO_COLOR"] = "1"

    def tearDown(self):
        sys.stdin, sys.stdout = self._stdin, self._stdout
        os.environ.pop("NO_COLOR", None)

    def _feed(self, text):
        sys.stdin = io.StringIO(text)

    def test_ask_default_and_value(self):
        self._feed("\n")
        self.assertEqual(ui.ask("q", "def"), "def")
        self._feed("hello\n")
        self.assertEqual(ui.ask("q", "def"), "hello")

    def test_ask_int_suffixes(self):
        self._feed("50m\n")
        self.assertEqual(ui.ask_int("q", 0), 50_000_000)
        self._feed("2.5k\n")
        self.assertEqual(ui.ask_int("q", 0), 2_500)
        self._feed("1b\n")
        self.assertEqual(ui.ask_int("q", 0), 1_000_000_000)
        self._feed("junk\n")
        self.assertEqual(ui.ask_int("q", 7), 7)         # falls back to default

    def test_ask_yes_no(self):
        self._feed("y\n")
        self.assertTrue(ui.ask_yes_no("q", False))
        self._feed("n\n")
        self.assertFalse(ui.ask_yes_no("q", True))
        self._feed("\n")
        self.assertTrue(ui.ask_yes_no("q", True))       # empty -> default

    def test_ask_choice_prefix(self):
        self._feed("agg\n")
        self.assertEqual(ui.ask_choice("q", ["conservative", "balanced",
                                             "aggressive"], "balanced"), "aggressive")
        self._feed("\n")
        self.assertEqual(ui.ask_choice("q", ["a", "b"], "b"), "b")

    def test_prompts_eof_safe(self):
        self._feed("")                                  # immediate EOF
        self.assertEqual(ui.ask("q", "d"), "d")
        self._feed("")
        self.assertTrue(ui.ask_yes_no("q", True))


class TestDoctor(unittest.TestCase):
    def setUp(self):
        self._stdout = sys.stdout
        sys.stdout = io.StringIO()          # swallow doctor's report

    def tearDown(self):
        sys.stdout = self._stdout

    def test_doctor_runs_with_mocked_network(self):
        cfg = A.default_config()
        onboarding.apply_account(cfg, "Me", username="Me", budget=1_000_000)
        cfg["hypixel_api_key"] = "key"
        with mock.patch("nulladdons.hypixel.fetch_bazaar",
                        return_value={"products": {"A": {}, "B": {}}}), \
             mock.patch("nulladdons.hypixel.resolve_uuid", return_value="uuid123"), \
             mock.patch("nulladdons.hypixel.check_key",
                        return_value=(True, "valid")):
            healthy = onboarding.doctor(cfg, check_gemini=False)
        self.assertTrue(healthy)

    def test_doctor_flags_dead_bazaar(self):
        from nulladdons import hypixel
        with mock.patch("nulladdons.hypixel.fetch_bazaar",
                        side_effect=hypixel.HypixelError("down")), \
             mock.patch("nulladdons.hypixel.resolve_uuid", return_value=None):
            healthy = onboarding.doctor(A.default_config(), check_gemini=False)
        self.assertFalse(healthy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
