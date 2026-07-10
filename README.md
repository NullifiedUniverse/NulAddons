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

## ▶ Run it in 30 seconds

You need **Python 3.9+** and an internet connection. Nothing to install.

```bash
git clone https://github.com/NullifiedUniverse/NulAddons && cd NulAddons

python3 -m nulladdons setup      # 2-min wizard (optional keys + your account)
python3 -m nulladdons status     # your dashboard: capital → income → goals
python3 -m nulladdons plan       # the exact orders to place right now
python3 -m nulladdons ask "what should I flip?"   # ask anything, in plain English
```

That's it. Everything works out of the box on the bundled example account, and
`setup` personalises it to you. Not sure something's configured? `nulladdons doctor`.

**Prefer it in‑game?** There are companion **Minecraft mods** that put a movable
top‑flips HUD and live flip/craft numbers on item tooltips, styled like
SkyBlockAddons/NEU — fully async and cached, so they only show up on SkyBlock and
cost nothing otherwise:

* [`mod/`](mod/README.md) — **Forge 1.8.9** (the classic SkyBlock target).
* [`mod-fabric/`](mod-fabric/README.md) — **Fabric 1.21+** (modern), adding
  craft‑flip tooltips, Mayor‑aware tax (Derpy → 0 %), and opt‑in
  [telemetry](mod-fabric/TELEMETRY.md).

Both share the exact same pure‑Java economics `core` (order flips, craft flips,
mayor effect, manipulation guards), reused with no duplication and covered by a
38‑check self‑test.

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

## Getting started (first run)

No dependencies — just Python 3.9+ and an internet connection.  One command sets
everything up:

```bash
python3 -m nulladdons setup     # friendly wizard — 2 minutes
```

The wizard walks you through it and validates as you go:

