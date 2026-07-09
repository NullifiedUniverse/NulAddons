"""
Null's Addons -- account progress snapshots & day-over-day diffs.

Feeds the daily brief.  Reads a SkyBlock profile, extracts a compact set of
progression stats, stores one snapshot per run, and diffs the newest snapshot
against the previous day's to show what changed (coins, skills, slayer, dungeons,
collections, pets, fairy souls).

The SkyBlock profile schema has drifted across API versions, so every extractor
is *defensive*: it tries the current nested path and the older flat one, and
falls back to ``None``/0 rather than raising.  The diff logic is pure and fully
tested.
"""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone

from .util import to_float as _num
from .util import to_int as _int

PROGRESS_DIR = os.path.join(os.path.expanduser("~"), ".nulladdons", "progress")

ALL_SKILLS = ["FARMING", "MINING", "COMBAT", "FORAGING", "FISHING", "ENCHANTING",
              "ALCHEMY", "CARPENTRY", "RUNECRAFTING", "TAMING", "SOCIAL", "HUNTING"]
#: Skills that count toward the classic "Skill Average".
AVERAGE_SKILLS = ["FARMING", "MINING", "COMBAT", "FORAGING", "FISHING",
                  "ENCHANTING", "ALCHEMY", "TAMING", "CARPENTRY"]


def _get(node, *keys, default=None):
    for k in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(k)
        if node is None:
            return default
    return node


def level_from_xp(xp: float, skill_levels: list[dict] | None) -> int | None:
    """Cumulative-XP -> level using a resource ``levels`` list, or ``None``."""
    if not skill_levels:
        return None
    lvl = 0
    for entry in skill_levels:
        if not isinstance(entry, dict):
            continue
        if xp >= _num(entry.get("totalExpRequired"), math.inf):
            lvl = _int(entry.get("level"), lvl)
        else:
            break
    return lvl


def _skill_xp(member: dict, skill: str) -> float | None:
    v = _get(member, "player_data", "experience", f"SKILL_{skill}")
    if v is None:
        v = member.get(f"experience_skill_{skill.lower()}")
    return _num(v) if v is not None else None


def pick_member(payload: dict, uuid: str) -> tuple[dict, dict]:
    """Return (profile, member) for the selected profile, else the first."""
    profiles = payload.get("profiles") or []
    chosen_profile, chosen_member = {}, {}
    for profile in profiles:
        member = (profile.get("members") or {}).get(uuid) or {}
        if not chosen_profile:
            chosen_profile, chosen_member = profile, member
        if profile.get("selected"):
            return profile, member
    return chosen_profile, chosen_member


def extract_stats(profile: dict, member: dict, skills_resource: dict | None
                  ) -> dict:
    """Build a compact progression snapshot from a profile + member."""
    res_skills = (skills_resource or {}).get("skills", {}) if skills_resource else {}

    purse = _get(member, "currencies", "coin_purse")
    if purse is None:
        purse = member.get("coin_purse")
    purse = _num(purse)
    bank = _num(_get(profile, "banking", "balance"))

    skills: dict[str, dict] = {}
    levels_for_avg = []
    for skill in ALL_SKILLS:
        xp = _skill_xp(member, skill)
        if xp is None:
            continue
        levels = (res_skills.get(skill) or {}).get("levels")
        lvl = level_from_xp(xp, levels)
        skills[skill] = {"xp": round(xp), "level": lvl}
        if skill in AVERAGE_SKILLS and lvl is not None:
            levels_for_avg.append(lvl)
    skill_avg = round(sum(levels_for_avg) / len(levels_for_avg), 2) if levels_for_avg else None

    collection = member.get("collection") or {}
    if not isinstance(collection, dict):
        collection = {}
    slayer_src = _get(member, "slayer", "slayer_bosses") or member.get("slayer_bosses") or {}
    slayer = {boss: int(_num(_get(data, "xp")))
              for boss, data in slayer_src.items() if isinstance(data, dict)}

    cata_xp = _get(member, "dungeons", "dungeon_types", "catacombs", "experience")
    pets = _get(member, "pets_data", "pets") or member.get("pets") or []
    pets_count = len(pets) if isinstance(pets, (list, dict)) else 0
    fairy = _get(member, "fairy_soul", "total_collected")
    if fairy is None:
        fairy = member.get("fairy_souls_collected", 0)

    now = int(time.time())
    return {
        "ts": now,
        "date": datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d"),
        "profile_name": profile.get("cute_name"),
        "purse": round(purse),
        "bank": round(bank),
        "coins": round(purse + bank),
        "skills": skills,
        "skill_average": skill_avg,
        "collections_sum": int(sum(_num(v) for v in collection.values())),
        "collections_count": len(collection),
        "slayer": slayer,
        "slayer_total": sum(slayer.values()),
        "catacombs_xp": int(_num(cata_xp)),
        "pets": pets_count,
        "fairy_souls": int(_num(fairy)),
    }


