"""
Null's Addons -- the economics engine.

This is where the "economy theory" lives.  Each concept below maps to a real
market-microstructure idea and to concrete code:

* **Bid-ask spread**            -> :func:`nulladdons.mechanics.flip_unit_economics`
* **Liquidity (Kyle's lambda)** -> :func:`fill_minutes`: weekly instant-flow sets
  how fast an order fills; thin flow = slow = risky.
* **Market impact / elasticity**-> :func:`size_position`: you may only take a
  small slice of weekly flow, or your own order moves the price against you.
* **Expected value & velocity** -> :func:`coins_per_hour`: profit is worthless
  without turnover; coins/hour (margin x velocity) is the real objective.
* **Volatility & mean reversion**-> :func:`confidence` uses the price-history
  z-score and coefficient of variation to down-weight unstable markets and to
  favour buying below fair value / selling above it.
* **Manipulation detection**    -> :func:`confidence` penalises "too good to be
  true" spreads sitting on razor-thin volume and order books.
* **Risk-adjusted ranking**     -> ``coins_per_hour * confidence``.

Everything is a pure function of a :class:`~nulladdons.bazaar.Product`, an
:class:`EvalParams`, and (optionally) price history, so it is fully testable
without the network.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import mechanics
from .bazaar import Product
from .history import PriceHistory

# Curve anchors for the confidence sub-scores (documented, tunable constants).
_LIQ_FLOOR = 50_000        # weekly flow below this earns ~0 liquidity confidence
_LIQ_FULL = 10_000_000     # weekly flow at/above this earns full liquidity conf
_DEPTH_FULL = 20_000       # resting units (bid+ask) for full depth confidence
_SUSPICIOUS_MARGIN = 0.50  # margins above this smell like manipulation/stale data
_VOL_CAP = 0.12            # coefficient of variation at which volatility conf -> 0


@dataclass
class EvalParams:
    """Tunable knobs an account's risk profile feeds into the engine."""

    tax: float = mechanics.BASE_BAZAAR_TAX
    capture_fraction: float = 0.5      # share of instant-flow your front order wins
    max_fill_minutes: float = 30.0     # patience: total round-trip time budget
    impact_fraction: float = 0.02      # max slice of weekly flow you'll consume
    max_orders_per_flip: int = 1       # Bazaar order slots to spend per opportunity
    min_margin: float = 0.02           # 2% after-tax margin floor
    min_liquidity: int = 200_000       # weekly flow floor (thinner => skipped)
    min_unit_profit: float = 0.1       # ignore sub-0.1-coin/unit dust
    min_coins_per_hour: float = 0.0
    min_confidence: float = 0.0        # "guarantee" mode raises this
    # --- sanity ceilings (manipulation / bad-data / wrong-recipe guards) -----
    max_margin: float = 3.0            # reject "too good to be true" margins
    max_spread_pct: float = 0.50       # reject flip books whose spread is an outlier
    require_instant_profit: bool = False  # crafts must profit even insta-buy/insta-sell


def flow_per_min(weekly_units: int) -> float:
    """Convert a rolling weekly instant-flow into a per-minute rate."""
    return weekly_units / mechanics.WEEK_MINUTES


def fill_minutes(product: Product, quantity: float, capture: float) -> dict:
    """
    Estimate how long each leg of a flip takes.

    * Your **buy order** fills from other players' *instant sells* -> it drains
      the product's weekly **supply** flow.
    * Your **sell offer** fills from other players' *instant buys* -> it drains
      the weekly **demand** flow.

    ``capture`` is the fraction of that flow your front-of-queue order actually
    wins (you share it with rival flippers).  Returns per-leg and total minutes;
    ``inf`` if a side has no flow at all.
    """
    supply_rate = flow_per_min(product.supply_per_week) * capture
    demand_rate = flow_per_min(product.demand_per_week) * capture
    buy_leg = quantity / supply_rate if supply_rate > 0 else math.inf
    sell_leg = quantity / demand_rate if demand_rate > 0 else math.inf
    return {"buy_minutes": buy_leg, "sell_minutes": sell_leg,
            "total_minutes": buy_leg + sell_leg}


def max_quantity_for_time(product: Product, minutes: float, capture: float) -> float:
    """Largest position whose full round-trip is expected to fill within ``minutes``."""
    supply_rate = flow_per_min(product.supply_per_week) * capture
    demand_rate = flow_per_min(product.demand_per_week) * capture
    if supply_rate <= 0 or demand_rate <= 0:
        return 0.0
    minutes_per_unit = (1.0 / supply_rate) + (1.0 / demand_rate)
    return minutes / minutes_per_unit if minutes_per_unit > 0 else 0.0


