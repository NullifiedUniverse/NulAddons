"""
Null's Addons -- Bazaar data model.

Wraps the raw Hypixel ``/skyblock/bazaar`` product blobs in a typed object with
sane, *unambiguous* names.  The Hypixel API's own field names are famously
back-to-front, so the whole point of this module is to translate them exactly
once, here, and never touch the raw dict again.

The Hypixel naming trap
-----------------------
Each product carries ``quick_status`` plus two order-book summaries:

* ``buy_summary``  -> the **sell offers** (asks).  These are the orders you
  *buy from*.  ``buy_summary[0]`` is the cheapest ask == the instant-buy price.
* ``sell_summary`` -> the **buy orders** (bids).  These are the orders you
  *sell to*.  ``sell_summary[0]`` is the highest bid == the instant-sell price.
* ``quick_status.buyPrice``  -> weighted-average ask (what buying costs).
* ``quick_status.sellPrice`` -> weighted-average bid (what selling fetches).
* ``buyMovingWeek``  -> units **instant-bought** over the past week (demand).
* ``sellMovingWeek`` -> units **instant-sold** over the past week (supply).

We expose these as ``best_ask`` / ``best_bid`` and ``demand_per_week`` /
``supply_per_week`` so no downstream code has to remember the trap.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import mechanics


@dataclass
class Product:
    """A single Bazaar product with disambiguated market fields."""

    product_id: str

    # Top of book (from the order summaries -- exact, not weighted averages).
    best_bid: float          # highest existing buy order  (you sell *to* this)
    best_ask: float          # lowest existing sell offer   (you buy *from* this)
    best_bid_amount: int     # units resting at the best bid
    best_ask_amount: int     # units resting at the best ask

    # Weighted averages (from quick_status) -- used for instant-buy/sell values.
    insta_buy_price: float   # quick_status.buyPrice
    insta_sell_price: float  # quick_status.sellPrice

    # Flow (rolling 7-day) -- the heart of the liquidity model.
    demand_per_week: int     # buyMovingWeek  -> feeds YOUR sell offers
    supply_per_week: int     # sellMovingWeek -> feeds YOUR buy orders

    # Standing depth (snapshot).
    ask_volume: int          # buyVolume  -> total units in sell offers
    bid_volume: int          # sellVolume -> total units in buy orders
    ask_orders: int          # number of distinct sell offers
    bid_orders: int          # number of distinct buy orders

    raw: dict = field(default_factory=dict, repr=False)

    # --- Derived market stats ------------------------------------------------

    @property
    def spread(self) -> float:
        """Absolute bid-ask spread (coins)."""
        return self.best_ask - self.best_bid

    @property
    def mid(self) -> float:
        """Mid price -- the fair-value reference for volatility / reversion."""
        return (self.best_ask + self.best_bid) / 2.0

    @property
    def spread_pct(self) -> float:
        """Spread as a fraction of mid price."""
        return self.spread / self.mid if self.mid > 0 else 0.0

    @property
    def has_two_sided_market(self) -> bool:
        """True only if both a bid and an ask actually exist."""
        return self.best_bid > 0 and self.best_ask > 0 and self.best_ask > self.best_bid

    @property
    def liquidity(self) -> int:
        """
        Conservative liquidity = the *thinner* of supply and demand flow.

        A flip needs both sides to fill, so the binding constraint is whichever
        weekly flow is smaller.  This is the number the whole risk model leans on.
        """
        return min(self.demand_per_week, self.supply_per_week)


def parse_product(pid: str, blob: dict) -> Product | None:
    """
    Build a :class:`Product` from one raw API entry, or ``None`` if the entry is
    unusable (missing a side of the book, malformed, etc.).
    """
    q = blob.get("quick_status") or {}
    buy_summary = blob.get("buy_summary") or []    # asks
    sell_summary = blob.get("sell_summary") or []  # bids

    if not buy_summary or not sell_summary:
        return None  # one-sided market: cannot flip it safely

    best_ask = buy_summary[0].get("pricePerUnit", 0.0)
    best_ask_amount = int(buy_summary[0].get("amount", 0))
    best_bid = sell_summary[0].get("pricePerUnit", 0.0)
    best_bid_amount = int(sell_summary[0].get("amount", 0))

    if best_ask <= 0 or best_bid <= 0:
        return None

    return Product(
        product_id=pid,
        best_bid=best_bid,
        best_ask=best_ask,
        best_bid_amount=best_bid_amount,
        best_ask_amount=best_ask_amount,
        insta_buy_price=float(q.get("buyPrice", best_ask)),
        insta_sell_price=float(q.get("sellPrice", best_bid)),
        demand_per_week=int(q.get("buyMovingWeek", 0)),
        supply_per_week=int(q.get("sellMovingWeek", 0)),
        ask_volume=int(q.get("buyVolume", 0)),
        bid_volume=int(q.get("sellVolume", 0)),
        ask_orders=int(q.get("buyOrders", 0)),
        bid_orders=int(q.get("sellOrders", 0)),
        raw=blob,
    )


class Market:
    """An in-memory view of the whole Bazaar: ``{product_id -> Product}``."""

    def __init__(self, products: dict[str, Product], last_updated: int | None = None):
        self.products = products
        self.last_updated = last_updated  # epoch millis from the API

    def age_seconds(self) -> float | None:
        """How old the snapshot is, in seconds (``None`` if unknown)."""
        if not self.last_updated:
            return None
        return max(0.0, time.time() - self.last_updated / 1000.0)

    def is_stale(self, max_age: float = 300.0) -> bool:
        """True if the data is older than ``max_age`` seconds (default 5 min)."""
        age = self.age_seconds()
        return age is not None and age > max_age

    def __contains__(self, pid: str) -> bool:
        return pid in self.products

    def __len__(self) -> int:
        return len(self.products)

    def get(self, pid: str) -> Product | None:
        return self.products.get(pid)

    @classmethod
    def from_api(cls, payload: dict) -> "Market":
        """Build a Market from a raw ``/skyblock/bazaar`` response payload."""
        parsed: dict[str, Product] = {}
        for pid, blob in (payload.get("products") or {}).items():
            product = parse_product(pid, blob)
            if product is not None:
                parsed[pid] = product
        return cls(parsed, last_updated=payload.get("lastUpdated"))

    def flippable(self) -> list[Product]:
        """All products with a genuine two-sided market."""
        return [p for p in self.products.values() if p.has_two_sided_market]
