"""
Null's Addons -- extensive, opt-in, local-first telemetry & personal stats.

This is *your* data, collected *for you*, and it is **off by default**. Nothing
here runs, and no file is ever created, unless you turn it on (``nulladdons
telemetry on``, or ``features.telemetry: true`` in your config). When it's on,
every command appends one compact JSON line to a log in your home directory --
and that is the whole story, unless you *additionally* set an explicit
``telemetry.sink_url``, in which case the exact same line is also POSTed there so
you can pipe your stats wherever you like.

We are loud about what's collected: :data:`COLLECTED_FIELDS` documents every
field, ``nulladdons telemetry manifest`` prints it, and there is deliberately no
PII in the schema -- no usernames, no UUIDs, no API keys, and never the text of a
question you ``ask`` (only its category). It's mostly here to be *fun*: it powers
a stats dashboard, a "SkyBlock Wrapped", and a pile of unlockable achievements.

Everything in this module is best-effort: telemetry must never crash a command or
slow it down, so writes are guarded and the optional network send is a fire-and-
forget daemon thread.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
from collections import Counter

from . import features

SCHEMA_VERSION = 1

TELEMETRY_DIR = os.path.join(os.path.expanduser("~"), ".nulladdons", "telemetry")
EVENTS_PATH = os.path.join(TELEMETRY_DIR, "events.jsonl")
MAX_EVENTS = 50_000

#: The full manifest: every field we may store, and what it means. This is the
#: source of truth behind ``telemetry manifest`` -- if it's collected, it's here.
COLLECTED_FIELDS: list[tuple[str, str]] = [
    ("v", "schema version of this record"),
    ("ts", "unix timestamp of the run"),
    ("day", "calendar day (YYYY-MM-DD) — powers streaks"),
    ("hour", "hour of day 0–23 — powers your 'when do you grind' clock"),
    ("weekday", "abbreviated weekday (Mon…Sun)"),
    ("command", "which command you ran (plan, flips, status, ask, …)"),
    ("flavor", "the personality flavor in effect (gremlin/zen/…)"),
    ("risk", "risk profile used (conservative/balanced/aggressive)"),
    ("duration_ms", "how long the command took, in milliseconds"),
    ("offline", "true if you ran against a saved snapshot (not live)"),
    ("serious", "true if you ran with --serious (personality muted)"),
    ("results", "how many opportunities the command surfaced"),
    ("top_margin", "best after-tax margin shown this run (a fraction, e.g. 0.15)"),
    ("top_coins_per_hour", "best coins/hour shown this run"),
    ("projected_profit", "projected profit for the run (theoretical, not realized)"),
    ("capital", "the budget the run was sized against"),
    ("positions", "number of diversified positions in a plan/status"),
    ("mp_gain", "Magical Power the cheapest suggestion would add"),
    ("mp_cost", "coin cost of that Magical Power suggestion"),
    ("mayor", "the active/simulated SkyBlock mayor's name, if any"),
    ("tax_free", "true if the mayor made the Bazaar tax-free (Derpy)"),
    ("item", "product id inspected via the `item` command"),
    ("ask_intent", "category of an `ask` question (NEVER the question text)"),
    ("ask_answered", "true if `ask` answered from data (vs 'I don't know')"),
    ("easter_egg", "true if a hidden joke was triggered"),
    ("movers", "how many market movers were shown"),
]

# A stable, human-facing list of the commands we consider "core" for the
# completionist achievement.
CORE_COMMANDS = ["plan", "flips", "crafts", "status", "mp", "ah", "brief", "ask", "item"]


# ---------------------------------------------------------------------------
# consent
# ---------------------------------------------------------------------------

def is_enabled(config: dict | None) -> bool:
    """Telemetry is on only if you explicitly enabled the feature."""
    return features.enabled("telemetry", config)


# ---------------------------------------------------------------------------
# recording
# ---------------------------------------------------------------------------

_PENDING: dict = {}


def annotate(**fields) -> None:
    """Stash command-specific fields for the event ``main()`` will record.

    Command handlers call this to enrich their event without having to thread a
    recorder object around. ``None`` values are dropped so absent facts simply
    don't appear. A no-op cost when telemetry is off (it's just a dict write that
    gets discarded)."""
    for key, value in fields.items():
        if value is not None:
            _PENDING[key] = value


def take_annotations() -> dict:
    """Return and clear the pending annotations."""
    global _PENDING
    pending, _PENDING = _PENDING, {}
    return pending


def build_event(command: str, *, flavor: str = features.DEFAULT_FLAVOR,
                risk: str | None = None, duration_ms: float = 0.0,
                offline: bool = False, serious: bool = False,
                extra: dict | None = None,
                now: datetime.datetime | None = None) -> dict:
    """Assemble one telemetry record (pure; used by ``record`` and tested)."""
    now = now or datetime.datetime.now()
    event = {
        "v": SCHEMA_VERSION,
        "ts": int(now.timestamp()),
        "day": now.strftime("%Y-%m-%d"),
        "hour": now.hour,
        "weekday": now.strftime("%a"),
        "command": command,
        "flavor": flavor,
        "duration_ms": int(duration_ms),
        "offline": bool(offline),
        "serious": bool(serious),
    }
    if risk:
        event["risk"] = risk
    if extra:
        event.update({k: v for k, v in extra.items() if v is not None})
    return event


def record(config: dict | None, event: dict, path: str | None = None) -> bool:
    """Append ``event`` to the local log if telemetry is enabled. Best-effort."""
    if not is_enabled(config):
        return False
    path = path or EVENTS_PATH
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        _trim(path)
    except OSError:
        return False
    _maybe_sink(config, event)
    return True


def _trim(path: str) -> None:
    """Keep the log bounded so it can't grow without limit."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        if len(lines) > MAX_EVENTS:
            with open(path, "w", encoding="utf-8") as fh:
                fh.writelines(lines[-MAX_EVENTS:])
    except OSError:
        pass


