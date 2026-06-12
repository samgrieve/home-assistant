"""English question generators, banded 1-5, fed by the bundled word banks."""
from __future__ import annotations

import random

from . import adaptive
from .models import (
    QTYPE_LETTERS_FILL,
    QTYPE_MULTIPLE_CHOICE,
    QTYPE_UNSCRAMBLE,
    Question,
)
from .wordlists import WordBanks

VOWELS = set("aeiou")


def _by_band(entries: list[dict], band: int, exclude: set[str], key) -> list[dict]:
    """Entries within band +/- 1, dropping recently used; widen if too few."""
    near = [e for e in entries if abs(e["band"] - band) <= 1]
    fresh = [e for e in near if key(e) not in exclude]
    if len(fresh) >= 2:
        return fresh
    fresh = [e for e in entries if key(e) not in exclude]
    return fresh if fresh else entries


def _make(skill: str, prompt: str, answer: str, word_key: str | None = None) -> Question:
    return Question(
        question_id="",
        skill=skill,
        qtype=QTYPE_MULTIPLE_CHOICE,
        prompt=prompt,
        answer=answer,
        target_ms=adaptive.target_ms(skill),
        word_key=word_key,
    )


# --------------------------------------------------------------------------- spelling

def _spelling_choose(entry: dict, rng: random.Random) -> Question:
    q = _make("english.spelling", "Which spelling is correct?", entry["word"],
              word_key=entry["word"])
    q.options = list(entry["wrong"][:3]) + [entry["word"]]
    rng.shuffle(q.options)
    return q


def _spelling_missing_letters(entry: dict, rng: random.Random) -> Question:
    word = entry["word"]
    n_blanks = 2 if len(word) <= 7 else 3
    positions = sorted(rng.sample(range(len(word)), n_blanks))
    pattern = "".join("_" if i in positions else ch for i, ch in enumerate(word))
    needed = [word[i] for i in positions]
    decoys = []
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    while len(decoys) < 3:
        letter = rng.choice(alphabet)
        if letter not in needed and letter not in decoys:
            decoys.append(letter)
    tiles = needed + decoys
    rng.shuffle(tiles)
    q = Question(
        question_id="",
        skill="english.spelling",
        qtype=QTYPE_LETTERS_FILL,
        prompt="Fill in the missing letters",
        answer=word,
        options=tiles,
        fill_pattern=pattern,
        target_ms=adaptive.target_ms("english.spelling"),
        word_key=word,
    )
    return q


def _spelling_unscramble(entry: dict, rng: random.Random) -> Question:
    word = entry["word"]
    letters = list(word)
    for _ in range(20):
        rng.shuffle(letters)
        if "".join(letters) != word:
            break
    return Question(
        question_id="",
        skill="english.spelling",
        qtype=QTYPE_UNSCRAMBLE,
        prompt="Unscramble the word",
        answer=word,
        options=letters,
        fill_pattern="_" * len(word),
        target_ms=adaptive.target_ms("english.spelling"),
        word_key=word,
    )


def _gen_spelling(band: int, rng: random.Random, banks: WordBanks, exclude: set[str]) -> Question:
    entry = rng.choice(_by_band(banks.spelling, band, exclude, lambda e: e["word"]))
    variants = [_spelling_choose, _spelling_missing_letters]
    if len(entry["word"]) <= 8:
        variants.append(_spelling_unscramble)
    return rng.choice(variants)(entry, rng)


# --------------------------------------------------------------------------- vocabulary

def _vocab_distractors(banks: WordBanks, entry: dict, band: int, count: int,
                       rng: random.Random, taboo: set[str]) -> list[str]:
    pool = [
        e["word"]
        for e in banks.vocab
        if e["word"] != entry["word"]
        and e["word"] not in taboo
        and abs(e["band"] - band) <= 2
    ]
    rng.shuffle(pool)
    return pool[:count]


def _gen_vocabulary(band: int, rng: random.Random, banks: WordBanks, exclude: set[str]) -> Question:
    entry = rng.choice(_by_band(banks.vocab, band, exclude, lambda e: e["word"]))
    taboo = set(entry["synonyms"]) | set(entry["antonyms"]) | {entry["word"]}
    form = rng.choice(("definition", "synonym", "antonym"))

    if form == "definition":
        q = _make("english.vocabulary",
                  f"Which word means: “{entry['definition']}”?",
                  entry["word"], word_key=entry["word"])
        q.options = _vocab_distractors(banks, entry, band, 3, rng, taboo) + [entry["word"]]
    elif form == "synonym":
        answer = rng.choice(entry["synonyms"])
        q = _make("english.vocabulary",
                  f"Which word means the same as ‘{entry['word']}’?",
                  answer, word_key=entry["word"])
        q.options = _vocab_distractors(banks, entry, band, 3, rng, taboo) + [answer]
        q.explain = f"‘{entry['word']}’ means {entry['definition']}."
    else:
        answer = rng.choice(entry["antonyms"])
        q = _make("english.vocabulary",
                  f"Which word means the OPPOSITE of ‘{entry['word']}’?",
                  answer, word_key=entry["word"])
        q.options = _vocab_distractors(banks, entry, band, 3, rng, taboo) + [answer]
        q.explain = f"‘{entry['word']}’ means {entry['definition']}."
    rng.shuffle(q.options)
    return q


