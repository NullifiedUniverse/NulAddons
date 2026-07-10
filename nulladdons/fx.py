"""
Null's Addons -- fx: terminal animations & effects (opt-out, TTY-safe, honest).

A thin layer of delight on top of the CLI: a spinner while the live Bazaar
loads, a slot-machine count-up on headline numbers, and a sparkle when a flip is
genuinely cracked.  Three hard rules keep it from ever being a problem:

1. **Effects never change a number.** A count-up *always* lands on the exact
   value it was given (see :func:`count_frames`) -- the animation is pure
   presentation. If you disabled every effect the numbers would be identical.
2. **It degrades to nothing.** Every effect no-ops unless it's writing to a real
   interactive terminal. Piped output, ``NO_COLOR``, ``TERM=dumb``, a dumb log,
   ``--serious`` / ``NULLADDONS_SERIOUS``, or ``NULLADDONS_NO_ANIM`` all fall
   back to a single plain write. It never corrupts a redirect.
3. **It's fast.** Every animation is bounded by a time budget (a few hundred ms
   at most) so it can't slow real work down.

The one part with real logic -- turning a target value into eased integer frames
that end exactly on the target -- is a pure function and is unit-tested.
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time

from . import flair

#: Braille spinner frames -- smooth and available in most modern terminals.
_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
#: Sparkles for a cracked flip, picked by seed.
_SPARKLES = ["✦", "✧", "⋆", "✵", "❖", "✴", "＊"]


def _opted_out() -> bool:
    """True if the user has globally turned effects off (any of several ways)."""
    v = os.environ.get("NULLADDONS_NO_ANIM", "")
    if v not in ("", "0", "false", "False"):
        return True
    if os.environ.get("NO_COLOR") is not None:
        return True
    if os.environ.get("TERM") == "dumb":
        return True
    return flair.serious()


def enabled(stream=None) -> bool:
    """Animations run only for an interactive human who hasn't opted out.

    ``stream`` defaults to stdout; pass ``sys.stderr`` for status effects that
    should show even when stdout is being piped to a file.
    """
    if _opted_out():
        return False
    stream = stream if stream is not None else sys.stdout
    try:
        return bool(stream.isatty())
    except Exception:
        return False


# --- eased count-up ---------------------------------------------------------

def count_frames(start: int, end: int, steps: int) -> list[int]:
    """Ease-out integer frames from ``start`` to ``end``.

    The last frame is *always* exactly ``end`` -- this is the honesty guarantee
    the whole module rests on: the number you see settle is the real one, never a
    rounding artifact of the animation.
    """
    start, end = int(start), int(end)
    if steps <= 1 or start == end:
        return [end]
    frames = []
    span = end - start
    for i in range(1, steps + 1):
        t = i / steps
        eased = 1.0 - (1.0 - t) ** 3          # ease-out cubic: fast then settles
        frames.append(start + int(round(span * eased)))
    frames[-1] = end                          # guarantee the exact landing
    return frames


def count_up(value, *, fmt=None, label: str = "", suffix: str = "",
             stream=None, steps: int = 18, budget: float = 0.45,
             color: str = "") -> None:
    """Print a single line that counts up to ``value`` then settles on it.

    ``fmt`` formats each integer frame (defaults to thousands-separated). When
    effects are disabled this is just one plain ``print`` of the final value, so
    callers never need to branch.
    """
    stream = stream if stream is not None else sys.stdout
    fmt = fmt or (lambda v: f"{v:,}")
    ival = int(value)

    def render(v: int) -> str:
        body = f"{label}{fmt(v)}{suffix}"
        return _paint(body, color, stream)

    if not enabled(stream):
        stream.write(render(ival) + "\n")
        stream.flush()
        return

    frames = count_frames(0, ival, steps)
    delay = budget / max(1, len(frames))
    _hide_cursor(stream)
    try:
        for v in frames:
            stream.write("\r\033[K" + render(v))
            stream.flush()
            time.sleep(delay)
    finally:
        stream.write("\n")
        _show_cursor(stream)
        stream.flush()


# --- spinner ----------------------------------------------------------------

class Spinner:
    """A background spinner for slow work (a network fetch). Use as a context
    manager: ``with fx.spinner("Fetching the Bazaar"): ...``.

    Runs on a daemon thread and always restores the cursor and clears its line
    on exit, even if the wrapped block raises. A complete no-op when disabled.
    """

    def __init__(self, text: str, stream=None, interval: float = 0.08):
        self.text = text
        self.stream = stream if stream is not None else sys.stderr
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._active = enabled(self.stream)

    def __enter__(self) -> Spinner:
        if self._active:
            _hide_cursor(self.stream)
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self) -> None:
        frames = itertools.cycle(_SPINNER_FRAMES)
        while not self._stop.is_set():
            frame = _paint(next(frames), "cyan", self.stream)
            self.stream.write(f"\r  {frame} {self.text}…")
            self.stream.flush()
            self._stop.wait(self.interval)

    def stop(self) -> None:
        if not self._active:
            return
        self._active = False
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=0.4)
        self.stream.write("\r\033[K")   # wipe the spinner line
        _show_cursor(self.stream)
        self.stream.flush()

    def __exit__(self, *exc) -> bool:
        self.stop()
        return False


def spinner(text: str, stream=None) -> Spinner:
    return Spinner(text, stream=stream)


# --- small decorative bits --------------------------------------------------

def sparkle(seed: int | None = None) -> str:
    """A single sparkle glyph to bracket a headline, or "" in serious mode."""
    if flair.serious():
        return ""
    import random
    rng = random.Random(seed if seed is not None else 0)
    return rng.choice(_SPARKLES)


# --- internals --------------------------------------------------------------

_COLORS = {"cyan": "36", "green": "32", "yellow": "33", "magenta": "35",
           "blue": "34", "bold": "1"}


def _paint(text: str, color: str, stream) -> str:
    if not color or color not in _COLORS or not enabled(stream):
        return text
    return f"\033[{_COLORS[color]}m{text}\033[0m"


def _hide_cursor(stream) -> None:
    try:
        stream.write("\033[?25l")
        stream.flush()
    except Exception:
        pass


def _show_cursor(stream) -> None:
    try:
        stream.write("\033[?25h")
        stream.flush()
    except Exception:
        pass