def _maybe_sink(config: dict | None, event: dict) -> None:
    """If (and only if) you configured a sink URL, mirror the event there.

    Fire-and-forget on a daemon thread; every error is swallowed. This is the one
    path by which telemetry can leave your machine, and it exists only when you
    opt into it a second time by setting ``telemetry.sink_url``."""
    url = ((config or {}).get("telemetry") or {}).get("sink_url")
    if not url:
        return

    def send():
        try:
            import urllib.request
            data = json.dumps(event).encode("utf-8")
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass  # telemetry must never make noise

    threading.Thread(target=send, daemon=True).start()


# ---------------------------------------------------------------------------
# reading & aggregation
# ---------------------------------------------------------------------------

def load_events(path: str | None = None) -> list[dict]:
    """Read the local log into a list of event dicts (skips malformed lines)."""
    path = path or EVENTS_PATH
    events: list[dict] = []
    if not os.path.exists(path):
        return events
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        events.append(obj)
                except ValueError:
                    continue
    except OSError:
        pass
    return events


def _streaks(days: set[str]) -> tuple[int, int]:
    """(current_streak_ending_today, longest_streak) from a set of day strings."""
    if not days:
        return 0, 0
    parsed = sorted({datetime.date.fromisoformat(d) for d in days
                     if _is_isodate(d)})
    if not parsed:
        return 0, 0
    longest = run = 1
    for prev, cur in zip(parsed, parsed[1:]):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)
    # current streak counts back from today (or yesterday, grace for tz drift).
    today = datetime.date.today()
    current = 0
    day = today
    dayset = set(parsed)
    if today not in dayset and (today - datetime.timedelta(days=1)) in dayset:
        day = today - datetime.timedelta(days=1)
    while day in dayset:
        current += 1
        day -= datetime.timedelta(days=1)
    return current, longest


