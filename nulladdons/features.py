"""
Null's Addons -- flavors (pick your voice) and feature toggles (pick your loud).

Two knobs the player owns, both pure presentation/config -- neither ever changes
a price, a margin, or a recommendation:

* **Flavor** -- the *voice*. Same honest numbers, different personality: the edgy
  default (``gremlin``), calm (``zen``), finance-brained (``wallstreet``),
  PB-chasing (``speedrunner``), or nautical (``pirate``). ``--serious`` still
  mutes personality entirely, whatever the flavor.
* **Features** -- coarse on/off switches (animations, easter eggs, the movers
  radar, the mayor, telemetry, ...) stored in your config so every run is exactly
  as loud or as quiet as you like.

Resolution order for both is: explicit override (a ``--flag``) → environment
variable → your config → the built-in default.
"""

from __future__ import annotations

import os

# ---------------------------------------------------------------------------
# Flavors
# ---------------------------------------------------------------------------

DEFAULT_FLAVOR = "gremlin"

#: flavor id -> {label, taglines}. Add one here and it's instantly pickable in
#: setup, via ``--flavor``, or ``NULLADDONS_FLAVOR``.
FLAVORS: dict[str, dict] = {
    "gremlin": {
        "label": "Gremlin — edgy, chronically online (default)",
        "taglines": [
            "flip coins, not tables",
            "buy low, sell slightly-less-low",
            "financial advice from a block game 💀",
            "outsmarting 12-year-olds since forever",
            "number go up (most of the time)",
            "the bazaar doesn't care about your feelings",
            "touch grass — after this flip",
            "not financial advice, it's literally SkyBlock",
            "your minions would be proud",
            "get rich or dig trying",
            "we undercut by 0.1 coins and we will not apologize",
            "certified hustle, uncertified accountant",
        ],
    },
    "zen": {
        "label": "Zen — calm, mindful, suspiciously peaceful",
        "taglines": [
            "the market breathes; so should you",
            "buy low, sell high, stay centered",
            "profit is temporary; the spread is eternal",
            "do not chase the pump — let it come to you",
            "a patient order fills the deepest book",
            "detach from the outcome, keep the 1.25% tax",
            "still water flips deep",
        ],
    },
    "wallstreet": {
        "label": "Wall Street — finance-bro, provides 'liquidity'",
        "taglines": [
            "we're not flipping, we're providing liquidity",
            "alpha is just a spread you noticed first",
            "diamond hands, paper minions",
            "buy the dip, sell the rip, expense the tax",
            "it's not gambling if you have a spreadsheet",
            "risk-adjusted, tax-adjusted, vibe-adjusted",
            "the trend is your friend until the 0.1 undercut",
        ],
    },
    "speedrunner": {
        "label": "Speedrunner — PB-obsessed, resets the market",
        "taglines": [
            "gotta go fast, gotta sell faster",
            "any% profit, no major glitches",
            "reset the market, chase the PB",
            "frame-perfect undercut by 0.1",
            "sub-5-minute round trips or riot",
            "the timer never stops, neither do you",
        ],
    },
    "pirate": {
        "label": "Pirate — arr, thar be spread in these waters",
        "taglines": [
            "arr, thar be spread in these waters",
            "plunder the bid, hoist the ask",
            "dead men undercut no tales",
            "yo ho ho and a bottle of enchanted rum",
            "X marks the 71,680-unit order cap",
            "the tax collector be the real kraken",
        ],
    },
}

_FLAVOR_OVERRIDE: str | None = None


def set_flavor(flavor: str | None) -> None:
    """Force the active flavor (None = fall back to env/config/default)."""
    global _FLAVOR_OVERRIDE
    _FLAVOR_OVERRIDE = flavor


def normalize_flavor(flavor: str | None) -> str:
    key = (flavor or "").strip().lower()
    return key if key in FLAVORS else DEFAULT_FLAVOR


def active_flavor(config: dict | None = None) -> str:
    """The flavor in effect: override → env → config → default."""
    if _FLAVOR_OVERRIDE is not None:
        return normalize_flavor(_FLAVOR_OVERRIDE)
    env = os.environ.get("NULLADDONS_FLAVOR")
    if env:
        return normalize_flavor(env)
    return normalize_flavor((config or {}).get("flavor"))


def taglines(flavor: str | None = None, config: dict | None = None) -> list[str]:
    return FLAVORS[normalize_flavor(flavor or active_flavor(config))]["taglines"]


def flavor_label(flavor: str | None = None) -> str:
    return FLAVORS[normalize_flavor(flavor)]["label"]


def flavor_ids() -> list[str]:
    return list(FLAVORS.keys())


# ---------------------------------------------------------------------------
# Feature toggles
# ---------------------------------------------------------------------------

#: name -> (default_enabled, one-line description shown in setup).
FEATURES: dict[str, tuple[bool, str]] = {
    "animations": (True, "spinners, count-ups and other terminal motion"),
    "easter_eggs": (True, "hidden jokes & responses in `ask` and around the app"),
    "market_movers": (True, "the pump/dump radar in `status`"),
    "mayor": (True, "fold the live SkyBlock mayor's perks into the economics"),
    "achievements": (True, "unlock fun badges as you use the tool (needs telemetry)"),
    "telemetry": (False, "opt-in local stats & SkyBlock Wrapped — OFF unless you say so"),
}


def default_features() -> dict[str, bool]:
    return {name: default for name, (default, _desc) in FEATURES.items()}


def describe(name: str) -> str:
    return FEATURES.get(name, (False, ""))[1]


def enabled(name: str, config: dict | None = None) -> bool:
    """Is a feature on? config['features'][name] wins, else the built-in default."""
    feats = (config or {}).get("features") or {}
    if name in feats:
        return bool(feats[name])
    return FEATURES.get(name, (False, ""))[0]
