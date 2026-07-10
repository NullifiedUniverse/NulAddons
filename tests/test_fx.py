"""
Tests for the terminal effects layer (fx) and the cracked-flip flair label.

The load-bearing guarantee is that effects are *pure presentation*: a count-up
always lands on the exact value it was given, and every effect degrades to a
single plain write (or nothing) when it isn't talking to an interactive
terminal. Network-free.
"""

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nulladdons import flair, fx  # noqa: E402


class FakeTTY:
    """A minimal writable stream that claims to be a terminal."""

    def __init__(self):
        self.buf = []

    def write(self, s):
        self.buf.append(s)

    def flush(self):
        pass

    def isatty(self):
        return True

    def text(self):
        return "".join(self.buf)


class _CleanEnv(unittest.TestCase):
    """Base: force a known 'effects allowed' environment, restore after."""

    def setUp(self):
        self._saved = {k: os.environ.get(k)
                       for k in ("NULLADDONS_NO_ANIM", "NO_COLOR", "TERM",
                                 "NULLADDONS_SERIOUS")}
        for k in self._saved:
            os.environ.pop(k, None)
        flair.set_serious(False)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        flair.set_serious(None)


class TestCountFrames(unittest.TestCase):
    def test_lands_exactly_on_target(self):
        for end in (0, 1, 7, 100, 2_560_000, 999_999_999):
            frames = fx.count_frames(0, end, 18)
            self.assertEqual(frames[-1], end, f"must settle exactly on {end}")

    def test_degenerate_cases(self):
        self.assertEqual(fx.count_frames(5, 5, 10), [5])   # nothing to animate
        self.assertEqual(fx.count_frames(0, 100, 1), [100])
        self.assertEqual(fx.count_frames(0, 100, 0), [100])

    def test_monotonic_non_decreasing_for_increasing(self):
        frames = fx.count_frames(0, 1_000_000, 20)
        self.assertEqual(len(frames), 20)
        for a, b in zip(frames, frames[1:]):
            self.assertLessEqual(a, b)
        self.assertTrue(all(isinstance(v, int) for v in frames))

    def test_handles_downward_count(self):
        frames = fx.count_frames(100, 0, 6)
        self.assertEqual(frames[-1], 0)


class TestEnabledGating(_CleanEnv):
    def test_disabled_for_non_tty(self):
        self.assertFalse(fx.enabled(io.StringIO()))

    def test_enabled_for_tty_when_no_optout(self):
        self.assertTrue(fx.enabled(FakeTTY()))

    def test_no_anim_env_disables(self):
        os.environ["NULLADDONS_NO_ANIM"] = "1"
        self.assertFalse(fx.enabled(FakeTTY()))

    def test_no_color_disables(self):
        os.environ["NO_COLOR"] = "1"
        self.assertFalse(fx.enabled(FakeTTY()))

    def test_dumb_terminal_disables(self):
        os.environ["TERM"] = "dumb"
        self.assertFalse(fx.enabled(FakeTTY()))

    def test_serious_disables(self):
        flair.set_serious(True)
        self.assertFalse(fx.enabled(FakeTTY()))


class TestCountUp(_CleanEnv):
    def test_disabled_prints_one_plain_line_with_exact_value(self):
        sio = io.StringIO()
        fx.count_up(2_560_000, fmt=lambda v: f"{v:,}", label="net ",
                    suffix="!", stream=sio)
        out = sio.getvalue()
        self.assertEqual(out.count("\n"), 1)          # exactly one line
        self.assertEqual(out.strip(), "net 2,560,000!")
        self.assertNotIn("\033", out)                 # no escape codes when off

    def test_enabled_settles_on_exact_value(self):
        tty = FakeTTY()
        fx.count_up(1_234_567, fmt=lambda v: f"{v:,}", stream=tty,
                    steps=4, budget=0.0)              # budget 0 => no real sleeping
        text = tty.text()
        self.assertIn("1,234,567", text)              # the true value appears
        # ...and it is the final settled frame (last carriage-return segment).
        last = text.rstrip("\n").split("\r")[-1]
        self.assertIn("1,234,567", last)
        self.assertIn("\033[?25l", text)              # cursor hidden
        self.assertIn("\033[?25h", text)              # ...and restored


class TestSpinner(_CleanEnv):
    def test_noop_when_disabled(self):
        sio = io.StringIO()
        with fx.spinner("working", stream=sio):
            pass
        self.assertEqual(sio.getvalue(), "")          # wrote nothing at all

    def test_restores_cursor_when_enabled(self):
        tty = FakeTTY()
        with fx.spinner("working", stream=tty):
            pass
        # Whatever it drew, it must leave the cursor visible and the line clear.
        self.assertIn("\033[?25h", tty.text())
        self.assertIn("\r\033[K", tty.text())


class TestSparkle(_CleanEnv):
    def test_present_in_fun_mode_and_stable(self):
        s = fx.sparkle(seed=3)
        self.assertTrue(s)
        self.assertIn(s, fx._SPARKLES)
        self.assertEqual(s, fx.sparkle(seed=3))       # stable per seed

    def test_empty_in_serious_mode(self):
        flair.set_serious(True)
        self.assertEqual(fx.sparkle(seed=3), "")


class TestCrackedLabel(_CleanEnv):
    def test_tiers(self):
        self.assertIn("CRACKED", flair.cracked_label(0.30))
        self.assertEqual(flair.cracked_label(0.15), "HOT")
        self.assertEqual(flair.cracked_label(0.05), "")

    def test_serious_mode_is_silent(self):
        flair.set_serious(True)
        self.assertEqual(flair.cracked_label(0.30), "")
        self.assertEqual(flair.cracked_label(0.15), "")


if __name__ == "__main__":
    unittest.main()
