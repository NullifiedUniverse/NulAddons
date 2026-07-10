"""
Null's Addons -- command-line interface.

First run
---------
* ``setup``    -- interactive wizard: API keys, Discord, accounts, goals.
* ``doctor``   -- check keys, accounts and connectivity, with fix hints.

Every day
---------
* ``status``   -- ecosystem dashboard: capital -> income -> goals -> next action.
* ``plan``     -- diversified, budgeted set of orders to place now (default).
* ``brief``    -- daily progress + opportunities, summarised by Gemini.

Deep dives
----------
* ``flips`` / ``crafts`` / ``mp`` / ``ah`` / ``item ID`` / ``alert`` / ``accounts``.

Global options override budget, risk, patience and margin, run offline against a
saved snapshot, or flip on ``--guaranteed`` (strict, near-risk-free filters).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import accessories as accessoriesmod
from . import accounts as accountsmod
from . import ask as askmod
from . import (
    auction,
    commands,
    craft,
    economy,
    features,
    flair,
    flip,
    fx,
    hypixel,
    llm,
    mayor,
    mechanics,
    notify,
    onboarding,
    progress,
    projection,
    tasks,
    telemetry,
    ui,
)
from . import brief as briefmod
from .bazaar import Market
from .history import PriceHistory, record_snapshot

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPES = os.path.join(_ROOT, "data", "recipes.json")
DEFAULT_ACCESSORIES = os.path.join(_ROOT, "data", "accessories.json")
DEFAULT_SAMPLE = os.path.join(_ROOT, "data", "sample_bazaar.json")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-a", "--account", default=None,
                   help="configured account name (default: your first account)")
    p.add_argument("-b", "--budget", type=float, default=None,
                   help="override capital, in coins")
    p.add_argument("-r", "--risk", default=None,
                   help="override risk profile: conservative / balanced / aggressive")
    p.add_argument("--serious", action="store_true",
                   help="disable the personality/flair — clean, neutral output")
    p.add_argument("--no-anim", action="store_true",
                   help="disable terminal animations/effects (spinners, count-ups)")
    p.add_argument("--flavor", default=None, metavar="NAME",
                   help="personality flavor: " + " / ".join(features.flavor_ids()))
    p.add_argument("--hold-time", type=float, default=None,
                   help="max minutes you're willing to wait for a round-trip")
    p.add_argument("--min-margin", type=float, default=None,
                   help="minimum after-tax margin percent (e.g. 3 for 3%%)")
    p.add_argument("--top", type=int, default=10, help="how many results to show")
    p.add_argument("--guaranteed", action="store_true",
                   help="strict near-risk-free filters (implies conservative)")
    p.add_argument("--live", action="store_true",
                   help="enrich account from the live Hypixel profile (needs key)")
    p.add_argument("--api-key", default=os.environ.get("HYPIXEL_API_KEY"),
                   help="Hypixel API key (or set HYPIXEL_API_KEY)")
    p.add_argument("--webhook", default=None,
                   help="Discord webhook URL to post to (overrides config)")
    p.add_argument("--mayor", default=None, metavar="NAME",
                   help="simulate a mayor's economy (e.g. --mayor derpy for 0%% tax)")
    p.add_argument("--offline", nargs="?", const=DEFAULT_SAMPLE, default=None,
                   help="use a saved bazaar snapshot instead of the network")
    p.add_argument("--recipes", default=DEFAULT_RECIPES,
                   help="path to the craft recipe database")
    p.add_argument("--no-history", action="store_true",
                   help="do not read/write the local price-history log")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nulladdons",
        description="Null's Addons — Hypixel SkyBlock money-making assistant. "
                    "New here? Run:  nulladdons setup",
        epilog="tip: try  nulladdons ask \"are you sentient\"  ·  "
               "add --serious to mute the vibes. not financial advice, it's a block game.")
    sub = parser.add_subparsers(dest="command")

    sp_setup = sub.add_parser("setup", help="interactive first-run setup wizard")
    sp_setup.add_argument("--config", default=None,
                          help="where to write config (default ~/.nulladdons/accounts.json)")

    sp_doc = sub.add_parser("doctor", help="check your setup (keys, accounts, connectivity)")
    sp_doc.add_argument("--config", default=None, help="config file to check")
    sp_doc.add_argument("--quick", action="store_true",
                        help="skip the live Gemini test call")

    # Undocumented on purpose: no help text, so it stays out of the detailed
    # command list but still peeks from the usage line -- a little something to find.
    sub.add_parser("lore")

    tp = sub.add_parser("telemetry",
                        help="opt-in local stats, SkyBlock Wrapped & achievements")
    tp.add_argument("action", nargs="?", default="status",
                    choices=["status", "on", "off", "manifest", "stats", "wrapped",
                             "achievements", "export", "clear"],
                    help="status (default) · on · off · manifest · stats · wrapped "
                         "· achievements · export · clear")
    tp.add_argument("--path", default=None,
                    help="destination file for `telemetry export`")
    tp.add_argument("--yes", action="store_true",
                    help="skip the confirmation for `telemetry clear`")

    for name, help_ in (("plan", "diversified session plan (default)"),
                        ("flips", "ranked order flips"),
                        ("crafts", "ranked craft flips"),
                        ("accounts", "list configured accounts")):
        sp = sub.add_parser(name, help=help_)
        _add_common(sp)

    ip = sub.add_parser("item", help="deep dive on one product id")
    ip.add_argument("product_id")
    _add_common(ip)

    mp = sub.add_parser("mp", help="cheapest Magical Power (accessories/recomb)")
    _add_common(mp)
    mp.add_argument("--mp-goal", type=int, default=None,
                    help="target Magical Power to reach")
    mp.add_argument("--accessories", default=DEFAULT_ACCESSORIES,
                    help="path to the accessory database")

    al = sub.add_parser("alert", help="post crucial opportunities to Discord")
    _add_common(al)
    al.add_argument("--watch", type=float, default=None, metavar="MINUTES",
                    help="re-check every MINUTES and post only new opportunities")

    ah = sub.add_parser("ah", help="Auction House insights (recent sales, your listings)")
    _add_common(ah)
    ah.add_argument("--scan", type=int, default=0, metavar="PAGES",
                    help="scan PAGES of the live AH for underpriced BIN flips")

    aq = sub.add_parser("ask", help="ask anything about the live market / your account")
    _add_common(aq)
    aq.add_argument("question", nargs="+", help="your question in plain English")
    aq.add_argument("--show-facts", action="store_true",
                    help="also print the live facts the answer is grounded in")
    aq.add_argument("--accessories", default=DEFAULT_ACCESSORIES)
    aq.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"),
                    help="Gemini API key (or set GEMINI_API_KEY / config)")
    aq.add_argument("--gemini-model", default=None, help="Gemini model id")
    aq.add_argument("--no-llm", action="store_true",
                    help="answer locally only (no Gemini call)")

    st = sub.add_parser("status", help="ecosystem dashboard: capital → income → goals")
    _add_common(st)
    st.add_argument("--accessories", default=DEFAULT_ACCESSORIES)

    br = sub.add_parser("brief", help="daily SkyBlock brief (progress + Gemini insights)")
    _add_common(br)
    br.add_argument("--accessories", default=DEFAULT_ACCESSORIES)
    br.add_argument("--gemini-key", default=os.environ.get("GEMINI_API_KEY"),
                    help="Gemini API key (or set GEMINI_API_KEY / config)")
    br.add_argument("--gemini-model", default=None, help="Gemini model id")
    br.add_argument("--no-llm", action="store_true",
                    help="skip Gemini, use the deterministic local brief")
    return parser


def _load_market(args, payload=None) -> tuple[Market, PriceHistory | None]:
    offline = getattr(args, "offline", None)
    if offline:
        # Explicit offline mode: use a snapshot, but never silently.
        if not os.path.exists(offline):
            print(f"! offline snapshot not found: {offline}", file=sys.stderr)
            sys.exit(2)
        payload = hypixel.fetch_bazaar(offline_path=offline)
        market = Market.from_api(payload)
        print(f"⚠ OFFLINE MODE — snapshot {os.path.basename(offline)}; prices "
              f"are NOT live. Drop --offline for real trading.", file=sys.stderr)
    elif payload is not None:
        # Already fetched (e.g. by the parallel prefetch): reuse it.
        market = Market.from_api(payload)
        age = market.age_seconds()
        age_txt = f"{age:.0f}s ago" if age is not None else "unknown"
        note = "  ⚠ STALE" if market.is_stale() else ""
        print(f"· live Bazaar — updated {age_txt}, {len(market)} products{note}",
              file=sys.stderr)
    else:
        # Live is mandatory for real trading. Fail loudly rather than trade on
        # stale data.
        try:
            with fx.spinner("Fetching the live Bazaar"):
                payload = hypixel.fetch_bazaar()
        except hypixel.HypixelError as exc:
            print(f"! live Bazaar fetch failed: {exc}", file=sys.stderr)
            print("  check your connection, or pass --offline to demo on the "
                  "bundled snapshot (not for real trades).", file=sys.stderr)
            sys.exit(2)
        market = Market.from_api(payload)
        age = market.age_seconds()
        age_txt = f"{age:.0f}s ago" if age is not None else "unknown"
        note = "  ⚠ STALE" if market.is_stale() else ""
        print(f"· live Bazaar — updated {age_txt}, {len(market)} products{note}",
              file=sys.stderr)

    history = None
    if not args.no_history:
        if not offline:
            record_snapshot(market)  # only log real, live data
        history = PriceHistory.load()
    return market, history


def _resolve_account_name(args, config) -> str:
    """Pick the account: the one named, or the first configured. Guides to
    `setup` when there are none / the name is wrong."""
    names = accountsmod.account_names(config)
    if not names:
        print(ui.c("\n  No accounts configured yet.", "yellow", "bold"))
        print("  Run  " + ui.c("nulladdons setup", "cyan", "bold") +
              "  to get started (takes ~2 minutes).\n")
        sys.exit(3)
    requested = getattr(args, "account", None)
    if requested is None:
        return names[0]
    if requested not in names:
        print(f"! unknown account '{requested}'. Configured: {', '.join(names)}",
              file=sys.stderr)
        print("  Add it with  nulladdons setup", file=sys.stderr)
        sys.exit(2)
    return requested


def _mayor_context(args, config=None, election=None):
    """The active (or simulated) SkyBlock mayor, or None.

    ``--mayor`` always wins (explicit simulation). Otherwise honours the ``mayor``
    feature toggle and skips the fetch offline. ``election`` may be pre-fetched by
    the parallel prefetch so we don't hit the network twice."""
    if getattr(args, "mayor", None):
        return mayor.simulate(args.mayor)
    if getattr(args, "offline", None) or not features.enabled("mayor", config):
        return None
    try:
        if election is None:
            with fx.spinner("Checking the mayor election"):
                election = hypixel.fetch_resource("election")
        return mayor.build_context(election)
    except Exception:
        return None


