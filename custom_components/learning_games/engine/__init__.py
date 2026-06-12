"""Game engine facade: mode registry and question dispatch. Pure Python."""
from __future__ import annotations

import random

from . import english, maths
from .models import Question, SkillState
from .wordlists import WordBanks

MODES: dict[str, dict] = {
    "times_tables_blitz": {
        "name": "Times Table Blitz", "subject": "maths", "emoji": "⚡",
        "skills": ["maths.times_tables"],
    },
    "number_crunch": {
        "name": "Number Crunch", "subject": "maths", "emoji": "🔢",
        "skills": ["maths.addition", "maths.subtraction", "maths.place_value", "maths.rounding"],
    },
    "big_multiply": {
        "name": "Big Multiply", "subject": "maths", "emoji": "✖️",
        "skills": ["maths.long_multiplication", "maths.division"],
    },
    "fraction_lab": {
        "name": "Fraction Lab", "subject": "maths", "emoji": "🧪",
        "skills": ["maths.fractions", "maths.decimals", "maths.negative_numbers"],
    },
    "shop_keeper": {
        "name": "Shop Keeper", "subject": "maths", "emoji": "🛒",
        "skills": ["maths.money"],
    },
    "spelling_star": {
        "name": "Spelling Star", "subject": "english", "emoji": "⭐",
        "skills": ["english.spelling"],
    },
    "word_wizard": {
        "name": "Word Wizard", "subject": "english", "emoji": "🧙",
        "skills": ["english.vocabulary"],
    },
    "word_detective": {
        "name": "Word Detective", "subject": "english", "emoji": "🔍",
        "skills": ["english.word_classes", "english.punctuation"],
    },
    "tricky_twins": {
        "name": "Tricky Twins", "subject": "english", "emoji": "👯",
        "skills": ["english.homophones"],
    },
    "word_builder": {
        "name": "Word Builder", "subject": "english", "emoji": "🧱",
        "skills": ["english.affixes"],
    },
    "boss_battle": {
        "name": "Boss Battle", "subject": "challenge", "emoji": "👾",
        "skills": [],  # filled below: draws from every skill
    },
}

ALL_SKILLS: list[str] = sorted({skill for mode in MODES.values() for skill in mode["skills"]})
MODES["boss_battle"]["skills"] = list(ALL_SKILLS)
BOSS_WEAKEST_POOL = 4
BOSS_XP_MULTIPLIER = 1.5
BOSS_DEFEAT_THRESHOLD = 7
MATHS_SKILLS = [s for s in ALL_SKILLS if s.startswith("maths.")]
ENGLISH_SKILLS = [s for s in ALL_SKILLS if s.startswith("english.")]

# Share of questions steered toward the mode's two weakest skills.
FOCUS_WEIGHT = 0.7


def pick_skill(mode_id: str, skills: dict[str, SkillState], rng: random.Random) -> str:
    """Pick the next skill for a mode: 70% from the two lowest-mastery skills."""
    if mode_id == "boss_battle":
        weakest = sorted(skills, key=lambda s: skills[s].mastery)[:BOSS_WEAKEST_POOL]
        return rng.choice(weakest)
    mode_skills = MODES[mode_id]["skills"]
    if len(mode_skills) == 1:
        return mode_skills[0]
    by_mastery = sorted(mode_skills, key=lambda s: skills[s].mastery)
    if rng.random() < FOCUS_WEIGHT:
        return rng.choice(by_mastery[:2])
    return rng.choice(mode_skills)


def generate_question(skill: str, band: int, rng: random.Random,
                      banks: WordBanks | None, exclude: set[str]) -> Question:
    if skill.startswith("maths."):
        return maths.generate(skill, band, rng)
    if banks is None:
        raise ValueError("English questions need word banks")
    return english.generate(skill, band, rng, banks, exclude)