# --- persistence ------------------------------------------------------------

def _path(account: str) -> str:
    return os.path.join(PROGRESS_DIR, f"{account}.jsonl")


def save_snapshot(account: str, stats: dict) -> None:
    try:
        os.makedirs(PROGRESS_DIR, exist_ok=True)
        with open(_path(account), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(stats) + "\n")
    except OSError:
        pass


def load_history(account: str) -> list[dict]:
    path = _path(account)
    if not os.path.exists(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return []
    return out


def previous_snapshot(history: list[dict], current: dict) -> dict | None:
    """The most recent snapshot from a different day (else the prior entry)."""
    for snap in reversed(history):
        if snap is current:
            continue
        if snap.get("date") != current.get("date"):
            return snap
    # No earlier day yet: fall back to the immediately preceding snapshot.
    prior = [s for s in history if s is not current]
    return prior[-1] if prior else None


# --- diff -------------------------------------------------------------------

def diff(previous: dict | None, current: dict) -> dict:
    """Compute deltas between two snapshots. Empty-ish when no baseline."""
    if not previous:
        return {"baseline": False, "lines": ["First snapshot — no baseline to "
                                             "compare yet. Run again tomorrow."],
                "coins_delta": 0, "days": 0}
    days = max(0, (current.get("ts", 0) - previous.get("ts", 0)) / 86400.0)
    lines: list[str] = []

    def delta(key):  # tolerates snapshots written by older tool versions
        return int(_num(current.get(key))) - int(_num(previous.get(key)))

    coins_delta = delta("coins")
    if coins_delta:
        lines.append(f"Coins: {_signed(coins_delta)} "
                     f"(now {current.get('coins', 0):,})")

    if current.get("skill_average") is not None and previous.get("skill_average") is not None:
        avg_d = round(current["skill_average"] - previous["skill_average"], 2)
        if avg_d:
            lines.append(f"Skill Average: {_signed(avg_d)} "
                         f"(now {current['skill_average']})")

    skill_gains = {}
    for skill, cur in current.get("skills", {}).items():
        prev = previous.get("skills", {}).get(skill)
        if not prev:
            continue
        xp_d = cur["xp"] - prev["xp"]
        if xp_d:
            skill_gains[skill] = xp_d
        if cur.get("level") is not None and prev.get("level") is not None \
                and cur["level"] > prev["level"]:
            lines.append(f"{skill.title()} leveled up: "
                         f"{prev['level']} → {cur['level']}")
    if skill_gains:
        top = sorted(skill_gains.items(), key=lambda kv: kv[1], reverse=True)[:3]
        lines.append("Top skill XP: " + ", ".join(
            f"{s.title()} +{x:,}" for s, x in top))

    if delta("slayer_total"):
        lines.append(f"Slayer XP: +{delta('slayer_total'):,}")
    if delta("catacombs_xp"):
        lines.append(f"Catacombs XP: +{delta('catacombs_xp'):,}")
    if delta("collections_sum"):
        lines.append(f"Collections: +{delta('collections_sum'):,} items")
    if delta("pets"):
        lines.append(f"Pets: {_signed(delta('pets'))} (now {current.get('pets', 0)})")
    if delta("fairy_souls"):
        lines.append(f"Fairy Souls: +{delta('fairy_souls')}")

    if not lines:
        lines.append("No measurable change since the last snapshot.")
    return {"baseline": True, "days": round(days, 2),
            "coins_delta": coins_delta, "lines": lines}


def _signed(n) -> str:
    return f"+{n:,}" if n >= 0 else f"{n:,}"
