"""
Null's Addons -- first-run setup wizard & health check.

``nulladdons setup`` walks anyone through configuring the tool from scratch:
optional API keys (Hypixel, Gemini) and a Discord webhook, then one or more
accounts with live UUID resolution, budget, risk profile and goals.  It validates
what it can as it goes (resolves the username, tests the webhook, pings Gemini)
and writes a private (0600) config to ``~/.nulladdons/accounts.json``.

``nulladdons doctor`` is the non-interactive counterpart: it reports what's
configured, what's missing, and what's broken, with a fix hint for each.

The config-building helpers are pure and unit-tested; only :func:`run_setup` and
:func:`doctor` touch the terminal or the network.
"""

from __future__ import annotations

import os

from . import accounts as accountsmod
from . import features, hypixel, llm, notify, telemetry, ui
from .accounts import RISK_PROFILES

HYPIXEL_KEY_URL = "https://developer.hypixel.net"
GEMINI_KEY_URL = "https://aistudio.google.com/apikey"


# --- pure config builders (unit-tested) -------------------------------------

def apply_account(cfg: dict, name: str, *, username: str, risk: str = "balanced",
                  budget: int = 0, cookie_buffed: bool = False, mp_goal: int = 0,
                  coin_goal: int = 0, active_hours: float = 6.0,
                  webhook_url: str | None = None) -> dict:
    """Add/replace one account in ``cfg`` (mutates and returns it)."""
    cfg.setdefault("accounts", {})[name] = {
        "username": username or name,
        "budget": int(budget),
        "risk": risk if risk in RISK_PROFILES else "balanced",
        "cookie_buffed": bool(cookie_buffed),
        "mp_goal": int(mp_goal),
        "coin_goal": int(coin_goal),
        "active_hours": float(active_hours),
        "owned_families": [],
        "blacklist": [],
        "webhook_url": webhook_url or None,
        "alert": {},
    }
    return cfg


def apply_globals(cfg: dict, *, hypixel_api_key=None, gemini_api_key=None,
                  gemini_model=None, discord_webhook_url=None) -> dict:
    cfg["hypixel_api_key"] = hypixel_api_key or None
    cfg["gemini_api_key"] = gemini_api_key or None
    if gemini_model:
        cfg["gemini_model"] = gemini_model
    cfg["discord_webhook_url"] = discord_webhook_url or None
    return cfg


def apply_preferences(cfg: dict, *, flavor: str | None = None,
                      feature_overrides: dict | None = None,
                      telemetry_enabled: bool | None = None,
                      telemetry_sink: str | None = None) -> dict:
    """Set the flavor, feature toggles and telemetry choice (mutates & returns)."""
    if flavor:
        cfg["flavor"] = features.normalize_flavor(flavor)
    feats = cfg.setdefault("features", features.default_features())
    for name, value in (feature_overrides or {}).items():
        if name in features.FEATURES:
            feats[name] = bool(value)
    if telemetry_enabled is not None:
        feats["telemetry"] = bool(telemetry_enabled)
    tel = cfg.setdefault("telemetry", {})
    if telemetry_sink is not None:
        tel["sink_url"] = telemetry_sink or None
    return cfg


# --- interactive wizard -----------------------------------------------------

