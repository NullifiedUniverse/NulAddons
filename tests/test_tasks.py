"""
Tests for the parallel task scheduler. Verifies real concurrency, per-task error
isolation, and the value/timing helpers. Network-free.
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import tasks  # noqa: E402


class TestGather(unittest.TestCase):
    def test_runs_concurrently(self):
        def sleeper(x):
            def f():
                time.sleep(0.1)
                return x * 2
            return f
        t0 = time.monotonic()
        res = tasks.gather({"a": sleeper(1), "b": sleeper(2), "c": sleeper(3)})
        elapsed = time.monotonic() - t0
        # Three 0.1s tasks in parallel should finish well under the 0.3s serial cost.
        self.assertLess(elapsed, 0.25)
        self.assertEqual(res["a"].value, 2)
        self.assertEqual(res["b"].value, 4)
        self.assertEqual(res["c"].value, 6)
        self.assertTrue(all(r.ok for r in res.values()))

    def test_error_isolation(self):
        def boom():
            raise ValueError("nope")
        res = tasks.gather({"good": lambda: 42, "bad": boom})
        self.assertTrue(res["good"].ok)
        self.assertEqual(res["good"].value, 42)
        self.assertFalse(res["bad"].ok)
        self.assertIsInstance(res["bad"].error, ValueError)
        self.assertIsNone(res["bad"].value)

    def test_empty(self):
        self.assertEqual(tasks.gather({}), {})

    def test_values_with_default(self):
        def boom():
            raise RuntimeError
        res = tasks.gather({"ok": lambda: "v", "bad": boom})
        vals = tasks.values(res, default="X")
        self.assertEqual(vals, {"ok": "v", "bad": "X"})

    def test_total_saved_is_nonnegative(self):
        res = tasks.gather({"a": lambda: 1, "b": lambda: 2})
        self.assertGreaterEqual(tasks.total_saved(res), 0.0)
        self.assertEqual(tasks.total_saved({}), 0.0)

    def test_records_timing(self):
        res = tasks.gather({"a": lambda: (time.sleep(0.05), 1)[1]})
        self.assertGreater(res["a"].seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