1. **API keys & integrations** (all optional): a free **Hypixel** key
   ([developer.hypixel.net](https://developer.hypixel.net)) for live capital,
   progress tracking and your AH listings; a **Gemini** key
   ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) for the AI
   daily brief; a **Discord webhook** for alerts — it sends a test message to
   confirm it works.
2. **Accounts**: type a Minecraft username (it resolves the UUID live), pick a
   risk profile, set the budget (or pull your real purse + bank if you gave a
   key), and set optional coin / Magical‑Power goals.

Your answers are written to a private (`chmod 600`) `~/.nulladdons/accounts.json`
— so a fresh clone or a `pip install` both just work, and your keys stay in your
home dir, not the repo.  Then check everything's healthy:

```bash
python3 -m nulladdons doctor    # verifies keys, accounts & connectivity, with fix hints
python3 -m nulladdons status    # you're ready — the ecosystem dashboard
```

Prefer to skip the wizard?  Edit `config/accounts.json` (the bundled example) or
set `HYPIXEL_API_KEY` / `GEMINI_API_KEY` env vars.  Point at any config with
`NULLADDONS_CONFIG=/path/to/accounts.json`.

## All the commands

```bash
python3 -m nulladdons status               # ecosystem dashboard: capital → income → goals
python3 -m nulladdons plan                 # the headline: a full session plan
python3 -m nulladdons flips --top 10       # ranked order flips
python3 -m nulladdons crafts               # ranked craft flips
python3 -m nulladdons mp                    # cheapest Magical Power to buy/craft/recomb
python3 -m nulladdons ah                     # Auction House: recent sales + your listings
python3 -m nulladdons brief                  # daily brief: progress + insights (Gemini)
python3 -m nulladdons item ENCHANTED_LAPIS_LAZULI   # deep dive on one product
python3 -m nulladdons accounts             # your configured accounts

# personalise
python3 -m nulladdons plan -a YunUnderTheMoon
python3 -m nulladdons plan -a NullifiedGalaxy --budget 120000000 --risk aggressive
python3 -m nulladdons mp -a NullifiedGalaxy --live --mp-goal 2000   # uses your real bag

# "guarantee profit" mode — strict, near‑risk‑free filters
python3 -m nulladdons plan --guaranteed

# push crucial opportunities to Discord (optionally watch on a loop)
python3 -m nulladdons alert --webhook https://discord.com/api/webhooks/...
python3 -m nulladdons alert --watch 10     # re-check every 10 min, post only what's new

# no internet? run against the bundled market snapshot (never for real trades)
python3 -m nulladdons plan --offline
```

**Bazaar data is always live.** Every command fetches the Hypixel Bazaar in real
time (cached ~60s) and prints how old the snapshot is; if the fetch fails it
errors out rather than trade on stale numbers. `--offline` is an explicit,
loudly‑flagged demo mode only.

Optional install for a shorter command:

```bash
pip install -e .
nulls-addons plan
```

---

## The ecosystem: capital → income → goals (`status`)

Everything is wired to your **live capital**.  `status` is the hub that ties it
together and answers *"how much can I make from the Bazaar with what's in my bank
right now, and how close am I to my goals?"*:

```
 Capital: 50.00M   ·   balanced risk   ·   5 live positions
 ── Bazaar income potential ──
   Deploy 49.9M across 5 positions → 24.4M/hr
   ≈ 146M / 6h day   ·   ≈ 1.02B / week   (reinvest to compound)
 ── Goals ──
   Coins 50.00M → 500.00M (450M to go): 18.4h (~3.1 days @6h/day)
   Best recomb: 1.89M/MP — afford one in 28 min
 ── Auction House ──   2 sold & claimable (12.0M) · 3 active
 ── Do this now ──   buy 7,144 Enchanted Mithril @ 2,379.3 → 2.56M (+15.1%)
```

The projection is honest: positions are **sized to what your bank can afford**,
so the rate is capital‑limited, and it's flagged that reinvesting profits each
cycle compounds faster than the linear figure.  Set `coin_goal`, `mp_goal` and
`active_hours` per account and the ETAs update automatically.  `plan` shows the
same income projection as a footer.

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

## Magical Power planner (`mp`)

Magical Power (MP) scales your Accessory Bag, and every accessory grants MP purely
by **rarity** (Common 3 · Uncommon 5 · Rare 8 · Epic 12 · Legendary 16 · Mythic
22).  So "more MP, cheap and fast" is an optimisation over **coins per MP**, and
the planner ranks every lever it can price from the live Bazaar:

* **Buy / craft** accessories you don't own — a Bazaar accessory, or one crafted
  from Bazaar mats (priced through the same recursive recipe engine as craft
  flips).  Ranked cheapest coins/MP first, one entry per accessory family, skipping
  what you already own.
* **Recombobulate** accessories you *do* own — a Recombobulator 3000 bumps an
  accessory one rarity (+MP).  Its price comes straight from the Bazaar, so
  coins/MP = recomb price ÷ MP gained.  The planner shows the best‑value tiers
  (e.g. Legendary→Mythic is +6 MP).

**Reality check:** almost no accessories are Bazaar‑tradable (verified against the
live API — 0 of 58 common ones), so the Recombobulator is the main live‑priced
lever, plus the handful of Bazaar accessories.  The accessory database
(`data/accessories.json`) is the extensible part: add any accessory with a
`bazaar`, `craft`, or `npc` cost and it's priced and ranked automatically. Unlike a
bad *flip* recipe, a slightly‑off *accessory* recipe only mis‑estimates a shopping
cost — you still get the real MP — and every id is still validated live.

**Personalised:** with `--live` and an API key, the planner decodes your talisman
bag (a minimal built‑in NBT reader) to skip accessories you already own and to
target `mp_goal`.  Without a key it uses `owned_families` from config.

## Discord alerts (`alert`)

Get pinged only when it matters.  `alert` posts **crucial** opportunities to a
Discord webhook — a rare high‑value flip, a guaranteed craft, a great MP deal —
where "crucial" is defined per account by thresholds:

```json
"alert": { "min_profit": 1000000, "min_coins_per_hour": 5000000, "min_confidence": 0.6 }
```

```bash
python3 -m nulladdons alert --webhook https://discord.com/api/webhooks/xxx/yyy
python3 -m nulladdons alert --watch 10      # loop: re-check every 10 min, only post NEW ones
python3 -m nulladdons plan  --webhook ...    # also posts the session-plan summary
```

Set the webhook once in `config/accounts.json` (`discord_webhook_url` globally, or
`webhook_url` per account) and drop the flag.  The watch loop de‑dupes so you're
never spammed with the same flip twice.

## Auction House (`ah`)

The Bazaar is only half the economy.  The AH API is heavy (~50k live auctions
across 50 pages), so `ah` leans on the light, public `auctions_ended` feed for
price discovery and only scans the live book when you ask:

* **Recent notable sales** — decodes the ended‑auction feed (item ids from NBT,
  pets included) and shows what actually sold and for how much.
* **Rolling sale‑price index** — every run appends real sales to a local log, so a
  per‑item recent median builds up over time (the more you run it, the deeper).
* **Your listings** (`--live` + key) — what's active, and what's **sold &
  claimable** so you never forget to collect.
* **BIN flips** (`--scan N`) — scans `N` pages of the live book for Buy‑It‑Now
  auctions priced well under an item's recent median.  Conservative and honest:
  it needs several recent samples and nets AH tax, and it flags that AH items vary
  by stats (stars/enchants/reforge) — treat these as leads to verify, not sure
  things.

```bash
python3 -m nulladdons ah                 # recent sales + (with --live) your listings
python3 -m nulladdons ah --scan 3        # also scan 3 pages for underpriced BINs
```

## Daily brief (`brief`) — powered by Gemini

A once‑a‑day SkyBlock briefing.  It **snapshots your account** from the API,
**diffs it against yesterday's snapshot** (coins, skills + level‑ups, slayer,
catacombs, collections, pets, fairy souls), gathers the day's best Bazaar/craft
flips, cheapest Magical Power and Auction House highlights, and feeds all of it as
**facts** to a Google **Gemini** model acting as a SkyBlock economy & progression
expert, which returns a short summary with prioritised, actionable advice.

