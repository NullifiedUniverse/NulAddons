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

from . import accounts as accountsmod
from . import commands, craft, economy, flip, hypixel, mechanics
from .bazaar import Market
from .history import PriceHistory, record_snapshot

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_RECIPES = os.path.join(_ROOT, "data", "recipes.json")
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
    return parser


def _load_market(args) -> tuple[Market, PriceHistory | None]:
    offline = args.offline
    if offline and not os.path.exists(offline):
        print(f"! offline snapshot not found: {offline}", file=sys.stderr)
        sys.exit(2)
    try:
        payload = hypixel.fetch_bazaar(offline_path=offline)
    except hypixel.HypixelError as exc:
        print(f"! could not fetch bazaar: {exc}", file=sys.stderr)
        if os.path.exists(DEFAULT_SAMPLE):
            print(f"  falling back to bundled snapshot ({DEFAULT_SAMPLE})",
                  file=sys.stderr)
            payload = hypixel.fetch_bazaar(offline_path=DEFAULT_SAMPLE)
        else:
            sys.exit(2)
    market = Market.from_api(payload)

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


def _cmd_flips(args):
    market, history = _load_market(args)
    ctx, _ = _build_account(args)
    plans = flip.find_flips(market, ctx.params, ctx.budget, history, limit=args.top)
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
                              ctx.allowed_outputs, limit=args.top)
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
    "item": _cmd_item, "accounts": _cmd_accounts,
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
