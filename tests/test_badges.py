"""Tests for badge predicates."""
from custom_components.learning_games.engine.badges import BADGES, badge_public, check_badges


def base_data(**overrides):
    data = {
        "xp": {"total": 0, "level": 1},
        "streak": {"current": 0, "best": 0, "last_goal_date": None, "freezes": 0},
        "weekly": {"modes_played": []},
        "skills": {},
        "badges": {},
    }
    data.update(overrides)
    return data


def test_first_steps_on_round():
    assert "first_steps" in check_badges(base_data(), {"trigger": "round", "round": {
        "total": 10, "correct": 4, "speed_bonuses": 0}})
    assert "first_steps" not in check_badges(base_data(), {"trigger": "answer"})


def test_perfect_10_and_speedster():
    ctx = {"trigger": "round", "round": {"total": 10, "correct": 10, "speed_bonuses": 9}}
    new = check_badges(base_data(), ctx)
    assert "perfect_10" in new
    assert "speedster" in new
    ctx = {"trigger": "round", "round": {"total": 10, "correct": 9, "speed_bonuses": 7}}
    new = check_badges(base_data(), ctx)
    assert "perfect_10" not in new
    assert "speedster" not in new


def test_streak_badges():
    data = base_data(streak={"current": 14, "best": 14, "last_goal_date": None, "freezes": 0})
    new = check_badges(data, {"trigger": "goal"})
    assert {"hat_trick", "week_warrior", "fortnight_hero"} <= set(new)
    assert "marathon_month" not in new


def test_question_count_badges():
    data = base_data(skills={
        "maths.addition": {"band": 2, "attempts": 80, "correct": 60},
        "english.spelling": {"band": 1, "attempts": 25, "correct": 20},
    })
    new = check_badges(data, {"trigger": "answer"})
    assert "century_club" in new
    assert "brainiac_500" not in new


def test_skill_band_badges():
    data = base_data(skills={
        "maths.times_tables": {"band": 5, "attempts": 1, "correct": 1},
        "maths.fractions": {"band": 4, "attempts": 1, "correct": 1},
        "english.spelling": {"band": 4, "attempts": 1, "correct": 1},
        "english.vocabulary": {"band": 1, "attempts": 120, "correct": 100},
    })
    new = check_badges(data, {"trigger": "answer"})
    assert {"times_table_titan", "fraction_wizard", "spelling_star", "word_collector"} <= set(new)


def test_all_rounder_and_high_flyer_and_comeback():
    data = base_data(
        xp={"total": 5000, "level": 10},
        weekly={"modes_played": [
            "times_tables_blitz", "number_crunch", "big_multiply", "fraction_lab",
            "spelling_star", "word_wizard", "word_detective", "tricky_twins"]},
    )
    new = check_badges(data, {"trigger": "goal", "comeback": True})
    assert {"all_rounder", "high_flyer", "comeback_kid"} <= set(new)


def test_earned_badges_not_re_earned():
    data = base_data(badges={"first_steps": "2026-01-01T00:00:00"})
    new = check_badges(data, {"trigger": "round", "round": {
        "total": 5, "correct": 1, "speed_bonuses": 0}})
    assert "first_steps" not in new


def test_badge_metadata_complete():
    assert len(BADGES) == 16
    for badge in BADGES:
        for key in ("id", "name", "icon", "desc", "hint", "predicate"):
            assert badge[key], f"{badge['id']} missing {key}"
    public = badge_public("perfect_10")
    assert "hint" in public and "ts" not in public
    public = badge_public("perfect_10", "2026-01-01T00:00:00")
    assert public["ts"] and "hint" not in public