```bash
export HYPIXEL_API_KEY=...   # for progress tracking (purse/skills/…)
export GEMINI_API_KEY=...    # for the AI summary (from Google AI Studio)
python3 -m nulladdons brief -a NullifiedGalaxy --live
python3 -m nulladdons brief --webhook <discord>       # post the brief to Discord
# schedule it daily, e.g. cron:  0 9 * * *  cd /path/NulAddons && python3 -m nulladdons brief --live --webhook <url>
```

Everything degrades gracefully: **no Gemini key** → a deterministic local brief
built from the same facts; **no Hypixel key** → a market‑only brief (no progress).
The LLM only ever adds prose on top of numbers the tool already computed — it is
never load‑bearing for correctness, and is instructed never to invent numbers.

## Ask anything (grounded AI, never makes things up)

Ask in plain English and get an answer built **only** from live Hypixel data:

```bash
python3 -m nulladdons ask "how much profit flipping enchanted diamond?"
python3 -m nulladdons ask "who's the mayor and does it matter?"
python3 -m nulladdons ask "how long until I hit 500m?"
python3 -m nulladdons ask "what should I craft right now?"
python3 -m nulladdons ask "should I flip enchanted lapis" --show-facts   # see the grounding
```

How it stays honest:

1. **Retrieval** — your question is parsed for the items and topics it mentions,
   and only the *relevant* live facts (Bazaar prices, the Mayor, your capital,
   top flips, AH sales…) are assembled into a FACTS sheet (`--show-facts` prints it).
2. **Answering** — with a Gemini key, those facts + your question go to the model
   under a strict prompt that **forbids inventing anything** and requires it to
   reply *"I don't know based on the current data."* when the facts don't cover it.
   Numbers only ever come from the live API.

No Gemini key?  A built‑in **local answerer** still handles the common questions
(price, flip, mayor, income, budget, magical power, best flip/craft) from the same
live facts — and also says *"I don't know"* rather than guess.  So the AI works
for everyone; a key just unlocks open‑ended questions.

