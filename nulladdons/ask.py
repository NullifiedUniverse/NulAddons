"""
Null's Addons -- ``ask``: a grounded question-answerer over live game data.

Ask anything in plain English -- "how much profit flipping enchanted diamond?",
"who's the mayor?", "what should I craft?", "how long until 500m?" -- and get an
answer built strictly from **live** Hypixel data (Bazaar, Auction House, Mayor,
your account).

Anti-hallucination is the whole point.  Two layers:

1. **Retrieval**: the question is parsed for item mentions and intents, and only
   the *relevant* live facts are assembled into a FACTS sheet.
2. **Answering**: if a Gemini key is set, the FACTS + question go to the model
   under a strict prompt that forbids inventing anything and requires it to say
   "I don't know based on the current data." when unsupported.  Without a key, a
   deterministic local answerer handles the common questions from the same facts
   -- and also says it doesn't know rather than guess.

Either way, numbers only ever come from the live API, never from the model's
imagination.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import economy, flair, llm, mechanics
from .commands import coins, nice_name, price

DONT_KNOW = "I don't know based on the current data."


@dataclass
class AskContext:
    account: object
    market: object
    tax: float = mechanics.BASE_BAZAAR_TAX
    mayor: object = None
    items: list = field(default_factory=list)         # [(product_id, Product)]
    flips: list = field(default_factory=list)
    crafts: list = field(default_factory=list)
    mp_plan: dict | None = None
    projection: object = None
    ah_recent: list = field(default_factory=list)     # [(id, price)]
    ah_index: object = None
    stats: dict | None = None                         # progress stats if live
    data_age: float | None = None


# --- retrieval: which items does the question mention? ----------------------

_STOP = {"the", "a", "an", "of", "is", "are", "for", "and", "to", "in", "on",
         "my", "me", "i", "how", "much", "many", "what", "whats", "price",
         "cost", "worth", "buy", "sell", "flip", "flipping", "profit", "make",
         "should", "can", "do", "does", "with", "now", "right"}


def find_items(question: str, market, limit: int = 6) -> list:
    """Return product ids mentioned in the question (longest names first)."""
    ql = " " + re.sub(r"[^a-z0-9 ]", " ", question.lower()) + " "
    ql = re.sub(r"\s+", " ", ql)
    # Build a name -> id index (nice name + raw id, both normalised).
    index: dict[str, str] = {}
    for pid in market.products:
        index[nice_name(pid).lower()] = pid
        index[re.sub(r"[^a-z0-9 ]", " ", pid.lower())] = pid
    found: list[str] = []
    for name in sorted(index, key=len, reverse=True):
        if len(name) < 4 or name in _STOP:
            continue
        if f" {name} " in ql:
            pid = index[name]
            if pid not in found:
                found.append(pid)
                ql = ql.replace(f" {name} ", "  ")  # consume, avoid sub-matches
            if len(found) >= limit:
                break
    return found


# --- fact-sheet assembly (shared by LLM and local answerer) -----------------

def _item_fact(pid, product, tax) -> str:
    econ = mechanics.flip_unit_economics(product.best_bid, product.best_ask, tax)
    conf, _ = economy.confidence(product, econ["margin"], None)
    return (
        f"- {nice_name(pid)} ({pid}): instant-buy {price(product.best_ask)}, "
        f"instant-sell {price(product.best_bid)}, spread {product.spread_pct:.1%}, "
        f"demand/wk {coins(product.demand_per_week)}, supply/wk "
        f"{coins(product.supply_per_week)}. "
        f"FLIP: buy-order {price(econ['buy_order_price'])} -> sell-offer "
        f"{price(econ['sell_offer_price'])}, profit {price(econ['unit_profit'])}"
        f"/unit (+{econ['margin']:.1%} after {tax:.2%} tax), confidence {conf:.0%}.")


def build_facts(ctx: AskContext) -> str:
    acc = ctx.account
    lines = ["FACTS (live Hypixel data" +
             (f", {ctx.data_age:.0f}s old" if ctx.data_age is not None else "") + "):"]

    # Account + macro.
    src = "live" if getattr(acc, "live", False) else "configured"
    lines.append(f"Account: {acc.name}, capital {coins(acc.budget)} ({src}), "
                 f"{acc.risk} risk, Bazaar tax {ctx.tax:.2%}.")
    if getattr(acc, "coin_goal", 0):
        lines.append(f"Coin goal: {coins(acc.coin_goal)}. "
                     f"MP goal: {getattr(acc, 'mp_goal', 0)}.")
    if ctx.mayor is not None:
        tf = " (TAX-FREE — 0% Bazaar tax)" if getattr(ctx.mayor, "tax_free", False) else ""
        lines.append(f"Mayor: {ctx.mayor.name}{tf}. " +
                     "; ".join(ctx.mayor.notes[:2]))
    if ctx.projection is not None:
        lines.append(f"Income potential at your capital: "
                     f"{coins(ctx.projection.coins_per_hour)}/hr, "
                     f"{coins(ctx.projection.per_day)}/day, "
                     f"{coins(ctx.projection.per_week)}/week.")
    if ctx.stats:
        s = ctx.stats
        lines.append(f"Profile: {coins(s.get('coins', 0))} coins, skill avg "
                     f"{s.get('skill_average', '?')}, {s.get('pets', 0)} pets.")

    # Mentioned items.
    if ctx.items:
        lines.append("ITEMS ASKED ABOUT:")
        for pid, product in ctx.items:
            lines.append(_item_fact(pid, product, ctx.tax))
            if ctx.ah_index is not None:
                st = ctx.ah_index.stats(pid)
                if st:
                    lines.append(f"  AH recent sales: median {coins(st['median'])} "
                                 f"({st['count']} samples).")

    # Opportunities.
    if ctx.flips:
        lines.append("TOP BAZAAR FLIPS NOW:")
        for p in ctx.flips[:4]:
            lines.append(f"- {nice_name(p.product_id)}: profit {coins(p.total_profit)} "
                         f"(+{p.margin:.1%}), {coins(p.coins_per_hour)}/hr, "
                         f"{p.confidence:.0%} conf.")
    if ctx.crafts:
        lines.append("TOP CRAFTS NOW:")
        for p in ctx.crafts[:3]:
            lines.append(f"- craft {p.quantity:,} {nice_name(p.output_id)}: "
                         f"profit {coins(p.total_profit)} (+{p.margin:.1%}).")
    mp = ctx.mp_plan or {}
    if mp.get("picks") or mp.get("recombs"):
        best = (mp.get("picks") or mp.get("recombs"))[0]
        lines.append(f"CHEAPEST MAGICAL POWER: {best.label} +{best.mp_gain} MP "
                     f"for {coins(best.cost)} ({coins(best.coins_per_mp)}/MP).")
    if ctx.ah_recent:
        lines.append("AH RECENT NOTABLE SALES: " + ", ".join(
            f"{nice_name(n)} {coins(p)}" for n, p in ctx.ah_recent[:4]))
    return "\n".join(lines)


# --- deterministic local answerer (no key needed, never hallucinates) -------

def _has(ql, *words) -> bool:
    return any(w in ql for w in words)


def local_answer(question: str, ctx: AskContext) -> str:
    ql = " " + question.lower().strip() + " "

    if _has(ql, "mayor", "election", "derpy", "perk"):
        if ctx.mayor is None:
            return DONT_KNOW + " Mayor data isn't loaded (are you offline?)."
        out = [ctx.mayor.headline()] + ctx.mayor.notes[:2]
        return " ".join(out)

    # Item-specific: flip/profit is more specific than a plain price query.
    if ctx.items:
        pid, product = ctx.items[0]
        if _has(ql, "flip", "profit", "margin", "make money", "worth flipping"):
            econ = mechanics.flip_unit_economics(product.best_bid, product.best_ask, ctx.tax)
            if econ["unit_profit"] <= 0:
                return (f"{nice_name(pid)} isn't a good flip right now — the "
                        f"spread doesn't cover the {ctx.tax:.2%} tax.")
            return (f"Flip {nice_name(pid)}: buy-order {price(econ['buy_order_price'])}"
                    f", sell-offer {price(econ['sell_offer_price'])} → "
                    f"{price(econ['unit_profit'])}/unit (+{econ['margin']:.1%} "
                    f"after tax). Confidence and sizing: see `nulladdons item {pid}`.")
        if _has(ql, "price", "cost", "worth", "how much", "value", "sell", "buy"):
            return (f"{nice_name(pid)}: instant-buy {price(product.best_ask)}, "
                    f"instant-sell {price(product.best_bid)} coins "
                    f"(spread {product.spread_pct:.1%}).")
        # An item was named but no clear intent → give both.
        econ = mechanics.flip_unit_economics(product.best_bid, product.best_ask, ctx.tax)
        return (f"{nice_name(pid)}: buy {price(product.best_ask)} / sell "
                f"{price(product.best_bid)}. As a flip: +{econ['margin']:.1%} "
                f"({price(econ['unit_profit'])}/unit after tax).")

    if _has(ql, "best flip", "what to flip", "what should i flip", "top flip") and ctx.flips:
        p = ctx.flips[0]
        return (f"Best flip now: buy {p.quantity:,} {nice_name(p.product_id)} @ "
                f"{price(p.buy_order_price)}, sell @ {price(p.sell_offer_price)} → "
                f"{coins(p.total_profit)} (+{p.margin:.1%}).")
    if _has(ql, "craft") and ctx.crafts:
        p = ctx.crafts[0]
        return (f"Best craft now: {p.quantity:,}× {nice_name(p.output_id)} → "
                f"{coins(p.total_profit)} (+{p.margin:.1%}).")
    if _has(ql, "income", "per hour", "per day", "per week", "how much can i",
            "make a day", "earn") and ctx.projection is not None:
        pr = ctx.projection
        return (f"At your {coins(ctx.account.budget)} capital you can make about "
                f"{coins(pr.coins_per_hour)}/hr → {coins(pr.per_day)}/day → "
                f"{coins(pr.per_week)}/week (capital-limited; reinvest to compound).")
    if _has(ql, "budget", "capital", "how much money", "balance", "coins do i",
            "how much do i have"):
        return f"Your working capital is {coins(ctx.account.budget)}."
    if _has(ql, "magical power", " mp ", "accessor", "recomb"):
        mp = ctx.mp_plan or {}
        best = (mp.get("picks") or mp.get("recombs") or [None])[0]
        if best:
            return (f"Cheapest Magical Power: {best.label} — +{best.mp_gain} MP for "
                    f"{coins(best.cost)} ({coins(best.coins_per_mp)}/MP).")
    if _has(ql, "goal", "how long", "when will", "eta") and ctx.projection is not None \
            and getattr(ctx.account, "coin_goal", 0):
        from . import projection as projmod
        eta = projmod.eta_to_coins(ctx.account.budget, ctx.account.coin_goal,
                                   ctx.projection.coins_per_hour)
        return (f"To reach {coins(ctx.account.coin_goal)} from "
                f"{coins(ctx.account.budget)}: about "
                f"{projmod.human_duration(eta, getattr(ctx.account, 'active_hours', 6))}.")
    if _has(ql, "auction", " ah ", "sold", "bin") and ctx.ah_recent:
        return "Recent notable AH sales: " + ", ".join(
            f"{nice_name(n)} {coins(p)}" for n, p in ctx.ah_recent[:4]) + "."

    return (DONT_KNOW + " Try asking about a specific item (price/flip), the "
            "mayor, your income/budget, the best flip or craft, or magical power.")


# --- orchestration ----------------------------------------------------------

def answer(question: str, ctx: AskContext, gemini_key: str | None = None,
           model: str = llm.DEFAULT_MODEL) -> tuple[str, bool]:
    """Return (answer, produced_by_llm). Falls back to the local answerer."""
    # Meme questions get a flavour reply (never fabricated market data). Off in
    # serious mode. Real market questions never match these.
    egg = flair.easter_egg(question)
    if egg is not None:
        return egg, False
    facts = build_facts(ctx)
    if gemini_key:
        prompt = f"{facts}\n\nQUESTION: {question.strip()}"
        text = llm.gemini_generate(prompt, system=llm.ANSWER_SYSTEM,
                                   api_key=gemini_key, model=model,
                                   temperature=0.2, max_tokens=500)
        if text:
            return text, True
    return local_answer(question, ctx), False
