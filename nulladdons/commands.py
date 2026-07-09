"""
Null's Addons -- turn analysis into direct, copy-me commands.

The whole promise of the tool is that the player never has to think about market
theory -- they just read a line and do it.  This module renders sized
:class:`~nulladdons.flip.FlipPlan` and :class:`~nulladdons.craft.CraftPlan`
objects into exactly that: "place this buy order, wait N minutes, place this
sell offer".

It also builds the ``plan`` view: a *diversified portfolio* that spreads the
account's capital across several uncorrelated opportunities (no single position
may exceed a set fraction of the bankroll), which is how you convert a pile of
good-looking edges into a low-variance income stream.
"""

from __future__ import annotations

from . import craft as craftmod
from . import flair
from . import flip as flipmod
from . import projection as projmod
from .accounts import AccountContext
from .bazaar import Market
from .craft import CraftPlan, Recipe
from .flip import FlipPlan
from .history import PriceHistory

# --- number / name formatting ----------------------------------------------

def coins(n: float) -> str:
    """Human coin formatting: 1_234_567 -> '1.23M'."""
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit, div in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= div:
            return f"{sign}{n / div:.2f}{unit}"
    return f"{sign}{n:,.1f}"


def price(n: float) -> str:
    return f"{n:,.1f}"


def minutes(m: float) -> str:
    if m == float("inf"):
        return "∞"
    if m < 1:
        return f"{m * 60:.0f}s"
    if m < 60:
        return f"{m:.1f} min"
    return f"{m / 60:.1f} h"


def nice_name(product_id: str) -> str:
    """'ENCHANTED_DIAMOND_BLOCK' -> 'Enchanted Diamond Block'."""
    base = product_id.split(":")[0]
    return base.replace("_", " ").title()


def mayor_lines(mc) -> list[str]:
    """Render the active/simulated mayor as a few concise lines (or none)."""
    if mc is None:
        return []
    out = [f"👑 {mc.headline()}"]
    out += [f"   {n}" for n in mc.notes]
    quip = flair.mayor_quip("tax_free" if getattr(mc, "tax_free", False) else "")
    if quip:
        out.append(f"   {quip}")
    from . import mayor as mayormod
    cand = mayormod.candidates_line(mc)
    if cand:
        out.append(f"   {cand}")
    return out


def mayor_banner(mc) -> str:
    return "\n".join(mayor_lines(mc))


# --- single-opportunity renderers ------------------------------------------

def render_flip(plan: FlipPlan, index: int | None = None) -> str:
    head = f"FLIP {('#' + str(index)) if index else ''}".rstrip()
    lines = [
        f"{head}  ·  {nice_name(plan.product_id)}"
        f"   [confidence {plan.confidence:.0%} · {coins(plan.coins_per_hour)}/hr]",
        f"   1. BUY ORDER  {plan.quantity:,} @ {price(plan.buy_order_price)}"
        f"   → outlay {coins(plan.capital_required)}",
        f"      wait ~{minutes(plan.buy_minutes)} to fill "
        f"(you're first in the buy queue)",
        f"   2. SELL OFFER {plan.quantity:,} @ {price(plan.sell_offer_price)}",
        f"      wait ~{minutes(plan.sell_minutes)} to fill",
        f"   ⇒ PROFIT {coins(plan.total_profit)}  (+{plan.margin:.1%} after tax)"
        f"   ·  round-trip ~{minutes(plan.total_minutes)}  ·  size capped by "
        f"{plan.binding_constraint}",
    ]
    if plan.orders_needed > 1:
        lines.append(f"      note: split across {plan.orders_needed} orders "
                     f"(71,680 unit/order cap)")
    return "\n".join(lines)