> Ask it "how do I beat Necron?" and it will honestly say it doesn't know — it's a
> live‑market analyst, not a wiki, and it won't pretend otherwise.

## Game‑aware: the Mayor runs the economy

Every ~5 SkyBlock days the community elects a **Mayor** whose perks reshape the
market — and most spreadsheets ignore it.  Null's Addons reads the live election
(`resources/skyblock/election`, no key) and adapts:

* **Derpy** ("Tax Evasion") zeroes the Bazaar & AH tax.  The tool sets tax to 0%,
  every margin recalculates, and it tells you to flip big.
* **Mining** mayors (Cole / Mining Fiesta) glut the ore supply → *"buy ores
  cheap; sell your enchanted‑ore stock **before** the dump."*  **Farming**
  (Finnegan) and **Fishing** (Marina) do the same for crops and sea‑creature drops.
* Upcoming **candidates** become a heads‑up: `Next election: Cole ⛏️, Marina 🎣`.

The active mayor shows on `status`, `plan`, `flips`, `crafts` and feeds the daily
brief.  And you can **simulate** any mayor to plan ahead:

```bash
python3 -m nulladdons flips --mayor derpy   # see every flip at 0% tax
python3 -m nulladdons plan  --mayor cole     # plan around a mining glut
```

## Market movers (pump/dump radar)

`status` also mines your accumulated price‑history log for the biggest recent
movers among liquid items (`📈 Ice Bait +42%  ·  📉 Raw Fish −18%`) — a free
signal for event spikes, pumps and manipulation.  It deepens the more you run the
tool.

## Vibes (and how to turn them off)

Null's Addons has a mouth on it. Headers get taglines, empty results roast you
gently, `--risk yolo` and `--risk scared` are real, and `ask` has opinions about
whether it's sentient. There's a hidden `nulladdons lore` command and a few other
things to dig up. **The numbers are never a joke** — flair only ever lives in the
chrome, and `ask` still says *"I don't know"* rather than make anything up.

It also *moves* a little, when you're at a real terminal: a spinner while the
live Bazaar loads, a slot‑machine count‑up on the headline number in `plan` and
`status`, a `HOT`/`CRACKED 🔥` tag on juicy flips, and — in the mod — the HUD
panel fades in and gently pulses when a cracked flip is on the board. **None of
it touches a number**: a count‑up always lands on the exact real value, and the
instant you pipe output to a file or another program every effect vanishes, so
scripts see clean text.

Hate fun? `--serious` (or `NULLADDONS_SERIOUS=1`) mutes the personality *and* the
motion for clean, neutral output. Want the jokes but not the motion? `--no-anim`
(or `NULLADDONS_NO_ANIM=1`) turns off just the animations. Respect either way.

## Make it yours: flavors & features

Same honest numbers, your voice. Pick a **flavor** and the taglines change
personality:

| Flavor | Voice |
|---|---|
| `gremlin` | edgy, chronically online (default) |
| `zen` | calm, mindful, suspiciously peaceful |
| `wallstreet` | finance-bro, "provides liquidity" |
| `speedrunner` | PB-obsessed, resets the market |
| `pirate` | arr, thar be spread in these waters |

Set it per run with `--flavor pirate`, for the shell with `NULLADDONS_FLAVOR`, or
permanently in `setup`. Coarse **feature toggles** (stored in config) let you turn
off anything you don't want: `animations`, `easter_eggs`, `market_movers`,
`mayor`, and `telemetry`. `setup` walks you through all of it.

## Telemetry & your stats — opt-in, local, and honestly kind of fun 🎁

Null's Addons can keep a **personal stats log** of how you play — and it is
**OFF by default**. Nothing is recorded, and no file is created, until you turn
it on:

```bash
nulladdons telemetry manifest   # see EXACTLY what it would collect, and where
nulladdons telemetry on         # opt in (writes to ~/.nulladdons/telemetry/)
```

Once on, every command appends one compact JSON line locally. Then:

