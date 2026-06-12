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
        assert challenge["target"] in meta["targets"]
        assert challenge["progress"] == 0
        assert challenge["done"] is False
        assert challenge["id"].startswith("2026-06-08-")


def test_describe_interpolates_and_caps():
    challenge = {"id": "w-xp", "type": "xp", "target": 400, "progress": 950, "done": True}
    desc = challenges.describe(challenge)
    assert desc["desc"] == "Earn 400 XP"
    assert desc["progress"] == 400  # capped at target
    assert desc["icon"] and desc["name"]
