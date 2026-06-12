"""Badge definitions and checking. Pure Python.

check_badges(data, ctx) inspects the profile's stored data plus a small
event context and returns badge ids newly earned (caller stamps timestamps).

ctx keys:
  trigger:  "answer" | "round" | "goal"
  round:    dict from RoundResults (only on trigger == "round")
  comeback: True when today's goal was met the day after a streak freeze
"""
from __future__ import annotations


def _total_questions(data: dict) -> int:
    return sum(s.get("attempts", 0) for s in data.get("skills", {}).values())


def _band(data: dict, skill: str) -> int:
    return data.get("skills", {}).get(skill, {}).get("band", 1)


BADGES: list[dict] = [
    {
        "id": "first_steps", "name": "First Steps", "icon": "👣",
        "desc": "Finish your very first round",
        "hint": "Play one full round of any game",
        "predicate": lambda d, c: c.get("trigger") == "round",
    },
    {
        "id": "perfect_10", "name": "Perfect 10", "icon": "💯",
        "desc": "Get 10 out of 10 in a round",
        "hint": "Answer every question in a round correctly",
        "predicate": lambda d, c: (r := c.get("round")) is not None
        and r["total"] >= 10 and r["correct"] == r["total"],
    },
    {
        "id": "hat_trick", "name": "Hat-Trick", "icon": "🎩",
        "desc": "Reach a 3-day streak",
        "hint": "Meet your daily goal 3 days in a row",
        "predicate": lambda d, c: d["streak"]["current"] >= 3,
    },
    {
        "id": "week_warrior", "name": "Week Warrior", "icon": "🗡️",
        "desc": "Reach a 7-day streak",
        "hint": "Meet your daily goal 7 days in a row",
        "predicate": lambda d, c: d["streak"]["current"] >= 7,
    },
    {
        "id": "fortnight_hero", "name": "Fortnight Hero", "icon": "🦸",
        "desc": "Reach a 14-day streak",
        "hint": "Meet your daily goal 14 days in a row",
        "predicate": lambda d, c: d["streak"]["current"] >= 14,
    },
    {
        "id": "marathon_month", "name": "Marathon Month", "icon": "🏃",
        "desc": "Reach a 30-day streak",
        "hint": "Meet your daily goal 30 days in a row",
        "predicate": lambda d, c: d["streak"]["current"] >= 30,
    },
    {
        "id": "century_club", "name": "Century Club", "icon": "🏏",
        "desc": "Answer 100 questions",
        "hint": "Keep playing — every question counts",
        "predicate": lambda d, c: _total_questions(d) >= 100,
    },
    {
        "id": "brainiac_500", "name": "Brainiac 500", "icon": "🧠",
        "desc": "Answer 500 questions",
        "hint": "Answer 500 questions in total",
        "predicate": lambda d, c: _total_questions(d) >= 500,
    },
    {
        "id": "speedster", "name": "Speedster", "icon": "🚀",
        "desc": "8 lightning-fast answers in one round",
        "hint": "Answer quickly to earn speed bonuses",
        "predicate": lambda d, c: (r := c.get("round")) is not None
        and r["speed_bonuses"] >= 8,
    },
    {
        "id": "times_table_titan", "name": "Times Table Titan", "icon": "⚡",
        "desc": "Times tables mastered to the top level",
        "hint": "Keep playing Times Table Blitz",
        "predicate": lambda d, c: _band(d, "maths.times_tables") >= 5,
    },
    {
        "id": "fraction_wizard", "name": "Fraction Wizard", "icon": "🧙‍♀️",
        "desc": "Fractions at level 4 or higher",
        "hint": "Keep playing Fraction Lab",
        "predicate": lambda d, c: _band(d, "maths.fractions") >= 4,
    },
    {
        "id": "spelling_star", "name": "Spelling Star", "icon": "🌟",
        "desc": "Spelling at level 4 or higher",
        "hint": "Keep playing Spelling Star",
        "predicate": lambda d, c: _band(d, "english.spelling") >= 4,
    },
    {
        "id": "word_collector", "name": "Word Collector", "icon": "📚",
        "desc": "100 correct vocabulary answers",
        "hint": "Keep playing Word Wizard",
        "predicate": lambda d, c: d.get("skills", {}).get("english.vocabulary", {}).get("correct", 0) >= 100,
    },
    {
        "id": "all_rounder", "name": "All-Rounder", "icon": "🎪",
        "desc": "Play all 8 games in one week",
        "hint": "Try every game tile this week",
        "predicate": lambda d, c: len(set(d.get("weekly", {}).get("modes_played", []))) >= 8,
    },
    {
        "id": "comeback_kid", "name": "Comeback Kid", "icon": "💪",
        "desc": "Bounce back the day after a streak freeze saved you",
        "hint": "A freeze saves your streak — come back the next day!",
        "predicate": lambda d, c: bool(c.get("comeback")),
    },
    {
        "id": "high_flyer", "name": "High Flyer", "icon": "🪁",
        "desc": "Reach level 10",
        "hint": "Earn XP to level up",
        "predicate": lambda d, c: d["xp"]["level"] >= 10,
    },
    {
        "id": "shop_star", "name": "Shop Star", "icon": "🛒",
        "desc": "Money skills at level 4 or higher",
        "hint": "Keep playing Shop Keeper",
        "predicate": lambda d, c: _band(d, "maths.money") >= 4,
    },
    {
        "id": "word_architect", "name": "Word Architect", "icon": "🧱",
        "desc": "Prefixes & suffixes at level 4 or higher",
        "hint": "Keep playing Word Builder",
        "predicate": lambda d, c: _band(d, "english.affixes") >= 4,
    },
    {
        "id": "boss_slayer", "name": "Boss Slayer", "icon": "👾",
        "desc": "Defeat the boss",
        "hint": "Score 7 or more in a Boss Battle",
        "predicate": lambda d, c: (r := c.get("round")) is not None
        and r.get("mode") == "boss_battle" and r.get("boss_defeated", False),
    },
    {
        "id": "fly_snapper", "name": "Fly Snapper", "icon": "🪰",
        "desc": "Finish a game of Fly Snap",
        "hint": "Help the frog catch some flies",
        "predicate": lambda d, c: d.get("arcade", {}).get("games", 0) >= 1,
    },
    {
        "id": "frog_champion", "name": "Frog Champion", "icon": "👑",
        "desc": "Win all 6 rounds of Fly Snap",
        "hint": "Survive every round of Fly Snap",
        "predicate": lambda d, c: d.get("arcade", {}).get("wins", 0) >= 1,
    },
    {
        "id": "pond_master", "name": "Pond Master", "icon": "🌊",
        "desc": "Win Fly Snap in all three categories",
        "hint": "Win with synonyms, antonyms AND homophones",
        "predicate": lambda d, c: len(d.get("arcade", {}).get("categories_won", [])) >= 3,
    },
    {
        "id": "challenge_champ", "name": "Challenge Champ", "icon": "🏆",
        "desc": "Complete all 3 weekly challenges",
        "hint": "Finish every challenge in one week",
        "predicate": lambda d, c: (ch := d.get("weekly", {}).get("challenges"))
        and len(ch) >= 3 and all(x["done"] for x in ch),
    },
]

BADGES_BY_ID = {b["id"]: b for b in BADGES}


def check_badges(data: dict, ctx: dict) -> list[str]:
    """Return ids of badges newly earned given current data + event context."""
    earned = data.get("badges", {})
    new: list[str] = []
    for badge in BADGES:
        if badge["id"] in earned:
            continue
        try:
            if badge["predicate"](data, ctx):
                new.append(badge["id"])
        except (KeyError, TypeError):
            continue
    return new


def badge_public(badge_id: str, earned_ts: str | None = None) -> dict:
    badge = BADGES_BY_ID[badge_id]
    out = {"id": badge["id"], "name": badge["name"], "icon": badge["icon"], "desc": badge["desc"]}
    if earned_ts:
        out["ts"] = earned_ts
    else:
        out["hint"] = badge["hint"]
    return out
