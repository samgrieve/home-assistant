"""Tests for the English word banks and generators."""
import random
from collections import Counter

import pytest

from custom_components.learning_games.engine import english
from custom_components.learning_games.engine.models import (
    QTYPE_LETTERS_FILL,
    QTYPE_MULTIPLE_CHOICE,
    QTYPE_UNSCRAMBLE,
)
from custom_components.learning_games.engine.wordlists import load_banks

ALL_SKILLS = sorted(english.GENERATORS)


@pytest.fixture(scope="module")
def banks():
    return load_banks()


def test_banks_load_and_validate(banks):
    assert len(banks.spelling) >= 50
    assert len(banks.vocab) >= 40
    assert len(banks.homophones) >= 15
    assert len(banks.word_classes["items"]) >= 25
    assert len(banks.punctuation) >= 12
    assert len(banks.affixes) >= 30
    # Every band 1-5 has content in each bank used for banding.
    for entries in (banks.spelling, banks.vocab, banks.affixes):
        bands = Counter(e["band"] for e in entries)
        for band in (1, 2, 3, 4, 5):
            assert bands[band] >= 5


@pytest.mark.parametrize("skill", ALL_SKILLS)
@pytest.mark.parametrize("band", [1, 2, 3, 4, 5])
def test_fuzz_generator(skill, band, banks):
    rng = random.Random(f"{skill}-{band}")
    for _ in range(200):
        q = english.generate(skill, band, rng, banks)
        assert q.skill == skill
        assert q.prompt
        assert q.answer
        assert q.check(q.answer)
        if q.qtype == QTYPE_MULTIPLE_CHOICE:
            assert q.answer in q.options
            assert len(q.options) == len(set(q.options)), q.options
            assert len(q.options) >= 2
        elif q.qtype == QTYPE_LETTERS_FILL:
            assert len(q.fill_pattern) == len(q.answer)
            # Pattern blanks must be fillable from the tile bank.
            for i, ch in enumerate(q.fill_pattern):
                if ch == "_":
                    assert q.answer[i] in q.options
                else:
                    assert ch == q.answer[i]
        elif q.qtype == QTYPE_UNSCRAMBLE:
            assert sorted(q.options) == sorted(q.answer)
        else:
            pytest.fail(f"unexpected qtype {q.qtype}")


def test_vocab_distractors_are_not_synonyms(banks):
    rng = random.Random(9)
    for _ in range(300):
        q = english.generate("english.vocabulary", 3, rng, banks)
        entry = next(e for e in banks.vocab if e["word"] == q.word_key)
        taboo = set(entry["synonyms"]) | set(entry["antonyms"])
        for option in q.options:
            if option != q.answer:
                assert option not in taboo, (q.prompt, option)


def test_exclude_avoids_recent_words(banks):
    rng = random.Random(11)
    exclude = {e["word"] for e in banks.spelling if e["band"] != 3}
    for _ in range(50):
        q = english.generate("english.spelling", 3, rng, banks, exclude)
        assert q.word_key not in exclude


def test_affix_real_answer_never_in_distractors(banks):
    rng = random.Random(17)
    for _ in range(400):
        q = english.generate("english.affixes", 3, rng, banks)
        assert q.options.count(q.answer) == 1
        assert len(q.options) >= 3


def test_homophone_answer_fits_sentence(banks):
    rng = random.Random(13)
    for _ in range(100):
        q = english.generate("english.homophones", 3, rng, banks)
        assert "___" in q.prompt_secondary
        assert set(q.options) <= {w for s in banks.homophones for w in s["words"]}