```bash
nulladdons telemetry stats          # dashboard: favorite commands, grind clock, records
nulladdons telemetry wrapped        # your "SkyBlock Wrapped" recap 🎁
nulladdons telemetry achievements   # ~24 unlockable badges (Whale Watcher, Tax Evader, …)
nulladdons telemetry export         # portable JSONL, take your data anywhere
nulladdons telemetry off            # stop recording   ·   clear = wipe the log
```

The rules, up front and enforced by tests:

- **Off by default**, and it's a real second opt-in — turning it on is the only
  way anything is written.
- **No PII**: no usernames, no UUIDs, no API keys, and never the *text* of a
  question you `ask` — only its category. `telemetry manifest` lists every field.
- **Local only**, unless *you* additionally set `telemetry.sink_url`, in which
  case the same line is POSTed there so you can pipe your stats wherever you like.
- It only ever records *presentation* facts about your runs — it can't and
  doesn't change a single price or recommendation.

## Command reference

| Command | Does |
|---|---|
| `setup` | Interactive first‑run wizard: keys, Discord, accounts, goals (writes `~/.nulladdons/accounts.json`). |
| `doctor` | Health check: validates keys, resolves accounts, tests connectivity — with a fix hint per line. |
| `ask "…"` | Grounded AI: answer any question from live data, or honestly say "I don't know". |
| `status` | Ecosystem dashboard: live capital → income projection → goal ETAs → next action. |
| `plan` | Diversified, budgeted set of orders to place now (default). |
| `flips` | Ranked order flips. |
| `crafts` | Ranked craft flips. |
| `mp` | Cheapest Magical Power: accessories to buy/craft + Recombobulator upgrades. |
| `ah` | Auction House: recent sales, your listings, `--scan N` for BIN flips. |
| `brief` | Daily brief: account progress diff + opportunities + Gemini insights. |
| `item <ID>` | Deep dive: book, spread, liquidity, flip economics, confidence breakdown. |
| `alert` | Post crucial opportunities to Discord (optionally `--watch`). |
| `accounts` | List configured accounts (with live capital if `--live`). |
| `telemetry` | Opt-in local stats, SkyBlock **Wrapped** & achievements: `on`/`off`/`manifest`/`stats`/`wrapped`/`achievements`/`export`/`clear`. |

Common flags: `-a/--account`, `-b/--budget`, `-r/--risk`, `--hold-time`,
`--min-margin`, `--top`, `--guaranteed`, `--live`, `--api-key`, `--webhook`,
`--offline`, `--no-history`, `--serious`, `--no-anim`, `--flavor`.  Plus
`--mp-goal` (mp) and `--watch` (alert).

### Per‑account config (`config/accounts.json`)

`budget`, `risk`, `cookie_buffed`, `notes`, plus: `mp_goal`, `coin_goal`,
`active_hours` (flipping hours/day used for income projections & ETAs),
`owned_families`, `blacklist`/`whitelist` (product ids to force‑skip or restrict
to), `webhook_url` and `alert` thresholds.  Top‑level keys apply to all accounts: `hypixel_api_key`,
`gemini_api_key`, `gemini_model`, `discord_webhook_url`, and default `alert`
thresholds.  Any of these can also come from `--flags` or the `HYPIXEL_API_KEY` /
`GEMINI_API_KEY` environment variables.

---

## Architecture

