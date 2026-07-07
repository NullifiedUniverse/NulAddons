# Null's Addons

**A Hypixel SkyBlock Bazaar‑flipping assistant that turns live market data into
direct, do‑this‑now commands.**

> *"Buy 7,144 Enchanted Mithril @ 2,379.3 · wait ~5 min · sell @ 2,768.7 →
> +2.56M coins (+15.1% after tax)."*

Null's Addons connects to the live Hypixel Bazaar, runs the order book through a
market‑microstructure model (bid‑ask spread, liquidity, market impact, velocity,
mean reversion), sizes every position to your bankroll and risk appetite, and
prints the exact orders to place. No spreadsheets, no guesswork — read a line,
place the order, collect the spread.

It is **advisory**: it tells *you* what to do, you place the orders yourself in
game. It never automates play. Think of it as a market analyst sitting next to
you, not a bot.

---

## What "Bazaar Flipping" is

The Bazaar has two ways to trade:

* **Instant Buy / Instant Sell** — trade immediately at the current best price.
* **Buy Order / Sell Offer** — post *your* price and wait in a queue.

There is always a gap — the **spread** — between the lowest sell offer (what
buying costs) and the highest buy order (what selling fetches). A *flip* captures
that gap: post a **Buy Order** slightly above the best bid, wait for it to fill,
then post a **Sell Offer** slightly below the best ask. You are paid the spread
for providing liquidity, minus Hypixel's tax.

**Craft flipping** is the same idea across the price surface: buy cheap raw
materials, craft them into a higher‑value item (e.g. `160 Diamond → 1 Enchanted
Diamond`), and sell the product for more than the mats cost.

---

## Quick start

No dependencies — just Python 3.9+ and an internet connection.

```bash
# from the repo root
python3 -m nulladdons plan                 # the headline: a full session plan
python3 -m nulladdons flips --top 10       # ranked order flips
python3 -m nulladdons crafts               # ranked craft flips
python3 -m nulladdons item ENCHANTED_LAPIS_LAZULI   # deep dive on one product
python3 -m nulladdons accounts             # your configured accounts

# personalise
python3 -m nulladdons plan -a YunUnderTheMoon
python3 -m nulladdons plan -a NullifiedGalaxy --budget 120000000 --risk aggressive

# "guarantee profit" mode — strict, near‑risk‑free filters
python3 -m nulladdons plan --guaranteed

# no internet? run against the bundled market snapshot
python3 -m nulladdons plan --offline
```

Optional install for a shorter command:

```bash
pip install -e .
nulls-addons plan
```

---

## The promise: "as easy as possible, profit as safe as possible"

Every recommendation is a numbered checklist you can follow blindly:

```
FLIP #1  ·  Enchanted Mithril   [confidence 84% · 11.74M/hr]
   1. BUY ORDER  7,144 @ 2,379.3   → outlay 17.00M
      wait ~5.0 min to fill (you're first in the buy queue)
   2. SELL OFFER 7,144 @ 2,768.7
      wait ~8.1 min to fill
   ⇒ PROFIT 2.56M  (+15.1% after tax)   ·  round-trip ~13.1 min  ·  capped by capital
```

**Can profit ever be *guaranteed*?** Honestly, no market is 100% certain — a
whale can dump, or a price can move while your order rests. What Null's Addons
does is drive that risk as close to zero as the data allows, and it is candid
about it:

* **Conservative / `--guaranteed` mode** only surfaces deep, liquid, stable
  markets with a healthy margin and high confidence, and — for crafts — only
  those that still profit if you execute *instantly* (buy the mats at instant‑buy
  and dump the product at instant‑sell, zero waiting, zero fill risk). That last
  test is a genuine risk‑free floor.
* Everything is **sized** so no single position can consume the market or blow
  your bankroll, and the `plan` view **diversifies** across several uncorrelated
  positions so one bad tick can't sink the session.
* Numbers are labelled `patient` vs `instant`, and anything that only works with
  patient orders is flagged, so you always know which profits are locked in.

---

## The economics, and where each idea lives in the code

Null's Addons is small but every number is grounded in a market concept:

