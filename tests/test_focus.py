"""Today's Focus and journal-weighted skill selection."""
import random
from collections import Counter

from custom_components.learning_games.engine import (
    ALL_SKILLS,
    MODES,
    focus_ranking,
    pick_focus_skill,
    pick_skill,
)
from custom_components.learning_games.engine.models import SkillState


def _skills():
    skills = {s: SkillState() for s in ALL_SKILLS}
    for i, s in enumerate(ALL_SKILLS):
        skills[s].mastery = 20 + i * 4  # all practised, distinct mastery
        skills[s].attempts = 50
    return skills


def test_focus_mode_registered():
    assert MODES["todays_focus"]["skills"] == ALL_SKILLS
    assert MODES["todays_focus"]["subject"] == "challenge"


def test_journal_flag_jumps_the_queue():
    skills = _skills()
    strong = ALL_SKILLS[-1]  # highest mastery
    assert focus_ranking(skills, {})[0] != strong
    assert focus_ranking(skills, {strong: 2.0})[0] == strong


def test_unpractised_skills_count_as_weak():
    skills = _skills()
    fresh = ALL_SKILLS[-1]
    skills[fresh].attempts = 0
    skills[fresh].mastery = 0
    assert fresh in focus_ranking(skills, {})[:3]


def test_focus_mix_of_weak_and_easy_wins():
    skills = _skills()
    rng = random.Random(7)
    picks = Counter(pick_focus_skill(skills, {"maths.fractions": 2.0}, rng) for _ in range(2000))
    weak_pool = set(focus_ranking(skills, {"maths.fractions": 2.0})[:3])
    strong_pool = set(sorted(ALL_SKILLS, key=lambda s: -skills[s].mastery)[:3])
    weak_share = sum(picks[s] for s in weak_pool) / 2000
    strong_share = sum(picks[s] for s in strong_pool) / 2000
    assert 0.62 < weak_share < 0.78
    assert 0.22 < strong_share < 0.38
    assert picks["maths.fractions"] > 350
    assert set(picks) <= weak_pool | strong_pool


def test_focus_works_with_empty_profile():
    skills = {s: SkillState() for s in ALL_SKILLS}
    rng = random.Random(1)
    for _ in range(50):
        assert pick_focus_skill(skills, None, rng) in ALL_SKILLS


def test_pick_skill_unchanged_without_focus():
    skills = _skills()
    a = [pick_skill("number_crunch", skills, random.Random(3)) for _ in range(1)]
    b = [pick_skill("number_crunch", skills, random.Random(3), None) for _ in range(1)]
    assert a == b
    rng = random.Random(5)
    picks = Counter(pick_skill("number_crunch", skills, rng) for _ in range(1000))
    weakest_two = sorted(MODES["number_crunch"]["skills"], key=lambda s: skills[s].mastery)[:2]
    assert sum(picks[s] for s in weakest_two) > 700


def test_journal_focus_steers_existing_modes_and_boss():
    skills = _skills()
    strongest = max(MODES["number_crunch"]["skills"], key=lambda s: skills[s].mastery)
    rng = random.Random(9)
    picks = Counter(
        pick_skill("number_crunch", skills, rng, {strongest: 3.0}) for _ in range(1000)
    )
    assert picks[strongest] > 300
    mid = ALL_SKILLS[5]  # 40% mastery: not in the boss's weakest four...
    assert mid not in {pick_skill("boss_battle", skills, random.Random(i)) for i in range(200)}
    # ...until she says it was tricky.
    boss = {pick_skill("boss_battle", skills, random.Random(i), {mid: 3.0}) for i in range(200)}
    assert mid in boss
