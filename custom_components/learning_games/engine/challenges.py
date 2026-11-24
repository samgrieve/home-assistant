"""Weekly challenges: 3 per ISO week, deterministic per profile. Pure Python.

Definitions are regenerated from sha256(week_start:profile_id) so they survive
restarts identically; only progress/done flags live in storage
(weekly["challenges"]).
"""
from __future__ import annotations

import hashlib
import random

CHALLENGE_TYPES: list[dict] = [
    {"type": "questions", "name": "Question Quest", "icon": "❓",
     "desc": "Answer {target} questions", "targets": (60, 80, 100)},
    {"type": "correct", "name": "Sharp Shooter", "icon": "🎯",
     "desc": "Get {target} answers right", "targets": (50, 65, 80)},
    {"type": "perfect_rounds", "name": "Perfectionist", "icon": "💯",
     "desc": "Score 10/10 in {target} round(s)", "targets": (1, 2, 3)},
    {"type": "modes", "name": "Explorer", "icon": "🗺️",
     "desc": "Play {target} different games", "targets": (5, 6, 8)},
    {"type": "xp", "name": "XP Hunter", "icon": "⚡",
     "desc": "Earn {target} XP", "targets": (400, 550, 700)},
    {"type": "speed", "name": "Speed Demon", "icon": "🚀",
     "desc": "Earn {target} speed bonuses", "targets": (15, 25, 35)},
    {"type": "maths_correct", "name": "Number Ninja", "icon": "🔢",
     "desc": "Get {target} maths answers right", "targets": (25, 35, 50)},
    {"type": "english_correct", "name": "Word Smith", "icon": "📖",
     "desc": "Get {target} English answers right", "targets": (25, 35, 50)},
    {"type": "boss_wins", "name": "Boss Crusher", "icon": "👾",
     "desc": "Defeat the boss {target} time(s)", "targets": (1, 2)},
    {"type": "arcade_games", "name": "Pond Patrol", "icon": "🐸",
     "desc": "Finish {target} Fly Snap game(s)", "targets": (1, 2, 3)},
]

# Topic-targeted challenges: one per week, aimed at her weakest or
# journal-flagged topic. The skill (and, for raises, the starting mastery) is
# stored on the challenge because it depends on her data, not just the seed.
TOPIC_CHALLENGE_TYPES: list[dict] = [
    {"type": "topic_correct", "name": "Topic Trainer", "icon": "🎯",
     "desc": "Get {target} {topic} answers right", "targets": (10, 15, 20)},
    {"type": "topic_raise", "name": "Level Up", "icon": "📈",
     "desc": "Raise {topic} by {target} points", "targets": (5, 8)},
]
TOPIC_TYPES = {c["type"] for c in TOPIC_CHALLENGE_TYPES}
TOPIC_POOL = 2

TYPES_BY_ID = {c["type"]: c for c in CHALLENGE_TYPES + TOPIC_CHALLENGE_TYPES}
CHALLENGE_XP = 100
CHALLENGES_PER_WEEK = 3


def generate_week(week_start: str, profile_id: str,
                  focus_skills: list[str] | None = None,
                  mastery: dict[str, float] | None = None) -> list[dict]:
    """Deterministic 3 challenges for a given week + profile.

    With ``focus_skills`` (most-needed first), one of the three targets a topic.
    """
    seed = int(hashlib.sha256(f"{week_start}:{profile_id}".encode()).hexdigest(), 16)
    rng = random.Random(seed)
    if focus_skills:
        meta = rng.choice(TOPIC_CHALLENGE_TYPES)
        skill = rng.choice(list(focus_skills[:TOPIC_POOL]))
        topic = {
            "id": f"{week_start}-{meta['type']}",
            "type": meta["type"],
            "target": rng.choice(meta["targets"]),
            "progress": 0,
            "done": False,
            "skill": skill,
        }
        if meta["type"] == "topic_raise":
            topic["start"] = round((mastery or {}).get(skill, 0.0), 1)
        picks = rng.sample(CHALLENGE_TYPES, CHALLENGES_PER_WEEK - 1)
        return [topic] + [_generic(week_start, pick, rng) for pick in picks]
    picks = rng.sample(CHALLENGE_TYPES, CHALLENGES_PER_WEEK)
    return [
        {
            "id": f"{week_start}-{pick['type']}",
            "type": pick["type"],
            "target": rng.choice(pick["targets"]),
            "progress": 0,
            "done": False,
        }
        for pick in picks
    ]


def _generic(week_start: str, pick: dict, rng: random.Random) -> dict:
    return {
        "id": f"{week_start}-{pick['type']}",
        "type": pick["type"],
        "target": rng.choice(pick["targets"]),
        "progress": 0,
        "done": False,
    }


def describe(challenge: dict) -> dict:
    """Join stored progress with catalogue metadata for the card/sensor."""
    from .journal import topic_name

    meta = TYPES_BY_ID[challenge["type"]]
    skill = challenge.get("skill")
    out = {
        "id": challenge["id"],
        "type": challenge["type"],
        "name": meta["name"],
        "icon": meta["icon"],
        "desc": meta["desc"].format(
            target=challenge["target"], topic=topic_name(skill) if skill else ""
        ),
        "target": challenge["target"],
        "progress": int(min(challenge["progress"], challenge["target"])),
        "done": challenge["done"],
    }
    if skill:
        out["skill"] = skill
    return out
