"""
Null's Addons -- per-account personalisation.

Two players are configured out of the box, NullifiedGalaxy and YunUnderTheMoon,
each with their own capital, risk appetite and tax perks.  An account becomes an
:class:`AccountContext` -- the bundle of settings the whole engine reads.

Personalisation has two layers:

1. **Static config** (``config/accounts.json``) -- always available, no key
   needed: budget, risk profile, whether a Booster Cookie is active (lower tax),
   patience, notes.
2. **Live enrichment** (optional, needs a Hypixel API key) -- resolves the
   username to a UUID and reads the real SkyBlock profile to override the budget
   with the player's actual purse + bank and to list unlocked collections.

Risk profiles are the personality of the recommendations.  ``conservative`` is
effectively "guarantee profit" mode: it only surfaces deep, liquid, stable
markets with a comfortable margin and high confidence.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from . import hypixel, mechanics
from .economy import EvalParams

# Each profile is a set of overrides applied on top of EvalParams' defaults.
RISK_PROFILES: dict[str, dict] = {
    # Near-guaranteed: only huge, stable, deep markets; wide safety margins;
    # crafts must clear even when executed instantly (no fill risk at all).
    "conservative": dict(
        capture_fraction=0.35, max_fill_minutes=20.0, impact_fraction=0.010,
        max_orders_per_flip=1, min_margin=0.03, min_liquidity=1_000_000,
        min_unit_profit=0.5, min_confidence=0.55, min_coins_per_hour=50_000,
        max_margin=1.5, max_spread_pct=0.25, require_instant_profit=True,
    ),
    # Sensible default: good balance of turnover, safety and choice.
    "balanced": dict(
        capture_fraction=0.50, max_fill_minutes=30.0, impact_fraction=0.020,
        max_orders_per_flip=2, min_margin=0.02, min_liquidity=400_000,
        min_unit_profit=0.2, min_confidence=0.35, min_coins_per_hour=10_000,
        max_margin=3.0, max_spread_pct=0.50, require_instant_profit=False,
    ),
    # Chase every edge; accept thinner books and longer waits for more options.
    "aggressive": dict(
        capture_fraction=0.65, max_fill_minutes=60.0, impact_fraction=0.040,
        max_orders_per_flip=4, min_margin=0.015, min_liquidity=150_000,
        min_unit_profit=0.1, min_confidence=0.15, min_coins_per_hour=0,
        max_margin=8.0, max_spread_pct=1.00, require_instant_profit=False,
    ),
}

DEFAULT_ACCOUNTS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "accounts.json",
)


@dataclass
class AccountContext:
    """Everything the engine needs to tailor output to one player."""

    name: str
    username: str
    budget: float
    risk: str
    params: EvalParams
    uuid: str | None = None
    notes: str = ""
    cookie_buffed: bool = False
    live: bool = False                 # True if enriched from the live profile
    collections: dict[str, int] = field(default_factory=dict)
    allowed_outputs: set[str] | None = None  # None => all craft recipes allowed

    def summary(self) -> str:
        src = "live profile" if self.live else "config"
        cookie = " · cookie tax" if self.cookie_buffed else ""
        return (f"{self.name} ({self.username}) · {self.risk} · "
                f"budget {int(self.budget):,} coins [{src}]{cookie}")


def load_config(path: str = DEFAULT_ACCOUNTS_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _extract_live_budget(profiles_payload: dict, uuid: str) -> tuple[float | None, dict]:
    """Pull (purse + bank) and collections from a profiles payload.

    Prefers the profile the player currently has selected, else the richest one.
    Returns (budget_or_None, collections)."""
    profiles = profiles_payload.get("profiles") or []
    best_budget: float | None = None
    collections: dict[str, int] = {}
    for profile in profiles:
        member = (profile.get("members") or {}).get(uuid) or {}
        purse = float(member.get("coin_purse", 0) or 0)
        bank = float((profile.get("banking") or {}).get("balance", 0) or 0)
        total = purse + bank
        selected = profile.get("selected", False)
        if best_budget is None or total > best_budget or selected:
            if selected or best_budget is None or total > best_budget:
                best_budget = total
                collections = dict(member.get("collection") or {})
        if selected:
            break
    return best_budget, collections


def build_context(name: str, config: dict, *, live: bool = False,
                  api_key: str | None = None,
                  budget_override: float | None = None,
                  risk_override: str | None = None) -> AccountContext:
    """Assemble the :class:`AccountContext` for ``name`` from config (+ live)."""
    accounts = config.get("accounts", {})
    if name not in accounts:
        raise KeyError(f"Unknown account '{name}'. Known: {', '.join(accounts)}")
    acc = accounts[name]

    username = acc.get("username", name)
    risk = risk_override or acc.get("risk", "balanced")
    if risk not in RISK_PROFILES:
        raise ValueError(f"Unknown risk profile '{risk}'. "
                         f"Choose from {', '.join(RISK_PROFILES)}")
    cookie = bool(acc.get("cookie_buffed", False))
    best_case = bool(acc.get("best_case_tax", False))
    tax = mechanics.sell_tax(cookie_buffed=cookie, best_case=best_case)

    budget = float(acc.get("budget", 0))
    uuid = None
    collections: dict[str, int] = {}
    is_live = False

    if live:
        uuid = hypixel.resolve_uuid(username)
        key = api_key or config.get("hypixel_api_key")
        if uuid and key:
            payload = hypixel.fetch_profiles(uuid, key)
            if payload:
                live_budget, collections = _extract_live_budget(payload, uuid)
                if live_budget is not None:
                    budget = live_budget
                    is_live = True

    if budget_override is not None:
        budget = budget_override

    params = EvalParams(tax=tax, **RISK_PROFILES[risk])

    return AccountContext(
        name=name, username=username, budget=budget, risk=risk, params=params,
        uuid=uuid, notes=acc.get("notes", ""), cookie_buffed=cookie,
        live=is_live, collections=collections,
        allowed_outputs=None,  # unlock-gating is opt-in; see README
    )
