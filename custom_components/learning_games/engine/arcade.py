"""Fly Snap arcade word pools. Pure Python.

The real-time game loop runs on the card; the server builds 6 rounds of
(target, match) pairs plus a per-round decoy bank, then settles XP and
adaptive stats in one finish call. Decoys are guaranteed "safe": a decoy
word never belongs to any of the round's target word families, so tapping
a decoy is always genuinely wrong.
"""
from __future__ import annotations

import random

from .wordlists import WordBanks

CATEGORIES = ("synonyms", "antonyms", "homophones")
ROUNDS = 6
PAIRS_PER_ROUND = 20
DECOYS_PER_ROUND = 14
ROUND_TIME_S = 60
LIVES = 3
TRAVEL_S = [18, 15, 12.5, 10.5, 9, 7.5]  # edge-to-lilypad seconds per round

# Settlement rules (anti-cheese clamps + XP)
XP_SNAP = 5
XP_ROUND_SURVIVED = 15
XP_ARCADE_WIN = 50
MAX_ROUNDS_PLAYED = 8  # 6 wins + 2 lost retries
MAX_SNAPS_PER_ROUND = 12  # ~one every 5s is already quick
MAX_COUNTED_WRONG = 30
MAX_ADAPTIVE_SAMPLES = 20


def skill_for_category(category: str) -> str:
    return "english.homophones" if category == "homophones" else "english.vocabulary"


def _vocab_pairs(banks: WordBanks, band: int, key: str) -> list[dict]:
    entries = [e for e in banks.vocab if abs(e["band"] - band) <= 1] or banks.vocab
    pairs = []
    for entry in entries:
        family = {entry["word"], *entry["synonyms"], *entry["antonyms"]}
        for match in entry[key]:
            pairs.append({"t": entry["word"], "m": match, "family": family})
    return pairs


def _homophone_pairs(banks: WordBanks, band: int) -> list[dict]:
    sets_ = [s for s in banks.homophones if abs(s["band"] - band) <= 1] or banks.homophones
    pairs = []
    for hset in sets_:
        family = set(hset["words"])
        for target in hset["words"]:
            for match in hset["words"]:
                if match != target:
                    pairs.append({"t": target, "m": match, "family": family})
    return pairs


def _decoy_pool(banks: WordBanks, category: str) -> list[tuple[str, set]]:
    if category == "homophones":
        return [(w, set(s["words"])) for s in banks.homophones for w in s["words"]]
    return [
        (e["word"], {e["word"], *e["synonyms"], *e["antonyms"]})
        for e in banks.vocab
    ]


def build_game(category: str, band: int, banks: WordBanks,
               rng: random.Random) -> list[dict]:
    """ROUNDS dicts: {"pairs": [{"t", "m"}, ...], "decoys": [word, ...]}."""
    if category not in CATEGORIES:
        raise ValueError(f"unknown category {category}")
    if category == "homophones":
        all_pairs = _homophone_pairs(banks, band)
    else:
        all_pairs = _vocab_pairs(banks, band, category)

    rounds = []
    for _ in range(ROUNDS):
        shuffled = all_pairs[:]
        rng.shuffle(shuffled)
        pairs: list[dict] = []
        targets: set[str] = set()
        taboo: set[str] = set()
        for pair in shuffled:
            if len(pairs) >= PAIRS_PER_ROUND:
                break
            if pair["t"] in targets:
                continue
            pairs.append({"t": pair["t"], "m": pair["m"]})
            targets.add(pair["t"])
            taboo |= pair["family"]

        decoys: list[str] = []
        candidates = _decoy_pool(banks, category)
        rng.shuffle(candidates)
        for word, family in candidates:
            if len(decoys) >= DECOYS_PER_ROUND:
                break
            if word in taboo or word in decoys or family & targets:
                continue
            decoys.append(word)

        rounds.append({"pairs": pairs, "decoys": decoys})
    return rounds
