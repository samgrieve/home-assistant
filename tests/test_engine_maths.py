"""Fuzz + correctness tests for the maths generators."""
import random
import re

import pytest

from custom_components.learning_games.engine import maths
from custom_components.learning_games.engine.models import (
    QTYPE_MULTIPLE_CHOICE,
    QTYPE_NUMERIC,
    QTYPE_NUMERIC_REMAINDER,
)

ALL_SKILLS = sorted(maths.GENERATORS)


@pytest.mark.parametrize("skill", ALL_SKILLS)
@pytest.mark.parametrize("band", [1, 2, 3, 4, 5])
def test_fuzz_generator(skill, band):
    rng = random.Random(f"{skill}-{band}")
    for _ in range(300):
        q = maths.generate(skill, band, rng)
        assert q.skill == skill
        assert q.prompt
        assert q.answer != ""
        assert q.target_ms > 0
        if q.qtype == QTYPE_MULTIPLE_CHOICE:
            assert q.options, f"MC question with no options: {q.prompt}"
            assert q.answer in q.options
            assert len(q.options) == len(set(q.options)), f"duplicate options for {q.prompt}: {q.options}"
            assert len(q.options) >= 2
        elif q.qtype == QTYPE_NUMERIC:
            float(q.answer.replace(",", ""))
        elif q.qtype == QTYPE_NUMERIC_REMAINDER:
            assert re.fullmatch(r"\d+ r \d+", q.answer), q.answer
        else:
            pytest.fail(f"unexpected qtype {q.qtype} for maths")
        # The correct answer must verify through the public check path.
        assert q.check(q.answer)
        assert q.check(f"  {q.answer.upper()}  ")


@pytest.mark.parametrize(
    ("skill", "pattern", "op"),
    [
        ("maths.times_tables", r"^(\d+) × (\d+) = \?$", lambda a, b: a * b),
        ("maths.addition", r"^(\d+) \+ (\d+) = \?$", lambda a, b: a + b),
        ("maths.subtraction", r"^(\d+) − (\d+) = \?$", lambda a, b: a - b),
        ("maths.long_multiplication", r"^(\d+) × (\d+) = \?$", lambda a, b: a * b),
    ],
)
def test_arithmetic_answers_are_correct(skill, pattern, op):
    rng = random.Random(42)
    checked = 0
    for band in (1, 2, 3, 4, 5):
        for _ in range(200):
            q = maths.generate(skill, band, rng)
            m = re.fullmatch(pattern, q.prompt)
            if not m:
                continue
            a, b = int(m.group(1)), int(m.group(2))
            assert int(q.answer) == op(a, b), q.prompt
            checked += 1
    assert checked > 100


def test_division_with_remainder_verifies():
    rng = random.Random(7)
    seen_remainder = False
    for _ in range(300):
        q = maths.generate("maths.division", 5, rng)
        m = re.fullmatch(r"^(\d+) ÷ (\d+) = \? r \?$", q.prompt)
        if not m:
            continue
        seen_remainder = True
        n, d = int(m.group(1)), int(m.group(2))
        quotient, rem = map(int, re.fullmatch(r"(\d+) r (\d+)", q.answer).groups())
        assert d * quotient + rem == n
        assert 0 < rem < d
        # Spacing variants must be accepted.
        assert q.check(f"{quotient}r{rem}")
        assert q.check(f"{quotient} R {rem}")
    assert seen_remainder


def test_subtraction_never_negative():
    rng = random.Random(1)
    for band in (1, 2, 3, 4, 5):
        for _ in range(200):
            q = maths.generate("maths.subtraction", band, rng)
            if q.qtype == QTYPE_NUMERIC and "− ?" not in q.prompt:
                assert int(q.answer) >= 0


def test_band_clamped():
    rng = random.Random(3)
    q = maths.generate("maths.times_tables", 99, rng)
    assert q.skill == "maths.times_tables"
    q = maths.generate("maths.addition", -1, rng)
    assert q.skill == "maths.addition"
