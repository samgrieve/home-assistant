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
    "todays_focus": {
        "name": "Today's Focus", "subject": "challenge", "emoji": "🎯",
        "skills": [],  # filled below: draws from every skill
    },
    "boss_battle": {
        "name": "Boss Battle", "subject": "challenge", "emoji": "👾",
        "skills": [],  # filled below: draws from every skill
    },
}

ALL_SKILLS: list[str] = sorted({skill for mode in MODES.values() for skill in mode["skills"]})
MODES["boss_battle"]["skills"] = list(ALL_SKILLS)
MODES["todays_focus"]["skills"] = list(ALL_SKILLS)
BOSS_WEAKEST_POOL = 4
BOSS_XP_MULTIPLIER = 1.5
BOSS_DEFEAT_THRESHOLD = 7
MATHS_SKILLS = [s for s in ALL_SKILLS if s.startswith("maths.")]
ENGLISH_SKILLS = [s for s in ALL_SKILLS if s.startswith("english.")]

# Share of questions steered toward the mode's two weakest skills.
FOCUS_WEIGHT = 0.7


# Journal "tricky" ratings lower a skill's effective mastery by this many points
# per unit of focus weight, so it is picked a little more often everywhere.
JOURNAL_MASTERY_PENALTY = 15
# Today's Focus: share of questions from the weakest/flagged skills (rest are
# easy wins from her strongest skills so the round stays fun).
TODAYS_FOCUS_WEAK_SHARE = 0.7
TODAYS_FOCUS_POOL = 3
JOURNAL_PRIORITY_WEIGHT = 0.6


def effective_mastery(skill: str, skills: dict[str, SkillState],
                      focus: dict[str, float] | None) -> float:
    return skills[skill].mastery - JOURNAL_MASTERY_PENALTY * (focus or {}).get(skill, 0.0)


def focus_priority(skill: str, skills: dict[str, SkillState],
                   focus: dict[str, float] | None) -> float:
    """Higher = needs practice more. Untouched skills count as weak."""
    state = skills[skill]
    weakness = (100 - state.mastery) / 100
    if state.attempts == 0:
        weakness = max(weakness, 0.9)
    return weakness + JOURNAL_PRIORITY_WEIGHT * (focus or {}).get(skill, 0.0)


def focus_ranking(skills: dict[str, SkillState], focus: dict[str, float] | None) -> list[str]:
    return sorted(skills, key=lambda s: (-focus_priority(s, skills, focus), s))


def pick_focus_skill(skills: dict[str, SkillState], focus: dict[str, float] | None,
                     rng: random.Random) -> str:
    """Today's Focus: ~70% weakest/journal-flagged skills, ~30% easy wins."""
    if rng.random() < TODAYS_FOCUS_WEAK_SHARE:
        return rng.choice(focus_ranking(skills, focus)[:TODAYS_FOCUS_POOL])
    practised = [s for s in skills if skills[s].attempts > 0] or list(skills)
    strongest = sorted(practised, key=lambda s: (-skills[s].mastery, s))[:TODAYS_FOCUS_POOL]
    return rng.choice(strongest)


def pick_skill(mode_id: str, skills: dict[str, SkillState], rng: random.Random,
               focus: dict[str, float] | None = None) -> str:
    """Pick the next skill for a mode: 70% from the two lowest-mastery skills.

    ``focus`` (journal weights) nudges flagged skills down the mastery order.
    """
    if mode_id == "todays_focus":
        return pick_focus_skill(skills, focus, rng)
    if mode_id == "boss_battle":
        weakest = sorted(skills, key=lambda s: effective_mastery(s, skills, focus))[
            :BOSS_WEAKEST_POOL
        ]
        return rng.choice(weakest)
    mode_skills = MODES[mode_id]["skills"]
    if len(mode_skills) == 1:
        return mode_skills[0]
    by_mastery = sorted(mode_skills, key=lambda s: effective_mastery(s, skills, focus))
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
