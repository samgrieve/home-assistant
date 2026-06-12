"""Tests for the mastery-band adaptive system."""
from custom_components.learning_games.engine import adaptive
from custom_components.learning_games.engine.models import SkillState

SKILL = "maths.times_tables"  # target 7000 ms


def test_promotion_after_fast_accurate_window():
    state = SkillState()
    changed = None
    for _ in range(8):
        changed = adaptive.record_answer(state, SKILL, True, 2000)
    assert changed == 2
    assert state.band == 2
    assert state.window == []  # cleared on band change


def test_no_promotion_when_slow():
    state = SkillState()
    for _ in range(10):
        assert adaptive.record_answer(state, SKILL, True, 20000) is None
    assert state.band == 1


def test_no_promotion_at_max_band():
    state = SkillState(band=5)
    for _ in range(10):
        assert adaptive.record_answer(state, SKILL, True, 1000) is None
    assert state.band == 5


def test_demotion_after_poor_window():
    state = SkillState(band=3)
    changed = None
    for _ in range(6):
        changed = adaptive.record_answer(state, SKILL, False, 5000)
    assert changed == 2
    assert state.band == 2
    assert state.window == []


def test_no_demotion_below_band_one():
    state = SkillState(band=1)
    for _ in range(10):
        assert adaptive.record_answer(state, SKILL, False, 5000) is None
    assert state.band == 1


def test_mastery_bounded_and_monotonic_signal():
    state = SkillState()
    for _ in range(50):
        adaptive.record_answer(state, SKILL, True, 2000)
    high = state.mastery
    assert 0 <= high <= 100
    assert high > 40  # plenty of correct fast answers must read as progress

    state2 = SkillState()
    for _ in range(5):
        adaptive.record_answer(state2, SKILL, False, 5000)
    assert state2.mastery < high


def test_window_capped_at_ten():
    state = SkillState(band=5)  # max band so no promotion clears the window
    for _ in range(25):
        adaptive.record_answer(state, SKILL, True, 50000)
    assert len(state.window) == 10


def test_elapsed_clamped():
    state = SkillState()
    adaptive.record_answer(state, SKILL, True, -5)
    adaptive.record_answer(state, SKILL, True, 10**9)
    assert state.window[0]["t"] == 300
    assert state.window[1]["t"] == 60000


def test_roundtrip_serialisation():
    state = SkillState(band=4, mastery=66.6, attempts=12, correct=9)
    adaptive.record_answer(state, SKILL, True, 1500)
    again = SkillState.from_dict(state.to_dict())
    assert again.band == state.band
    assert again.attempts == state.attempts
    assert again.window == state.window
