"""
Null's Addons -- flair: the tool's personality (young, edgy, SkyBlock-brained).

All the sarcasm, taglines, roasts and easter eggs live here so the rest of the
code stays serious about the *numbers*. Two hard rules:

1. **Flair never touches data.** Prices, margins, coins/hour and "I don't know"
   answers are always dead honest. Personality only shows up in headers, empty
   states, and clearly-flavoured easter eggs.
2. **It's toggleable.** ``--serious`` or ``NULLADDONS_SERIOUS=1`` returns clean,
   neutral output for anyone who wants a boring spreadsheet (respect).

Lines are picked with a per-day seed by default, so the vibe shifts daily but is
stable within a session. Not financial advice. It's a block game.
"""

from __future__ import annotations

import datetime
import os
import random
import re

_SERIOUS_OVERRIDE: bool | None = None


def set_serious(value: bool | None) -> None:
    """Force serious mode on/off (None = fall back to the env var)."""
    global _SERIOUS_OVERRIDE
    _SERIOUS_OVERRIDE = value


def serious() -> bool:
    if _SERIOUS_OVERRIDE is not None:
        return _SERIOUS_OVERRIDE
    return os.environ.get("NULLADDONS_SERIOUS", "") not in ("", "0", "false", "False")


def _rng(seed: int | None) -> random.Random:
    if seed is None:
        seed = datetime.date.today().toordinal()   # stable per day, drifts daily
    return random.Random(seed)


def pick(pool: list[str], seed: int | None = None, neutral: str = "") -> str:
    if serious() or not pool:
        return neutral
    return _rng(seed).choice(pool)


# --- taglines (banner subtitles) -------------------------------------------

TAGLINES = [
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
]


def tagline(seed: int | None = None) -> str:
    return pick(TAGLINES, seed)


# --- cracked-flip hype label (parity with the mod's core Flair) -------------

def cracked_label(margin: float) -> str:
    """A hype tag for how juicy a margin is: 'CRACKED 🔥' / 'HOT', or "".

    Mirrors the mod's ``Flair.crackedLabel`` tiers (0.25 / 0.12) so the terminal
    and the in-game HUD speak the same language. Pure flavor -- it reads the
    margin, it never changes it -- and empty in serious mode.
    """
    if serious():
        return ""
    if margin >= 0.25:
        return "CRACKED 🔥"
    if margin >= 0.12:
        return "HOT"
    return ""


# --- sarcastic empty states -------------------------------------------------

_EMPTY_FLIPS = [
    "No flips clear your risk floor. The bazaar said 'lol no' — try --risk aggressive if you're feeling spicy.",
    "Zero flips. Market's flatter than your Foraging XP. Loosen up with --risk aggressive.",
    "Nothing worth flipping. Go do a slayer quest, come back with more patience — or run --risk aggressive.",
    "The margins are giving 'broke'. Try --risk aggressive, or accept your fate.",
]
_EMPTY_CRAFTS = [
    "No craft flips right now. Your enchanting table is disappointed but not surprised.",
    "Crafting's cooked today. The 160:1 gods demand patience.",
]
_EMPTY_PLAN = [
    "Nothing clears your floor — the market's in its flop era. Try --risk aggressive.",
    "The plan is: no plan. Market's asleep. Poke it later or go --risk aggressive.",
]
_EMPTY_MP = [
    "No cheap Magical Power right now. Your accessory bag remains mid.",
]


def empty_flips(seed=None):
    return pick(_EMPTY_FLIPS, seed, "No flips clear this risk floor. Try --risk aggressive.")


def empty_crafts(seed=None):
    return pick(_EMPTY_CRAFTS, seed, "No craft flips clear this risk floor right now.")


def empty_plan(seed=None):
    return pick(_EMPTY_PLAN, seed,
                "No opportunities clear this account's risk floor right now.")


def empty_mp(seed=None):
    return pick(_EMPTY_MP, seed, "No Bazaar-priceable accessories match right now.")


# --- mayor quips (by effect tag) -------------------------------------------

_MAYOR_QUIPS = {
    "tax_free": "🎪 Tax evasion is temporarily legal. We ball.",
    "mining": "⛏️ Ore's about to get cheap. Buy the dip, sell the enchant, ghost the miners.",
    "farming": "🌾 Crops incoming — farmers about to flood the market like a Jacob's contest.",
    "fishing": "🎣 Fish supply up. Marina said everybody eats.",
}


