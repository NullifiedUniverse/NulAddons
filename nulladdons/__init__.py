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
__all__ = [
    "mechanics", "bazaar", "history", "hypixel",
    "economy", "flip", "craft", "accounts", "commands", "cli",
]
