"""
Null's Addons -- income projection & goal ETAs (the ecosystem glue).

This is the module that answers "how much money can I make from the Bazaar with
what's in my bank right now, and how long until I hit my goals?".  It takes the
account's live capital (purse + bank) and the diversified portfolio the flip
engine already sized to that capital, and turns coins/hour into honest hourly /
daily / weekly projections and time-to-goal estimates.

The number is deliberately capital-limited and marked as such: your positions are
sized to what you can afford, and profits are assumed reinvested each cycle, so
the real curve compounds a bit faster than the linear projection shown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class IncomeProjection:
    capital_deployed: float
    positions: int
    coins_per_hour: float
    active_hours: float
    per_day: float
    per_week: float


def project_bazaar_income(portfolio: list, active_hours: float = 6.0
                          ) -> IncomeProjection:
    """Turn a sized portfolio into hourly / daily / weekly income."""
    cph = sum(p.coins_per_hour for p in portfolio)
    capital = sum(p.capital_required for p in portfolio)
    active_hours = max(0.0, active_hours)
    return IncomeProjection(
        capital_deployed=capital, positions=len(portfolio), coins_per_hour=cph,
        active_hours=active_hours, per_day=cph * active_hours,
        per_week=cph * active_hours * 7)


def hours_to_earn(amount: float, coins_per_hour: float) -> float:
    """Active flipping hours to earn ``amount`` coins (``inf`` if no income)."""
    if amount <= 0:
        return 0.0
    if coins_per_hour <= 0:
        return math.inf
    return amount / coins_per_hour


def eta_to_coins(current: float, target: float, coins_per_hour: float) -> float:
    """Active hours to grow ``current`` coins to ``target`` (0 if already there)."""
    return hours_to_earn(max(0.0, target - current), coins_per_hour)


def human_duration(hours: float, active_hours: float = 6.0) -> str:
    """Human-readable active-time estimate, e.g. '20.2h (~3.4 days @6h)'."""
    if hours == math.inf:
        return "never (no income)"
    if hours <= 0:
        return "already reached"
    if hours < 1:
        base = f"{hours * 60:.0f} min"
    elif hours < 48:
        base = f"{hours:.1f}h"
    else:
        base = f"{hours / 24:.1f} days"
    if active_hours > 0 and hours >= active_hours:
        days = hours / active_hours
        return f"{base} (~{days:.1f} days @{active_hours:g}h/day)"
    return base
