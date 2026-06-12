"""Maths question generators, UK Year 5 baseline, banded 1-5.

Pure functions: generate(skill, band, rng) -> Question, fully deterministic
under a seeded random.Random for tests.
"""
from __future__ import annotations

import math
import random
from fractions import Fraction

from . import adaptive
from .models import (
    QTYPE_MULTIPLE_CHOICE,
    QTYPE_NUMERIC,
    QTYPE_NUMERIC_REMAINDER,
    Question,
)


def _fmt(value: float) -> str:
    """Format a number without a trailing .0."""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _numeric_distractors(correct: int, candidates: list[int], rng: random.Random) -> list[str]:
    """Pick 3 unique plausible wrong answers, padding with small offsets."""
    pool: list[int] = []
    for c in candidates:
        if c != correct and c >= 0 and c not in pool:
            pool.append(c)
    rng.shuffle(pool)
    picked = pool[:3]
    while len(picked) < 3:
        offset = rng.randint(2, 9) * rng.choice((-1, 1))
        cand = correct + offset
        if cand >= 0 and cand != correct and cand not in picked:
            picked.append(cand)
    return [str(p) for p in picked]


def _mc(question: Question, distractors: list[str], rng: random.Random) -> Question:
    options = distractors + [question.answer]
    rng.shuffle(options)
    question.qtype = QTYPE_MULTIPLE_CHOICE
    question.options = options
    return question


def _make(skill: str, qtype: str, prompt: str, answer: str, **kwargs) -> Question:
    return Question(
        question_id="",
        skill=skill,
        qtype=qtype,
        prompt=prompt,
        answer=answer,
        target_ms=adaptive.target_ms(skill),
        **kwargs,
    )


# --------------------------------------------------------------------------- times tables

_TABLE_BANDS = {1: [2, 5, 10], 2: [2, 3, 4, 5, 10], 3: [3, 4, 6, 7, 8], 4: [6, 7, 8, 9, 11, 12]}


def _gen_times_tables(band: int, rng: random.Random) -> Question:
    skill = "maths.times_tables"
    tables = _TABLE_BANDS.get(min(band, 4), _TABLE_BANDS[4])
    a = rng.choice(tables)
    b = rng.randint(2, 12)
    product = a * b

    if band == 5:
        form = rng.choice(("missing_factor", "division", "multiply"))
        if form == "missing_factor":
            q = _make(skill, QTYPE_NUMERIC, f"{a} × ? = {product}", str(b))
            q.explain = f"{a} × {b} = {product}"
            return q
        if form == "division":
            return _make(skill, QTYPE_NUMERIC, f"{product} ÷ {a} = ?", str(b))
        return _make(skill, QTYPE_NUMERIC, f"{a} × {b} = ?", str(product))

    if band == 4 and rng.random() < 0.4:
        return _make(skill, QTYPE_NUMERIC, f"{product} ÷ {a} = ?", str(b))

    q = _make(skill, QTYPE_NUMERIC, f"{a} × {b} = ?", str(product))
    if band <= 2:
        wrongs = [a * (b + 1), a * (b - 1), (a + 1) * b, product + a, product - 1]
        return _mc(q, _numeric_distractors(product, wrongs, rng), rng)
    return q


# --------------------------------------------------------------------------- addition / subtraction

def _add_operands(band: int, rng: random.Random) -> tuple[int, int]:
    if band == 1:  # 2-digit, no carrying
        while True:
            a, b = rng.randint(10, 89), rng.randint(10, 89)
            if a % 10 + b % 10 < 10 and a // 10 + b // 10 < 10:
                return a, b
    if band == 2:
        return rng.randint(15, 99), rng.randint(15, 99)
    if band == 3:
        return rng.randint(100, 999), rng.randint(100, 999)
    return rng.randint(1000, 9999), rng.randint(1000, 9999)


def _gen_addition(band: int, rng: random.Random) -> Question:
    skill = "maths.addition"
    a, b = _add_operands(min(band, 4), rng)
    total = a + b
    if band == 5 and rng.random() < 0.5:
        q = _make(skill, QTYPE_NUMERIC, f"{a} + ? = {total}", str(b))
        q.explain = f"{total} − {a} = {b}"
        return q
    return _make(skill, QTYPE_NUMERIC, f"{a} + {b} = ?", str(total))


