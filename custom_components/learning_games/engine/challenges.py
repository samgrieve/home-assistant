"""Weekly challenges: 3 per ISO week, deterministic per profile. Pure Python.

The picks come from sha256(week_start:profile_id), so they are the same after a
restart. The concrete target, the daily cap and progress are stored in
weekly["challenges"].

Since v1.5 every challenge has a **daily cap**: only so much counts each day,
so a challenge takes several separate days however long one session lasts.
Volume targets scale with the profile's daily question goal (G).
"""
from __future__ import annotations

import hashlib
import math
import random

# targets/cap: numbers, or ("G", multiplier) meaning multiplier × daily goal.
CHALLENGE_TYPES: list[dict] = [
    {"type": "questions", "name": "Question Quest", "icon": "❓",
     "desc": "Answer {target} questions",
     "targets": (("G", 4), ("G", 5), ("G", 6)), "cap": ("G", 1.5)},
    {"type": "correct", "name": "Sharp Shooter", "icon": "🎯",
     "desc": "Get {target} answers right",
     "targets": (("G", 3), ("G", 4), ("G", 5)), "cap": ("G", 1.2)},
    {"type": "perfect_rounds", "name": "Perfectionist", "icon": "💯",
     "desc": "Score 10/10 in {target} rounds", "targets": (2, 3), "cap": 1},
    {"type": "modes", "name": "Explorer", "icon": "🗺️",
     "desc": "Play {target} different games", "targets": (6, 8), "cap": 3},
    {"type": "xp", "name": "XP Hunter", "icon": "⚡",
     "desc": "Earn {target} XP",
     "targets": (("G", 40), ("G", 50), ("G", 60)), "cap": ("G", 15)},
    {"type": "speed", "name": "Speed Demon", "icon": "🚀",
     "desc": "Earn {target} speed bonuses", "targets": (30, 40), "cap": 12},
    {"type": "maths_correct", "name": "Number Ninja", "icon": "🔢",
     "desc": "Get {target} maths answers right", "targets": (50, 60, 75), "cap": 20},
    {"type": "english_correct", "name": "Word Smith", "icon": "📖",
     "desc": "Get {target} English answers right", "targets": (50, 60, 75), "cap": 20},
    {"type": "boss_wins", "name": "Boss Crusher", "icon": "👾",
     "desc": "Defeat the boss {target} times", "targets": (2, 3), "cap": 1},
    {"type": "arcade_games", "name": "Pond Patrol", "icon": "🐸",
     "desc": "Finish {target} Fly Snap games", "targets": (2, 3), "cap": 1},
    {"type": "goal_days", "name": "Steady Player", "icon": "📅",
     "desc": "Meet your daily goal on {target} days", "targets": (3, 4, 5), "cap": 1},
]

# Topic-targeted challenges: one per week, aimed at her weakest or
# journal-flagged topic. The skill (and, for raises, the starting mastery) is
# stored on the challenge because it depends on her data, not just the seed.
TOPIC_CHALLENGE_TYPES: list[dict] = [
    {"type": "topic_correct", "name": "Topic Trainer", "icon": "🎯",
     "desc": "Get {target} {topic} answers right", "targets": (20, 25, 30), "cap": 10},
    {"type": "topic_raise", "name": "Level Up", "icon": "📈",
     "desc": "Raise {topic} by {target} points", "targets": (10, 15), "cap": 5},
]
TOPIC_TYPES = {c["type"] for c in TOPIC_CHALLENGE_TYPES}
TOPIC_POOL = 2

TYPES_BY_ID = {c["type"]: c for c in CHALLENGE_TYPES + TOPIC_CHALLENGE_TYPES}
CHALLENGE_XP = 100
CHALLENGES_PER_WEEK = 3
DEFAULT_GOAL = 20
# Units shown in "(up to N a day)" — empty means a plain count.
CAP_UNITS = {"xp": " XP", "topic_raise": " points", "modes": " new"}


def _resolve(value, goal: int) -> int:
    if isinstance(value, tuple):
        return max(1, math.ceil(value[1] * goal))
    return int(value)


def resolve_targets(meta: dict, goal: int) -> tuple[list[int], int]:
    """Concrete (targets, daily_cap) for a catalogue entry and daily goal."""
    return [_resolve(t, goal) for t in meta["targets"]], _resolve(meta["cap"], goal)


def _make(week_start: str, meta: dict, rng: random.Random, goal: int) -> dict:
    targets, cap = resolve_targets(meta, goal)
    return {
        "id": f"{week_start}-{meta['type']}",
        "type": meta["type"],
        "target": rng.choice(targets),
        "daily_cap": cap,
        "progress": 0,
        "done": False,
        "days": {},
    }