def render_craft(plan: CraftPlan, index: int | None = None) -> str:
    head = f"CRAFT {('#' + str(index)) if index else ''}".rstrip()
    lines = [
        f"{head}  ·  make {plan.quantity:,} × {nice_name(plan.output_id)}"
        f"   [confidence {plan.confidence:.0%} · {coins(plan.coins_per_hour)}/hr]",
    ]
    step_no = 1
    for step in plan.steps:
        if step.action == "buy":
            lines.append(
                f"   {step_no}. BUY ORDER {step.quantity:,} × "
                f"{nice_name(step.item)} @ {price(step.unit_price)}"
                f"   ({coins(step.quantity * step.unit_price)})")
        else:
            src = ", ".join(f"{cnt:,} {nice_name(i)}" for i, cnt in step.from_inputs)
            lines.append(
                f"   {step_no}. CRAFT {step.quantity:,} × "
                f"{nice_name(step.item)}  from  {src}")
        step_no += 1
    lines.append(
        f"   {step_no}. SELL OFFER {plan.quantity:,} × {nice_name(plan.output_id)}"
        f" @ {price(plan.sell_offer_price)}"
        f"   (nets {coins(plan.revenue_per_output)}/ea after tax)")
    guaranteed = (f"  ·  even insta-buy/insta-sell nets +{plan.instant_margin:.1%}"
                  if plan.instant_unit_profit > 0 else
                  "  ·  ⚠ only profits with patient orders (not instant)")
    lines.append(
        f"   ⇒ PROFIT {coins(plan.total_profit)}  (+{plan.margin:.1%} patient)"
        f"{guaranteed}")
    lines.append(
        f"      outlay {coins(plan.capital_required)}  ·  ~{minutes(plan.total_minutes)}"
        f"  ·  capped by {plan.binding_constraint}")
    return "\n".join(lines)


# --- magical power plan -----------------------------------------------------

def render_mp_plan(account: AccountContext, plan: dict) -> str:
    out = ["═" * 68,
           f" NULL'S ADDONS · MAGICAL POWER PLAN — {account.name} ({account.username})"]
    _tag = flair.tagline()
    if _tag:
        out.append(f" \"{_tag}\"")
    out.append("═" * 68)
    detail = f"owned accessories detected: {plan['owned_count']}"
    if not account.live:
        detail += "  (run --live to read your talisman bag)"
    if account.mp_goal:
        detail += f"   ·   goal: {account.mp_goal} MP"
    out.append(" " + detail)
    out.append("")

    if plan["picks"]:
        out.append(" BUY / CRAFT — cheapest Magical Power you don't own yet:")
        for i, b in enumerate(plan["picks"], 1):
            out.append(f"  {i}. +{b.mp_gain} MP  ·  {b.label}  ·  {coins(b.cost)}"
                       f"  ({coins(b.coins_per_mp)}/MP)")
            out.append(f"        → {b.how}")
        out.append(f"   ⇒ +{plan['mp_gained']} MP for {coins(plan['coins_spent'])} total")
    else:
        out.append(" BUY / CRAFT: " + flair.empty_mp())
        out.append("   Most cheap MP comes from talisman crafts specific to your")
        out.append("   collections — add their recipes to data/accessories.json and")
        out.append("   they'll be priced and ranked here automatically.")
    out.append("")

    if plan["recombs"]:
        out.append(" RECOMBOBULATOR 3000 — bump an accessory's rarity for more MP")
        out.append(" (cheapest coins/MP first; buy the recomb on the Bazaar):")
        for i, b in enumerate(plan["recombs"], 1):
            out.append(f"  {i}. +{b.mp_gain} MP  ·  {b.label}  ·  {coins(b.cost)}"
                       f"  ({coins(b.coins_per_mp)}/MP)")
    out.append("═" * 68)
    return "\n".join(out)


# --- portfolio (the `plan` view) -------------------------------------------

MAX_POSITION_FRACTION = 0.34   # diversification: no position > 34% of bankroll
MAX_SLOTS = 6                  # how many concurrent opportunities to spread over
MIN_REMAINDER_FRACTION = 0.02  # stop allocating once <2% of budget is left