def _is_isodate(s) -> bool:
    try:
        datetime.date.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


def compute_stats(events: list[dict]) -> dict:
    """Crunch the raw event log into the aggregates that power stats & Wrapped."""
    days = {e.get("day") for e in events if e.get("day")}
    commands = Counter(e.get("command") for e in events if e.get("command"))
    flavors = Counter(e.get("flavor") for e in events if e.get("flavor"))
    risks = Counter(e.get("risk") for e in events if e.get("risk"))
    hours = Counter(int(e["hour"]) for e in events if isinstance(e.get("hour"), int))
    weekdays = Counter(e.get("weekday") for e in events if e.get("weekday"))
    items = Counter(e.get("item") for e in events if e.get("item"))
    mayors = Counter(e.get("mayor") for e in events if e.get("mayor"))

    margins = [(_f(e.get("top_margin")), e.get("day")) for e in events
               if e.get("top_margin") is not None]
    best_margin = max(margins, default=(0.0, None))
    cph = [_f(e.get("top_coins_per_hour")) for e in events
           if e.get("top_coins_per_hour") is not None]
    projected = sum(_f(e.get("projected_profit")) for e in events)

    current_streak, longest_streak = _streaks(days)

    return {
        "total_events": len(events),
        "first_day": min(days) if days else None,
        "last_day": max(days) if days else None,
        "active_days": len(days),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "command_counts": dict(commands),
        "favorite_command": commands.most_common(1)[0][0] if commands else None,
        "flavors_used": dict(flavors),
        "risks_used": dict(risks),
        "hour_histogram": {h: hours.get(h, 0) for h in range(24)},
        "busiest_hour": hours.most_common(1)[0][0] if hours else None,
        "weekday_counts": dict(weekdays),
        "items_viewed": dict(items),
        "spirit_item": items.most_common(1)[0][0] if items else None,
        "mayors_seen": sorted(m for m in mayors if m),
        "tax_free_sessions": sum(1 for e in events if e.get("tax_free")),
        "biggest_margin": best_margin[0],
        "biggest_margin_day": best_margin[1],
        "best_coins_per_hour": max(cph, default=0.0),
        "total_projected_profit": projected,
        "ask_count": commands.get("ask", 0),
        "ask_answered": sum(1 for e in events if e.get("ask_answered")),
        "dont_know_count": sum(1 for e in events
                               if e.get("command") == "ask" and e.get("ask_answered") is False),
        "easter_eggs_found": sum(1 for e in events if e.get("easter_egg")),
        "offline_sessions": sum(1 for e in events if e.get("offline")),
        "live_sessions": sum(1 for e in events if e.get("offline") is False),
        "total_time_ms": sum(_f(e.get("duration_ms")) for e in events),
    }


