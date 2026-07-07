"""
Null's Addons -- Magical Power planner (accessories / talismans).

Magical Power (MP) scales the stats you get from your Accessory Bag.  Each
accessory grants MP purely by **rarity** (this table is a fixed game rule):

    Common 3 · Uncommon 5 · Rare 8 · Epic 12 · Legendary 16 · Mythic 22

So "more MP, fast and cheap" is an optimisation over **coins per MP**.  This
module ranks every way to add MP that can be priced from the live Bazaar:

1. **Buy / craft accessories** you don't already own -- priced live (an
   accessory on the Bazaar, or crafted from Bazaar mats via the recipe engine).
2. **Recombobulate** accessories you *do* own -- a Recombobulator 3000 bumps an
   accessory one rarity, adding MP.  Its cost comes straight from the Bazaar, so
   coins/MP for a recomb = recomb price / (MP gained).

Personalisation: owned accessories (read live from the talisman bag, or listed
in config) are skipped in the buy list and become recomb candidates instead.

Correctness note: unlike a bad *flip* recipe (which invents fake profit), a
slightly-off *accessory* recipe only mis-estimates a shopping cost -- you still
receive the real MP.  Every id is still validated against the live market and a
coins/MP sanity floor flags anything implausibly cheap.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import craft as craftmod
from . import mechanics
from .bazaar import Market
from .economy import EvalParams

#: Fixed game rule: Magical Power granted per accessory rarity.
MAGICAL_POWER = {
    "COMMON": 3, "UNCOMMON": 5, "RARE": 8, "EPIC": 12,
    "LEGENDARY": 16, "MYTHIC": 22, "SPECIAL": 3, "VERY_SPECIAL": 5,
}
#: Recombobulator upgrade path (each step is +1 rarity).
RARITY_LADDER = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC"]

RECOMB_ID = "RECOMBOBULATOR_3000"

#: A recomb costing less than this per MP is almost certainly mispriced data.
_MIN_SANE_COINS_PER_MP = 1.0


def mp_for(rarity: str) -> int:
    return MAGICAL_POWER.get(rarity.upper(), 0)


def next_rarity(rarity: str) -> str | None:
    rarity = rarity.upper()
    if rarity in RARITY_LADDER:
        i = RARITY_LADDER.index(rarity)
        if i + 1 < len(RARITY_LADDER):
            return RARITY_LADDER[i + 1]
    return None


def recomb_delta(rarity: str) -> int:
    """MP gained by recombobulating an accessory of this rarity by one tier."""
    nxt = next_rarity(rarity)
    return mp_for(nxt) - mp_for(rarity) if nxt else 0


@dataclass
class Accessory:
    id: str
    name: str
    family: str
    rarity: str
    acquire: dict = field(default_factory=dict)  # {"bazaar":id} | {"craft":[[id,q]]} | {"npc":coins}

    @property
    def mp(self) -> int:
        return mp_for(self.rarity)


def load_accessories(path: str) -> list[Accessory]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    out = []
    for a in data.get("accessories", []):
        out.append(Accessory(
            id=a["id"], name=a.get("name", a["id"]),
            family=a.get("family", a["id"]).lower(),
            rarity=a["rarity"].upper(), acquire=a.get("acquire", {}),
        ))
    return out


@dataclass
class MPBuy:
    """A recommended way to add Magical Power."""
    label: str
    kind: str            # "buy" | "craft" | "recomb"
    mp_gain: int
    cost: float
    coins_per_mp: float
    how: str             # human-readable instruction
    family: str = ""


class AccessoryEngine:
    def __init__(self, market: Market, accessories: list[Accessory],
                 recipes: list[craftmod.Recipe]):
        self.market = market
        self._all = accessories
        # Reuse the recursive craft-costing engine to price accessory mats.
        self._craft = craftmod.CraftEngine(market, recipes, EvalParams())

    def _buy_order_cost(self, pid: str) -> float | None:
        p = self.market.get(pid)
        return (p.best_bid + mechanics.UNDERCUT_INCREMENT) if p else None

    def price(self, acc: Accessory) -> tuple[float | None, str, str]:
        """Return (cost, method, how-text) for obtaining one, or (None, ...)."""
        acq = acc.acquire
        if "npc" in acq:
            return float(acq["npc"]), "npc", f"buy from NPC for {int(acq['npc']):,}"
        if "bazaar" in acq:
            cost = self._buy_order_cost(acq["bazaar"])
            if cost is None:
                return None, "buy", "unavailable on Bazaar"
            return cost, "buy", f"BUY ORDER {acq['bazaar']} @ {cost:,.1f}"
        if "craft" in acq:
            total = 0.0
            parts = []
            for mat, qty in acq["craft"]:
                unit = self._craft.acquisition_cost(mat)
                if unit == float("inf"):
                    return None, "craft", f"missing mat {mat}"
                total += unit * qty
                parts.append(f"{qty:,} {mat}")
            return total, "craft", "CRAFT from " + " + ".join(parts)
        return None, "?", "no acquisition method"

    # --- buy/craft the cheapest MP you don't own ----------------------------

    def buy_options(self, owned_ids: set[str], owned_families: set[str]) -> list[MPBuy]:
        """Best coins/MP way to add each family the player is missing."""
        best_per_family: dict[str, MPBuy] = {}
        for acc in self._all:
            if acc.id in owned_ids or acc.family in owned_families:
                continue
            if acc.mp <= 0:
                continue
            cost, method, how = self.price(acc)
            if cost is None or cost <= 0:
                continue
            cpm = cost / acc.mp
            if cpm < _MIN_SANE_COINS_PER_MP:
                continue  # implausibly cheap => bad data, skip
            cand = MPBuy(label=f"{acc.name} ({acc.rarity.title()})", kind=method,
                         mp_gain=acc.mp, cost=cost, coins_per_mp=cpm, how=how,
                         family=acc.family)
            cur = best_per_family.get(acc.family)
            if cur is None or cpm < cur.coins_per_mp:
                best_per_family[acc.family] = cand
        return sorted(best_per_family.values(), key=lambda b: b.coins_per_mp)

    # --- recombobulate what you own -----------------------------------------

    def recomb_options(self, owned: list[Accessory]) -> list[MPBuy]:
        cost = self._buy_order_cost(RECOMB_ID)
        if cost is None:
            return []
        out = []
        for acc in owned:
            delta = recomb_delta(acc.rarity)
            if delta <= 0:
                continue
            out.append(MPBuy(
                label=f"Recomb {acc.name} ({acc.rarity.title()}→"
                      f"{next_rarity(acc.rarity).title()})",
                kind="recomb", mp_gain=delta, cost=cost,
                coins_per_mp=cost / delta,
                how=f"BUY ORDER {RECOMB_ID} @ {cost:,.0f}, apply to {acc.name}",
                family=acc.family))
        return sorted(out, key=lambda b: b.coins_per_mp)

    def generic_recomb_table(self) -> list[MPBuy]:
        """When we don't know what's owned, show recomb value by rarity tier."""
        cost = self._buy_order_cost(RECOMB_ID)
        if cost is None:
            return []
        out = []
        for rarity in RARITY_LADDER:
            delta = recomb_delta(rarity)
            if delta <= 0:
                continue
            out.append(MPBuy(
                label=f"Recomb any {rarity.title()} accessory (→"
                      f"{next_rarity(rarity).title()})",
                kind="recomb", mp_gain=delta, cost=cost,
                coins_per_mp=cost / delta,
                how=f"BUY ORDER {RECOMB_ID} @ {cost:,.0f}", family=""))
        return out


def owned_accessories(accessories: list[Accessory],
                      owned_ids: set[str]) -> list[Accessory]:
    return [a for a in accessories if a.id in owned_ids]


def plan_magic_power(engine: AccessoryEngine, accessories: list[Accessory],
                     owned_ids: set[str], owned_families: set[str],
                     mp_goal: int = 0, budget: float | None = None,
                     top: int = 12) -> dict:
    """
    Assemble a Magical-Power shopping plan.

    Greedily takes the cheapest coins/MP buy/craft options for families the
    player is missing, until the MP goal (or budget, or ``top``) is reached, then
    lists recomb upgrades for owned accessories as the next lever.
    """
    buys = engine.buy_options(owned_ids, owned_families)
    picks: list[MPBuy] = []
    spent = 0.0
    gained = 0
    for b in buys:
        if mp_goal and gained >= mp_goal:
            break
        if budget is not None and spent + b.cost > budget:
            continue
        picks.append(b)
        spent += b.cost
        gained += b.mp_gain
        if not mp_goal and len(picks) >= top:
            break

    owned = owned_accessories(accessories, owned_ids)
    recombs = engine.recomb_options(owned) if owned else engine.generic_recomb_table()
    return {"picks": picks, "mp_gained": gained, "coins_spent": spent,
            "recombs": recombs[:top], "owned_count": len(owned)}
