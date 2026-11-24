"""Daily challenges: 3 quick ones per day, deterministic per profile. Pure Python.

One is always aimed at a topic she needs (from her focus ranking). The other
two come from a pool where each one can be done in a single round. They sit
alongside the daily question goal and never count towards it.
"""
from __future__ import annotations

import hashlib
import random

DAILY_XP = 20
DAILY_ALL_BONUS = 30
DAILY_PER_DAY = 3
TOPIC_POOL = 3
GOOD_ROUND_SCORE = 8

TOPIC_TYPE = {"type": "topic_today", "name": "Topic Spark", "icon": "✨",
              "desc": "Get {target} {topic} answers right", "targets": (5, 8)}

POOL: list[dict] = [
    {"type": "streak_run", "name": "Hot Streak", "icon": "🔥",
     "desc": "Get {target} right in a row", "targets": (5, 7)},
    {"type": "good_round", "name": "High Scorer", "icon": "⭐",
     "desc": f"Score {GOOD_ROUND_SCORE} or more in a round", "targets": (1,)},
    {"type": "focus_round", "name": "Focus Time", "icon": "🎯",
     "desc": "Play a Today's Focus round", "targets": (1,)},
    {"type": "journal", "name": "Dear Diary", "icon": "📔",
     "desc": "Write in your journal", "targets": (1,)},
    {"type": "new_game", "name": "Try Something New", "icon": "🧭",
     "desc": "Play a game you haven't tried this week", "targets": (1,)},
    {"type": "speedy", "name": "Quick Fire", "icon": "⚡",
     "desc": "Earn {target} speed bonuses", "targets": (5, 8)},
    {"type": "fly_snap", "name": "Frog Friend", "icon": "🐸",
     "desc": "Survive {target} rounds of Fly Snap", "targets": (2, 3)},
]
TYPES_BY_ID = {c["type"]: c for c in [TOPIC_TYPE, *POOL]}
# Types whose progress is "best so far today" rather than a running total.
BEST_OF = {"streak_run", "fly_snap"}


def generate_day(day: str, profile_id: str, focus_skills: list[str] | None,
                 unplayed_modes: list[str] | None) -> list[dict]:
    seed = int(hashlib.sha256(f"daily:{day}:{profile_id}".encode()).hexdigest(), 16)
    rng = random.Random(seed)
    out: list[dict] = []
    if focus_skills:
        out.append(_make(day, TOPIC_TYPE, rng, skill=rng.choice(list(focus_skills[:TOPIC_POOL]))))
    pool = [p for p in POOL if p["type"] != "new_game" or unplayed_modes]
    for meta in rng.sample(pool, DAILY_PER_DAY - len(out)):
        out.append(_make(day, meta, rng))
    return out


def _make(day: str, meta: dict, rng: random.Random, skill: str | None = None) -> dict:
    ch = {
        "id": f"{day}-{meta['type']}",
        "type": meta["type"],
        "target": rng.choice(meta["targets"]),
        "progress": 0,
        "done": False,
    }
    if skill:
        ch["skill"] = skill
    return ch


def apply(challenge: dict, signals: dict) -> bool:
    """Advance one challenge from a bag of signals. Returns True if it just finished."""
    if challenge["done"]:
        return False
    kind = challenge["type"]
    if kind == "topic_today":
        challenge["progress"] += signals.get(f"correct:{challenge.get('skill')}", 0)
    elif kind == "streak_run":
        challenge["progress"] = max(challenge["progress"], signals.get("run_streak", 0))
    elif kind == "speedy":
        challenge["progress"] += signals.get("speed", 0)
    elif kind == "fly_snap":
        challenge["progress"] = max(challenge["progress"], signals.get("fly_rounds", 0))
    elif kind == "good_round":
        if signals.get("round_correct", 0) >= GOOD_ROUND_SCORE:
            challenge["progress"] = 1
    elif kind == "focus_round":
        if signals.get("round_mode") == "todays_focus":
            challenge["progress"] = 1
    elif kind == "new_game":
        if signals.get("new_game"):
            challenge["progress"] = 1
    elif kind == "journal":
        if signals.get("journal"):
            challenge["progress"] = 1
    if challenge["progress"] >= challenge["target"]:
        challenge["done"] = True
        return True
    return False


def describe(challenge: dict) -> dict:
    from .journal import topic_name

    meta = TYPES_BY_ID[challenge["type"]]
    skill = challenge.get("skill")
    out = {
        "id": challenge["id"],
        "type": challenge["type"],
        "name": meta["name"],
        "icon": meta["icon"],
        "desc": meta["desc"].format(
            target=challenge["target"], topic=topic_name(skill) if skill else ""),
        "target": challenge["target"],
        "progress": int(min(challenge["progress"], challenge["target"])),
        "done": challenge["done"],
    }
    if skill:
        out["skill"] = skill
    return out