def _gen_subtraction(band: int, rng: random.Random) -> Question:
    skill = "maths.subtraction"
    if band == 1:  # 2-digit, no borrowing
        while True:
            a, b = rng.randint(20, 99), rng.randint(11, 88)
            if a > b and a % 10 >= b % 10:
                break
    else:
        a, b = _add_operands(min(band, 4), rng)
        if a < b:
            a, b = b, a
        if a == b:
            a += rng.randint(1, 9)
    diff = a - b
    if band == 5 and rng.random() < 0.5:
        q = _make(skill, QTYPE_NUMERIC, f"{a} − ? = {diff}", str(b))
        q.explain = f"{a} − {diff} = {b}"
        return q
    return _make(skill, QTYPE_NUMERIC, f"{a} − {b} = ?", str(diff))


# --------------------------------------------------------------------------- long multiplication / division

def _gen_long_multiplication(band: int, rng: random.Random) -> Question:
    skill = "maths.long_multiplication"
    if band == 1:
        a, b = rng.randint(11, 25), rng.randint(2, 5)
    elif band == 2:
        a, b = rng.randint(12, 99), rng.randint(2, 9)
    elif band == 3:
        a, b = rng.randint(102, 999), rng.randint(2, 9)
    elif band == 4:
        a, b = rng.randint(12, 99), rng.randint(11, 99)
    else:
        a, b = rng.randint(102, 999), rng.randint(11, 99)
    return _make(skill, QTYPE_NUMERIC, f"{a} × {b} = ?", str(a * b))


def _gen_division(band: int, rng: random.Random) -> Question:
    skill = "maths.division"
    if band == 1:
        d = rng.choice((2, 5, 10))
        quotient = rng.randint(2, 12)
        return _make(skill, QTYPE_NUMERIC, f"{d * quotient} ÷ {d} = ?", str(quotient))
    if band == 2:
        d = rng.randint(2, 12)
        quotient = rng.randint(2, 12)
        return _make(skill, QTYPE_NUMERIC, f"{d * quotient} ÷ {d} = ?", str(quotient))
    if band == 3:
        d = rng.randint(3, 9)
        quotient = rng.randint(3, 12)
        rem = rng.randint(1, d - 1)
    elif band == 4:
        d = rng.randint(3, 9)
        quotient = rng.randint(12, 99)
        rem = 0
    else:
        d = rng.randint(3, 9)
        quotient = rng.randint(12, 120)
        rem = rng.randint(1, d - 1)
    n = d * quotient + rem
    if rem:
        q = _make(skill, QTYPE_NUMERIC_REMAINDER, f"{n} ÷ {d} = ? r ?", f"{quotient} r {rem}")
        q.explain = f"{d} × {quotient} = {d * quotient}, remainder {rem}"
        return q
    return _make(skill, QTYPE_NUMERIC, f"{n} ÷ {d} = ?", str(quotient))


# --------------------------------------------------------------------------- fractions

def _frac(n: int, d: int) -> str:
    return f"{n}/{d}"


def _gen_fractions(band: int, rng: random.Random) -> Question:
    skill = "maths.fractions"
    if band == 1:
        n, d = rng.choice(((1, 2), (1, 4), (3, 4), (1, 3)))
        k = rng.randint(2, 4)
        correct = _frac(n * k, d * k)
        wrongs = {_frac(n * k + 1, d * k), _frac(n, d * k), _frac(n * k, d * k + 1), _frac(d * k, n * k) if n != d else _frac(n * k + 2, d * k)}
        wrongs.discard(correct)
        q = _make(skill, QTYPE_MULTIPLE_CHOICE, f"Which fraction is equal to {_frac(n, d)}?", correct)
        q.options = list(wrongs)[:3] + [correct]
        rng.shuffle(q.options)
        return q
    if band == 2:
        n = rng.randint(1, 5)
        d = rng.randint(n + 1, 9)
        k = rng.randint(2, 5)
        q = _make(skill, QTYPE_NUMERIC, f"{_frac(n, d)} = ?/{d * k}", str(n * k))
        q.explain = f"Multiply top and bottom by {k}: {_frac(n * k, d * k)}"
        return q
    if band == 3:
        d = rng.randint(5, 12)
        a, b = rng.sample(range(1, d), 2)
        correct = _frac(max(a, b), d)
        q = _make(skill, QTYPE_MULTIPLE_CHOICE, f"Which is bigger: {_frac(a, d)} or {_frac(b, d)}?", correct)
        q.options = [_frac(a, d), _frac(b, d)]
        rng.shuffle(q.options)
        q.explain = "Same denominator — the bigger numerator wins."
        return q
    if band == 4:
        d = rng.randint(5, 12)
        a = rng.randint(1, d - 2)
        b = rng.randint(1, d - 1 - a)
        correct = _frac(a + b, d)
        wrongs = {_frac(a + b, d * 2), _frac(a * b, d), _frac(a + b + 1, d), _frac(a + b - 1, d)}
        wrongs.discard(correct)
        q = _make(skill, QTYPE_MULTIPLE_CHOICE, f"{_frac(a, d)} + {_frac(b, d)} = ?", correct)
        q.options = sorted(wrongs)[:3] + [correct]
        rng.shuffle(q.options)
        q.explain = "Same denominator: just add the numerators."
        return q
    # band 5: compare unlike denominators
    while True:
        d1, d2 = rng.sample((2, 3, 4, 5, 6, 8, 10, 12), 2)
        n1, n2 = rng.randint(1, d1 - 1), rng.randint(1, d2 - 1)
        f1, f2 = Fraction(n1, d1), Fraction(n2, d2)
        if f1 != f2:
            break
    correct = _frac(n1, d1) if f1 > f2 else _frac(n2, d2)
    q = _make(skill, QTYPE_MULTIPLE_CHOICE, f"Which is bigger: {_frac(n1, d1)} or {_frac(n2, d2)}?", correct)
    q.options = [_frac(n1, d1), _frac(n2, d2)]
    rng.shuffle(q.options)
    q.explain = f"Use a common denominator of {d1 * d2 // math.gcd(d1, d2)}."
    return q