def run_setup(config_path: str | None = None) -> tuple[dict, str]:
    ui.banner("Null's Addons — Setup",
              "Press Enter to accept [defaults]. Everything here is optional.")
    # Update an existing personal config; otherwise start fresh (don't inherit
    # the repo's example accounts).
    target = config_path or accountsmod.USER_CONFIG_PATH
    cfg = accountsmod.load_config(target) if os.path.exists(target) \
        else accountsmod.default_config()
    if not isinstance(cfg, dict) or "accounts" not in cfg:
        cfg = accountsmod.default_config()

    # --- integrations -------------------------------------------------------
    ui.section("API keys & integrations (all optional)")
    ui.info("A free Hypixel key unlocks live capital, progress tracking and your")
    ui.info(f"AH listings.  Get one at {HYPIXEL_KEY_URL}")
    hkey = ui.ask_secret("Hypixel API key", cfg.get("hypixel_api_key")) or None

    ui.info(f"A Gemini key powers the AI daily brief.  Get one at {GEMINI_KEY_URL}")
    gkey = ui.ask_secret("Gemini API key", cfg.get("gemini_api_key")) or None
    gmodel = cfg.get("gemini_model") or accountsmod.GEMINI_DEFAULT_MODEL
    if gkey:
        gmodel = ui.ask("Gemini model", gmodel)
        if ui.ask_yes_no("Validate the Gemini key now?", True):
            (ui.ok("Gemini key works.") if llm.check_gemini(gkey, gmodel)
             else ui.warn("Couldn't validate — check the key/model. Saving anyway."))

    ui.info("A Discord webhook receives crucial alerts and daily briefs.")
    wh = ui.ask("Discord webhook URL", cfg.get("discord_webhook_url") or "") or None
    if wh and ui.ask_yes_no("Send a test message to Discord?", True):
        (ui.ok("Sent — check your channel.") if notify.test_webhook(wh)
         else ui.warn("Couldn't reach the webhook. Saving anyway."))

    apply_globals(cfg, hypixel_api_key=hkey, gemini_api_key=gkey,
                  gemini_model=gmodel, discord_webhook_url=wh)

    # --- accounts -----------------------------------------------------------
    ui.section("Accounts")
    if accountsmod.account_names(cfg):
        ui.info("Existing: " + ", ".join(accountsmod.account_names(cfg)))
    add = ui.ask_yes_no("Add an account now?", True)
    while add:
        if not _setup_one_account(cfg, hkey):
            break
        add = ui.ask_yes_no("Add another account?", False)

    _setup_preferences(cfg)

    # --- save ---------------------------------------------------------------
    path = accountsmod.save_config(cfg, target)
    ui.section("All set")
    ui.ok(f"Saved config to {path}  (readable only by you)")
    names = accountsmod.account_names(cfg)
    if names:
        live = "  --live" if hkey else ""
        ui.info(f"Try:   nulladdons status -a {names[0]}{live}")
        ui.info("Then:  nulladdons plan   ·   nulladdons mp   ·   nulladdons doctor")
    else:
        ui.info("No accounts yet — re-run `nulladdons setup` to add one.")
    return cfg, path


def _setup_preferences(cfg: dict) -> None:
    """Interactive: pick a flavor, toggle features, and make the telemetry call."""
    ui.section("Personality & features")
    ui.info("Pick a flavor — same honest numbers, totally different voice:")
    for fid in features.flavor_ids():
        ui.info(f"  {fid:<12} {features.flavor_label(fid)}")
    flavor = ui.ask_choice("Flavor", features.flavor_ids(),
                           cfg.get("flavor") or features.DEFAULT_FLAVOR)

    ui.info("Toggle features (Enter keeps the current default):")
    overrides = {}
    for name in ("animations", "easter_eggs", "market_movers", "mayor"):
        overrides[name] = ui.ask_yes_no(
            f"  Enable {name} — {features.describe(name)}?",
            features.enabled(name, cfg))

    ui.section("Telemetry — opt-in, local, and honestly kind of fun")
    ui.info("It's OFF by default and this is exactly what it would collect:")
    print(telemetry.manifest_text(cfg))
    tel_on = ui.ask_yes_no("Turn on local telemetry, stats & SkyBlock Wrapped?", False)
    sink = None
    if tel_on and ui.ask_yes_no(
            "Advanced: also POST each event to a URL you control? (default no)", False):
        sink = ui.ask("Telemetry sink URL", "") or None

    apply_preferences(cfg, flavor=flavor, feature_overrides=overrides,
                      telemetry_enabled=tel_on, telemetry_sink=sink)
    ui.ok(f"Flavor set to {flavor}."
          + ("  Telemetry ON — see `nulladdons telemetry`." if tel_on
             else "  Telemetry left OFF."))