def _build_account(args):
    config = accountsmod.load_config()
    name = _resolve_account_name(args, config)
    risk = "conservative" if args.guaranteed else args.risk
    if risk:  # allow fun aliases like --risk yolo / --risk scared
        risk, quip = flair.resolve_risk_alias(risk)
        if quip:
            print(ui.c("· " + quip, "grey"), file=sys.stderr)
    ctx = accountsmod.build_context(
        name, config, live=args.live, api_key=args.api_key,
        budget_override=args.budget, risk_override=risk)
    # CLI overrides on top of the risk profile.
    if args.hold_time is not None:
        ctx.params.max_fill_minutes = args.hold_time
    if args.min_margin is not None:
        ctx.params.min_margin = args.min_margin / 100.0
    if args.guaranteed:
        ctx.params.min_confidence = max(ctx.params.min_confidence, 0.6)
        ctx.params.min_margin = max(ctx.params.min_margin, 0.03)
        ctx.params.require_instant_profit = True
    # Fold the live game macro-economy (the Mayor) into the tax.
    ctx.mayor = _mayor_context(args, config, election=getattr(args, "_election", None))
    if ctx.mayor is not None:
        ctx.params.tax *= ctx.mayor.tax_multiplier
        telemetry.annotate(mayor=ctx.mayor.name, tax_free=bool(ctx.mayor.tax_free))
    telemetry.annotate(risk=ctx.risk)
    return ctx, config


