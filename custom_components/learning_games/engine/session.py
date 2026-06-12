"""A single game round: question sequencing, scoring, XP and adaptive updates."""
from __future__ import annotations

import math
import random

from . import adaptive, generate_question, pick_skill
from .models import AnswerOutcome, Question, RoundResults, SkillState
from .wordlists import WordBanks

XP_CORRECT = 10
XP_SPEED_BONUS = 5
XP_STREAK_BONUS = 2  # per correct answer while run streak >= 3
XP_WRONG_EFFORT = 1
XP_ROUND_COMPLETE = 20

DEFAULT_LENGTH = 10
MAX_GENERATE_RETRIES = 6


class SessionError(Exception):
    """Raised for invalid session operations (wrong question id, finished round)."""


class GameSession:
    """One round of one mode. Lives in memory only; mutates the SkillStates
    handed to it so the caller (coordinator) owns persistence."""

    def __init__(
        self,
        session_id: str,
        mode_id: str,
        length: int,
        skills: dict[str, SkillState],
        banks: WordBanks | None,
        rng: random.Random | None = None,
        xp_multiplier: float = 1.0,
    ) -> None:
        self.session_id = session_id
        self.mode_id = mode_id
        self.length = max(3, min(30, length or DEFAULT_LENGTH))
        self.skills = skills
        self.banks = banks
        self.rng = rng or random.Random()
        self.xp_multiplier = xp_multiplier

        self.index = 0  # 1-based index of the current question
        self.current: Question | None = None
        self.correct_count = 0
        self.xp = 0
        self.run_streak = 0
        self.best_run_streak = 0
        self.speed_bonuses = 0
        self.times_ms: list[int] = []
        self.skill_changes: list[dict] = []
        self.done = False
        self._used_word_keys: set[str] = set()
        self._used_prompts: set[str] = set()

    def next_question(self) -> Question:
        if self.done:
            raise SessionError("session finished")
        self.index += 1
        skill = pick_skill(self.mode_id, self.skills, self.rng)
        band = self.skills[skill].band
        question = None
        for _ in range(MAX_GENERATE_RETRIES):
            question = generate_question(skill, band, self.rng, self.banks, self._used_word_keys)
            key = question.prompt + (question.prompt_secondary or "")
            if key not in self._used_prompts:
                break
        self._used_prompts.add(question.prompt + (question.prompt_secondary or ""))
        if question.word_key:
            self._used_word_keys.add(question.word_key)
        question.question_id = f"q{self.index}"
        self.current = question
        return question

    def submit(self, question_id: str, answer: str, elapsed_ms: int) -> AnswerOutcome:
        if self.done:
            raise SessionError("session finished")
        if self.current is None or question_id != self.current.question_id:
            raise SessionError("unexpected question id")

        question = self.current
        elapsed_ms = max(300, min(60000, int(elapsed_ms)))
        self.times_ms.append(elapsed_ms)
        correct = question.check(answer)
        speed_bonus = False

        if correct:
            self.correct_count += 1
            self.run_streak += 1
            self.best_run_streak = max(self.best_run_streak, self.run_streak)
            xp_delta = XP_CORRECT
            if elapsed_ms <= question.target_ms:
                xp_delta += XP_SPEED_BONUS
                speed_bonus = True
                self.speed_bonuses += 1
            if self.run_streak >= 3:
                xp_delta += XP_STREAK_BONUS
        else:
            self.run_streak = 0
            xp_delta = XP_WRONG_EFFORT

        xp_delta = math.ceil(xp_delta * self.xp_multiplier)
        self.xp += xp_delta

        state = self.skills[question.skill]
        old_band = state.band
        new_band = adaptive.record_answer(state, question.skill, correct, elapsed_ms)
        band_change = None
        if new_band is not None:
            band_change = (old_band, new_band)
            self.skill_changes.append(
                {"skill": question.skill, "old_band": old_band, "new_band": new_band}
            )

        self.current = None
        if self.index >= self.length:
            self.done = True
            self.xp += math.ceil(XP_ROUND_COMPLETE * self.xp_multiplier)

        return AnswerOutcome(
            correct=correct,
            correct_answer=question.answer,
            explain=question.explain,
            xp_delta=xp_delta,
            run_streak=self.run_streak,
            speed_bonus=speed_bonus,
            done=self.done,
            skill=question.skill,
            band_change=band_change,
        )

    def results(self) -> RoundResults:
        return RoundResults(
            mode=self.mode_id,
            total=self.length if self.done else self.index,
            correct=self.correct_count,
            xp_gained=self.xp,
            speed_bonuses=self.speed_bonuses,
            best_run_streak=self.best_run_streak,
            avg_ms=int(sum(self.times_ms) / len(self.times_ms)) if self.times_ms else 0,
            skill_changes=self.skill_changes,
        )
