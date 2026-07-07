"""
Null's Addons -- order-flip finder.

Scans the whole Bazaar and returns the best *order flips* for an account: place
a Buy Order, wait for it to fill, place a Sell Offer, pocket the spread minus
tax.  Each result is a fully-sized, ready-to-execute :class:`FlipPlan` -- the
commands module turns it into "buy X of Y, wait Z minutes, sell".

Ranking is risk-adjusted velocity: ``coins_per_hour * confidence``.  A flip only
survives if it clears every floor in :class:`~nulladdons.economy.EvalParams`
(margin, liquidity, unit profit, confidence), which is what lets the
conservative profile behave like a "near-guaranteed profit" filter.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import economy, mechanics
from .bazaar import Market, Product
from .economy import EvalParams
from .history import PriceHistory


@dataclass
class FlipPlan:
    """A single, sized, executable order flip."""

    product_id: str
    buy_order_price: float
    sell_offer_price: float
    quantity: int
    orders_needed: int

    unit_profit: float
    margin: float
    capital_required: float
    total_profit: float

    buy_minutes: float
    sell_minutes: float
    total_minutes: float
    coins_per_hour: float

    confidence: float
    confidence_parts: dict
    binding_constraint: str

    @property
    def score(self) -> float:
        """Risk-adjusted ranking key: velocity discounted by confidence."""
        return self.coins_per_hour * self.confidence


def evaluate(product: Product, params: EvalParams, budget: float,
             history: PriceHistory | None = None) -> FlipPlan | None:
    """Evaluate one product as a flip; return a sized plan or ``None`` if it
    fails any risk floor."""
    if not product.has_two_sided_market:
        return None
    if product.liquidity < params.min_liquidity:
        return None
    # A wildly wide spread means the best bid/ask is a lone outlier, not a price
    # you can really fill against -- skip it before it flatters the numbers.
    if product.spread_pct > params.max_spread_pct:
        return None

    econ = mechanics.flip_unit_economics(
        product.best_bid, product.best_ask, params.tax)
    if econ["unit_profit"] < params.min_unit_profit:
        return None
    if not (params.min_margin <= econ["margin"] <= params.max_margin):
        return None

    qty, binding = economy.size_position(
        product, econ["unit_cost"], params, budget)
    if qty <= 0:
        return None

    fills = economy.fill_minutes(product, qty, params.capture_fraction)
    if fills["total_minutes"] > params.max_fill_minutes * 1.01:
        return None  # safety net; sizing should already respect this

    cph = economy.coins_per_hour(econ["unit_profit"], qty, fills["total_minutes"])
    if cph < params.min_coins_per_hour:
        return None

    conf, parts = economy.confidence(product, econ["margin"], history)
    if conf < params.min_confidence:
        return None

    return FlipPlan(
        product_id=product.product_id,
        buy_order_price=econ["buy_order_price"],
        sell_offer_price=econ["sell_offer_price"],
        quantity=qty,
        orders_needed=mechanics.orders_needed(qty),
        unit_profit=econ["unit_profit"],
        margin=econ["margin"],
        capital_required=econ["unit_cost"] * qty,
        total_profit=econ["unit_profit"] * qty,
        buy_minutes=fills["buy_minutes"],
        sell_minutes=fills["sell_minutes"],
        total_minutes=fills["total_minutes"],
        coins_per_hour=cph,
        confidence=conf,
        confidence_parts=parts,
        binding_constraint=binding,
    )


def find_flips(market: Market, params: EvalParams, budget: float,
               history: PriceHistory | None = None,
               limit: int | None = None,
               blacklist: set[str] | None = None,
               whitelist: set[str] | None = None) -> list[FlipPlan]:
    """Return all qualifying flips, best risk-adjusted opportunity first.

    ``blacklist`` skips product ids the account never wants to touch;
    ``whitelist`` (if given) restricts to only those ids."""
    plans: list[FlipPlan] = []
    for product in market.flippable():
        if blacklist and product.product_id in blacklist:
            continue
        if whitelist is not None and product.product_id not in whitelist:
            continue
        plan = evaluate(product, params, budget, history)
        if plan is not None:
            plans.append(plan)
    plans.sort(key=lambda p: p.score, reverse=True)
    return plans[:limit] if limit else plans
