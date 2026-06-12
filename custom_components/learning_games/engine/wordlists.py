"""Loader for the bundled English content JSON. Pure Python — no HA imports.

Loading does blocking file I/O, so the integration calls load_banks() via an
executor job during setup and caches the result.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


@dataclass
class WordBanks:
    spelling: list[dict]
    vocab: list[dict]
    homophones: list[dict]
    word_classes: dict
    punctuation: list[dict]
    affixes: list[dict]


def _read(name: str) -> dict:
    with open(DATA_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def load_banks(data_dir: Path | None = None) -> WordBanks:
    global DATA_DIR
    if data_dir is not None:
        DATA_DIR = data_dir
    banks = WordBanks(
        spelling=_read("spelling_y56.json")["words"],
        vocab=_read("vocab.json")["words"],
        homophones=_read("homophones.json")["sets"],
        word_classes=_read("word_classes.json"),
        punctuation=_read("punctuation.json")["items"],
        affixes=_read("affixes.json")["items"],
    )
    _validate(banks)
    return banks


def _validate(banks: WordBanks) -> None:
    for entry in banks.spelling:
        word = entry["word"]
        if word in entry["wrong"]:
            raise ValueError(f"spelling bank: correct word {word!r} appears in its wrong list")
        if len(set(entry["wrong"])) != len(entry["wrong"]):
            raise ValueError(f"spelling bank: duplicate misspellings for {word!r}")
    for entry in banks.vocab:
        if not entry.get("synonyms") or not entry.get("antonyms"):
            raise ValueError(f"vocab bank: {entry['word']!r} needs synonyms and antonyms")
    for hset in banks.homophones:
        words = set(hset["words"])
        for sentence in hset["sentences"]:
            if sentence["answer"] not in words:
                raise ValueError(f"homophones bank: answer {sentence['answer']!r} not in set {words}")
    for item in banks.word_classes["items"]:
        if item["class"] not in banks.word_classes["classes"]:
            raise ValueError(f"word_classes bank: unknown class {item['class']!r}")
    for item in banks.punctuation:
        if item["correct"] in item["wrong"]:
            raise ValueError("punctuation bank: correct sentence duplicated in wrong list")
    for entry in banks.affixes:
        word = entry["word"]
        affix = entry.get("prefix") or entry.get("suffix")
        if not affix:
            raise ValueError(f"affixes bank: {word!r} needs a prefix or suffix")
        if len(entry["wrong_affixes"]) < 3:
            raise ValueError(f"affixes bank: {word!r} needs >= 3 wrong_affixes")
        for wrong in entry["wrong_affixes"]:
            if wrong in (entry.get("prefix"), entry.get("suffix")):
                raise ValueError(f"affixes bank: {word!r} lists its real affix as wrong")
        if word in entry.get("misspellings", []):
            raise ValueError(f"affixes bank: {word!r} appears in its own misspellings")
