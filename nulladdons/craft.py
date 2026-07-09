"""
Null's Addons -- craft-flip finder (materials arbitrage).

Some items are worth more crafted than raw: buy cheap materials off the Bazaar,
combine them (enchanting, compacting), and sell the product back for more.  This
is spatial arbitrage across the Bazaar's own price surface.

The engine is recursive and self-optimising.  ``acquisition_cost`` answers "what
is the cheapest way to obtain one unit of X?" by comparing *buying it* against
*crafting it from its inputs* -- and each input is priced the same way.  So a
2-step chain like ``Diamond -> Enchanted Diamond -> Enchanted Diamond Block`` is
discovered automatically: the block's recipe asks for Enchanted Diamond, which
the costing function decides is cheaper to craft from raw Diamond than to buy.

Because every price comes from the live market and every product id is checked
against it, a wrong id or a broken recipe simply prices out to infinity and is
skipped -- the tool can never emit a craft it cannot actually execute.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from . import economy, mechanics
from .bazaar import Market, Product
from .economy import EvalParams
from .history import PriceHistory

_INF = float("inf")


@dataclass(frozen=True)
class Recipe:
    output: str
    inputs: tuple[tuple[str, int], ...]   # ((ingredient_id, count), ...)
    output_qty: int = 1
    unlock: tuple[str, int] | None = None  # (collection_id, tier) if gated


def load_recipes(path: str) -> list[Recipe]:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []  # missing/corrupt DB -> just no craft flips, never a crash
    recipes: list[Recipe] = []
    for r in data.get("recipes", []):
        # Skip malformed / example entries rather than crashing the whole app.
        try:
            if not isinstance(r, dict) or not r.get("output") or not r.get("inputs"):
                continue
            unlock = None
            if r.get("unlock"):
                unlock = (r["unlock"]["collection"], int(r["unlock"]["tier"]))
            recipes.append(Recipe(
                output=str(r["output"]),
                inputs=tuple((str(i[0]), int(i[1])) for i in r["inputs"]),
                output_qty=int(r.get("output_qty", 1)),
                unlock=unlock,
            ))
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return recipes


def buy_order_unit_price(product: Product) -> float:
    """What it costs to acquire one unit via a Buy Order (front of the queue)."""
    return product.best_bid + mechanics.UNDERCUT_INCREMENT


def sell_offer_unit_net(product: Product, tax: float) -> float:
    """Coins received per unit from a Sell Offer at front of queue, after tax."""
    return mechanics.net_sell_unit(
        product.best_ask - mechanics.UNDERCUT_INCREMENT, tax)


@dataclass
class CraftStep:
    """One executable line of a craft: buy raws, or convert inputs into output."""
    action: str            # "buy" or "craft"
    item: str
    quantity: int
    unit_price: float = 0.0                    # for buy steps
    from_inputs: tuple[tuple[str, int], ...] = ()  # for craft steps


@dataclass
class CraftPlan:
    output_id: str
    quantity: int                              # output units produced
    input_cost_per_output: float
    sell_offer_price: float                    # gross price you list the output at
    revenue_per_output: float                  # net coins/output after tax
    unit_profit: float
    margin: float
    total_profit: float
    capital_required: float
    instant_unit_profit: float = 0.0   # worst-case: insta-buy raws, insta-sell output
    instant_margin: float = 0.0
    steps: list[CraftStep] = field(default_factory=list)
    raw_shopping: dict[str, tuple[int, float]] = field(default_factory=dict)  # id->(units,price)
    buy_minutes: float = 0.0
    sell_minutes: float = 0.0
    total_minutes: float = 0.0
    coins_per_hour: float = 0.0
    confidence: float = 0.0
    binding_constraint: str = ""

    @property
    def score(self) -> float:
        return self.coins_per_hour * self.confidence


class CraftEngine:
    """Prices and plans crafts against a live market snapshot."""

    def __init__(self, market: Market, recipes: list[Recipe], params: EvalParams,
                 allowed_outputs: set[str] | None = None):
        self.market = market
        self.params = params
        self.by_output: dict[str, Recipe] = {r.output: r for r in recipes}
        # ``allowed_outputs`` gates recipes the account hasn't unlocked yet.
        self.allowed = allowed_outputs
        self._cost_memo: dict[str, float] = {}
        self._method_memo: dict[str, str] = {}

    # --- cheapest acquisition (buy vs craft), recursive + memoised -----------

    def acquisition_cost(self, item: str, _stack: frozenset[str] = frozenset()) -> float:
        if item in self._cost_memo:
            return self._cost_memo[item]
        if item in _stack:                       # recipe cycle guard
            return _INF

        product = self.market.get(item)
        buy_cost = buy_order_unit_price(product) if product else _INF

        craft_cost = _INF
        recipe = self.by_output.get(item)
        if recipe is not None and self._unlocked(recipe):
            total = 0.0
            for ing, count in recipe.inputs:
                total += self.acquisition_cost(ing, _stack | {item}) * count
                if total == _INF:
                    break
            if total != _INF:
                craft_cost = total / recipe.output_qty

        if craft_cost < buy_cost:
            self._method_memo[item] = "craft"
            cost = craft_cost
        else:
            self._method_memo[item] = "buy"
            cost = buy_cost
        self._cost_memo[item] = cost
        return cost

    def _unlocked(self, recipe: Recipe) -> bool:
        return self.allowed is None or recipe.output in self.allowed

    # --- expand a target quantity into ordered, executable steps -------------

    def _expand(self, item: str, qty: int, steps: list[CraftStep],
                shopping: dict[str, int]) -> None:
        """Post-order: buy raws first, then craft upward to the target."""
        method = self._method_memo.get(item, "buy")
        recipe = self.by_output.get(item)
        if method == "craft" and recipe is not None:
            batches = math.ceil(qty / recipe.output_qty)
            for ing, count in recipe.inputs:
                self._expand(ing, batches * count, steps, shopping)
            steps.append(CraftStep(
                action="craft", item=item, quantity=batches * recipe.output_qty,
                from_inputs=tuple((ing, batches * count) for ing, count in recipe.inputs),
            ))
        else:
            product = self.market.get(item)
            price = buy_order_unit_price(product) if product else 0.0
            shopping[item] = shopping.get(item, 0) + qty
            steps.append(CraftStep(action="buy", item=item, quantity=qty, unit_price=price))

    # --- throughput of a craft (raw-buy leg vs product-sell leg) -------------

    def _throughput(self, output: Product, shopping_per_output: dict[str, float]):
        cap = self.params.capture_fraction
        sell_rate = economy.flow_per_min(output.demand_per_week) * \
            economy.effective_capture(output, cap, "sell")
        buy_rate = _INF
        for raw_id, per_out in shopping_per_output.items():
            product = self.market.get(raw_id)
            if not product or per_out <= 0:
                continue
            rate = economy.flow_per_min(product.supply_per_week) * \
                economy.effective_capture(product, cap, "buy") / per_out
            buy_rate = min(buy_rate, rate)
        return buy_rate, sell_rate

    # --- evaluate one recipe as a craft flip ---------------------------------

    def evaluate(self, recipe: Recipe, budget: float,
                 history: PriceHistory | None = None) -> CraftPlan | None:
        output = self.market.get(recipe.output)
        if output is None or not output.has_two_sided_market:
            return None
        if not self._unlocked(recipe):
            return None
        if output.demand_per_week < self.params.min_liquidity:
            return None

        # Prime memo, then cost one output via the cheapest path.
        cost_per_output = self.acquisition_cost(recipe.output)
        # Force the top-level item to actually be crafted (that's the whole point).
        if self._method_memo.get(recipe.output) != "craft":
            return None
        if cost_per_output == _INF or cost_per_output <= 0:
            return None

        sell_offer_price = output.best_ask - mechanics.UNDERCUT_INCREMENT
        revenue = sell_offer_unit_net(output, self.params.tax)
        unit_profit = revenue - cost_per_output
        margin = unit_profit / cost_per_output if cost_per_output > 0 else 0.0
        if unit_profit < self.params.min_unit_profit or margin < self.params.min_margin:
            return None
        # Absurdity ceiling: an efficient market never sustains a huge craft
        # margin, so anything above the ceiling is a manipulated/stale price OR a
        # wrong recipe ratio in our own data. Either way, refuse to recommend it.
        if margin > self.params.max_margin:
            return None

        # Flatten one output into its raw shopping list to model throughput.
        one_shopping: dict[str, int] = {}
        self._expand(recipe.output, 1, [], one_shopping)
        buy_rate, sell_rate = self._throughput(output, one_shopping)
        if buy_rate <= 0 or sell_rate <= 0:
            return None

        # Worst case, executable *right now*: buy every raw at the instant-buy
        # price and dump the product at the instant-sell price. If this still
        # profits, the craft is genuinely risk-free (no waiting, no fill risk).
        instant_cost = 0.0
        for rid, per_out in one_shopping.items():
            raw = self.market.get(rid)
            if raw:
                instant_cost += per_out * raw.best_ask
        instant_revenue = mechanics.net_sell_unit(output.best_bid, self.params.tax)
        instant_profit = instant_revenue - instant_cost
        instant_margin = instant_profit / instant_cost if instant_cost > 0 else 0.0
        if self.params.require_instant_profit and instant_profit <= 0:
            return None

        minutes_per_output = (1.0 / buy_rate) + (1.0 / sell_rate)
        q_time = self.params.max_fill_minutes / minutes_per_output
        q_budget = budget / cost_per_output
        q_impact = self.params.impact_fraction * output.demand_per_week
        caps = {"liquidity": q_time, "capital": q_budget, "impact": q_impact}
        binding = min(caps, key=caps.get)
        quantity = int(max(0, math.floor(caps[binding])))
        if quantity <= 0:
            return None

        # Build the real, ordered step list at the chosen quantity.
        steps: list[CraftStep] = []
        shopping_units: dict[str, int] = {}
        self._expand(recipe.output, quantity, steps, shopping_units)
        raw_shopping = {
            rid: (units, buy_order_unit_price(self.market.get(rid)))
            for rid, units in shopping_units.items() if self.market.get(rid)
        }

        total_minutes = quantity * minutes_per_output
        total_profit = unit_profit * quantity
        cph = economy.coins_per_hour(unit_profit, quantity, total_minutes)
        if cph < self.params.min_coins_per_hour:
            return None
        conf, _ = economy.confidence(output, margin, history)
        if conf < self.params.min_confidence:
            return None

        return CraftPlan(
            output_id=recipe.output,
            quantity=quantity,
            input_cost_per_output=cost_per_output,
            sell_offer_price=sell_offer_price,
            revenue_per_output=revenue,
            unit_profit=unit_profit,
            margin=margin,
            total_profit=total_profit,
            capital_required=cost_per_output * quantity,
            instant_unit_profit=instant_profit,
            instant_margin=instant_margin,
            steps=steps,
            raw_shopping=raw_shopping,
            buy_minutes=quantity / buy_rate,
            sell_minutes=quantity / sell_rate,
            total_minutes=total_minutes,
            coins_per_hour=cph,
            confidence=conf,
            binding_constraint=binding,
        )


def find_crafts(market: Market, recipes: list[Recipe], params: EvalParams,
                budget: float, history: PriceHistory | None = None,
                allowed_outputs: set[str] | None = None,
                limit: int | None = None,
                blacklist: set[str] | None = None,
                whitelist: set[str] | None = None) -> list[CraftPlan]:
    """Return all qualifying craft flips, best risk-adjusted opportunity first."""
    engine = CraftEngine(market, recipes, params, allowed_outputs)
    plans: list[CraftPlan] = []
    for recipe in recipes:
        if blacklist and recipe.output in blacklist:
            continue
        if whitelist is not None and recipe.output not in whitelist:
            continue
        # Fresh memo per recipe so top-level "force craft" logic stays correct.
        engine._cost_memo.clear()
        engine._method_memo.clear()
        plan = engine.evaluate(recipe, budget, history)
        if plan is not None:
            plans.append(plan)
    plans.sort(key=lambda p: p.score, reverse=True)
    return plans[:limit] if limit else plans