| Economic idea | What it means here | Code |
|---|---|---|
| **Bid‑ask spread** | The raw edge you capture per unit | `mechanics.flip_unit_economics` |
| **Taxes & fees** | 1.25% sell tax (1.1% with a Booster Cookie) is subtracted from every sale | `mechanics.sell_tax`, `net_sell_unit` |
| **Queue priority / undercutting** | You bid +0.1 above the best buy order and offer −0.1 below the best sell offer to reach the front | `mechanics.flip_prices` |
| **Liquidity (Kyle's λ)** | Weekly instant‑flow sets how fast an order fills; thin flow = slow = risky | `economy.fill_minutes` |
| **Market impact / elasticity** | You may take only a small slice of weekly flow, or your own order moves the price | `economy.size_position` (impact cap) |
| **Velocity of money** | Profit is worthless without turnover; **coins/hour = margin × velocity** is the real objective | `economy.coins_per_hour` |
| **Volatility & mean reversion** | A local price‑history log gives a z‑score and coefficient of variation to down‑weight unstable markets and prefer buying below fair value | `history.py`, `economy.confidence` |
| **Manipulation detection** | "Too good to be true" spreads on thin books, blown‑out spread %, and absurd margins are penalised or rejected | `economy.confidence`, `max_margin`/`max_spread_pct` filters |
| **Arbitrage** | Craft flips are arbitrage across the Bazaar's own prices, priced by a recursive cheapest‑acquisition search | `craft.CraftEngine.acquisition_cost` |
| **Risk management / diversification** | Position caps + a diversified portfolio, no position over 34% of bankroll | `economy.size_position`, `commands.build_portfolio` |

**Ranking** is risk‑adjusted velocity: `coins_per_hour × confidence`. Fast,
reliable turnover beats a fat margin you can't fill.

### Position sizing — four independent caps

Every position is the **minimum** of four limits, so none is ever silently
violated (`economy.size_position`):

1. **Capital** — what your budget can afford at the buy price.
2. **Liquidity** — what will actually fill within your patience window.
3. **Impact** — a small slice of weekly flow, so you don't move the price against yourself.
4. **Order cap** — the Bazaar's hard limit of 71,680 units per order.

The output tells you which cap was binding ("capped by capital / liquidity /
impact / order‑cap").

---

## Game mechanics modelled

* **Sell tax:** 1.25% base, 1.1% with a Booster Cookie (set `cookie_buffed` per
  account), configurable for future perks. Buying is untaxed.
* **Undercut increment:** 0.1 coins to jump the queue.
* **Order size limit:** 71,680 units per order; larger positions are reported as
  needing multiple orders.
* **Order‑book truth:** the Hypixel API's `buy_summary`/`sell_summary` and
  `buy…`/`sell…` fields are famously reversed (`buy_summary` is actually the
  *sell offers* you buy from). `bazaar.py` translates them **once** into
  unambiguous `best_bid` / `best_ask` / `demand_per_week` / `supply_per_week`.
* **Legacy IDs:** some products use old Minecraft ids (e.g. Lapis is
  `INK_SACK:4`). Recipes use the exact Bazaar id and are validated live.

---

## Personalisation

Two accounts ship configured in `config/accounts.json`:

| Account | Default risk | Notes |
|---|---|---|
| **NullifiedGalaxy** | balanced | Main account — good turnover with sensible safety |
| **YunUnderTheMoon** | conservative | Growing account — protect the bankroll |

Personalisation has two layers:

1. **Static** (always on, no key): budget, risk profile, Booster‑Cookie tax,
   patience, notes.
2. **Live** (`--live`, needs a free key from
   [developer.hypixel.net](https://developer.hypixel.net)): resolves the
   username to a UUID via Mojang and reads the real SkyBlock profile to override
   the budget with the account's actual **purse + bank** and read unlocked
   collections.

```bash
export HYPIXEL_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
python3 -m nulladdons plan -a NullifiedGalaxy --live
```

Without a key the tool still runs fully on the configured budget.

### Risk profiles

| Profile | Behaviour |
|---|---|
| `conservative` | Only huge, stable, deep markets; wide margins; crafts must profit even executed instantly. This is "guarantee profit" mode. |
| `balanced` | Sensible default — good turnover, safety and choice. |
| `aggressive` | Chases thinner books and longer waits for more options. |

Override anything at the command line: `--budget`, `--risk`, `--hold-time`
(minutes of patience), `--min-margin`, `--top`.

---

## Craft flipping & the safety net

Recipes live in `data/recipes.json` using SkyBlock's standard **160:1** enchant/
compact ratio. The engine:

* prices each craft **from live Bazaar prices**,
* resolves the **cheapest way to obtain every ingredient** recursively — so a
  2‑step chain like `Diamond → Enchanted Diamond → Enchanted Diamond Block` is
  discovered automatically when crafting beats buying at each step,
* **validates every product id** against the live market (a wrong id simply
  prices to infinity and is skipped), and
* refuses to recommend **absurd margins**: an efficient market never sustains a
  huge craft edge, so anything past the ceiling is treated as a manipulated
  price *or a wrong recipe ratio in our own data* and dropped. This guard is why
  a bad recipe can't produce a dangerous fake "+49,000%" recommendation.

Add your own recipes by appending to `data/recipes.json`:

```json
{"output": "ENCHANTED_IRON_BLOCK", "inputs": [["ENCHANTED_IRON", 160]]}
```

---

## Command reference

| Command | Does |
|---|---|
| `plan` | Diversified, budgeted set of orders to place now (default). |
| `flips` | Ranked order flips. |
| `crafts` | Ranked craft flips. |
| `item <ID>` | Deep dive: book, spread, liquidity, flip economics, confidence breakdown. |
| `accounts` | List configured accounts (with live capital if `--live`). |

Common flags: `-a/--account`, `-b/--budget`, `-r/--risk`, `--hold-time`,
`--min-margin`, `--top`, `--guaranteed`, `--live`, `--api-key`, `--offline`,
`--no-history`.

---

## Architecture

```
nulladdons/
  mechanics.py   Game constants & pure flip math (tax, undercut, order caps)
  bazaar.py      Product/Market model — disambiguates the Hypixel API fields
  hypixel.py     Zero-dependency API client (bazaar, Mojang UUID, profiles)
  history.py     Local price-history log for volatility & mean reversion
  economy.py     The theory: fill time, sizing, confidence, coins/hour
  flip.py        Order-flip finder
  craft.py       Craft-flip finder (recursive cheapest-acquisition arbitrage)
  accounts.py    Per-account personalisation & risk profiles
  commands.py    Renders plans into direct commands + the diversified portfolio
  cli.py         Command-line interface
config/accounts.json     Account settings
data/recipes.json        Craft recipe database
data/sample_bazaar.json  Bundled snapshot for --offline / demos
tests/test_core.py       Unit tests (no network)
```

Run the tests with `python3 -m unittest discover -s tests`.

---

## Notes & honesty

* Prices move. Re‑run before acting; the tool re‑prices every run and logs a
  price‑history sample so its volatility model sharpens over time.
* Recipe ratios are curated assumptions validated against live ids and guarded
  by the absurdity ceiling, but if you add recipes, double‑check the quantities.
* This is an **analysis tool** that suggests manual actions. It does not
  automate gameplay.