def build_portfolio(account: AccountContext, market: Market,
                    recipes: list[Recipe], history: PriceHistory | None = None,
                    include_crafts: bool = True) -> list:
    """
    Greedily allocate the account's budget across the top opportunities,
    diversifying so no single flip/craft dominates.  Returns an ordered list of
    (FlipPlan | CraftPlan) sized to their allocated slice of capital.
    """
    budget = account.budget
    params = account.params

    # Rank candidates by risk-adjusted score at full budget.
    flips = flipmod.find_flips(market, params, budget, history, limit=40,
                               blacklist=account.blacklist,
                               whitelist=account.whitelist)
    crafts = (craftmod.find_crafts(market, recipes, params, budget, history,
                                   account.allowed_outputs, limit=40,
                                   blacklist=account.blacklist,
                                   whitelist=account.whitelist)
              if include_crafts else [])
    by_output = {r.output: r for r in recipes}

    candidates = sorted(
        [("flip", p) for p in flips] + [("craft", p) for p in crafts],
        key=lambda kp: kp[1].score, reverse=True,
    )

    portfolio: list = []
    used_keys: set[str] = set()
    remaining = budget
    slot_cap = min(MAX_SLOTS, params.max_orders_per_flip * 3 + 3)

    for kind, cand in candidates:
        if len(portfolio) >= slot_cap or remaining <= budget * MIN_REMAINDER_FRACTION:
            break
        key = cand.product_id if kind == "flip" else cand.output_id
        if key in used_keys:
            continue
        alloc = min(remaining, budget * MAX_POSITION_FRACTION)

        if kind == "flip":
            product = market.get(cand.product_id)
            sized = flipmod.evaluate(product, params, alloc, history)
        else:
            engine = craftmod.CraftEngine(market, recipes, params,
                                          account.allowed_outputs)
            sized = engine.evaluate(by_output[cand.output_id], alloc, history)

        if sized is None or sized.capital_required <= 0:
            continue
        portfolio.append(sized)
        used_keys.add(key)
        remaining -= sized.capital_required

    return portfolio


def render_portfolio(account: AccountContext, portfolio: list) -> str:
    total_profit = sum(p.total_profit for p in portfolio)
    total_capital = sum(p.capital_required for p in portfolio)
    total_cph = sum(p.coins_per_hour for p in portfolio)
    max_time = max((p.total_minutes for p in portfolio), default=0.0)

    out = ["═" * 68, f" NULL'S ADDONS · SESSION PLAN — {account.summary()}"]
    _tag = flair.tagline()
    if _tag:
        out.append(f" \"{_tag}\"")
    out.append("═" * 68)
    mayor_ctx = getattr(account, "mayor", None)
    if mayor_ctx is not None:
        out += mayor_lines(mayor_ctx)
        out.append("")
    if not portfolio:
        out.append(flair.empty_plan())
        return "\n".join(out)

    for i, plan in enumerate(portfolio, 1):
        if isinstance(plan, FlipPlan):
            out.append(render_flip(plan, i))
        else:
            out.append(render_craft(plan, i))
        out.append("")

    out.append("─" * 68)
    out.append(
        f" Deploy {coins(total_capital)} of {coins(account.budget)} across "
        f"{len(portfolio)} positions (diversified, ≤{MAX_POSITION_FRACTION:.0%} each)")
    out.append(
        f" Expected profit this cycle: {coins(total_profit)}"
        f"   ·   combined ~{coins(total_cph)}/hr running in parallel")
    proj = projmod.project_bazaar_income(portfolio, account.active_hours)
    out.append(
        f" At your capital: ~{coins(proj.coins_per_hour)}/hr → "
        f"~{coins(proj.per_day)}/day ({account.active_hours:g}h) → "
        f"~{coins(proj.per_week)}/week  (reinvest to compound)")
    out.append(
        f" Longest position fills in ~{minutes(max_time)}. Re-run to re-price as "
        f"the market moves.")
    out.append("─" * 68)
    return "\n".join(out)


def _one_line_action(plan) -> str:
    if isinstance(plan, FlipPlan):
        return (f"buy {plan.quantity:,} {nice_name(plan.product_id)} @ "
                f"{price(plan.buy_order_price)} → sell @ {price(plan.sell_offer_price)}"
                f"  ({coins(plan.total_profit)}, +{plan.margin:.1%})")
    return (f"craft {plan.quantity:,}× {nice_name(plan.output_id)}"
            f"  ({coins(plan.total_profit)}, +{plan.margin:.1%})")


