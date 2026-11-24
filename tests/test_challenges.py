"""Tests for deterministic weekly challenge generation."""
from custom_components.learning_games.engine import challenges


def test_deterministic_per_week_and_profile():
    a = challenges.generate_week("2026-06-08", "profile1")
    b = challenges.generate_week("2026-06-08", "profile1")
    assert a == b


def test_different_weeks_or_profiles_differ():
    base = challenges.generate_week("2026-06-08", "profile1")
    differing = 0
    for other in (
        challenges.generate_week("2026-06-15", "profile1"),
        challenges.generate_week("2026-06-08", "profile2"),
        challenges.generate_week("2026-06-22", "profile1"),
    ):
        if other != base:
            differing += 1
    assert differing >= 2


def test_three_distinct_types_with_valid_targets():
    week = challenges.generate_week("2026-06-08", "abc123")
    assert len(week) == challenges.CHALLENGES_PER_WEEK
    types = [c["type"] for c in week]
    assert len(set(types)) == 3
    for challenge in week:
        meta = challenges.TYPES_BY_ID[challenge["type"]]
        targets, cap = challenges.resolve_targets(meta, challenges.DEFAULT_GOAL)
        assert challenge["target"] in targets
        assert challenge["daily_cap"] == cap
        assert challenge["progress"] == 0
        assert challenge["done"] is False
        assert challenge["id"].startswith("2026-06-08-")


def test_describe_interpolates_and_caps():
    challenge = {"id": "w-xp", "type": "xp", "target": 400, "progress": 950, "done": True}
    desc = challenges.describe(challenge)
    assert desc["desc"] == "Earn 400 XP"  # pre-v1.5 challenge: no cap suffix
    assert "daily_cap" not in desc
    assert desc["progress"] == 400  # capped at target
    assert desc["icon"] and desc["name"]


def test_no_focus_output_is_unchanged():
    week = challenges.generate_week("2026-06-08", "abc123")
    assert week == challenges.generate_week("2026-06-08", "abc123", None)
    assert not any(c["type"] in challenges.TOPIC_TYPES for c in week)


def test_focus_adds_exactly_one_topic_challenge():
    focus = ["maths.fractions", "english.spelling", "maths.money"]
    mastery = {"maths.fractions": 11.0, "english.spelling": 0.0}
    seen = set()
    for i in range(30):
        week = challenges.generate_week(f"2026-06-{i:02d}", "abc", focus, mastery)
        assert week == challenges.generate_week(f"2026-06-{i:02d}", "abc", focus, mastery)
        topic = [c for c in week if c["type"] in challenges.TOPIC_TYPES]
        assert len(topic) == 1 and len(week) == 3
        assert len({c["type"] for c in week}) == 3
        t = topic[0]
        assert t["skill"] in focus[:2]
        assert t["target"] in challenges.TYPES_BY_ID[t["type"]]["targets"]
        if t["type"] == "topic_raise":
            assert t["start"] == mastery[t["skill"]]
        seen.add(t["type"])
    assert seen == challenges.TOPIC_TYPES


def test_describe_topic_challenges():
    d = challenges.describe({"id": "w-topic_correct", "type": "topic_correct", "target": 15,
                             "progress": 4, "done": False, "skill": "maths.fractions"})
    assert d["desc"] == "Get 15 Fractions answers right"
    assert d["skill"] == "maths.fractions"
    d = challenges.describe({"id": "w-topic_raise", "type": "topic_raise", "target": 5,
                             "progress": 2, "done": False, "skill": "english.spelling",
                             "start": 0.0})
    assert d["desc"] == "Raise Spelling by 5 points"
    assert d["name"] == "Level Up"
    generic = challenges.describe({"id": "w-xp", "type": "xp", "target": 400,
                                   "progress": 1, "done": False})
    assert "skill" not in generic


# ---------------------------------------------------------------- v1.5: daily caps

import math

import pytest


@pytest.mark.parametrize("goal", [5, 20, 30, 60, 100])
def test_every_challenge_takes_at_least_two_days(goal):
    for meta in challenges.CHALLENGE_TYPES + challenges.TOPIC_CHALLENGE_TYPES:
        targets, cap = challenges.resolve_targets(meta, goal)
        for target in targets:
            assert math.ceil(target / cap) >= 2, (meta["type"], goal, target, cap)


def test_lizzie_targets_take_three_to_four_days():
    targets, cap = challenges.resolve_targets(challenges.TYPES_BY_ID["questions"], 30)
    assert targets == [120, 150, 180] and cap == 45
    targets, cap = challenges.resolve_targets(challenges.TYPES_BY_ID["xp"], 30)
    assert targets == [1200, 1500, 1800] and cap == 450


def test_count_caps_each_day():
    ch = {"id": "w-questions", "type": "questions", "target": 120, "daily_cap": 45,
          "progress": 0, "done": False, "days": {}}
    challenges.count(ch, 198, "2026-11-30")  # a marathon Monday
    assert ch["progress"] == 45
    challenges.count(ch, 10, "2026-11-30")
    assert ch["progress"] == 45
    challenges.count(ch, 30, "2026-12-01")
    assert ch["progress"] == 75
    d = challenges.describe(ch, "2026-12-01")
    assert d["today"] == 30 and d["capped_today"] is False
    assert d["desc"] == "Answer 120 questions (up to 45 a day)"
    assert challenges.describe(ch, "2026-11-30")["capped_today"] is True


def test_uncapped_legacy_challenge_counts_as_before():
    ch = {"id": "w-questions", "type": "questions", "target": 80, "progress": 0, "done": False}
    challenges.count(ch, 90, "2026-11-23")
    assert ch["progress"] == 90


def test_explorer_three_new_games_a_day():
    ch = {"id": "w-modes", "type": "modes", "target": 6, "daily_cap": 3,
          "progress": 0, "done": False, "days": {}}
    for m in ["a", "b", "b", "c", "d", "e"]:
        challenges.count_mode(ch, m, "day1", [])
    assert ch["progress"] == 3 and ch["seen"] == ["a", "b", "c"]
    challenges.count_mode(ch, "d", "day2", [])
    challenges.count_mode(ch, "a", "day2", [])  # already counted
    assert ch["progress"] == 4


def test_level_up_counts_gains_only_capped_daily():
    ch = {"id": "w-topic_raise", "type": "topic_raise", "target": 10, "daily_cap": 5,
          "progress": 0, "done": False, "days": {}, "skill": "english.spelling",
          "start": 0.0, "last": 0.0}
    challenges.count_raise(ch, 9.0, "day1")
    assert ch["progress"] == 5
    challenges.count_raise(ch, 6.0, "day2")  # a dip resets the baseline
    assert ch["progress"] == 5
    challenges.count_raise(ch, 9.5, "day2")
    assert ch["progress"] == 8
    assert challenges.describe(ch, "day2")["desc"] == (
        "Raise Spelling by 10 points (up to 5 points a day)")


def test_goal_days_and_one_a_day_wording():
    ch = {"id": "w-goal_days", "type": "goal_days", "target": 4, "daily_cap": 1,
          "progress": 0, "done": False, "days": {}}
    assert challenges.describe(ch, "d")["desc"] == "Meet your daily goal on 4 days"
    ch2 = {"id": "w-boss_wins", "type": "boss_wins", "target": 2, "daily_cap": 1,
           "progress": 0, "done": False, "days": {}}
    assert challenges.describe(ch2, "d")["desc"] == "Defeat the boss 2 times (one a day)"
