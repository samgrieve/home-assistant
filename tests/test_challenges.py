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
