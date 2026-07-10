"""
Tests for the opt-in telemetry engine. The load-bearing guarantees: it is OFF by
default and writes nothing until enabled; the schema is PII-free; and the
aggregation (stats, streaks, achievements, Wrapped) is correct. Network-free.
"""

import datetime
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import telemetry as T  # noqa: E402

CFG_ON = {"features": {"telemetry": True}}
CFG_OFF = {"features": {"telemetry": False}}


class TestConsent(unittest.TestCase):
    def test_off_by_default(self):
        self.assertFalse(T.is_enabled(None))
        self.assertFalse(T.is_enabled({}))
        self.assertFalse(T.is_enabled(CFG_OFF))
        self.assertTrue(T.is_enabled(CFG_ON))

    def test_record_off_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "events.jsonl")
            wrote = T.record(CFG_OFF, T.build_event("plan"), path=path)
            self.assertFalse(wrote)
            self.assertFalse(os.path.exists(path))

    def test_record_on_appends(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "events.jsonl")
            self.assertTrue(T.record(CFG_ON, T.build_event("plan"), path=path))
            self.assertTrue(T.record(CFG_ON, T.build_event("flips"), path=path))
            self.assertEqual(len(T.load_events(path)), 2)


class TestEventSchema(unittest.TestCase):
    def test_build_event_base_and_extra(self):
        now = datetime.datetime(2026, 7, 10, 3, 30)
        ev = T.build_event("status", flavor="zen", risk="aggressive",
                           duration_ms=12.7, offline=True, serious=False,
                           extra={"positions": 3, "top_margin": None}, now=now)
        self.assertEqual(ev["command"], "status")
        self.assertEqual(ev["day"], "2026-07-10")
        self.assertEqual(ev["hour"], 3)
        self.assertEqual(ev["flavor"], "zen")
        self.assertEqual(ev["risk"], "aggressive")
        self.assertEqual(ev["duration_ms"], 12)
        self.assertTrue(ev["offline"])
        self.assertEqual(ev["positions"], 3)
        self.assertNotIn("top_margin", ev)   # None extras are dropped

    def test_manifest_has_no_pii_fields(self):
        names = {n for n, _ in T.COLLECTED_FIELDS}
        for forbidden in ("username", "uuid", "api_key", "question", "name"):
            self.assertNotIn(forbidden, names)
        # And the human manifest states the local path + off-by-default.
        text = T.manifest_text(CFG_OFF)
        self.assertIn("OFF", text)
        self.assertIn(T.EVENTS_PATH, text)


class TestAnnotations(unittest.TestCase):
    def test_annotate_and_take(self):
        T.take_annotations()  # clear
        T.annotate(results=5, top_margin=None, item="ENCHANTED_LAPIS")
        taken = T.take_annotations()
        self.assertEqual(taken, {"results": 5, "item": "ENCHANTED_LAPIS"})
        self.assertEqual(T.take_annotations(), {})  # cleared after taking


class TestAggregation(unittest.TestCase):
    def _events(self):
        d = "2026-07-10"
        return [
            {"command": "plan", "day": d, "hour": 2, "flavor": "zen",
             "risk": "aggressive", "offline": True, "top_margin": 0.55,
             "projected_profit": 5e6, "top_coins_per_hour": 1e7},
            {"command": "item", "day": d, "hour": 2, "flavor": "pirate",
             "item": "ENCHANTED_LAPIS", "offline": True},
            {"command": "item", "day": d, "hour": 3, "flavor": "pirate",
             "item": "ENCHANTED_LAPIS", "offline": True},
            {"command": "status", "day": d, "hour": 6, "flavor": "zen",
             "mayor": "Derpy", "tax_free": True, "projected_profit": 1.2e9,
             "offline": False},
        ]

    def test_core_aggregates(self):
        s = T.compute_stats(self._events())
        self.assertEqual(s["total_events"], 4)
        self.assertEqual(s["favorite_command"], "item")     # ran twice
        self.assertEqual(s["spirit_item"], "ENCHANTED_LAPIS")
        self.assertAlmostEqual(s["biggest_margin"], 0.55)
        self.assertAlmostEqual(s["total_projected_profit"], 5e6 + 1.2e9)
        self.assertEqual(s["mayors_seen"], ["Derpy"])
        self.assertEqual(s["tax_free_sessions"], 1)
        self.assertEqual(s["flavors_used"], {"zen": 2, "pirate": 2})
        self.assertEqual(s["offline_sessions"], 3)
        self.assertEqual(s["live_sessions"], 1)

    def test_empty_stats_are_safe(self):
        s = T.compute_stats([])
        self.assertEqual(s["total_events"], 0)
        self.assertIsNone(s["favorite_command"])
        self.assertIn("No telemetry yet", T.stats_text(s))
        self.assertIn("wrap yet", T.wrapped_text(s))

    def test_streaks(self):
        today = datetime.date.today()
        days = {(today - datetime.timedelta(days=i)).isoformat() for i in range(3)}
        events = [{"command": "plan", "day": d} for d in days]
        s = T.compute_stats(events)
        self.assertEqual(s["current_streak"], 3)
        self.assertGreaterEqual(s["longest_streak"], 3)


class TestAchievements(unittest.TestCase):
    def test_predicates_unlock(self):
        stats = T.compute_stats([
            {"command": "plan", "day": "2026-07-10", "hour": 2,
             "flavor": "pirate", "top_margin": 0.6, "projected_profit": 2e12},
        ])
        got = {a["id"] for a in T.achievements(stats) if a["unlocked"]}
        self.assertIn("made_a_move", got)
        self.assertIn("whale_watcher", got)     # 0.6 >= 0.30
        self.assertIn("cracked", got)           # 0.6 >= 0.50
        self.assertIn("number_went_up", got)    # 2e12 >= 1e12
        self.assertIn("yarrr", got)             # pirate flavor
        self.assertIn("night_owl", got)         # hour 2
        # A hard one stays locked.
        self.assertNotIn("completionist", got)

    def test_achievements_text_counts(self):
        stats = T.compute_stats([{"command": "plan", "day": "2026-07-10"}])
        text = T.achievements_text(stats)
        self.assertIn("ACHIEVEMENTS", text)
        self.assertIn("Made a Move", text)


class TestClearAndExport(unittest.TestCase):
    def test_export_and_clear(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "events.jsonl")
            T.record(CFG_ON, T.build_event("plan"), path=src)
            dest = os.path.join(d, "out.jsonl")
            self.assertEqual(T.export_to(dest, src_path=src), 1)
            self.assertTrue(os.path.exists(dest))
            self.assertTrue(T.clear(src))
            self.assertFalse(os.path.exists(src))
            self.assertFalse(T.clear(src))   # already gone


if __name__ == "__main__":
    unittest.main()