# --------------------------------------------------------------------------- decimals

def _gen_decimals(band: int, rng: random.Random) -> Question:
    skill = "maths.decimals"
    if band == 1:
        a, b = rng.randint(1, 8), rng.randint(1, 8)
        total = round((a + b) / 10, 1)
        return _make(skill, QTYPE_NUMERIC, f"0.{a} + 0.{b} = ?", _fmt(total))
    if band == 2:
        while True:
            a = round(rng.uniform(0.1, 9.9), 1)
            b = round(rng.uniform(0.1, 9.9), 1)
            if a != b:
                break
        correct = _fmt(max(a, b))
        q = _make(skill, QTYPE_MULTIPLE_CHOICE, f"Which is bigger: {_fmt(a)} or {_fmt(b)}?", correct)
        q.options = [_fmt(a), _fmt(b)]
        rng.shuffle(q.options)
        return q
    if band == 3:
        a = round(rng.uniform(0.11, 8.99), 2)
        b = round(rng.uniform(0.01, 0.99), 2)
        total = round(a + b, 2)
        return _make(skill, QTYPE_NUMERIC, f"{_fmt(a)} + {_fmt(b)} = ?", _fmt(total))
    if band == 4:
        a = round(rng.uniform(0.01, 9.99), 2)
        mult = rng.choice((10, 100))
        result = round(a * mult, 2)
        return _make(skill, QTYPE_NUMERIC, f"{_fmt(a)} × {mult} = ?", _fmt(result))
    # band 5: order three decimals
    while True:
        nums = [round(rng.uniform(0.1, 9.99), rng.choice((1, 2))) for _ in range(3)]
        if len(set(nums)) == 3:
            break
    ordered = sorted(nums)
    correct = ", ".join(_fmt(n) for n in ordered)
    options = {correct}
    while len(options) < 3:
        shuffled = nums[:]
        rng.shuffle(shuffled)
        options.add(", ".join(_fmt(n) for n in shuffled))
    q = _make(skill, QTYPE_MULTIPLE_CHOICE, "Put these in order, smallest first:", correct)
    q.prompt_secondary = "   ".join(_fmt(n) for n in nums)
    q.options = list(options)
    rng.shuffle(q.options)
    return q


# --------------------------------------------------------------------------- rounding

def _gen_rounding(band: int, rng: random.Random) -> Question:
    skill = "maths.rounding"
    if band == 1:
        n = rng.randint(11, 99)
        if n % 10 == 0:
            n += 1
        return _make(skill, QTYPE_NUMERIC, f"Round {n} to the nearest 10", str(round(n, -1)))
    if band == 2:
        n = rng.randint(101, 999)
        to = rng.choice((10, 100))
        return _make(skill, QTYPE_NUMERIC, f"Round {n} to the nearest {to}",
                     str(round(n, -1 if to == 10 else -2)))
    if band == 3:
        n = rng.randint(1001, 9999)
        to = rng.choice((10, 100, 1000))
        digits = {10: -1, 100: -2, 1000: -3}[to]
        return _make(skill, QTYPE_NUMERIC, f"Round {n} to the nearest {to}", str(round(n, digits)))
    if band == 4:
        n = round(rng.uniform(1.1, 99.9), 1)
        if n == int(n):
            n += 0.1
        # Python's round() is banker's rounding; schools round .5 up.
        answer = int(n) + (1 if (n - int(n)) >= 0.5 else 0)
        return _make(skill, QTYPE_NUMERIC, f"Round {_fmt(n)} to the nearest whole number", str(answer))
    n = round(rng.uniform(1.01, 9.99), 2)
    tenths = int(n * 10) / 10
    hundredth = round(n * 100) % 10
    answer = round(tenths + (0.1 if hundredth >= 5 else 0), 1)
    return _make(skill, QTYPE_NUMERIC, f"Round {_fmt(n)} to 1 decimal place", _fmt(answer))


