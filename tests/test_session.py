"""Tests for the round/session lifecycle and XP scoring."""
import random

import pytest

from custom_components.learning_games.engine import ALL_SKILLS, MODES
from custom_components.learning_games.engine.models import SkillState
from custom_components.learning_games.engine.session import (
    XP_CORRECT,
    XP_ROUND_COMPLETE,
    XP_SPEED_BONUS,
    XP_STREAK_BONUS,
    XP_WRONG_EFFORT,
    GameSession,
    SessionError,
)
from custom_components.learning_games.engine.wordlists import load_banks

BANKS = load_banks()


def make_session(mode="number_crunch", length=10, seed=1):
    skills = {s: SkillState() for s in ALL_SKILLS}
    return GameSession("s1", mode, length, skills, BANKS, random.Random(seed))


def test_perfect_round_xp():
    session = make_session()
    for i in range(10):
        q = session.next_question()
        outcome = session.submit(q.question_id, q.answer, 1000)
        assert outcome.correct
        assert outcome.speed_bonus
    assert session.done
    results = session.results()
    assert results.correct == 10
    # 10 correct+speed, streak bonus applies from the 3rd consecutive answer.
    expected = 10 * (XP_CORRECT + XP_SPEED_BONUS) + 8 * XP_STREAK_BONUS + XP_ROUND_COMPLETE
    assert results.xp_gained == expected
    assert results.speed_bonuses == 10
    assert results.best_run_streak == 10


def test_wrong_answers_score_effort_and_reset_streak():
    session = make_session()
    for _ in range(10):
        q = session.next_question()
        outcome = session.submit(q.question_id, "definitely wrong answer", 1000)
        assert not outcome.correct
        assert outcome.xp_delta == XP_WRONG_EFFORT
        assert outcome.run_streak == 0
        assert outcome.correct_answer == q.answer
    results = session.results()
    assert results.correct == 0
    assert results.xp_gained == 10 * XP_WRONG_EFFORT + XP_ROUND_COMPLETE


def test_every_mode_runs_a_full_round():
    for i, mode in enumerate(MODES):
        session = make_session(mode=mode, seed=100 + i)
        for _ in range(10):
            q = session.next_question()
            assert q.skill in MODES[mode]["skills"]
            session.submit(q.question_id, q.answer, 2000)
        assert session.done


def test_submit_wrong_question_id_raises():
    session = make_session()
    session.next_question()
    with pytest.raises(SessionError):
        session.submit("q99", "1", 1000)


def test_submit_after_done_raises():
    session = make_session(length=3)
    for _ in range(3):
        q = session.next_question()
        session.submit(q.question_id, q.answer, 1000)
    with pytest.raises(SessionError):
        session.next_question()
    with pytest.raises(SessionError):
        session.submit("q4", "1", 1000)


def test_band_changes_reported():
    skills = {s: SkillState() for s in ALL_SKILLS}
    session = GameSession("s1", "times_tables_blitz", 10, skills, BANKS, random.Random(5))
    for _ in range(10):
        q = session.next_question()
        session.submit(q.question_id, q.answer, 1000)
    # 10 fast correct answers promote times_tables out of band 1.
    assert skills["maths.times_tables"].band >= 2
    assert any(c["skill"] == "maths.times_tables" for c in session.results().skill_changes)


def test_session_length_clamped():
    assert make_session(length=0).length > 0
    assert make_session(length=999).length <= 30


def test_xp_multiplier():
    skills = {s: SkillState() for s in ALL_SKILLS}
    session = GameSession("s1", "boss_battle", 10, skills, BANKS,
                          random.Random(3), xp_multiplier=1.5)
    q = session.next_question()
    outcome = session.submit(q.question_id, "definitely wrong", 1000)
    assert outcome.xp_delta == 2  # ceil(1 * 1.5)
    q = session.next_question()
    outcome = session.submit(q.question_id, q.answer, 59000)  # correct, slow
    assert outcome.xp_delta == 15  # ceil(10 * 1.5)
    # Finish the round; completion bonus is ceil(20 * 1.5) = 30.
    xp_before = session.xp
    extra = 0
    for _ in range(8):
        q = session.next_question()
        out = session.submit(q.question_id, "wrong again", 1000)
        extra += out.xp_delta
    assert session.results().xp_gained == xp_before + extra + 30


def test_boss_battle_targets_weakest_skills():
    skills = {s: SkillState(mastery=80.0) for s in ALL_SKILLS}
    weak = ["maths.money", "english.affixes", "maths.fractions", "english.spelling"]
    for i, s in enumerate(weak):
        skills[s] = SkillState(mastery=float(i))
    rng = random.Random(11)
    from custom_components.learning_games.engine import pick_skill

    picked = {pick_skill("boss_battle", skills, rng) for _ in range(200)}
    assert picked == set(weak)


def test_no_repeated_word_questions_in_round():
    session = make_session(mode="spelling_star", length=10, seed=2)
    seen = []
    for _ in range(10):
        q = session.next_question()
        seen.append(q.word_key)
        session.submit(q.question_id, q.answer, 1000)
    assert len(seen) == len(set(seen))