def generate_week(week_start: str, profile_id: str,
                  focus_skills: list[str] | None = None,
                  mastery: dict[str, float] | None = None,
                  daily_goal: int = DEFAULT_GOAL) -> list[dict]:
    """Deterministic 3 challenges for a given week + profile.

    With ``focus_skills`` (most-needed first), one of the three targets a topic.
    """
    seed = int(hashlib.sha256(f"{week_start}:{profile_id}".encode()).hexdigest(), 16)
    rng = random.Random(seed)
    goal = max(1, int(daily_goal))
    if focus_skills:
        meta = rng.choice(TOPIC_CHALLENGE_TYPES)
        skill = rng.choice(list(focus_skills[:TOPIC_POOL]))
        topic = _make(week_start, meta, rng, goal)
        topic["skill"] = skill
        if meta["type"] == "topic_raise":
            topic["start"] = round((mastery or {}).get(skill, 0.0), 1)
            topic["last"] = topic["start"]
        picks = rng.sample(CHALLENGE_TYPES, CHALLENGES_PER_WEEK - 1)
        return [topic] + [_make(week_start, pick, rng, goal) for pick in picks]
    picks = rng.sample(CHALLENGE_TYPES, CHALLENGES_PER_WEEK)
    return [_make(week_start, pick, rng, goal) for pick in picks]


# ---------------------------------------------------------------- progress


def count(challenge: dict, amount: float, today: str) -> None:
    """Add ``amount`` for ``today``, honouring the daily cap.

    Challenges saved before v1.5 have no ``daily_cap`` and count uncapped.
    """
    if amount <= 0:
        return
    cap = challenge.get("daily_cap")
    if cap is None:
        challenge["progress"] += amount
        return
    days = challenge.setdefault("days", {})
    days[today] = days.get(today, 0) + amount
    challenge["progress"] = int(sum(min(v, cap) for v in days.values()))


def count_mode(challenge: dict, mode: str, today: str, modes_played: list[str]) -> None:
    """Explorer: each new game counts once, at most ``daily_cap`` new games a day."""
    cap = challenge.get("daily_cap")
    if cap is None:  # pre-v1.5: distinct games this week
        challenge["progress"] = len(set(modes_played))
        return
    seen = challenge.setdefault("seen", [])
    days = challenge.setdefault("days", {})
    if not mode or mode in seen or days.get(today, 0) >= cap:
        return
    seen.append(mode)
    days[today] = days.get(today, 0) + 1
    challenge["progress"] = len(seen)


def count_raise(challenge: dict, mastery_now: float, today: str) -> None:
    """Level Up: count mastery gains (drops just reset the baseline)."""
    if challenge.get("daily_cap") is None:  # pre-v1.5: net change since start
        challenge["progress"] = max(0, int(mastery_now - challenge.get("start", 0.0)))
        return
    last = challenge.get("last", challenge.get("start", 0.0))
    gain = mastery_now - last
    challenge["last"] = round(mastery_now, 2)
    if gain > 0:
        days = challenge.setdefault("days", {})
        days[today] = round(days.get(today, 0) + gain, 2)
        cap = challenge["daily_cap"]
        challenge["progress"] = int(sum(min(v, cap) for v in days.values()))


def describe(challenge: dict, today: str | None = None) -> dict:
    """Join stored progress with catalogue metadata for the card/sensor."""
    from .journal import topic_name

    meta = TYPES_BY_ID[challenge["type"]]
    skill = challenge.get("skill")
    desc = meta["desc"].format(
        target=challenge["target"], topic=topic_name(skill) if skill else ""
    )
    cap = challenge.get("daily_cap")
    out = {
        "id": challenge["id"],
        "type": challenge["type"],
        "name": meta["name"],
        "icon": meta["icon"],
        "desc": desc,
        "target": challenge["target"],
        "progress": int(min(challenge["progress"], challenge["target"])),
        "done": challenge["done"],
    }
    if skill:
        out["skill"] = skill
    if cap is not None:
        if cap > 1:
            out["desc"] = f"{desc} (up to {cap}{CAP_UNITS.get(challenge['type'], '')} a day)"
        else:
            out["desc"] = f"{desc} (one a day)" if challenge["type"] != "goal_days" else desc
        counted_today = (challenge.get("days") or {}).get(today, 0) if today else 0
        out["daily_cap"] = cap
        out["today"] = int(min(counted_today, cap))
        out["capped_today"] = bool(today) and counted_today >= cap and not challenge["done"]
    return out
