"""
Null's Addons -- Auction House insights.

The Bazaar is only half the SkyBlock economy; the other half is the Auction
House.  Its API is heavy (≈50k live auctions across 50 pages), so this module
leans on the light, public ``auctions_ended`` feed for price discovery and only
scans the live book when you ask for flips.

What it provides
----------------
* **Sale-price index** -- decode the ``auctions_ended`` feed (recent real sales)
  and accumulate them to a local log, giving a rolling median/last price per item
  id.  The more often you run it, the deeper the history.
* **Your listings** -- with an API key, summarise a player's own auctions: what's
  active, what's sold and claimable, and how each BIN compares to the market.
* **BIN flips** -- a bounded scan of the live book for Buy-It-Now auctions priced
  well under an item's recent median.  Honestly flagged: AH items vary by stats
  (stars, enchants, reforge), so treat these as leads to verify, not sure things.

Item identity comes from the NBT ``item_bytes`` via :mod:`nulladdons.nbt`.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass

from . import nbt

SALES_LOG = os.path.join(os.path.expanduser("~"), ".nulladdons", "sales.jsonl")
MAX_SALES = 40_000
#: Auction House charges roughly 1% on a completed sale (more for pricey items).
AH_TAX = 0.01


def decode_item(item_bytes: str) -> dict | None:
    """Return ``{id, count, name}`` for an auction's item, or ``None``."""
    root = nbt.parse_b64(item_bytes)
    items = root.get("i") if isinstance(root, dict) else None
    if not items:
        return None
    it = items[0] or {}
    tag = it.get("tag") or {}
    extra = tag.get("ExtraAttributes") or {}
    item_id = extra.get("id")
    if not item_id:
        return None
    # Pets all share id "PET"; their real identity is in petInfo (a JSON string).
    if item_id == "PET" and extra.get("petInfo"):
        try:
            info = json.loads(extra["petInfo"])
            item_id = f"{info.get('type', 'PET')}_{info.get('tier', '')}_PET"
        except (ValueError, TypeError):
            pass
    name = ((tag.get("display") or {}).get("Name") or item_id)
    return {"id": item_id, "count": int(it.get("Count", 1) or 1), "name": name}


def sales_from_ended(ended: list[dict]) -> list[dict]:
    """Turn raw ``auctions_ended`` entries into normalised sale records."""
    out = []
    for a in ended:
        info = decode_item(a.get("item_bytes", ""))
        if not info:
            continue
        count = max(1, info["count"])
        price = float(a.get("price", 0))
        out.append({
            "auction_id": a.get("auction_id"),
            "id": info["id"],
            "name": info["name"],
            "price": price,
            "unit_price": price / count,
            "bin": bool(a.get("bin")),
            "ts": int(a.get("timestamp", 0)),
        })
    return out


# --- rolling sale-price index ----------------------------------------------

def record_sales(sales: list[dict], path: str = SALES_LOG) -> int:
    """Append new sales (deduped by auction_id) to the local log. Returns #added."""
    seen = _seen_ids(path)
    fresh = [s for s in sales if s.get("auction_id") not in seen]
    if not fresh:
        return 0
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for s in fresh:
                fh.write(json.dumps(s) + "\n")
        _truncate(path)
    except OSError:
        return 0
    return len(fresh)


def _seen_ids(path: str) -> set[str]:
    ids: set[str] = set()
    if not os.path.exists(path):
        return ids
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                try:
                    ids.add(json.loads(line).get("auction_id"))
                except ValueError:
                    continue
    except OSError:
        pass
    return ids


def _truncate(path: str) -> None:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > MAX_SALES:
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-MAX_SALES:])
    except OSError:
        pass


class SalePriceIndex:
    """Per-item recent-sale statistics built from the local sale log."""

    def __init__(self, by_id: dict[str, list[float]]):
        self._by_id = by_id

    @classmethod
    def load(cls, path: str = SALES_LOG) -> "SalePriceIndex":
        by_id: dict[str, list[float]] = {}
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        try:
                            s = json.loads(line)
                        except ValueError:
                            continue
                        by_id.setdefault(s["id"], []).append(float(s["unit_price"]))
            except OSError:
                pass
        return cls(by_id)

    def stats(self, item_id: str) -> dict | None:
        vals = self._by_id.get(item_id)
        if not vals:
            return None
        return {"count": len(vals), "median": statistics.median(vals),
                "min": min(vals), "max": max(vals), "last": vals[-1]}

    def top_by_volume(self, n: int = 8) -> list[tuple[str, int]]:
        return sorted(((k, len(v)) for k, v in self._by_id.items()),
                      key=lambda kv: kv[1], reverse=True)[:n]


# --- personalised: a player's own auctions ----------------------------------

@dataclass
class ListingSummary:
    active: int
    sold_claimable: int
    active_value: float
    sold_value: float
    lines: list[str]


def player_listing_summary(player_auctions: list[dict], now_ms: int | None = None
                           ) -> ListingSummary:
    now_ms = now_ms or int(time.time() * 1000)
    active = sold = 0
    active_value = sold_value = 0.0
    lines: list[str] = []
    for a in player_auctions:
        info = decode_item(a.get("item_bytes", ""))
        name = info["name"] if info else a.get("item_name", "?")
        price = float(a.get("highest_bid_amount") or a.get("starting_bid") or 0)
        ended = bool(a.get("claimed")) or a.get("end", 0) < now_ms
        bids = a.get("bids") or []
        won = ended and (a.get("highest_bid_amount", 0) > 0 or bids)
        if won:
            sold += 1
            sold_value += price
            lines.append(f"SOLD ✓ {name} — {price:,.0f} (claim it!)")
        elif not ended:
            active += 1
            active_value += price
        else:
            lines.append(f"EXPIRED ✗ {name} — relist")
    return ListingSummary(active, sold, active_value, sold_value, lines)


# --- bounded BIN-flip scan --------------------------------------------------

@dataclass
class BinFlip:
    item_id: str
    name: str
    buy_price: float
    market_median: float
    profit: float
    discount: float
    samples: int


def find_bin_flips(fetch_page, index: SalePriceIndex, max_pages: int = 3,
                   min_samples: int = 4, min_discount: float = 0.15,
                   min_profit: float = 100_000, limit: int = 15) -> list[BinFlip]:
    """
    Scan up to ``max_pages`` of the live AH for BINs priced under an item's
    recent median.  ``fetch_page(n) -> page dict``.  Conservative on purpose:
    needs several recent samples and a real discount, and profit is net of AH tax.
    Still verify item stats before buying -- the index keys on item id only.
    """
    flips: list[BinFlip] = []
    page0 = fetch_page(0)
    total_pages = min(max_pages, int(page0.get("totalPages", 1)))
    for page_no in range(total_pages):
        page = page0 if page_no == 0 else fetch_page(page_no)
        for a in page.get("auctions", []):
            if not a.get("bin"):
                continue
            buy = float(a.get("starting_bid", 0))
            if buy <= 0:
                continue
            info = decode_item(a.get("item_bytes", ""))
            if not info:
                continue
            st = index.stats(info["id"])
            if not st or st["count"] < min_samples:
                continue
            median = st["median"]
            profit = median * (1 - AH_TAX) - buy
            discount = 1 - (buy / median) if median > 0 else 0
            if discount >= min_discount and profit >= min_profit:
                flips.append(BinFlip(info["id"], info["name"], buy, median,
                                     profit, discount, st["count"]))
    flips.sort(key=lambda f: f.profit, reverse=True)
    return flips[:limit]