def _f(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# achievements (the fun part)
# ---------------------------------------------------------------------------

#: Each: (id, emoji, title, description, predicate over the stats dict).
ACHIEVEMENTS: list[tuple] = [
    ("made_a_move", "🎯", "Made a Move", "Run any command once.",
     lambda s: s["total_events"] >= 1),
    ("hes_back", "🔁", "He's Back", "Come back on a second day.",
     lambda s: s["active_days"] >= 2),
    ("day_trader", "📅", "Day Trader", "Keep a 7-day streak.",
     lambda s: s["longest_streak"] >= 7),
    ("no_life", "💀", "No Life, All Coins", "Keep a 30-day streak.",
     lambda s: s["longest_streak"] >= 30),
    ("veteran", "🎖️", "Veteran", "Run 100 commands total.",
     lambda s: s["total_events"] >= 100),
    ("creature_of_habit", "🔂", "Creature of Habit", "Run one command 50 times.",
     lambda s: max(s["command_counts"].values(), default=0) >= 50),
    ("whale_watcher", "🐋", "Whale Watcher", "Spot a 30%+ margin.",
     lambda s: s["biggest_margin"] >= 0.30),
    ("cracked", "🔥", "CRACKED", "Spot a 50%+ margin.",
     lambda s: s["biggest_margin"] >= 0.50),
    ("theoretical_billionaire", "🧠", "Theoretical Billionaire",
     "Witness 1B in projected profit (across all runs).",
     lambda s: s["total_projected_profit"] >= 1e9),
    ("number_went_up", "📈", "Number Went Up",
     "Witness 1T in projected profit.", lambda s: s["total_projected_profit"] >= 1e12),
    ("diamond_hands", "💎", "Diamond Hands", "Run conservative 10 times.",
     lambda s: s["risks_used"].get("conservative", 0) >= 10),
    ("degenerate", "🎰", "Degenerate", "Run aggressive 10 times.",
     lambda s: s["risks_used"].get("aggressive", 0) >= 10),
    ("split_personality", "🎭", "Split Personality", "Use 3 different flavors.",
     lambda s: len(s["flavors_used"]) >= 3),
    ("yarrr", "🏴‍☠️", "Yarrr", "Sail with the pirate flavor.",
     lambda s: s["flavors_used"].get("pirate", 0) >= 1),
    ("inner_peace", "🧘", "Inner Peace", "Find zen 10 times.",
     lambda s: s["flavors_used"].get("zen", 0) >= 10),
    ("night_owl", "🦉", "Night Owl", "Grind between midnight and 4am.",
     lambda s: any(s["hour_histogram"].get(h, 0) for h in (0, 1, 2, 3))),
    ("early_bird", "🐦", "Early Bird", "Grind between 5 and 7am.",
     lambda s: any(s["hour_histogram"].get(h, 0) for h in (5, 6, 7))),
    ("well_briefed", "🗞️", "Well Briefed", "Read a daily brief.",
     lambda s: s["command_counts"].get("brief", 0) >= 1),
    ("going_once", "🔨", "Going Once", "Check the Auction House.",
     lambda s: s["command_counts"].get("ah", 0) >= 1),
    ("power_hungry", "🔮", "Power Hungry", "Plan some Magical Power.",
     lambda s: s["command_counts"].get("mp", 0) >= 1),
    ("twenty_questions", "❓", "20 Questions", "Ask 20 questions.",
     lambda s: s["ask_count"] >= 20),
    ("found_the_secret", "🥚", "Found the Secret", "Trigger a hidden joke.",
     lambda s: s["easter_eggs_found"] >= 1),
    ("tax_evader", "🎪", "Tax Evader", "Catch Derpy making the Bazaar tax-free.",
     lambda s: s["tax_free_sessions"] >= 1),
    ("completionist", "🏆", "Completionist", "Run every core command at least once.",
     lambda s: all(s["command_counts"].get(c, 0) >= 1 for c in CORE_COMMANDS)),
]


def achievements(stats: dict) -> list[dict]:
    """Evaluate every badge against the stats; returns unlocked + locked."""
    out = []
    for aid, emoji, title, desc, predicate in ACHIEVEMENTS:
        try:
            got = bool(predicate(stats))
        except Exception:
            got = False
        out.append({"id": aid, "emoji": emoji, "title": title,
                    "desc": desc, "unlocked": got})
    return out


# ---------------------------------------------------------------------------
# rendering: manifest, stats dashboard, SkyBlock Wrapped
# ---------------------------------------------------------------------------

def humanize_coins(n: float) -> str:
    n = float(n)
    sign = "-" if n < 0 else ""
    n = abs(n)
    for unit, div in (("B", 1e9), ("M", 1e6), ("k", 1e3)):
        if n >= div:
            return f"{sign}{n / div:.2f}{unit}"
    return f"{sign}{n:,.0f}"


def manifest_text(config: dict | None = None) -> str:
    """A plain, honest description of exactly what telemetry collects & where."""
    on = is_enabled(config)
    sink = ((config or {}).get("telemetry") or {}).get("sink_url")
    lines = [
        "NULL'S ADDONS — TELEMETRY MANIFEST",
        "",
        f"Status:   {'ON' if on else 'OFF'}  (feature 'telemetry')",
        f"Stored:   {EVENTS_PATH}",
        f"Leaves your machine:  {'YES → ' + sink if sink else 'NO (local only)'}",
        "",
        "It is OFF by default. When ON, each command appends ONE line like this to",
        "the local log above. That's it — unless you set telemetry.sink_url, in",
        "which case the same line is also POSTed there.",
        "",
        "There is NO personally identifying data: no usernames, no UUIDs, no API",
        "keys, and never the text of a question you ask (only its category).",
        "",
        "Every field that may be stored:",
    ]
    for name, desc in COLLECTED_FIELDS:
        lines.append(f"  {name:<20} {desc}")
    lines += [
        "",
        "Turn it on:   nulladdons telemetry on",
        "Turn it off:  nulladdons telemetry off",
        "See it:       nulladdons telemetry stats   ·   ...wrapped   ·   ...achievements",
        "Wipe it:      nulladdons telemetry clear",
    ]
    return "\n".join(lines)


def _bar(count: int, peak: int, width: int = 20) -> str:
    if peak <= 0:
        return ""
    filled = int(round(width * count / peak))
    return "█" * filled + "·" * (width - filled)


def stats_text(stats: dict) -> str:
    """The personal stats dashboard."""
    if stats["total_events"] == 0:
        return ("No telemetry yet — it's on, so run a few commands and check back.\n"
                "(Or `nulladdons telemetry manifest` to see exactly what's collected.)")
    L = ["NULL'S ADDONS — YOUR STATS", "═" * 52,
         f" Runs: {stats['total_events']}   ·   Active days: {stats['active_days']}"
         f"   ·   Streak: {stats['current_streak']} (best {stats['longest_streak']})",
         f" Since {stats['first_day']} → {stats['last_day']}"
         f"   ·   Time in tool: {_dur(stats['total_time_ms'])}",
         ""]

    L.append(" ── Favorite commands ──")
    counts = Counter(stats["command_counts"])
    peak = max(counts.values(), default=0)
    for cmd, n in counts.most_common(6):
        L.append(f"   {cmd:<8} {_bar(n, peak)} {n}")

    L.append("")
    L.append(" ── When you grind (hour of day) ──")
    hist = stats["hour_histogram"]
    hpeak = max(hist.values(), default=0)
    for label, rng in (("night 0–5", range(0, 6)), ("morn  6–11", range(6, 12)),
                       ("noon 12–17", range(12, 18)), ("eve  18–23", range(18, 24))):
        c = sum(hist.get(h, 0) for h in rng)
        L.append(f"   {label:<11} {_bar(c, max(hpeak * 3, 1), 18)} {c}")
    if stats["busiest_hour"] is not None:
        L.append(f"   peak hour: {stats['busiest_hour']:02d}:00")

    L.append("")
    L.append(" ── Records ──")
    if stats["biggest_margin"]:
        L.append(f"   Juiciest margin spotted: +{stats['biggest_margin'] * 100:.1f}%"
                 + (f"  ({stats['biggest_margin_day']})" if stats["biggest_margin_day"] else ""))
    if stats["best_coins_per_hour"]:
        L.append(f"   Best coins/hour spotted: {humanize_coins(stats['best_coins_per_hour'])}/hr")
    L.append(f"   Theoretical profit witnessed: {humanize_coins(stats['total_projected_profit'])}")
    if stats["spirit_item"]:
        L.append(f"   Spirit item (most inspected): {_nice(stats['spirit_item'])}")
    if stats["mayors_seen"]:
        L.append(f"   Mayors witnessed: {', '.join(stats['mayors_seen'])}")
    if stats["flavors_used"]:
        fav_flavor = Counter(stats["flavors_used"]).most_common(1)[0][0]
        L.append(f"   Signature flavor: {fav_flavor}")

    unlocked = sum(1 for a in achievements(stats) if a["unlocked"])
    L.append("")
    L.append(f" 🏆 Achievements: {unlocked}/{len(ACHIEVEMENTS)}  "
             f"(nulladdons telemetry achievements)")
    L.append("═" * 52)
    return "\n".join(L)


def achievements_text(stats: dict) -> str:
    rows = achievements(stats)
    unlocked = [a for a in rows if a["unlocked"]]
    locked = [a for a in rows if not a["unlocked"]]
    L = [f"NULL'S ADDONS — ACHIEVEMENTS  ({len(unlocked)}/{len(rows)})", "═" * 52]
    for a in unlocked:
        L.append(f"  {a['emoji']}  {a['title']} — {a['desc']}")
    if locked:
        L.append("")
        L.append(" Still locked:")
        for a in locked:
            L.append(f"  🔒  {a['title']} — {a['desc']}")
    return "\n".join(L)


def wrapped_text(stats: dict, flavor: str = features.DEFAULT_FLAVOR) -> str:
    """A fun 'SkyBlock Wrapped' recap. Honest numbers, playful frame."""
    if stats["total_events"] == 0:
        return "Nothing to wrap yet — go make some (theoretical) coins first. 💸"
    grass = "0" if stats["total_events"] > 20 else "a suspicious amount of"
    lines = [
        "╔═══════════════════════════════════╗",
        "║     NULL'S ADDONS — WRAPPED 🎁     ║",
        "╚═══════════════════════════════════╝",
        f"You showed up {stats['active_days']} day(s) and ran {stats['total_events']} commands.",
        f"Your best streak was {stats['longest_streak']} day(s) — "
        + ("respect." if stats["longest_streak"] >= 7 else "we've all been there."),
    ]
    if stats["favorite_command"]:
        lines.append(f"Your ride-or-die command was `{stats['favorite_command']}`.")
    if stats["spirit_item"]:
        lines.append(f"Your spirit item is {_nice(stats['spirit_item'])}. Iconic.")
    if stats["busiest_hour"] is not None:
        lines.append(f"You grind hardest around {stats['busiest_hour']:02d}:00. "
                     + ("go to sleep." if stats["busiest_hour"] in (0, 1, 2, 3, 4) else "peak hustle hours."))
    if stats["biggest_margin"]:
        lines.append(f"The juiciest spread you spotted was "
                     f"+{stats['biggest_margin'] * 100:.1f}%. chef's kiss.")
    lines.append(f"Theoretical profit witnessed this era: "
                 f"{humanize_coins(stats['total_projected_profit'])} coins.")
    if stats["mayors_seen"]:
        lines.append(f"Mayors that ran your economy: {', '.join(stats['mayors_seen'])}.")
    unlocked = sum(1 for a in achievements(stats) if a["unlocked"])
    lines.append(f"Badges earned: {unlocked}/{len(ACHIEVEMENTS)}.")
    lines.append(f"Grass touched: {grass}.")
    lines.append("")
    lines.append("gg. see you next flip. 🫡")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _nice(product_id: str) -> str:
    return str(product_id).split(":")[0].replace("_", " ").title()


def _dur(ms: float) -> str:
    seconds = _f(ms) / 1000.0
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


def clear(path: str | None = None) -> bool:
    """Delete the local telemetry log. Returns True if a file was removed."""
    path = path or EVENTS_PATH
    try:
        os.remove(path)
        return True
    except OSError:
        return False


def export_to(dest_path: str, src_path: str | None = None) -> int:
    """Copy the telemetry log to ``dest_path`` (portable JSONL). Returns #events."""
    events = load_events(src_path)
    with open(dest_path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    return len(events)
