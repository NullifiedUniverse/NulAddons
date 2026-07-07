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
import math
import os
from dataclasses import dataclass, field

from . import hypixel, mechanics, nbt
from .economy import EvalParams


def _num(value, default: float = 0.0) -> float:
    """Coerce config / live-profile values to a finite float; default on bad input."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return f if math.isfinite(f) else default


def _int(value, default: int = 0) -> int:
    return int(_num(value, default))

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

#: The user's own config lives in their home dir so a pip-installed copy or a
#: fresh clone both work; the repo's config/accounts.json is the bundled example.
USER_CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".nulladdons")
USER_CONFIG_PATH = os.path.join(USER_CONFIG_DIR, "accounts.json")
BUNDLED_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "accounts.json",
)
DEFAULT_ACCOUNTS_PATH = BUNDLED_CONFIG_PATH  # backwards-compatible alias

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"


def default_config() -> dict:
    return {"accounts": {}, "hypixel_api_key": None, "gemini_api_key": None,
            "gemini_model": GEMINI_DEFAULT_MODEL, "discord_webhook_url": None,
            "alert": {}}


def config_path() -> str:
    """The active config path: env override → user home → bundled example."""
    env = os.environ.get("NULLADDONS_CONFIG")
    if env:
        return env
    if os.path.exists(USER_CONFIG_PATH):
        return USER_CONFIG_PATH
    return BUNDLED_CONFIG_PATH


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
    # Trading preferences
    blacklist: set[str] = field(default_factory=set)   # ids never to trade
    whitelist: set[str] | None = None                  # if set, only these ids
    # Progression
    mp_goal: int = 0                                   # target Magical Power
    coin_goal: int = 0                                 # target coin balance
    active_hours: float = 6.0                          # flipping hours/day for projections
    owned_families: set[str] = field(default_factory=set)   # accessory families owned
    owned_item_ids: set[str] = field(default_factory=set)   # from live talisman bag
    current_mp: int | None = None                      # from live talisman bag, if read
    # Notifications
    webhook_url: str | None = None
    alert: dict = field(default_factory=dict)          # crucial-message thresholds

    def summary(self) -> str:
        src = "live profile" if self.live else "config"
        cookie = " · cookie tax" if self.cookie_buffed else ""
        return (f"{self.name} ({self.username}) · {self.risk} · "
                f"budget {int(self.budget):,} coins [{src}]{cookie}")


def load_config(path: str | None = None) -> dict:
    """Load config from the active path, or a safe empty default if missing/bad."""
    p = path or config_path()
    try:
        with open(p, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg if isinstance(cfg, dict) else default_config()
    except (OSError, ValueError):
        return default_config()


def save_config(cfg: dict, path: str | None = None) -> str:
    """Write config to the user's home dir (0600) and return the path used."""
    p = path or USER_CONFIG_PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    try:
        os.chmod(p, 0o600)  # config may hold API keys
    except OSError:
        pass
    return p


def account_names(cfg: dict) -> list[str]:
    return list((cfg.get("accounts") or {}).keys())


def first_account(cfg: dict) -> str | None:
    names = account_names(cfg)
    return names[0] if names else None


def _extract_live_budget(profiles_payload: dict, uuid: str) -> tuple[float | None, dict]:
    """Pull (purse + bank) and collections from a profiles payload.

    Prefers the profile the player currently has selected, else the richest one.
    Returns (budget_or_None, collections)."""
    profiles = profiles_payload.get("profiles") or []
    best_budget: float | None = None
    collections: dict[str, int] = {}
    for profile in profiles:
        member = (profile.get("members") or {}).get(uuid) or {}
        purse = _num(member.get("coin_purse"))
        bank = _num((profile.get("banking") or {}).get("balance"))
        total = purse + bank
        selected = profile.get("selected", False)
        if best_budget is None or total > best_budget or selected:
            if selected or best_budget is None or total > best_budget:
                best_budget = total
                collections = dict(member.get("collection") or {})
        if selected:
            break
    return best_budget, collections


def _extract_owned_ids(profiles_payload: dict, uuid: str) -> set[str]:
    """Decode the player's talisman/accessory bag into a set of item ids.

    Best-effort: needs the player's inventory API enabled; returns an empty set
    on any problem, in which case the planner falls back to configured owned
    families."""
    profiles = profiles_payload.get("profiles") or []
    chosen = None
    for profile in profiles:
        member = (profile.get("members") or {}).get(uuid) or {}
        if chosen is None:
            chosen = member
        if profile.get("selected"):
            chosen = member
            break
    if not chosen:
        return set()
    # Newer API nests bags under inventory.bag_contents; older is top-level.
    bag = None
    inv = chosen.get("inventory") or {}
    bag_contents = inv.get("bag_contents") or {}
    for key in ("talisman_bag",):
        bag = bag_contents.get(key) or chosen.get(key)
        if bag:
            break
    return nbt.item_ids_from_bag(bag) if bag else set()


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

    budget = _num(acc.get("budget"))
    uuid = None
    collections: dict[str, int] = {}
    owned_ids: set[str] = set()
    is_live = False

    if live:
        uuid = hypixel.resolve_uuid(username)
        key = api_key or config.get("hypixel_api_key")
        if uuid and key:
            payload = hypixel.fetch_profiles(uuid, key)
            if payload:
                live_budget, collections = _extract_live_budget(payload, uuid)
                owned_ids = _extract_owned_ids(payload, uuid)
                if live_budget is not None:
                    budget = live_budget
                    is_live = True

    if budget_override is not None:
        budget = budget_override

    params = EvalParams(tax=tax, **RISK_PROFILES[risk])

    # Notifications: per-account webhook falls back to a global one.
    webhook = acc.get("webhook_url") or config.get("discord_webhook_url")
    alert = dict(config.get("alert", {}))       # global defaults ...
    alert.update(acc.get("alert", {}))          # ... overridden per account

    return AccountContext(
        name=name, username=username, budget=budget, risk=risk, params=params,
        uuid=uuid, notes=acc.get("notes", ""), cookie_buffed=cookie,
        live=is_live, collections=collections,
        allowed_outputs=None,  # unlock-gating is opt-in; see README
        blacklist=set(acc.get("blacklist", [])),
        whitelist=set(acc["whitelist"]) if acc.get("whitelist") else None,
        mp_goal=_int(acc.get("mp_goal")),
        coin_goal=_int(acc.get("coin_goal")),
        active_hours=_num(acc.get("active_hours"), 6.0),
        owned_families=set(acc.get("owned_families", [])),
        owned_item_ids=owned_ids,
        webhook_url=webhook,
        alert=alert,
    )
