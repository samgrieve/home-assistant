"""Tests for the Fly Snap arcade word-pool builder."""
import random

import pytest

from custom_components.learning_games.engine import arcade
from custom_components.learning_games.engine.wordlists import load_banks

BANKS = load_banks()


@pytest.mark.parametrize("category", arcade.CATEGORIES)
@pytest.mark.parametrize("band", [1, 3, 5])
def test_build_game_shape(category, band):
    rng = random.Random(f"{category}-{band}")
    rounds = arcade.build_game(category, band, BANKS, rng)
    assert len(rounds) == arcade.ROUNDS
    for rnd in rounds:
        assert len(rnd["pairs"]) >= 6, f"too few pairs for {category} band {band}"
        assert len(rnd["decoys"]) >= 5, f"too few decoys for {category} band {band}"
        targets = [p["t"] for p in rnd["pairs"]]
        assert len(targets) == len(set(targets)), "duplicate targets in a round"
        for pair in rnd["pairs"]:
            assert pair["t"] != pair["m"]


@pytest.mark.parametrize("category", arcade.CATEGORIES)
def test_decoys_are_safe(category):
    """A decoy must never be a valid answer for any target in its round."""
    rng = random.Random(99)
    rounds = arcade.build_game(category, 3, BANKS, rng)
    for rnd in rounds:
        targets = {p["t"] for p in rnd["pairs"]}
        matches = {p["m"] for p in rnd["pairs"]}
        for decoy in rnd["decoys"]:
            assert decoy not in targets
            assert decoy not in matches
            # The decoy's whole word family must avoid every target.
            for entry in BANKS.vocab:
                family = {entry["word"], *entry["synonyms"], *entry["antonyms"]}
                if decoy in family and category != "homophones":
                    assert not (family & targets), (decoy, family & targets)
            for hset in BANKS.homophones:
                if category == "homophones" and decoy in hset["words"]:
                    assert not (set(hset["words"]) & targets)


def test_deterministic_with_seed():
    a = arcade.build_game("synonyms", 2, BANKS, random.Random(7))
    b = arcade.build_game("synonyms", 2, BANKS, random.Random(7))
    assert a == b


def test_unknown_category_raises():
    with pytest.raises(ValueError):
        arcade.build_game("verbs", 1, BANKS, random.Random(1))


def test_skill_mapping():
    assert arcade.skill_for_category("synonyms") == "english.vocabulary"
    assert arcade.skill_for_category("antonyms") == "english.vocabulary"
    assert arcade.skill_for_category("homophones") == "english.homophones"
