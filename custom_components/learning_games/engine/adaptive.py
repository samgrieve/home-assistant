"""Mastery-band adaptive difficulty. Pure Python — no Home Assistant imports.

Each skill has a band 1-5 and a rolling window of the last 10 answers.
- Promote: >= 8 answers in window, >= 80% correct, median time <= skill target.
- Demote:  >= 6 answers in window, <= 40% correct.
The window is cleared after a band change so evidence restarts at the new level.
Mastery (0-100) is an EWMA of band progress + window accuracy, so the card and
sensors show a smooth score rather than a band-change sawtooth.
"""
from __future__ import annotations

from statistics import median

from .models import SkillState

MIN_BAND = 1
MAX_BAND = 5

WINDOW_SIZE = 10
PROMOTE_MIN_ANSWERS = 8
PROMOTE_ACCURACY = 0.8
DEMOTE_MIN_ANSWERS = 6
DEMOTE_ACCURACY = 0.4
EWMA_ALPHA = 0.2

# Per-skill "fast enough" targets in ms (median response time gate for promotion
# and the speed-bonus threshold shown to the card).
TARGET_MS = {
    "maths.times_tables": 7000,
    "maths.addition": 15000,
    "maths.subtraction": 15000,
    "maths.long_multiplication": 30000,
    "maths.division": 25000,
    "maths.fractions": 15000,
    "maths.decimals": 12000,
    "maths.rounding": 10000,
    "maths.place_value": 10000,
    "maths.negative_numbers": 12000,
    "english.spelling": 15000,
    "english.vocabulary": 12000,
    "english.word_classes": 10000,
    "english.homophones": 10000,
    "english.punctuation": 12000,
}
DEFAULT_TARGET_MS = 12000


def target_ms(skill: str) -> int:
    return TARGET_MS.get(skill, DEFAULT_TARGET_MS)


def record_answer(state: SkillState, skill: str, correct: bool, elapsed_ms: int) -> int | None:
    """Record one answer; return the new band if it changed, else None."""
    elapsed_ms = max(300, min(60000, int(elapsed_ms)))
    state.attempts += 1
    if correct:
        state.correct += 1
    state.window.append({"c": 1 if correct else 0, "t": elapsed_ms})
    if len(state.window) > WINDOW_SIZE:
        state.window = state.window[-WINDOW_SIZE:]

    new_band = _check_band_change(state, skill)
    _update_mastery(state)
    return new_band


def _check_band_change(state: SkillState, skill: str) -> int | None:
    n = len(state.window)
    if n == 0:
        return None
    accuracy = sum(a["c"] for a in state.window) / n

    if (
        n >= PROMOTE_MIN_ANSWERS
        and accuracy >= PROMOTE_ACCURACY
        and median(a["t"] for a in state.window) <= target_ms(skill)
        and state.band < MAX_BAND
    ):
        state.band += 1
        state.window = []
        return state.band

    if n >= DEMOTE_MIN_ANSWERS and accuracy <= DEMOTE_ACCURACY and state.band > MIN_BAND:
        state.band -= 1
        state.window = []
        return state.band

    return None


def _update_mastery(state: SkillState) -> None:
    if state.window:
        accuracy = sum(a["c"] for a in state.window) / len(state.window)
    else:
        # Window just cleared by a band change; credit the band itself.
        accuracy = 0.5
    instant = ((state.band - 1) + accuracy) / MAX_BAND * 100
    state.mastery = (1 - EWMA_ALPHA) * state.mastery + EWMA_ALPHA * instant
    state.mastery = max(0.0, min(100.0, state.mastery))
