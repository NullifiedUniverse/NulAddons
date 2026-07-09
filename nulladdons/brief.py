"""
Null's Addons -- the daily SkyBlock brief.

Gathers everything worth knowing today -- account progress vs yesterday, the best
live Bazaar/craft flips, cheapest Magical Power, and Auction House highlights --
into a compact set of FACTS, hands them to a Gemini SkyBlock-expert model for a
human summary, and renders the result.  If Gemini is unavailable it falls back to
a deterministic local brief built from the exact same facts, so the command
always produces something useful.
"""

from __future__ import annotations

from . import flair, llm
from .commands import coins, nice_name


def build_context(account, *, data_age=None, stats=None, prog_diff=None,
                  flips=None, crafts=None, mp_plan=None, ah=None) -> dict:
    return {
        "account": account,
        "data_age": data_age,
        "stats": stats,
        "prog_diff": prog_diff or {},
        "flips": flips or [],
        "crafts": crafts or [],
        "mp_plan": mp_plan or {},
        "ah": ah or {},
    }


# --- fact sheet handed to the LLM ------------------------------------------

def facts_text(ctx: dict) -> str:
    acc = ctx["account"]
    s = ctx.get("stats")
    lines = [f"ACCOUNT: {acc.name} ({acc.username})"
             + (f", profile {s['profile_name']}" if s and s.get("profile_name") else "")]
    if s:
        lines.append(f"COINS: {s['coins']:,} (purse {s['purse']:,} + bank {s['bank']:,})")
        if s.get("skill_average") is not None:
            lines.append(f"SKILL AVERAGE: {s['skill_average']}")
        if s.get("catacombs_xp"):
            lines.append(f"CATACOMBS XP: {s['catacombs_xp']:,}")

    mc = getattr(acc, "mayor", None)
    if mc is not None:
        lines.append("MAYOR: " + mc.name +
                     (" — TAX-FREE (0% Bazaar tax right now!)" if mc.tax_free else ""))
        for n in mc.notes[:2]:
            lines.append(f"- {n}")

    pd = ctx.get("prog_diff") or {}
    if pd.get("lines"):
        span = f" ({pd.get('days', 0)}d)" if pd.get("baseline") else ""
        lines.append(f"PROGRESS SINCE LAST SNAPSHOT{span}:")
        lines += [f"- {ln}" for ln in pd["lines"]]

    if ctx["flips"]:
        lines.append("TOP BAZAAR FLIPS:")
        for p in ctx["flips"][:4]:
            lines.append(f"- {nice_name(p.product_id)}: buy {p.quantity:,} @ "
                         f"{p.buy_order_price:,.1f}, sell @ {p.sell_offer_price:,.1f}"
                         f", profit {coins(p.total_profit)} (+{p.margin:.1%}), "
                         f"{coins(p.coins_per_hour)}/hr, {p.confidence:.0%} conf")
    if ctx["crafts"]:
        lines.append("TOP CRAFTS:")
        for p in ctx["crafts"][:3]:
            lines.append(f"- craft {p.quantity:,} {nice_name(p.output_id)}: profit "
                         f"{coins(p.total_profit)} (+{p.margin:.1%})")

    mp = ctx.get("mp_plan") or {}
    if mp.get("picks") or mp.get("recombs"):
        lines.append("MAGICAL POWER:")
        for b in (mp.get("picks") or [])[:2]:
            lines.append(f"- buy: {b.label} +{b.mp_gain} MP for {coins(b.cost)} "
                         f"({coins(b.coins_per_mp)}/MP)")
        if mp.get("recombs"):
            b = mp["recombs"][0]
            lines.append(f"- best recomb: {b.label} +{b.mp_gain} MP "
                         f"({coins(b.coins_per_mp)}/MP)")

    ah = ctx.get("ah") or {}
    if ah.get("recent_sales"):
        lines.append("AUCTION HOUSE recent notable sales:")
        for name, price in ah["recent_sales"][:5]:
            lines.append(f"- {nice_name(name)}: {coins(price)}")
    listing = ah.get("listings")
    if listing:
        lines.append(f"YOUR AH LISTINGS: {listing.active} active, "
                     f"{listing.sold_claimable} sold & claimable "
                     f"(worth {coins(listing.sold_value)})")
    return "\n".join(lines)


# --- deterministic fallback -------------------------------------------------

def local_brief(ctx: dict) -> str:
    pd = ctx.get("prog_diff") or {}
    out = []
    if pd.get("lines"):
        out.append("Since your last snapshot:")
        out += [f"  • {ln}" for ln in pd["lines"]]
    recs = []
    if ctx["flips"]:
        p = ctx["flips"][0]
        recs.append(f"Best flip: buy {p.quantity:,} {nice_name(p.product_id)} @ "
                    f"{p.buy_order_price:,.1f}, sell @ {p.sell_offer_price:,.1f} "
                    f"→ {coins(p.total_profit)} (+{p.margin:.1%}).")
    if ctx["crafts"]:
        p = ctx["crafts"][0]
        recs.append(f"Best craft: {p.quantity:,}× {nice_name(p.output_id)} → "
                    f"{coins(p.total_profit)}.")
    mp = ctx.get("mp_plan") or {}
    if mp.get("recombs"):
        b = mp["recombs"][0]
        recs.append(f"Cheapest MP: {b.label} (+{b.mp_gain} MP, {coins(b.coins_per_mp)}/MP).")
    ah = ctx.get("ah") or {}
    if ah.get("listings") and ah["listings"].sold_claimable:
        recs.append(f"Claim {ah['listings'].sold_claimable} sold auction(s) on the AH.")
    if recs:
        out.append("\nDo this next:")
        out += [f"  {i}. {r}" for i, r in enumerate(recs, 1)]
    if not out:
        out.append("Quiet day — no progress delta and no standout opportunities.")
    return "\n".join(out)


def summarize(ctx: dict, gemini_key: str | None, model: str) -> tuple[str, bool]:
    """Return (summary_text, produced_by_llm)."""
    text = llm.gemini_generate(facts_text(ctx), system=llm.SYSTEM_PROMPT,
                               api_key=gemini_key, model=model)
    if text:
        return text, True
    return local_brief(ctx), False


# --- final render -----------------------------------------------------------

def render_brief(ctx: dict, summary_text: str, via_llm: bool) -> str:
    acc = ctx["account"]
    date = (ctx.get("stats") or {}).get("date", "today")
    out = ["═" * 68, f" NULL'S ADDONS · SKYBLOCK DAILY BRIEF — {acc.name} · {date}"]
    _tag = flair.tagline()
    if _tag:
        out.append(f" \"{_tag}\"")
    out.append("═" * 68)
    s = ctx.get("stats")
    if s:
        out.append(f" {coins(s['coins'])} coins · skill avg "
                   f"{s.get('skill_average', '—')} · {s.get('pets', 0)} pets")
    engine = "Gemini" if via_llm else "local summary (set a Gemini key for AI insights)"
    out.append("")
    out.append(f" ── Insights ({engine}) ──")
    out.append(summary_text)
    out.append("")
    out.append(" ── The numbers ──")
    out += [f"  {ln}" for ln in facts_text(ctx).splitlines()]
    out.append("═" * 68)
    return "\n".join(out)