# --------------------------------------------------------------------------- place value

_PLACE_NAMES = ["ones", "tens", "hundreds", "thousands", "ten-thousands", "hundred-thousands", "millions"]


def _gen_place_value(band: int, rng: random.Random) -> Question:
    skill = "maths.place_value"
    n_digits = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7}[band]
    n = rng.randint(10 ** (n_digits - 1), 10**n_digits - 1)

    if band >= 4 and rng.random() < 0.5:
        step = rng.choice((1000, 10000) if band == 4 else (10000, 100000))
        more = rng.random() < 0.5
        answer = n + step if more else n - step
        if answer < 0:
            answer = n + step
            more = True
        word = "more" if more else "less"
        return _make(skill, QTYPE_NUMERIC, f"What is {step:,} {word} than {n:,}?", str(answer))

    digits = str(n)
    pos = rng.randrange(len(digits))
    while digits[pos] == "0":
        pos = rng.randrange(len(digits))
    digit = digits[pos]
    place_idx = len(digits) - 1 - pos
    value = int(digit) * 10**place_idx
    wrongs = {int(digit), int(digit) * 10 ** max(0, place_idx - 1), int(digit) * 10 ** (place_idx + 1)}
    wrongs.discard(value)
    q = _make(skill, QTYPE_MULTIPLE_CHOICE,
              f"In {n:,}, what is the value of the digit {digit}?", f"{value:,}")
    q.options = [f"{w:,}" for w in list(wrongs)[:3]] + [q.answer]
    rng.shuffle(q.options)
    q.explain = f"The {digit} is in the {_PLACE_NAMES[place_idx]} place."
    return q


# --------------------------------------------------------------------------- negative numbers

def _gen_negative_numbers(band: int, rng: random.Random) -> Question:
    skill = "maths.negative_numbers"
    if band == 1:
        while True:
            a, b = rng.randint(-10, 10), rng.randint(-10, 10)
            if a != b:
                break
        correct = str(min(a, b))
        q = _make(skill, QTYPE_MULTIPLE_CHOICE, f"Which is colder: {a}°C or {b}°C?", correct)
        q.options = [str(a), str(b)]
        rng.shuffle(q.options)
        return q
    if band in (2, 5):
        count = 3 if band == 2 else 4
        lo, hi = (-10, 10) if band == 2 else (-20, 20)
        nums = rng.sample(range(lo, hi + 1), count)
        ordered = sorted(nums)
        correct = ", ".join(str(x) for x in ordered)
        options = {correct, ", ".join(str(x) for x in sorted(nums, reverse=True))}
        while len(options) < (3 if band == 2 else 4):
            shuffled = nums[:]
            rng.shuffle(shuffled)
            options.add(", ".join(str(x) for x in shuffled))
        q = _make(skill, QTYPE_MULTIPLE_CHOICE, "Put these in order, lowest first:", correct)
        q.prompt_secondary = "   ".join(str(x) for x in nums)
        q.options = list(options)
        rng.shuffle(q.options)
        return q
    if band == 3:
        start = rng.randint(-5, 8)
        step = rng.randint(2, 12)
        q = _make(skill, QTYPE_NUMERIC, f"What is {step} less than {start}?", str(start - step))
        q.explain = "Count back through zero."
        return q
    # band 4: temperature difference across zero
    cold = rng.randint(-15, -1)
    warm = rng.randint(1, 15)
    q = _make(skill, QTYPE_NUMERIC,
              f"The temperature rises from {cold}°C to {warm}°C. By how many degrees did it rise?",
              str(warm - cold))
    q.explain = f"From {cold} up to 0 is {-cold}, then 0 up to {warm} is {warm}."
    return q


# --------------------------------------------------------------------------- registry

GENERATORS = {
    "maths.times_tables": _gen_times_tables,
    "maths.addition": _gen_addition,
    "maths.subtraction": _gen_subtraction,
    "maths.long_multiplication": _gen_long_multiplication,
    "maths.division": _gen_division,
    "maths.fractions": _gen_fractions,
    "maths.decimals": _gen_decimals,
    "maths.rounding": _gen_rounding,
    "maths.place_value": _gen_place_value,
    "maths.negative_numbers": _gen_negative_numbers,
}


def generate(skill: str, band: int, rng: random.Random) -> Question:
    band = max(1, min(5, band))
    return GENERATORS[skill](band, rng)
