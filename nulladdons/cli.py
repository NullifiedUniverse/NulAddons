"""
Null's Addons -- command-line interface.

Subcommands
-----------
* ``plan``     -- the headline view: a diversified, budgeted set of orders to
                  place right now (default if you pass no subcommand).
* ``flips``    -- ranked list of order flips (buy order -> wait -> sell offer).
* ``crafts``   -- ranked list of craft flips (buy mats -> craft -> sell).
* ``item ID``  -- deep dive on a single product.
* ``accounts`` -- show configured accounts (with live capital if a key is set).

Global options let you override the account's budget, risk profile, patience and
margin floor, run fully offline against a saved snapshot, or flip on
``--guaranteed`` mode (strict, near-risk-free filters).
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from . import accessories as accessoriesmod
from . import accounts as accountsmod
from . import commands, craft, economy, flip, hypixel, mechanics, notify
from .bazaar import Market
from .history import PriceHistory, record_snapshot

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPES = os.path.join(_ROOT, "data", "recipes.json")
DEFAULT_ACCESSORIES = os.path.join(_ROOT, "data", "accessories.json")
DEFAULT_SAMPLE = os.path.join(_ROOT, "data", "sample_bazaar.json")


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("-a", "--account", default="NullifiedGalaxy",
                   help="configured account name (default: NullifiedGalaxy)")
    p.add_argument("-b", "--budget", type=float, default=None,
                   help="override capital, in coins")
    p.add_argument("-r", "--risk", choices=list(accountsmod.RISK_PROFILES),
                   default=None, help="override risk profile")
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
    p.add_argument("--offline", nargs="?", const=DEFAULT_SAMPLE, default=None,
                   help="use a saved bazaar snapshot instead of the network")
    p.add_argument("--recipes", default=DEFAULT_RECIPES,
                   help="path to the craft recipe database")
    p.add_argument("--no-history", action="store_true",
                   help="do not read/write the local price-history log")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nulladdons",
        description="Null's Addons — Hypixel SkyBlock Bazaar flipping assistant.")
    sub = parser.add_subparsers(dest="command")

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
    return parser


def _load_market(args) -> tuple[Market, PriceHistory | None]:
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
    else:
        # Live is mandatory for real trading. Fail loudly rather than trade on
        # stale data.
        try:
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


def _build_account(args):
    config = accountsmod.load_config()
    risk = "conservative" if args.guaranteed else args.risk
    ctx = accountsmod.build_context(
        args.account, config, live=args.live, api_key=args.api_key,
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
    return ctx, config


def _cmd_plan(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    recipes = craft.load_recipes(args.recipes)
    portfolio = commands.build_portfolio(ctx, market, recipes, history)
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
    print(f"Top {len(plans)} order flips — {ctx.summary()}\n")
    if not plans:
        print("No flips clear this risk floor. Try --risk aggressive.")
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
    print(f"Top {len(plans)} craft flips — {ctx.summary()}\n")
    if not plans:
        print("No craft flips clear this risk floor right now.")
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


def _cmd_accounts(args):
    config = accountsmod.load_config()
    print("Configured accounts:\n")
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
    "plan": _cmd_plan, "flips": _cmd_flips, "crafts": _cmd_crafts,
    "item": _cmd_item, "mp": _cmd_mp, "alert": _cmd_alert,
    "accounts": _cmd_accounts,
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
    if args.command is None:
        parser.print_help()
        return 0
    try:
        _DISPATCH[args.command](args)
    except (KeyError, ValueError) as exc:
        print(f"! {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"! missing file: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
