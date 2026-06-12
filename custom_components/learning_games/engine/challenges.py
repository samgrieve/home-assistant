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

TYPES_BY_ID = {c["type"]: c for c in CHALLENGE_TYPES}
CHALLENGE_XP = 100
CHALLENGES_PER_WEEK = 3


def generate_week(week_start: str, profile_id: str) -> list[dict]:
    """Deterministic 3 challenges for a given week + profile."""
    seed = int(hashlib.sha256(f"{week_start}:{profile_id}".encode()).hexdigest(), 16)
    rng = random.Random(seed)
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


def describe(challenge: dict) -> dict:
    """Join stored progress with catalogue metadata for the card/sensor."""
    meta = TYPES_BY_ID[challenge["type"]]
    return {
        "id": challenge["id"],
        "type": challenge["type"],
        "name": meta["name"],
        "icon": meta["icon"],
        "desc": meta["desc"].format(target=challenge["target"]),
        "target": challenge["target"],
        "progress": min(challenge["progress"], challenge["target"]),
        "done": challenge["done"],
    }
