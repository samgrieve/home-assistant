"""Daily challenges engine."""
from custom_components.learning_games.engine import daily


def test_deterministic_with_one_topic_challenge():
    a = daily.generate_day("2026-11-25", "p1", ["english.spelling", "maths.money"], ["x"])
    assert a == daily.generate_day("2026-11-25", "p1", ["english.spelling", "maths.money"], ["x"])
    assert len(a) == 3 and len({c["type"] for c in a}) == 3
    assert a[0]["type"] == "topic_today" and a[0]["skill"] in ("english.spelling", "maths.money")
    assert all(c["id"].startswith("2026-11-25-") for c in a)


def test_new_game_dropped_when_everything_played():
    for d in range(1, 29):
        day = f"2026-11-{d:02d}"
        assert all(c["type"] != "new_game" for c in daily.generate_day(day, "p", ["a.b"], []))
    seen = {c["type"] for d in range(1, 29)
            for c in daily.generate_day(f"2026-11-{d:02d}", "p", ["a.b"], ["boss_battle"])}
    assert "new_game" in seen


def test_apply_signals():
    topic = {"id": "t", "type": "topic_today", "target": 5, "progress": 0, "done": False,
             "skill": "maths.money"}
    for _ in range(4):
        assert not daily.apply(topic, {"correct:maths.money": 1, "correct:maths.fractions": 0})
    assert not daily.apply(topic, {"correct:maths.fractions": 1})
    assert daily.apply(topic, {"correct:maths.money": 1}) and topic["done"]
    assert not daily.apply(topic, {"correct:maths.money": 1})  # finishes once

    run = {"id": "r", "type": "streak_run", "target": 5, "progress": 0, "done": False}
    daily.apply(run, {"run_streak": 4})
    daily.apply(run, {"run_streak": 0})
    assert run["progress"] == 4
    assert daily.apply(run, {"run_streak": 5})

    good = {"id": "g", "type": "good_round", "target": 1, "progress": 0, "done": False}
    assert not daily.apply(good, {"round_correct": 7})
    assert daily.apply(good, {"round_correct": 8})

    for kind, sig in (("focus_round", {"round_mode": "todays_focus"}),
                      ("journal", {"journal": 1}), ("new_game", {"new_game": True})):
        ch = {"id": kind, "type": kind, "target": 1, "progress": 0, "done": False}
        assert not daily.apply(ch, {"round_mode": "number_crunch"})
        assert daily.apply(ch, sig)

    fly = {"id": "f", "type": "fly_snap", "target": 3, "progress": 0, "done": False}
    daily.apply(fly, {"fly_rounds": 2})
    assert daily.apply(fly, {"fly_rounds": 3})


def test_describe():
    d = daily.describe({"id": "x", "type": "topic_today", "target": 5, "progress": 7,
                        "done": True, "skill": "english.spelling"})
    assert d["desc"] == "Get 5 Spelling answers right" and d["progress"] == 5
