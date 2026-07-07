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
import os
import time
from datetime import datetime, timezone

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
        if xp >= entry.get("totalExpRequired", float("inf")):
            lvl = entry.get("level", lvl)
        else:
            break
    return lvl


def _skill_xp(member: dict, skill: str) -> float | None:
    v = _get(member, "player_data", "experience", f"SKILL_{skill}")
    if v is None:
        v = member.get(f"experience_skill_{skill.lower()}")
    return float(v) if v is not None else None


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
    purse = float(purse or 0)
    bank = float(_get(profile, "banking", "balance", default=0) or 0)

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
    slayer_src = _get(member, "slayer", "slayer_bosses") or member.get("slayer_bosses") or {}
    slayer = {boss: int(_get(data, "xp", default=0) or 0)
              for boss, data in slayer_src.items() if isinstance(data, dict)}

    cata_xp = _get(member, "dungeons", "dungeon_types", "catacombs", "experience", default=0)
    pets = _get(member, "pets_data", "pets") or member.get("pets") or []
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
        "collections_sum": sum(int(v or 0) for v in collection.values()),
        "collections_count": len(collection),
        "slayer": slayer,
        "slayer_total": sum(slayer.values()),
        "catacombs_xp": int(cata_xp or 0),
        "pets": len(pets),
        "fairy_souls": int(fairy or 0),
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
        with open(path, "r", encoding="utf-8") as fh:
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
    days = max(0, (current["ts"] - previous["ts"]) / 86400.0)
    lines: list[str] = []

    coins_delta = current["coins"] - previous["coins"]
    if coins_delta:
        lines.append(f"Coins: {_signed(coins_delta)} "
                     f"(now {current['coins']:,})")

    if current.get("skill_average") is not None and previous.get("skill_average") is not None:
        d = round(current["skill_average"] - previous["skill_average"], 2)
        if d:
            lines.append(f"Skill Average: {_signed(d)} (now {current['skill_average']})")

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

    slayer_d = current["slayer_total"] - previous["slayer_total"]
    if slayer_d:
        lines.append(f"Slayer XP: +{slayer_d:,}")
    cata_d = current["catacombs_xp"] - previous["catacombs_xp"]
    if cata_d:
        lines.append(f"Catacombs XP: +{cata_d:,}")
    coll_d = current["collections_sum"] - previous["collections_sum"]
    if coll_d:
        lines.append(f"Collections: +{coll_d:,} items")
    pet_d = current["pets"] - previous["pets"]
    if pet_d:
        lines.append(f"Pets: {_signed(pet_d)} (now {current['pets']})")
    fairy_d = current["fairy_souls"] - previous["fairy_souls"]
    if fairy_d:
        lines.append(f"Fairy Souls: +{fairy_d}")

    if not lines:
        lines.append("No measurable change since the last snapshot.")
    return {"baseline": True, "days": round(days, 2),
            "coins_delta": coins_delta, "lines": lines}


def _signed(n) -> str:
    return f"+{n:,}" if n >= 0 else f"{n:,}"
