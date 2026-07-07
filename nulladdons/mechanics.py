"""
Null's Addons -- Hypixel SkyBlock game mechanics.

This module is the single source of truth for the *rules of the Bazaar*.  Every
number here is a game mechanic, not an opinion, so the rest of the code base can
trust it.  If Hypixel changes a value, change it here once.

Key Bazaar facts modelled below
-------------------------------
* **Two order types.**  A *Buy Order* is a bid: you offer to buy at a price and
  wait for someone to instant-sell into you.  A *Sell Offer* is an ask: you list
  goods and wait for someone to instant-buy from you.  A "flip" is a Buy Order
  followed by a Sell Offer -- you provide liquidity and pocket the spread.
* **Tax.**  Hypixel charges a tax on the *coins you receive from a Sell Offer /
  Instant Sell*.  The base rate is 1.25%.  Buying costs no tax.  The rate can be
  lowered per-account (Booster Cookie + Bazaar-flipper perks), so it is a
  parameter everywhere, defaulting to the base 1.25%.
* **Undercutting.**  Orders are matched by price-time priority.  To jump to the
  front of the queue you beat the current best order by the minimum increment,
  0.1 coins.  So your buy order sits 0.1 above the best bid and your sell offer
  0.1 below the best ask.
* **Order size cap.**  A single Bazaar order holds at most 71,680 units.  Larger
  positions must be split across multiple orders.
"""

from __future__ import annotations

# --- Taxes & fees -----------------------------------------------------------

#: Base Bazaar tax applied to coins received from a Sell Offer / Instant Sell.
BASE_BAZAAR_TAX: float = 0.0125  # 1.25%

#: Extra tax shaved off by having a Booster Cookie active (the Bazaar tax drops
#: from 1.25% -> 1.1%).  Applied only when an account is flagged as cookie-buffed.
COOKIE_TAX: float = 0.011  # 1.1%

#: Best-case tax with the community-center "Bazaar" perk maxed *and* a cookie.
BEST_CASE_TAX: float = 0.01  # 1.0%

# --- Order book mechanics ---------------------------------------------------

#: Minimum price step used to undercut / overbid the current best order.
UNDERCUT_INCREMENT: float = 0.1

#: Maximum number of items in a single Bazaar order.
ORDER_UNIT_LIMIT: int = 71_680

#: Minutes in the rolling window the API reports as ``*MovingWeek``.
WEEK_MINUTES: int = 7 * 24 * 60  # 10,080


def sell_tax(cookie_buffed: bool = False, best_case: bool = False) -> float:
    """Return the effective Sell-Offer tax rate for an account's perks."""
    if best_case:
        return BEST_CASE_TAX
    if cookie_buffed:
        return COOKIE_TAX
    return BASE_BAZAAR_TAX


def net_sell_unit(sell_price: float, tax: float = BASE_BAZAAR_TAX) -> float:
    """Coins actually received per unit from a Sell Offer after tax."""
    return sell_price * (1.0 - tax)


def flip_prices(best_bid: float, best_ask: float,
                increment: float = UNDERCUT_INCREMENT) -> tuple[float, float]:
    """
    Given the current best bid (top buy order) and best ask (top sell offer),
    return the (buy_order_price, sell_offer_price) that put *you* at the front of
    both queues.

    You bid one increment above the best bid and offer one increment below the
    best ask.  These are the prices a real flipper types into the Bazaar.
    """
    buy_order_price = best_bid + increment
    sell_offer_price = best_ask - increment
    return buy_order_price, sell_offer_price


def flip_unit_economics(best_bid: float, best_ask: float,
                        tax: float = BASE_BAZAAR_TAX,
                        increment: float = UNDERCUT_INCREMENT) -> dict:
    """
    Per-unit economics of an order flip, from the raw top-of-book prices.

    Returns a dict with the exact prices to type in and the resulting profit.
    ``profit`` is coins earned per unit after tax; ``margin`` is profit / cost.
    A non-positive spread (book too tight to squeeze between) yields negative
    profit, which callers should filter out.
    """
    buy_order_price, sell_offer_price = flip_prices(best_bid, best_ask, increment)
    revenue = net_sell_unit(sell_offer_price, tax)
    cost = buy_order_price
    profit = revenue - cost
    margin = profit / cost if cost > 0 else 0.0
    return {
        "buy_order_price": buy_order_price,
        "sell_offer_price": sell_offer_price,
        "gross_spread": sell_offer_price - buy_order_price,
        "unit_cost": cost,
        "unit_revenue_net": revenue,
        "unit_profit": profit,
        "margin": margin,
    }


def orders_needed(quantity: int) -> int:
    """How many Bazaar order slots a position of ``quantity`` units requires."""
    if quantity <= 0:
        return 0
    return -(-quantity // ORDER_UNIT_LIMIT)  # ceil division