def size_position(product: Product, unit_cost: float, params: EvalParams,
                  budget: float) -> tuple[int, str]:
    """
    Decide how many units to flip, and *why* that number (the binding limit).

    The position is the minimum of four independent caps -- this is textbook
    risk management: never let any single constraint be silently violated.

    * **Capital**   -- what ``budget`` can afford at the buy price.
    * **Liquidity** -- what will actually fill inside ``max_fill_minutes``.
    * **Impact**    -- a small slice of weekly flow, so you don't move the price.
    * **Order cap** -- Bazaar's 71,680-per-order hard limit x allowed slots.
    """
    if unit_cost <= 0:
        return 0, "invalid-price"
    caps = {
        "capital": budget / unit_cost,
        "liquidity": max_quantity_for_time(product, params.max_fill_minutes,
                                            params.capture_fraction),
        "impact": params.impact_fraction * product.liquidity,
        "order-cap": mechanics.ORDER_UNIT_LIMIT * params.max_orders_per_flip,
    }
    binding = min(caps, key=caps.get)
    qty = int(max(0, math.floor(caps[binding])))
    return qty, binding


def coins_per_hour(unit_profit: float, quantity: float, total_minutes: float) -> float:
    """Velocity-adjusted profit: the metric that actually maximises earnings."""
    if total_minutes <= 0 or quantity <= 0:
        return 0.0
    return unit_profit * quantity / (total_minutes / 60.0)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _liquidity_confidence(liquidity: int) -> float:
    if liquidity <= _LIQ_FLOOR:
        return 0.0
    span = math.log10(_LIQ_FULL) - math.log10(_LIQ_FLOOR)
    return _clamp((math.log10(liquidity) - math.log10(_LIQ_FLOOR)) / span)


def _depth_confidence(product: Product) -> float:
    resting = product.best_bid_amount + product.best_ask_amount
    depth = _clamp(resting / _DEPTH_FULL)
    # A market with only one order on a side is trivially manipulated; reward
    # having several independent orders on both sides.
    breadth = _clamp(min(product.bid_orders, product.ask_orders) / 5.0)
    return 0.5 * depth + 0.5 * breadth


def _margin_confidence(margin: float) -> float:
    if margin <= 0:
        return 0.0
    if margin <= 0.15:
        # More margin is better, up to a healthy 15%.
        return _clamp(0.4 + margin / 0.15 * 0.6)
    if margin <= _SUSPICIOUS_MARGIN:
        return 1.0
    # Beyond ~50% the "profit" is usually a stale quote or a manipulation trap.
    return _clamp(1.0 - (margin - _SUSPICIOUS_MARGIN) * 1.5, 0.15, 1.0)


def confidence(product: Product, margin: float, history: PriceHistory | None,
               ) -> tuple[float, dict]:
    """
    A 0..1 confidence that this flip is real and will pay out.

    Blends liquidity, order-book depth/breadth, margin sanity and (if price
    history exists) volatility, then nudges by mean-reversion: a price sitting
    below its recent average is a safer buy.
    """
    liq_c = _liquidity_confidence(product.liquidity)
    depth_c = _depth_confidence(product)
    margin_c = _margin_confidence(margin)
    # A blown-out spread means the top of book is a lone outlier you can't
    # actually trade against -- the classic manipulation tell.
    spread_c = _clamp(1.0 - product.spread_pct / 0.5)

    vol_c = 0.7  # neutral prior when we have no history yet
    reversion = 0.0
    if history is not None:
        vol = history.volatility(product.product_id)
        if vol is not None:
            vol_c = _clamp(1.0 - vol / _VOL_CAP)
        z = history.zscore(product.product_id, product.mid)
        if z is not None:
            # Cheap vs recent mean (z<0) is favourable; rich (z>0) is a caution.
            reversion = _clamp(-z * 0.05, -0.10, 0.10)

    base = (0.35 * liq_c + 0.15 * depth_c + 0.20 * margin_c
            + 0.15 * vol_c + 0.15 * spread_c)
    score = _clamp(base + reversion)
    parts = {"liquidity": liq_c, "depth": depth_c, "margin": margin_c,
             "volatility": vol_c, "spread": spread_c, "reversion": reversion}
    return score, parts
