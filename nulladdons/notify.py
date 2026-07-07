"""
Null's Addons -- Discord webhook notifier for crucial messages.

Posts the important stuff to a Discord channel so you don't have to babysit a
terminal: a rare high-value flip, a guaranteed craft, a great Magical-Power
deal, or the session plan summary.  "Crucial" is defined per account by
thresholds (min profit / coins-per-hour / confidence) so you only get pinged
when it's worth acting on.

Stdlib only; reuses the same proxy/CA-aware TLS context as the API client.
Discord webhooks return HTTP 204 on success.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .commands import coins, minutes, nice_name
from .hypixel import _ssl_context

# Default "crucial" thresholds; overridden per account via config `alert`.
DEFAULT_ALERT = {
    "min_profit": 1_000_000,
    "min_coins_per_hour": 5_000_000,
    "min_confidence": 0.6,
}

# Discord embed colours.
_GREEN = 0x2ECC71
_BLUE = 0x3498DB
_GOLD = 0xF1C40F


def post_webhook(url: str, content: str | None = None,
                 embeds: list[dict] | None = None,
                 username: str = "Null's Addons", timeout: float = 15.0) -> bool:
    """POST a message to a Discord webhook. Returns True on success (2xx)."""
    if not url:
        return False
    payload: dict = {"username": username}
    if content:
        payload["content"] = content[:1900]
    if embeds:
        payload["embeds"] = embeds[:10]
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "NullsAddons/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def test_webhook(url: str) -> bool:
    """Send a friendly connectivity test to a Discord webhook."""
    return post_webhook(url, embeds=[{
        "title": "✅ Null's Addons connected",
        "description": "Your Discord webhook is set up. Crucial alerts and daily "
                       "briefs will arrive here.",
        "color": _GREEN, "footer": {"text": "Null's Addons"}}])


# --- "crucial" filtering ----------------------------------------------------

def merged_alert(account) -> dict:
    cfg = dict(DEFAULT_ALERT)
    cfg.update(account.alert or {})
    return cfg


def is_crucial(plan, alert: dict) -> bool:
    return (plan.total_profit >= alert["min_profit"]
            and plan.coins_per_hour >= alert["min_coins_per_hour"]
            and plan.confidence >= alert["min_confidence"])


def crucial(plans, alert: dict) -> list:
    return [p for p in plans if is_crucial(p, alert)]


def opportunity_key(plan) -> str:
    """Stable-ish identity for dedupe in a watch loop (id + price bucket)."""
    pid = getattr(plan, "product_id", None) or getattr(plan, "output_id", "?")
    price = getattr(plan, "buy_order_price", None)
    if price is None:
        price = getattr(plan, "input_cost_per_output", 0.0)
    return f"{pid}@{round(price, 1)}"


# --- embed builders ---------------------------------------------------------

def _flip_line(p) -> str:
    return (f"**{nice_name(p.product_id)}** — buy {p.quantity:,} @ "
            f"{p.buy_order_price:,.1f} → sell @ {p.sell_offer_price:,.1f}  ·  "
            f"**{coins(p.total_profit)}** (+{p.margin:.1%}) · "
            f"{coins(p.coins_per_hour)}/hr · {p.confidence:.0%} · "
            f"~{minutes(p.total_minutes)}")


def _craft_line(p) -> str:
    return (f"**{nice_name(p.output_id)}** ×{p.quantity:,} — "
            f"**{coins(p.total_profit)}** (+{p.margin:.1%}) · "
            f"{coins(p.coins_per_hour)}/hr · {p.confidence:.0%}")


def opportunities_embed(account, flips: list, crafts: list,
                        age_seconds: float | None = None) -> dict:
    fields = []
    if flips:
        fields.append({"name": "🔁 Order flips",
                       "value": "\n".join(_flip_line(p) for p in flips[:6]) or "—"})
    if crafts:
        fields.append({"name": "🛠️ Craft flips",
                       "value": "\n".join(_craft_line(p) for p in crafts[:6]) or "—"})
    age = f"live data {age_seconds:.0f}s old · " if age_seconds is not None else ""
    return {
        "title": f"🔔 Crucial Bazaar opportunities — {account.name}",
        "color": _GREEN,
        "description": (f"{account.risk} profile · budget {coins(account.budget)}"
                        if not fields else ""),
        "fields": fields,
        "footer": {"text": f"{age}Null's Addons"},
    }


def mp_embed(account, picks: list, recombs: list) -> dict:
    lines = [f"+{b.mp_gain} MP · {b.label} · {coins(b.cost)} ({coins(b.coins_per_mp)}/MP)"
             for b in (picks[:5] + recombs[:3])]
    return {
        "title": f"✨ Magical Power deals — {account.name}",
        "color": _GOLD,
        "description": "\n".join(lines) or "No priceable MP options right now.",
        "footer": {"text": "Null's Addons"},
    }


def plan_summary_embed(account, portfolio: list) -> dict:
    total_profit = sum(p.total_profit for p in portfolio)
    total_capital = sum(p.capital_required for p in portfolio)
    total_cph = sum(p.coins_per_hour for p in portfolio)
    lines = []
    for i, p in enumerate(portfolio, 1):
        name = nice_name(getattr(p, "product_id", None) or p.output_id)
        lines.append(f"{i}. {name} — {coins(p.total_profit)} "
                     f"({coins(p.coins_per_hour)}/hr)")
    return {
        "title": f"📋 Session plan — {account.name}",
        "color": _BLUE,
        "description": "\n".join(lines) or "No positions.",
        "fields": [{
            "name": "Totals",
            "value": (f"Deploy {coins(total_capital)} · expect "
                      f"{coins(total_profit)} · ~{coins(total_cph)}/hr"),
        }],
        "footer": {"text": "Null's Addons"},
    }