def render_status(account: AccountContext, portfolio: list, mp_plan: dict,
                  ah: dict | None = None, prog_diff: dict | None = None,
                  movers: list | None = None) -> str:
    """The ecosystem dashboard: capital → income → goals → AH → next action."""
    src = "live" if account.live else "config"
    proj = projmod.project_bazaar_income(portfolio, account.active_hours)
    out = ["═" * 68, f" NULL'S ADDONS · ECOSYSTEM STATUS — {account.name}  [{src}]"]
    _tag = flair.tagline()
    if _tag:
        out.append(f" \"{_tag}\"")
    out.append("═" * 68)
    out.append(f" Capital: {coins(account.budget)}   ·   {account.risk} risk"
               f"   ·   {proj.positions} live positions")
    if prog_diff and prog_diff.get("baseline") and prog_diff.get("lines"):
        out.append(f" Today: " + " · ".join(prog_diff["lines"][:2]))

    mayor_ctx = getattr(account, "mayor", None)
    if mayor_ctx is not None:
        out.append("")
        out.append(" ── Mayor ──")
        out += [f"  {ln}" for ln in mayor_lines(mayor_ctx)]

    out.append("")
    out.append(" ── Bazaar income potential ──")
    if portfolio:
        out.append(f"   Deploy {coins(proj.capital_deployed)} across "
                   f"{proj.positions} positions → {coins(proj.coins_per_hour)}/hr")
        out.append(f"   ≈ {coins(proj.per_day)} / {account.active_hours:g}h day"
                   f"   ·   ≈ {coins(proj.per_week)} / week")
        out.append("   (capital-limited; reinvest profits to compound faster)")
    else:
        out.append("   No qualifying flips right now — try --risk aggressive.")

    # Goals
    out.append("")
    out.append(" ── Goals ──")
    if account.coin_goal:
        eta = projmod.eta_to_coins(account.budget, account.coin_goal,
                                   proj.coins_per_hour)
        remaining = max(0, account.coin_goal - account.budget)
        out.append(f"   Coins {coins(account.budget)} → {coins(account.coin_goal)}"
                   f"  ({coins(remaining)} to go): "
                   f"{projmod.human_duration(eta, account.active_hours)}")
    picks = (mp_plan or {}).get("picks") or []
    recombs = (mp_plan or {}).get("recombs") or []
    if account.mp_goal:
        out.append(f"   Magical Power goal: {account.mp_goal} MP"
                   + (f" · owned accessories detected: {mp_plan.get('owned_count', 0)}"
                      if account.live else ""))
    if picks:
        b = picks[0]
        out.append(f"   Cheapest MP: {b.label} +{b.mp_gain} MP for {coins(b.cost)}"
                   f" ({coins(b.coins_per_mp)}/MP)")
    if recombs:
        b = recombs[0]
        afford = projmod.hours_to_earn(b.cost, proj.coins_per_hour)
        out.append(f"   Best recomb: {coins(b.coins_per_mp)}/MP — afford one in "
                   f"{projmod.human_duration(afford, account.active_hours)}")

    # Auction House
    if ah:
        out.append("")
        out.append(" ── Auction House ──")
        listing = ah.get("listings")
        if listing:
            out.append(f"   {listing.active} active · {listing.sold_claimable} "
                       f"sold & claimable ({coins(listing.sold_value)})")
        elif not account.live:
            out.append("   run --live with an API key to see your listings")
        if ah.get("recent_sales"):
            name, p = ah["recent_sales"][0]
            out.append(f"   top recent sale: {nice_name(name)} {coins(p)}")

    # Market movers (from your accumulated price history)
    if movers:
        out.append("")
        out.append(" ── Market movers (over your recent history) ──")
        for pid, pct in movers:
            arrow = "📈" if pct >= 0 else "📉"
            out.append(f"   {arrow} {nice_name(pid)}  {pct:+.0%}")

    # Next action
    if portfolio:
        out.append("")
        out.append(" ── Do this now ──")
        out.append("   " + _one_line_action(portfolio[0]))
    out.append("═" * 68)
    return "\n".join(out)