def _setup_one_account(cfg: dict, hkey: str | None) -> bool:
    name = ui.ask("Minecraft username").strip()
    if not name:
        ui.warn("No username entered — skipping.")
        return False
    uuid = hypixel.resolve_uuid(name)
    if uuid:
        ui.ok(f"Found {name}  (uuid {uuid[:8]}…)")
    else:
        ui.warn(f"Couldn't resolve '{name}' via Mojang (typo?) — saving anyway.")

    risk = ui.ask_choice("Risk profile", list(RISK_PROFILES.keys()), "balanced")

    budget = 0
    if hkey and uuid and ui.ask_yes_no("Use your live purse + bank as the budget?", True):
        payload = hypixel.fetch_profiles(uuid, hkey)
        if payload:
            live_budget, _ = accountsmod._extract_live_budget(payload, uuid)
            if live_budget:
                budget = int(live_budget)
                ui.ok(f"Live capital: {budget:,} coins")
            else:
                ui.warn("Couldn't read your balance (profiles API off?).")
        else:
            ui.warn("Hypixel key didn't work for that account.")
    if not budget:
        budget = ui.ask_int("Starting budget (e.g. 50m or 10000000)", 10_000_000)

    cookie = ui.ask_yes_no("Booster Cookie active? (lowers Bazaar tax)", False)
    coin_goal = ui.ask_int("Coin goal (0 to skip)", 0)
    mp_goal = ui.ask_int("Magical Power goal (0 to skip)", 0)
    active = ui.ask_int("Flipping hours/day (for income projections)", 6)

    apply_account(cfg, name, username=name, risk=risk, budget=budget,
                  cookie_buffed=cookie, mp_goal=mp_goal, coin_goal=coin_goal,
                  active_hours=active)
    ui.ok(f"Configured {name} ({risk}, {budget:,} coins).")
    return True


# --- doctor -----------------------------------------------------------------

def doctor(cfg: dict | None = None, check_gemini: bool = True) -> bool:
    cfg = cfg if cfg is not None else accountsmod.load_config()
    ui.banner("Null's Addons — Doctor", f"config: {accountsmod.config_path()}")
    core_ok = True

    ui.section("Connectivity")
    try:
        bz = hypixel.fetch_bazaar()
        n = len(bz.get("products") or {})
        ui.ok(f"Bazaar API reachable ({n} products)") if n else ui.err("Bazaar API returned nothing")
        core_ok = core_ok and bool(n)
    except hypixel.HypixelError as exc:
        ui.err(f"Bazaar API unreachable: {exc}")
        core_ok = False

    ui.section("Accounts")
    names = accountsmod.account_names(cfg)
    if not names:
        ui.warn("No accounts configured — run `nulladdons setup`.")
    first_uuid = None
    for name in names:
        acc = cfg["accounts"][name]
        uuid = hypixel.resolve_uuid(acc.get("username", name))
        first_uuid = first_uuid or uuid
        if uuid:
            ui.ok(f"{name} → {acc.get('username', name)} resolves "
                  f"(budget {int(acc.get('budget', 0)):,})")
        else:
            ui.warn(f"{name}: username '{acc.get('username', name)}' didn't resolve")

    ui.section("Integrations")
    hk_state, detail = hypixel.check_key(cfg.get("hypixel_api_key"), first_uuid)
    if hk_state is True:
        ui.ok(f"Hypixel key: {detail}  (live capital, progress, listings)")
    elif hk_state is None:
        ui.info(f"Hypixel key: {detail}")
    elif cfg.get("hypixel_api_key"):
        ui.err(f"Hypixel key: {detail}")
    else:
        ui.info(f"Hypixel key: not set — add for live personalisation ({HYPIXEL_KEY_URL})")

    gk = cfg.get("gemini_api_key")
    if not gk:
        ui.info(f"Gemini key: not set — add for AI daily briefs ({GEMINI_KEY_URL})")
    elif check_gemini:
        (ui.ok("Gemini key: valid  (AI daily brief)") if
         llm.check_gemini(gk, cfg.get("gemini_model")) else
         ui.err("Gemini key: set but the test call failed (key or model?)"))
    else:
        ui.info("Gemini key: set (skipped live check)")

    wh = cfg.get("discord_webhook_url")
    if not wh:
        ui.info("Discord webhook: not set — add for alerts & briefs")
    else:
        (ui.ok("Discord webhook: test message sent") if notify.test_webhook(wh)
         else ui.err("Discord webhook: set but unreachable"))

    ui.section("Summary")
    if core_ok:
        ui.ok("Core is healthy — you can flip. `nulladdons status` to begin.")
    else:
        ui.err("Core issue above needs attention (usually connectivity).")
    return core_ok
