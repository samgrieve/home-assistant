"""Core dataclasses for the game engine. Pure Python — no Home Assistant imports."""
from __future__ import annotations

from dataclasses import dataclass, field

# Question answer-input types understood by the card.
QTYPE_MULTIPLE_CHOICE = "multiple_choice"
QTYPE_NUMERIC = "numeric"
QTYPE_NUMERIC_REMAINDER = "numeric_with_remainder"
QTYPE_LETTERS_FILL = "letters_fill"  # fill blanks from a tile bank (tiles reusable)
QTYPE_UNSCRAMBLE = "unscramble"  # arrange all tiles (tiles consumed)


def normalize_answer(value: str) -> str:
    """Canonicalise an answer string for comparison."""
    return "".join(str(value).strip().lower().split())


@dataclass
class Question:
    """A single generated question. `answer` never leaves the server."""

    question_id: str
    skill: str  # e.g. "maths.times_tables"
    qtype: str
    prompt: str
    answer: str
    options: list[str] | None = None
    prompt_secondary: str | None = None
    fill_pattern: str | None = None  # e.g. "n_cess_ry" for letters_fill
    explain: str | None = None
    target_ms: int = 10000  # speed-bonus threshold
    word_key: str | None = None  # dedupe key for word-based questions

    def check(self, submitted: str) -> bool:
        return normalize_answer(submitted) == normalize_answer(self.answer)

    def to_wire(self, index: int, total: int) -> dict:
        """Shape sent to the card — must not include the answer."""
        return {
            "question_id": self.question_id,
            "index": index,
            "total": total,
            "skill": self.skill,
            "type": self.qtype,
            "prompt": self.prompt,
            "prompt_secondary": self.prompt_secondary,
            "options": self.options,
            "fill_pattern": self.fill_pattern,
            "target_ms": self.target_ms,
        }


@dataclass
class SkillState:
    """Adaptive state for one skill."""

    band: int = 1
    mastery: float = 0.0
    window: list[dict] = field(default_factory=list)  # [{"c": 0|1, "t": ms}], last 10
    attempts: int = 0
    correct: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> SkillState:
        return cls(
            band=int(data.get("band", 1)),
            mastery=float(data.get("mastery", 0.0)),
            window=list(data.get("window", [])),
            attempts=int(data.get("attempts", 0)),
            correct=int(data.get("correct", 0)),
        )

    def to_dict(self) -> dict:
        return {
            "band": self.band,
            "mastery": round(self.mastery, 1),
            "window": self.window,
            "attempts": self.attempts,
            "correct": self.correct,
        }


@dataclass
class AnswerOutcome:
    """Result of submitting one answer."""

    correct: bool
    correct_answer: str
    explain: str | None
    xp_delta: int
    run_streak: int
    speed_bonus: bool
    done: bool
    skill: str
    band_change: tuple[int, int] | None = None  # (old, new) if the band moved


@dataclass
class RoundResults:
    """Summary returned when the last question of a session is answered."""

    mode: str
    total: int
    correct: int
    xp_gained: int
    speed_bonuses: int
    best_run_streak: int
    avg_ms: int
    skill_changes: list[dict] = field(default_factory=list)