def _hero_number(value: float, phrase: str, tail: str = "") -> None:
    """A sparkly, animated 'hero' number printed above a plan/dashboard.

    ``phrase`` is the text the number lands after (e.g. 'this session could net
    ~'). This is a pure bonus for interactive terminals -- the very same number
    appears in the static block below -- so when effects are off (piped,
    ``--serious``, ``--no-anim``) we skip it entirely and leave the output
    byte-for-byte as it was.
    """
    if value <= 0 or not fx.enabled():
        return
    s = fx.sparkle(seed=int(value))
    left = f"{s} " if s else ""
    right = f" {s}" if s else ""
    fx.count_up(value, fmt=commands.coins, color="green",
                label=f"  {left}{phrase}", suffix=f"{tail}{right}")


def _cmd_plan(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    recipes = craft.load_recipes(args.recipes)
    portfolio = commands.build_portfolio(ctx, market, recipes, history)
    if portfolio:
        total = sum(p.total_profit for p in portfolio)
        telemetry.annotate(results=len(portfolio), positions=len(portfolio),
                           projected_profit=total, capital=ctx.budget,
                           top_margin=max((p.margin for p in portfolio), default=None))
        _hero_number(total, "this session could net ~")
    print(commands.render_portfolio(ctx, portfolio))
    if args.webhook and portfolio:
        ok = notify.post_webhook(
            args.webhook, embeds=[notify.plan_summary_embed(ctx, portfolio)])
        print(f"· plan {'posted to' if ok else 'FAILED to post to'} Discord",
              file=sys.stderr)


def _cmd_flips(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    plans = flip.find_flips(market, ctx.params, ctx.budget, history, limit=args.top,
                            blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    telemetry.annotate(
        results=len(plans), capital=ctx.budget,
        top_margin=max((p.margin for p in plans), default=None),
        top_coins_per_hour=max((p.coins_per_hour for p in plans), default=None))
    print(f"Top {len(plans)} order flips — {ctx.summary()}")
    if ctx.mayor is not None:
        print(commands.mayor_banner(ctx.mayor))
    print()
    if not plans:
        print(flair.empty_flips())
        return
    for i, plan in enumerate(plans, 1):
        print(commands.render_flip(plan, i))
        print()


def _cmd_crafts(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    recipes = craft.load_recipes(args.recipes)
    plans = craft.find_crafts(market, recipes, ctx.params, ctx.budget, history,
                              ctx.allowed_outputs, limit=args.top,
                              blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    telemetry.annotate(
        results=len(plans), capital=ctx.budget,
        top_margin=max((p.margin for p in plans), default=None),
        top_coins_per_hour=max((p.coins_per_hour for p in plans), default=None))
    print(f"Top {len(plans)} craft flips — {ctx.summary()}")
    if ctx.mayor is not None:
        print(commands.mayor_banner(ctx.mayor))
    print()
    if not plans:
        print(flair.empty_crafts())
        return
    for i, plan in enumerate(plans, 1):
        print(commands.render_craft(plan, i))
        print()


def _cmd_item(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    product = market.get(args.product_id)
    if product is None:
        print(f"'{args.product_id}' not found or has no two-sided market.")
        alt = [pid for pid in market.products
               if args.product_id.upper() in pid.upper()][:10]
        if alt:
            print("Did you mean:", ", ".join(alt))
        return
    telemetry.annotate(item=args.product_id)
    econ = mechanics.flip_unit_economics(product.best_bid, product.best_ask,
                                         ctx.params.tax)
    print(f"{commands.nice_name(product.product_id)}  ({product.product_id})")
    print("─" * 56)
    print(f"  best bid (sell to)  : {commands.price(product.best_bid)}  "
          f"[{product.best_bid_amount:,} units, {product.bid_orders} orders]")
    print(f"  best ask (buy from) : {commands.price(product.best_ask)}  "
          f"[{product.best_ask_amount:,} units, {product.ask_orders} orders]")
    print(f"  spread              : {commands.price(product.spread)} "
          f"({product.spread_pct:.2%} of mid)")
    print(f"  weekly demand/supply: {commands.coins(product.demand_per_week)} / "
          f"{commands.coins(product.supply_per_week)}  (liquidity "
          f"{commands.coins(product.liquidity)})")
    conf, parts = economy.confidence(product, econ["margin"], history)
    print("─" * 56)
    print(f"  FLIP  buy @ {commands.price(econ['buy_order_price'])}  →  "
          f"sell @ {commands.price(econ['sell_offer_price'])}")
    print(f"        unit profit {commands.price(econ['unit_profit'])} "
          f"(+{econ['margin']:.1%} after {ctx.params.tax:.2%} tax)")
    print(f"        confidence {conf:.0%}  "
          f"({', '.join(f'{k} {v:.2f}' for k, v in parts.items())})")
    if history and history.samples(product.product_id):
        vol = history.volatility(product.product_id)
        z = history.zscore(product.product_id, product.mid)
        print(f"        history: {history.samples(product.product_id)} samples"
              + (f", volatility {vol:.2%}" if vol is not None else "")
              + (f", z-score {z:+.2f}" if z is not None else ""))


def _cmd_mp(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    accs = accessoriesmod.load_accessories(args.accessories)
    recipes = craft.load_recipes(args.recipes)
    engine = accessoriesmod.AccessoryEngine(market, accs, recipes)

    # Owned families = configured families + those inferred from the live bag.
    id_to_family = {a.id: a.family for a in accs}
    owned_families = set(ctx.owned_families) | {
        id_to_family[i] for i in ctx.owned_item_ids if i in id_to_family}

    goal = args.mp_goal if args.mp_goal is not None else ctx.mp_goal
    mp_budget = args.budget  # optional cap on MP spend
    plan = accessoriesmod.plan_magic_power(
        engine, accs, ctx.owned_item_ids, owned_families,
        mp_goal=goal, budget=mp_budget, top=args.top)
    # Reflect the goal in the header even if it came from the flag.
    ctx.mp_goal = goal or ctx.mp_goal
    picks = plan.get("picks") or []
    if picks:
        telemetry.annotate(mp_gain=getattr(picks[0], "mp_gain", None),
                           mp_cost=getattr(picks[0], "cost", None))
    print(commands.render_mp_plan(ctx, plan))


def _run_alert_cycle(args, ctx, webhook, seen: set) -> None:
    market, history = _load_market(args)
    recipes = craft.load_recipes(args.recipes)
    alert = notify.merged_alert(ctx)
    flips = flip.find_flips(market, ctx.params, ctx.budget, history, limit=25,
                            blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    crafts = craft.find_crafts(market, recipes, ctx.params, ctx.budget, history,
                               ctx.allowed_outputs, limit=25,
                               blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    new_f = [p for p in notify.crucial(flips, alert)
             if notify.opportunity_key(p) not in seen]
    new_c = [p for p in notify.crucial(crafts, alert)
             if notify.opportunity_key(p) not in seen]
    if not new_f and not new_c:
        print("· no new crucial opportunities", file=sys.stderr)
        return
    for p in new_f + new_c:
        seen.add(notify.opportunity_key(p))
    embed = notify.opportunities_embed(ctx, new_f, new_c, market.age_seconds())
    ok = notify.post_webhook(webhook, embeds=[embed])
    count = len(new_f) + len(new_c)
    print(f"· {'posted' if ok else 'FAILED to post'} {count} new opportunit"
          f"{'y' if count == 1 else 'ies'} to Discord", file=sys.stderr)


def _cmd_alert(args):
    ctx, _ = _build_account(args)
    webhook = args.webhook or ctx.webhook_url
    if not webhook:
        print("! no Discord webhook configured. Pass --webhook <url> or set "
              "'discord_webhook_url' (or per-account 'webhook_url') in "
              "config/accounts.json.", file=sys.stderr)
        sys.exit(2)
    seen: set = set()
    _run_alert_cycle(args, ctx, webhook, seen)
    if args.watch:
        print(f"· watching every {args.watch:g} min (Ctrl-C to stop)",
              file=sys.stderr)
        try:
            while True:
                time.sleep(max(1.0, args.watch) * 60)
                _run_alert_cycle(args, ctx, webhook, seen)
        except KeyboardInterrupt:
            print("\n· stopped watching", file=sys.stderr)


def _resolve_uuid(ctx):
    return ctx.uuid or hypixel.resolve_uuid(ctx.username)


def _load_progress(ctx, api_key, save: bool):
    """Fetch profile -> (stats, prog_diff, uuid). All None without a key/profile."""
    if not api_key:
        return None, None, None
    uuid = _resolve_uuid(ctx)
    payload = hypixel.fetch_profiles(uuid, api_key) if uuid else None
    if not payload:
        return None, None, uuid
    skills_res = hypixel.fetch_resource("skills")
    profile, member = progress.pick_member(payload, uuid)
    stats = progress.extract_stats(profile, member, skills_res)
    hist = progress.load_history(ctx.name)
    prog_diff = progress.diff(progress.previous_snapshot(hist, stats), stats)
    if save:
        progress.save_snapshot(ctx.name, stats)
    return stats, prog_diff, uuid


def _ah_context(ctx, api_key, uuid, top_sales: int = 3, ended=None):
    """Assemble Auction House highlights: recent sales + your listings."""
    if ended is None:
        ended = hypixel.fetch_auctions_ended()
    sales = auction.sales_from_ended(ended)
    auction.record_sales(sales)
    recent = [(s["id"], s["price"])
              for s in sorted(sales, key=lambda x: x["price"], reverse=True)[:top_sales]]
    listings = None
    if api_key and uuid:
        listings = auction.player_listing_summary(
            hypixel.fetch_player_auctions(uuid, api_key))
    return {"recent_sales": recent, "listings": listings}


def _market_movers(market, history, min_liquidity: int = 500_000,
                   min_move: float = 0.05, top: int = 5):
    """Biggest recent price moves among liquid products (pumps/dumps radar)."""
    if history is None:
        return []
    ranked = []
    for pid, pct in history.movers().items():
        product = market.get(pid)
        if product and product.liquidity >= min_liquidity and abs(pct) >= min_move:
            ranked.append((pid, pct))
    ranked.sort(key=lambda x: abs(x[1]), reverse=True)
    return ranked[:top]


def _cmd_ask(args):
    question = " ".join(args.question).strip()
    market, history = _load_market(args)
    ctx, config = _build_account(args)
    api_key = args.api_key or config.get("hypixel_api_key")
    gem_key = None if args.no_llm else (
        args.gemini_key or config.get("gemini_api_key"))
    gem_model = args.gemini_model or config.get("gemini_model") or llm.DEFAULT_MODEL
    recipes = craft.load_recipes(args.recipes)

    # Retrieve just the facts relevant to the question.
    items = [(pid, market.get(pid)) for pid in askmod.find_items(question, market)
             if market.get(pid)]
    flips = flip.find_flips(market, ctx.params, ctx.budget, history, limit=5,
                            blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    crafts = craft.find_crafts(market, recipes, ctx.params, ctx.budget, history,
                               ctx.allowed_outputs, limit=4,
                               blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    portfolio = commands.build_portfolio(ctx, market, recipes, history)
    proj = projection.project_bazaar_income(portfolio, ctx.active_hours)
    mp_plan = _mp_plan_for(ctx, market, args.accessories, recipes)

    stats = uuid = None
    if api_key:
        stats, _, uuid = _load_progress(ctx, api_key, save=False)
    ah = _ah_context(ctx, api_key, uuid, top_sales=5)

    ac = askmod.AskContext(
        account=ctx, market=market, tax=ctx.params.tax, mayor=ctx.mayor,
        items=items, flips=flips, crafts=crafts, mp_plan=mp_plan, projection=proj,
        ah_recent=ah.get("recent_sales", []),
        ah_index=auction.SalePriceIndex.load(), stats=stats,
        data_age=market.age_seconds())

    if args.show_facts:
        print(askmod.build_facts(ac))
        print("─" * 60)
    allow_eggs = features.enabled("easter_eggs", config)
    text, via_llm = askmod.answer(question, ac, gem_key, gem_model,
                                  allow_eggs=allow_eggs)
    answered = text != askmod.DONT_KNOW and not text.startswith(askmod.DONT_KNOW)
    telemetry.annotate(
        ask_answered=answered,
        easter_egg=bool(allow_eggs and flair.easter_egg(question)),
        ask_intent=("meme" if allow_eggs and flair.easter_egg(question)
                    else "item" if items else "market"))
    tag = "Gemini, grounded in live data" if via_llm else "local answer from live data"
    print(text)
    print(ui.c(f"\n[{tag}]", "grey"))
    if not gem_key and not args.no_llm:
        print(ui.c("tip: add a Gemini key (`nulladdons setup`) for open-ended "
                   "questions.", "grey"), file=sys.stderr)


def _prefetch_public(args, config):
    """Fetch the independent public endpoints for `status` concurrently.

    Bazaar, election and ended-auctions don't depend on each other, so running
    them in parallel turns three sequential round-trips into ~one. Returns
    ``{bazaar, election, ended}`` (values may be None on failure/offline; callers
    fall back to their own sequential fetch)."""
    if getattr(args, "offline", None):
        return {}
    jobs = {"bazaar": hypixel.fetch_bazaar,
            "ended": hypixel.fetch_auctions_ended}
    if features.enabled("mayor", config) and not getattr(args, "mayor", None):
        jobs["election"] = lambda: hypixel.fetch_resource("election")
    with fx.spinner(f"Fetching {len(jobs)} live feeds in parallel"):
        results = tasks.gather(jobs)
    return tasks.values(results)


def _cmd_status(args):
    config = accountsmod.load_config()
    pre = _prefetch_public(args, config)
    if pre.get("election") is not None:
        args._election = pre["election"]          # reused by _build_account
    market, history = _load_market(args, payload=pre.get("bazaar"))
    ctx, config = _build_account(args)
    api_key = args.api_key or config.get("hypixel_api_key")
    recipes = craft.load_recipes(args.recipes)
    portfolio = commands.build_portfolio(ctx, market, recipes, history)
    mp_plan = _mp_plan_for(ctx, market, args.accessories, recipes)
    _, prog_diff, uuid = _load_progress(ctx, api_key, save=False)
    ah = _ah_context(ctx, api_key, uuid, ended=pre.get("ended"))
    movers = _market_movers(market, history) if features.enabled("market_movers", config) else []
    if portfolio:
        proj = projection.project_bazaar_income(portfolio, ctx.active_hours)
        telemetry.annotate(positions=proj.positions, capital=ctx.budget,
                           projected_profit=proj.per_day)
        _hero_number(proj.per_day, "projected income ~", tail="/day")
    out = commands.render_status(ctx, portfolio, mp_plan, ah, prog_diff, movers)
    print(out)
    if args.webhook:
        embed = {"title": f"📊 Ecosystem Status — {ctx.name}",
                 "description": "```\n" + out[:3900] + "\n```", "color": 0x1ABC9C}
        ok = notify.post_webhook(args.webhook, embeds=[embed])
        print(f"· status {'posted to' if ok else 'FAILED to post to'} Discord",
              file=sys.stderr)


def _mp_plan_for(ctx, market, accessories_path, recipes):
    accs = accessoriesmod.load_accessories(accessories_path)
    engine = accessoriesmod.AccessoryEngine(market, accs, recipes)
    id_to_family = {a.id: a.family for a in accs}
    owned_fams = set(ctx.owned_families) | {
        id_to_family[i] for i in ctx.owned_item_ids if i in id_to_family}
    return accessoriesmod.plan_magic_power(
        engine, accs, ctx.owned_item_ids, owned_fams, mp_goal=ctx.mp_goal, top=6)


def _cmd_ah(args):
    ctx, config = _build_account(args)
    ended = hypixel.fetch_auctions_ended()
    sales = auction.sales_from_ended(ended)
    added = auction.record_sales(sales)
    index = auction.SalePriceIndex.load()
    print(f"Auction House — {ctx.name}   "
          f"(sale index: {len(index._by_id)} items, +{added} this run)\n")

    top = sorted(sales, key=lambda s: s["price"], reverse=True)[:10]
    print("Recent notable sales:")
    for s in top:
        kind = "BIN" if s["bin"] else "bid"
        print(f"  {commands.nice_name(s['id']):32s} {commands.coins(s['price']):>10}"
              f"  [{kind}]")

    api_key = args.api_key or config.get("hypixel_api_key")
    if api_key:
        uuid = _resolve_uuid(ctx)
        if uuid:
            summary = auction.player_listing_summary(
                hypixel.fetch_player_auctions(uuid, api_key))
            print(f"\nYour listings: {summary.active} active "
                  f"({commands.coins(summary.active_value)}), "
                  f"{summary.sold_claimable} sold & claimable "
                  f"({commands.coins(summary.sold_value)})")
            for ln in summary.lines[:8]:
                print(f"  · {ln}")

    if args.scan:
        print(f"\nScanning {args.scan} page(s) of the live AH for BIN flips…")
        flips = auction.find_bin_flips(hypixel.fetch_auctions_page, index,
                                       max_pages=args.scan)
        if not flips:
            print("  none clearing the discount/profit floor "
                  "(need several recent samples per item).")
        for f in flips:
            print(f"  {commands.nice_name(f.name):28s} buy {commands.coins(f.buy_price)}"
                  f" → median {commands.coins(f.market_median)}  "
                  f"= {commands.coins(f.profit)} (-{f.discount:.0%}, "
                  f"{f.samples} samples) ⚠ verify item stats")


def _cmd_brief(args):
    market, history = _load_market(args)
    ctx, config = _build_account(args)
    api_key = args.api_key or config.get("hypixel_api_key")
    gem_key = None if args.no_llm else (
        args.gemini_key or config.get("gemini_api_key"))
    gem_model = args.gemini_model or config.get("gemini_model") or llm.DEFAULT_MODEL
    recipes = craft.load_recipes(args.recipes)

    # 1) Progress snapshot + day-over-day diff (needs a Hypixel key).
    stats, prog_diff, uuid = _load_progress(ctx, api_key, save=True)
    if not api_key:
        print("· no Hypixel key — market-only brief (set hypixel_api_key for "
              "progress tracking)", file=sys.stderr)

    # 2) Market + MP opportunities.
    flips = flip.find_flips(market, ctx.params, ctx.budget, history, limit=6,
                            blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    crafts = craft.find_crafts(market, recipes, ctx.params, ctx.budget, history,
                               ctx.allowed_outputs, limit=4,
                               blacklist=ctx.blacklist, whitelist=ctx.whitelist)
    mp_plan = _mp_plan_for(ctx, market, args.accessories, recipes)

    # 3) Auction House highlights.
    ah = _ah_context(ctx, api_key, uuid, top_sales=6)

    ctxd = briefmod.build_context(
        ctx, data_age=market.age_seconds(), stats=stats, prog_diff=prog_diff,
        flips=flips, crafts=crafts, mp_plan=mp_plan, ah=ah)
    summary, via_llm = briefmod.summarize(ctxd, gem_key, gem_model)
    if gem_key and not via_llm:
        print("· Gemini call failed — showing local brief", file=sys.stderr)
    print(briefmod.render_brief(ctxd, summary, via_llm))

    webhook = args.webhook or ctx.webhook_url
    if webhook:
        embed = {"title": f"📅 SkyBlock Daily Brief — {ctx.name}",
                 "description": summary[:4000], "color": 0x9B59B6,
                 "footer": {"text": "Null's Addons"}}
        ok = notify.post_webhook(webhook, embeds=[embed])
        print(f"· brief {'posted to' if ok else 'FAILED to post to'} Discord",
              file=sys.stderr)


def _cmd_lore(args):
    print(flair.lore())


def _telemetry_set(config: dict, value: bool) -> int:
    config.setdefault("features", {})["telemetry"] = value
    path = accountsmod.save_config(config)
    if value:
        print(ui.c("✓ Telemetry ON", "green", "bold")
              + " — local stats will start recording. It never leaves your machine")
        print(f"  unless you set telemetry.sink_url.  Config: {path}\n")
        print(telemetry.manifest_text(config))
    else:
        print(ui.c("✓ Telemetry OFF", "green", "bold")
              + " — nothing will be recorded. Your existing log is untouched;")
        print("  wipe it any time with  nulladdons telemetry clear")
    return 0


def _cmd_telemetry(args):
    config = accountsmod.load_config()
    action = args.action

    if action == "on":
        return _telemetry_set(config, True)
    if action == "off":
        return _telemetry_set(config, False)
    if action == "manifest":
        print(telemetry.manifest_text(config))
        return 0
    if action == "export":
        dest = args.path or os.path.join(os.getcwd(), "nulladdons-telemetry.jsonl")
        try:
            n = telemetry.export_to(dest)
        except OSError as exc:
            print(f"! export failed: {exc}", file=sys.stderr)
            return 2
        print(f"· exported {n} event(s) to {dest}" if n
              else "· no telemetry to export yet.")
        return 0
    if action == "clear":
        if not args.yes and not ui.ask_yes_no(
                "Permanently delete your local telemetry log?", False):
            print("· kept your data.")
            return 0
        print("· telemetry log wiped." if telemetry.clear()
              else "· nothing to wipe (no log yet).")
        return 0

    # status / stats / wrapped / achievements all read the local log.
    on = telemetry.is_enabled(config)
    events = telemetry.load_events()
    stats = telemetry.compute_stats(events)
    if action == "stats":
        print(telemetry.stats_text(stats))
    elif action == "wrapped":
        print(telemetry.wrapped_text(stats, features.active_flavor(config)))
    elif action == "achievements":
        print(telemetry.achievements_text(stats))
    else:  # status
        print(ui.c(f"Telemetry is {'ON' if on else 'OFF'}.",
                   "green" if on else "yellow", "bold"))
        if not on:
            print("  Turn it on:   " + ui.c("nulladdons telemetry on", "cyan"))
            print("  See exactly what it collects:  "
                  + ui.c("nulladdons telemetry manifest", "cyan"))
        else:
            print(f"  Stored at {telemetry.EVENTS_PATH}\n")
            print(telemetry.stats_text(stats))
    return 0


def _cmd_setup(args):
    onboarding.run_setup(config_path=args.config)


def _cmd_doctor(args):
    cfg = accountsmod.load_config(args.config) if args.config else None
    healthy = onboarding.doctor(cfg, check_gemini=not args.quick)
    return 0 if healthy else 1


def _cmd_accounts(args):
    config = accountsmod.load_config()
    if not accountsmod.account_names(config):
        print("No accounts configured yet. Run  " +
              ui.c("nulladdons setup", "cyan", "bold") + "  to add one.")
        return
    print(f"Configured accounts  (config: {accountsmod.config_path()}):\n")
    for name in config.get("accounts", {}):
        try:
            ctx = accountsmod.build_context(
                name, config, live=args.live, api_key=args.api_key)
            line = f"  • {ctx.summary()}"
            if ctx.uuid:
                line += f"\n      uuid: {ctx.uuid}"
            if ctx.notes:
                line += f"\n      note: {ctx.notes}"
            print(line)
        except (KeyError, ValueError) as exc:
            print(f"  • {name}: {exc}")


_DISPATCH = {
    "setup": _cmd_setup, "doctor": _cmd_doctor,
    "plan": _cmd_plan, "flips": _cmd_flips, "crafts": _cmd_crafts,
    "item": _cmd_item, "mp": _cmd_mp, "alert": _cmd_alert,
    "ah": _cmd_ah, "brief": _cmd_brief, "status": _cmd_status,
    "ask": _cmd_ask, "accounts": _cmd_accounts, "lore": _cmd_lore,
    "telemetry": _cmd_telemetry,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    # Default to `plan` when the first token isn't a subcommand or help flag.
    if argv and argv[0] not in _DISPATCH and argv[0] not in ("-h", "--help"):
        argv = ["plan", *argv]
    elif not argv:
        argv = ["plan"]
    args = parser.parse_args(argv)
    if getattr(args, "serious", False):
        flair.set_serious(True)
    if getattr(args, "no_anim", False):
        os.environ["NULLADDONS_NO_ANIM"] = "1"   # fx reads this to stay silent
    if args.command is None:
        parser.print_help()
        return 0

    # Resolve global config once for flavor + telemetry (handlers reload as needed).
    config = accountsmod.load_config()
    flavor = features.active_flavor(config)
    if getattr(args, "flavor", None):
        flavor = features.normalize_flavor(args.flavor)
    features.set_flavor(flavor)
    if not features.enabled("animations", config):
        os.environ["NULLADDONS_NO_ANIM"] = "1"   # feature toggle mirrors --no-anim

    telemetry.take_annotations()   # start each run with a clean slate
    started = time.monotonic()
    try:
        result = _DISPATCH[args.command](args)
    except KeyboardInterrupt:
        print("\n· cancelled", file=sys.stderr)
        return 130
    except (KeyError, ValueError) as exc:
        print(f"! {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"! missing file: {exc}", file=sys.stderr)
        return 2
    finally:
        _record_run(args, config, flavor, started)
    return result if isinstance(result, int) else 0


def _record_run(args, config, flavor, started) -> None:
    """Append one telemetry event for this run (no-op unless you opted in)."""
    # Don't record the telemetry command itself -- checking your stats shouldn't
    # become a stat.
    if args.command == "telemetry" or not telemetry.is_enabled(config):
        telemetry.take_annotations()
        return
    event = telemetry.build_event(
        args.command,
        flavor=flavor,
        risk=getattr(args, "risk", None),
        duration_ms=(time.monotonic() - started) * 1000.0,
        offline=bool(getattr(args, "offline", None)),
        serious=flair.serious(),
        extra=telemetry.take_annotations(),
    )
    telemetry.record(config, event)


if __name__ == "__main__":
    raise SystemExit(main())