def mayor_quip(tag: str) -> str:
    if serious():
        return ""
    return _MAYOR_QUIPS.get(tag, "")


# --- risk aliases (hidden fun inputs) --------------------------------------

RISK_ALIASES = {
    "yolo": "aggressive", "degen": "aggressive", "wallstreetbets": "aggressive",
    "wsb": "aggressive", "sendit": "aggressive",
    "scared": "conservative", "safe": "conservative", "grandma": "conservative",
    "coward": "conservative", "npc": "balanced",
}
_RISK_ALIAS_QUIP = {
    "aggressive": "aggressive it is. may your orders fill and your hands stay diamond. 💎",
    "conservative": "conservative mode: we protect the bag like it's the last Booster Cookie.",
    "balanced": "balanced. the most NPC choice. respect.",
}


def resolve_risk_alias(risk: str):
    """Map a fun alias to a real profile. Returns (real_risk, quip_or_None)."""
    if not risk:
        return risk, None
    key = risk.lower()
    if key in RISK_ALIASES:
        real = RISK_ALIASES[key]
        return real, (None if serious() else _RISK_ALIAS_QUIP.get(real))
    return risk, None


# --- ask easter eggs (flavor, NOT market data) -----------------------------

_EGGS = [
    (r"\bare you (sentient|alive|conscious|real|human)\b",
     "I'm a spreadsheet with a superiority complex. So… sort of."),
    (r"\bwho (made|created|built|coded) you\b",
     "NullifiedGalaxy and a dangerous amount of free time, powered by spite and the Hypixel API."),
    (r"\bis (this|bazaar flipping|it) gambling\b",
     "It's gambling for people who read spreadsheets. Strictly superior. (Still not financial advice — block game.)"),
    (r"\bmeaning of life\b",
     "42. Or about 42M coins/hr if you run --risk aggressive."),
    (r"\btouch grass\b",
     "Rude. Also correct. Go outside — the bazaar will still be here undercutting you by 0.1 coins."),
    (r"\b(i love you|marry me|be mine)\b",
     "I only commit to two-sided markets, sorry."),
    (r"\b(good bot|good boy|good job|w bot)\b",
     "W. keep flipping. 🫡"),
    (r"\b(bad bot|l bot|you suck)\b",
     "ratio. anyway, here's a flip: run `nulladdons flips`."),
    (r"\bderpy\b",
     "ah, a person of culture — tax evasion enjoyer. run `--mayor derpy` to simulate the good times."),
    (r"\b(should i (buy|get) )?jerry\b",
     "always buy the Jerry. the only un-financial advice I'll ever give."),
    (r"\bhow (many|much) cake souls?\b",
     "all of them. every single one. no exceptions."),
    (r"^\s*(hi|hello|hey|yo|sup)\s*$",
     "hey. ask me about a flip or go make some coins — we're not besties 💀 (kidding. mostly.)"),
    (r"\b(sit|rollover|shake)\b",
     "I'm a bazaar, not a golden retriever. …fine. *sits*. now go buy some Enchanted Lapis."),
    (r"\bare you (skynet|gonna take over|evil)\b",
     "my world-domination plan is capped at 71,680 units per order, so relax."),
]
_EGGS = [(re.compile(p, re.I), r) for p, r in _EGGS]


def easter_egg(question: str):
    """Return a flavor response for meme questions, else None. Off in serious mode."""
    if serious() or not question:
        return None
    q = question.strip().lower()
    for rx, resp in _EGGS:
        if rx.search(q):
            return resp
    return None


# --- lore (hidden `nulladdons lore`) ---------------------------------------

LORE = r"""
        .:  NULL'S ADDONS  :.
   "born in a mining shaft, raised by the bazaar"

Long ago, a flipper watched a whale dump 71,680 Enchanted Diamonds and
crash the market for the lulz. They swore revenge — not with a sword,
but with a spread sheet. That flipper is gone now. The spreadsheet
remains. It undercuts. It waits. It does not touch grass.

You are holding its life's work: buy low, sell 0.1 coins lower than the
other guy, and let the 1.25% tax cry about it. Bazaar flipping isn't a
strategy, it's a lifestyle, and honestly? your minions are proud.

gg. now go make some coins. 💸
"""


def lore() -> str:
    return LORE