```
nulladdons/
  mechanics.py   Game constants & pure flip math (tax, undercut, order caps)
  bazaar.py      Product/Market model — disambiguates the Hypixel API fields; data age
  hypixel.py     Zero-dependency API client (bazaar, Mojang UUID, profiles)
  history.py     Local price-history log for volatility & mean reversion
  economy.py     The theory: congestion-aware fill time, sizing, confidence, coins/hour
  mayor.py       Live Mayor/Election economics (Derpy tax-free, mining/farming gluts)
  projection.py  Live capital -> hourly/daily/weekly income + goal ETAs (ecosystem glue)
  flip.py        Order-flip finder (+ blacklist/whitelist)
  craft.py       Craft-flip finder (recursive cheapest-acquisition arbitrage)
  accessories.py Magical Power planner (coins/MP, Recombobulator lever)
  nbt.py         Minimal NBT reader — decodes talisman bags & auction items
  auction.py     Auction House: sale-price index, your listings, BIN flips
  progress.py    Account snapshots + day-over-day progression diff
  llm.py         Google Gemini client (brief brain + grounded Q&A persona)
  ask.py         Grounded question-answerer (retrieval + no-hallucination answers)
  brief.py       Assembles the daily brief (facts -> Gemini -> summary)
  accounts.py    Per-account personalisation, risk profiles & config resolution
  onboarding.py  Setup wizard + doctor health check
  ui.py          Tiny terminal toolkit (colour + EOF-safe prompts)
  commands.py    Renders plans into direct commands + the diversified portfolio
  notify.py      Discord webhook notifier for crucial messages
  cli.py         Command-line interface
config/accounts.json     Bundled example config (your real one lives in ~/.nulladdons/)
data/recipes.json        Craft recipe database
data/accessories.json    Accessory / Magical-Power database
data/sample_bazaar.json  Bundled snapshot for --offline / demos
tests/                    Unit tests (no network): test_core / test_features / test_brief / test_ecosystem / test_onboarding / test_mayor / test_ask
```

Run the tests with `python3 -m unittest discover -s tests` (82 tests).

### Robustness — new items never crash the app

SkyBlock adds Bazaar products, item ids and accessories constantly, and users add
their own recipes/accessories.  Every ingestion point is defensive: numeric API
fields are coerced through a finite‑float guard (a `null`, a string, or even a
`NaN` price can't crash a parse or poison a calculation), a single unparseable
Bazaar product or auction item is skipped rather than sinking the batch, and the
recipe/accessory loaders skip malformed entries.  The progress diff tolerates
snapshots written by older versions of the tool.  This is covered by a dedicated
crash‑resistance test that feeds deliberate garbage through every parser.

## Hypixel APIs used

All fetched live, stdlib‑only, cached briefly: `skyblock/bazaar`,
`skyblock/auctions_ended` (+ paginated `skyblock/auctions` for BIN scans),
`skyblock/auction` (your listings), `skyblock/profiles` (progress + capital +
talisman bag), and `resources/skyblock/skills` (level thresholds).  Usernames
resolve via Mojang.  Personalised data (profiles, listings) needs a free key from
[developer.hypixel.net](https://developer.hypixel.net).

### Refined fill model

Fill times are congestion‑aware: a big stack of orders already resting on your
side of the book signals an undercut war, so the model measures *days of backlog*
(resting same‑side volume ÷ daily instant‑flow) and fades how much of the flow your
order actually wins.  A calm book fills near the naive estimate; a congested one
takes realistically longer — which flows straight through to position sizing.

---

## Notes & honesty

* Prices move. Re‑run before acting; the tool re‑prices every run and logs a
  price‑history sample so its volatility model sharpens over time.
* Recipe ratios are curated assumptions validated against live ids and guarded
  by the absurdity ceiling, but if you add recipes, double‑check the quantities.
* This is an **analysis tool** that suggests manual actions. It does not
  automate gameplay.

## Project

* **License:** [MIT](LICENSE) — free to use, modify, and share.
* **Contributing:** see [CONTRIBUTING.md](CONTRIBUTING.md) for the golden rules
  (numbers stay honest, the tool stays advisory) and how to run the tests.
* **Building the mod:** [BUILD.md](BUILD.md) — grab a prebuilt jar, or run
  `./build.sh` (each mod ships a Gradle wrapper, so no Gradle install needed).
* **Changelog:** [CHANGELOG.md](CHANGELOG.md).
* **Tests:** `python3 -m unittest discover -s tests` (131 Python tests) plus a
  standalone Java self-test for the mod core (61 checks). CI runs both on every
  push.
* **Fast where it counts:** `status` fetches the Bazaar, the mayor election, and
  the ended-auctions feed *concurrently* (`tasks.gather`), collapsing three
  network round-trips into about one.

Null's Addons is an unofficial, fan‑made tool. It is not affiliated with,
endorsed by, or associated with Hypixel Inc. or Mojang/Microsoft.
