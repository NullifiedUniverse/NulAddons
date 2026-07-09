"""
Null's Addons -- tiny shared utilities.

Just the defensive numeric coercion every API-facing module needs.  The Hypixel
API will happily hand you ``null``, a string, or a missing field where you
expected a number, and a single ``NaN`` slipping past a ``<= 0`` guard poisons
every downstream calculation.  Coerce once, here, and coerce *finitely*.
"""

from __future__ import annotations

import math

__all__ = ["to_float", "to_int"]


def to_float(value, default: float = 0.0) -> float:
    """Coerce ``value`` to a finite float, returning ``default`` on anything odd.

    Handles ``None``, strings, dicts, and -- crucially -- non-finite floats.
    ``float("nan")`` and ``float("inf")`` parse without error, so a raw
    ``float()`` isn't enough: a NaN price would sail past a ``<= 0`` check and
    corrupt margins, velocities, and rankings.  We reject them explicitly.
    """
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def to_int(value, default: int = 0) -> int:
    """Coerce ``value`` to an int via :func:`to_float`, ``default`` on bad input."""
    return int(to_float(value, default))