# --------------------------------------------------------------------------- word classes

def _gen_word_classes(band: int, rng: random.Random, banks: WordBanks, exclude: set[str]) -> Question:
    items = banks.word_classes["items"]
    entry = rng.choice(_by_band(items, band, exclude, lambda e: e["sentence"]))
    q = _make("english.word_classes",
              f"What type of word is ‘{entry['word']}’ in this sentence?",
              entry["class"], word_key=entry["sentence"])
    q.prompt_secondary = entry["sentence"]
    q.options = list(banks.word_classes["classes"])
    rng.shuffle(q.options)
    return q


# --------------------------------------------------------------------------- homophones

def _gen_homophones(band: int, rng: random.Random, banks: WordBanks, exclude: set[str]) -> Question:
    hset = rng.choice(_by_band(banks.homophones, band, exclude, lambda e: "/".join(e["words"])))
    sentence = rng.choice(hset["sentences"])
    q = _make("english.homophones", "Which word completes the sentence?",
              sentence["answer"], word_key="/".join(hset["words"]))
    q.prompt_secondary = sentence["text"]
    q.options = list(hset["words"])
    rng.shuffle(q.options)
    return q


# --------------------------------------------------------------------------- punctuation

def _gen_punctuation(band: int, rng: random.Random, banks: WordBanks, exclude: set[str]) -> Question:
    entry = rng.choice(_by_band(banks.punctuation, band, exclude, lambda e: e["correct"]))
    q = _make("english.punctuation", "Which sentence is punctuated correctly?",
              entry["correct"], word_key=entry["correct"])
    q.options = list(entry["wrong"][:3]) + [entry["correct"]]
    rng.shuffle(q.options)
    return q


# --------------------------------------------------------------------------- affixes

def _affix_forms(entry: dict) -> list[str]:
    forms = []
    if entry.get("prefix") and entry.get("meaning"):
        forms.append("prefix_pick")
    if entry.get("misspellings"):
        forms.append("spelling_pick")
    if entry.get("suffix") and entry.get("makes"):
        forms.append("suffix_function")
    if entry.get("prefix") or entry.get("suffix"):
        forms.append("root_word")
    return forms


def _gen_affixes(band: int, rng: random.Random, banks: WordBanks, exclude: set[str]) -> Question:
    entry = rng.choice(_by_band(banks.affixes, band, exclude, lambda e: e["word"]))
    form = rng.choice(_affix_forms(entry))
    word = entry["word"]

    if form == "prefix_pick":
        prefix = entry["prefix"]
        q = _make("english.affixes",
                  f"Which prefix makes a word meaning “{entry['meaning']}”?",
                  prefix, word_key=word)
        q.prompt_secondary = f"___ + {entry['root']}"
        q.options = list(entry["wrong_affixes"][:3]) + [prefix]
        q.explain = f"{prefix} + {entry['root']} = {word}"
    elif form == "spelling_pick":
        q = _make("english.affixes", "Which spelling is correct?", word, word_key=word)
        q.options = list(entry["misspellings"][:3]) + [word]
    elif form == "suffix_function":
        suffix = f"-{entry['suffix']}"
        q = _make("english.affixes",
                  f"Which suffix turns ‘{entry['root']}’ into "
                  f"{'an' if entry['makes'][0] in 'aeiou' else 'a'} {entry['makes']}?",
                  suffix, word_key=word)
        q.options = [f"-{w}" for w in entry["wrong_affixes"][:3]] + [suffix]
        q.explain = f"{entry['root']} → {word}"
    else:  # root_word
        root = entry["root"]
        distractors = {word}
        if entry.get("prefix") and entry.get("suffix"):
            distractors.add(word.removeprefix(entry["prefix"]))
            # strip-suffix-only variant, tolerating joined spelling changes
            if word.endswith(entry["suffix"]):
                distractors.add(word.removesuffix(entry["suffix"]))
        elif entry.get("prefix"):
            distractors.add(root + "ing")
        else:
            distractors.add("un" + root)
        distractors.discard(root)
        q = _make("english.affixes",
                  f"What is the root word of ‘{word}’?", root, word_key=word)
        q.options = sorted(distractors)[:3] + [root]
    rng.shuffle(q.options)
    return q


# --------------------------------------------------------------------------- registry

GENERATORS = {
    "english.spelling": _gen_spelling,
    "english.vocabulary": _gen_vocabulary,
    "english.word_classes": _gen_word_classes,
    "english.homophones": _gen_homophones,
    "english.punctuation": _gen_punctuation,
    "english.affixes": _gen_affixes,
}


def generate(skill: str, band: int, rng: random.Random, banks: WordBanks,
             exclude: set[str] | None = None) -> Question:
    band = max(1, min(5, band))
    return GENERATORS[skill](band, rng, banks, exclude or set())
