"""
Null's Addons — a Hypixel SkyBlock Bazaar-flipping assistant.

Connects to the live Hypixel Bazaar, applies market-microstructure theory
(bid-ask spread, liquidity, market impact, velocity, mean reversion), and hands
the player *direct commands* to make money with minimal risk:

    "Buy 3,200 Enchanted Lapis @ 923.9, wait ~7 min, sell @ 1,059.1"

See :mod:`nulladdons.cli` for the entry point and the project README for the
full design.
"""

__version__ = "1.0.0"

#: Public submodules, grouped by role.  Kept in sync with the package contents so
#: ``from nulladdons import *`` and tooling see the real surface.
__all__ = [
    # market data & mechanics
    "mechanics", "bazaar", "history", "nbt", "util",
    # live APIs
    "hypixel", "auction",
    # economics engine
    "economy", "flip", "craft", "accessories", "mayor", "projection",
    # personalization & ecosystem
    "accounts", "progress", "commands",
    # intelligence layer
    "llm", "brief", "ask",
    # workflows, personalization & instrumentation
    "tasks", "features", "telemetry",
    # interface & delivery
    "cli", "ui", "onboarding", "notify", "flair", "fx",
]
