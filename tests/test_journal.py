"""Pure-engine tests for the learning journal."""
from datetime import date

import pytest

from custom_components.learning_games.engine import journal as J
from custom_components.learning_games.engine.badges import check_badges
from custom_components.learning_games.storage import default_data

TODAY = date(2026, 11, 24)


@pytest.fixture
def jr():
    return J.default_journal("2026-11-01")


def test_slugify_normalises():
    assert J.slugify("  P.E. / Sport ") == "pe_sport"
    assert J.slugify("Arts & Crafts") == "arts_and_crafts"
    assert J.slugify("Français") == "francais"
    assert J.slugify("!!!") == ""


def test_seed_subjects(jr):
    names = {s["name"] for s in jr["subjects"].values()}
    assert {"Reading", "Science", "Maths", "PE/Sport"} <= names
    assert jr["entries"] == {}


def test_add_existing_returns_it_and_unhides(jr):
    jr["subjects"]["science"]["hidden"] = True
    res = J.add_subject(jr, "SCIENCE ", "", "2026-11-24")
    assert res["status"] == "exists"
    assert res["subject"]["id"] == "science"
    assert jr["subjects"]["science"]["hidden"] is False


def test_add_similar_needs_confirmation(jr):
    res = J.add_subject(jr, "Sciense", "", "2026-11-24")
    assert res["status"] == "similar"
    assert [s["id"] for s in res["similar"]] == ["science"]
    assert "sciense" not in jr["subjects"]
    forced = J.add_subject(jr, "Sciense", "🧪", "2026-11-24", force=True)
    assert forced["status"] == "added"
    assert jr["subjects"]["sciense"]["emoji"] == "🧪"


def test_prefix_counts_as_similar(jr):
    res = J.add_subject(jr, "Read", "", "2026-11-24")
    assert res["status"] == "similar"


def test_add_new_subject(jr):
    res = J.add_subject(jr, "Piano", "🎹", "2026-11-24")
    assert res["status"] == "added"
    assert jr["subjects"]["piano"]["name"] == "Piano"


def test_add_blank_name_rejected(jr):
    with pytest.raises(J.JournalError) as err:
        J.add_subject(jr, "  ", "", "2026-11-24")
    assert err.value.code == "invalid_name"


def _payload(**kw):
    base = {
        "date": TODAY.isoformat(),
        "mood": 4,
        "subjects": [{"id": "science", "enjoy": 5, "difficulty": "easy", "note": "Magnets"}],
        "did": "We did magnets",
        "enjoyed": "",
        "tricky": "",
    }
    base.update(kw)
    return base


def test_validate_entry_window(jr):
    assert J.validate_entry(jr, _payload(date="2026-11-22"), TODAY)["date"] == "2026-11-22"
    with pytest.raises(J.JournalError) as err:
        J.validate_entry(jr, _payload(date="2026-11-21"), TODAY)
    assert err.value.code == "date_locked"
    with pytest.raises(J.JournalError):
        J.validate_entry(jr, _payload(date="2026-11-25"), TODAY)


def test_validate_entry_rejects_bad_values(jr):
    with pytest.raises(J.JournalError):
        J.validate_entry(jr, _payload(subjects=[{"id": "nope"}]), TODAY)
    with pytest.raises(J.JournalError):
        J.validate_entry(jr, _payload(subjects=[{"id": "art", "enjoy": 9}]), TODAY)
    with pytest.raises(J.JournalError):
        J.validate_entry(jr, _payload(subjects=[{"id": "art", "difficulty": "hard"}]), TODAY)
    with pytest.raises(J.JournalError) as err:
        J.validate_entry(jr, _payload(subjects=[], did=""), TODAY)
    assert err.value.code == "empty_entry"


def test_validate_trims_and_dedupes(jr):
    body = J.validate_entry(
        jr,
        _payload(did="x" * 900, subjects=[{"id": "art"}, {"id": "art"}]),
        TODAY,
    )
    assert len(body["did"]) == J.MAX_TEXT
    assert len(body["subjects"]) == 1


def test_upsert_and_review(jr):
    body = J.validate_entry(jr, _payload(), TODAY)
    entry, is_update = J.upsert_entry(jr, body, "t1")
    assert not is_update and entry["reviews"] == [] and entry["seen_reviews"]
    entry, is_update = J.upsert_entry(jr, {**body, "mood": 2}, "t2")
    assert is_update and entry["mood"] == 2 and entry["created_ts"] == "t1"

    J.add_review(entry, "u1", "Sam", "⭐", "Brilliant!", "t3")
    assert entry["seen_reviews"] is False
    with pytest.raises(J.JournalError):
        J.add_review(entry, "u1", "Sam", "🍕", "", "t4")
    with pytest.raises(J.JournalError):
        J.add_review(entry, "u1", "Sam", None, "  ", "t4")


def test_merge_rewrites_history(jr):
    J.add_subject(jr, "Sciense", "", "2026-11-20", force=True)
    for d, sid in (("2026-11-20", "sciense"), ("2026-11-21", "science")):
        jr["entries"][d] = {"date": d, "subjects": [{"id": sid, "enjoy": 4}]}
    jr["entries"]["2026-11-22"] = {
        "date": "2026-11-22",
        "subjects": [{"id": "sciense", "enjoy": 2}, {"id": "science", "enjoy": 5}],
    }
    J.merge_subject(jr, "sciense", "science")
    assert jr["subjects"]["sciense"]["merged_into"] == "science"
    assert all(i["id"] == "science" for e in jr["entries"].values() for i in e["subjects"])
    assert len(jr["entries"]["2026-11-22"]["subjects"]) == 1
    assert J.resolve(jr, "sciense") == "science"
    assert "sciense" not in {s["id"] for s in J.active_subjects(jr, include_hidden=True)}
    # Adding the typo again now resolves to the merged-into subject.
    assert J.add_subject(jr, "Sciense", "", "2026-11-24")["subject"]["id"] == "science"


def test_subject_stats_and_streak(jr):
    jr["entries"] = {
        "2026-11-24": {"subjects": [{"id": "art", "enjoy": 5, "difficulty": "easy"}]},
        "2026-11-23": {"subjects": [{"id": "art", "enjoy": 3, "difficulty": "tricky"},
                                    {"id": "music", "enjoy": 4}]},
        "2026-11-21": {"subjects": [{"id": "art", "enjoy": 4}]},
        "2026-10-10": {"subjects": [{"id": "art", "enjoy": 1}]},
    }
    stats = J.subject_stats(jr, TODAY)
    art = stats[0]
    assert art["id"] == "art" and art["count"] == 4
    assert art["last_done"] == "2026-11-24"
    assert art["easy"] == 1 and art["tricky"] == 1
    assert art["trend"] == "up"
    assert stats[1]["id"] == "music"
    assert J.journal_streak(jr["entries"], TODAY) == 2
    assert J.journal_streak(jr["entries"], date(2026, 11, 25)) == 2
    assert J.journal_streak(jr["entries"], date(2026, 11, 27)) == 0
    assert J.distinct_subjects_logged(jr) == 2


def test_snippet_prefers_free_text():
    assert J.snippet({"did": "", "enjoyed": "Painting", "subjects": []}) == "Painting"
    assert J.snippet({"subjects": [{"id": "a", "note": "note!"}]}) == "note!"
    assert J.snippet({"did": "a" * 200}).endswith("…")


def test_journal_badges():
    data = default_data("Maya", "fox", "2026-11-24")
    assert "dear_diary" not in check_badges(data, {"trigger": "journal"})
    entry = {"did": "x" * 20, "enjoyed": "y" * 20, "tricky": "z" * 20, "subjects": []}
    data["journal"]["entries"]["2026-11-24"] = entry
    new = check_badges(data, {"trigger": "journal", "entry": entry, "journal_streak": 7})
    assert {"dear_diary", "deep_thinker", "reflective_writer"} <= set(new)
    assert "curious_mind" not in new
    entry["subjects"] = [{"id": s} for s in ("art", "music", "maths", "science", "french")]
    assert "curious_mind" in check_badges(data, {"trigger": "journal", "entry": entry})


# ---------------------------------------------------------------- v1.4: topics & focus


def test_seed_subjects_link_to_game_topics(jr):
    assert "maths.fractions" in jr["subjects"]["maths"]["skills"]
    assert all(s.startswith("maths.") for s in jr["subjects"]["maths"]["skills"])
    assert jr["subjects"]["spelling"]["skills"] == ["english.spelling"]
    assert jr["subjects"]["art"]["skills"] == []


def test_ensure_subject_skills_migrates_old_subjects(jr):
    for s in jr["subjects"].values():
        del s["skills"]
    assert J.ensure_subject_skills(jr) is True
    assert jr["subjects"]["writing"]["skills"] == [
        "english.punctuation", "english.word_classes", "english.affixes"]
    assert J.ensure_subject_skills(jr) is False  # idempotent


def test_topics_must_be_linked(jr):
    body = J.validate_entry(jr, _payload(subjects=[
        {"id": "maths", "difficulty": "tricky", "topics": ["maths.fractions", "maths.fractions"]}
    ]), TODAY)
    assert body["subjects"][0]["topics"] == ["maths.fractions"]
    with pytest.raises(J.JournalError) as err:
        J.validate_entry(jr, _payload(subjects=[
            {"id": "maths", "topics": ["english.spelling"]}]), TODAY)
    assert err.value.code == "unknown_topic"


def test_update_subject_skills(jr):
    J.add_subject(jr, "Piano", "🎹", "2026-11-24")
    J.update_subject(jr, "piano", skills=["maths.fractions"])
    assert jr["subjects"]["piano"]["skills"] == ["maths.fractions"]
    with pytest.raises(J.JournalError):
        J.update_subject(jr, "piano", skills=["maths.algebra"])


def test_merge_keeps_topic_links(jr):
    J.add_subject(jr, "Sums", "", "2026-11-20", force=True)
    J.update_subject(jr, "sums", skills=["maths.addition"])
    J.update_subject(jr, "art", skills=[])
    J.merge_subject(jr, "sums", "art")
    assert jr["subjects"]["art"]["skills"] == ["maths.addition"]


def test_journal_focus_weights_and_decay(jr):
    jr["entries"] = {
        "2026-11-24": {"subjects": [
            {"id": "maths", "difficulty": "tricky", "topics": ["maths.fractions"]},
            {"id": "spelling", "difficulty": "easy"},
        ]},
        "2026-11-17": {"subjects": [  # a week old: half weight
            {"id": "maths", "difficulty": "tricky", "topics": ["maths.fractions"]},
        ]},
        "2026-11-20": {"subjects": [  # tricky, no topic picked: spread thinly
            {"id": "writing", "difficulty": "tricky", "enjoy": 2},
        ]},
        "2026-11-01": {"subjects": [  # older than 14 days: ignored
            {"id": "maths", "difficulty": "tricky", "topics": ["maths.money"]},
        ]},
        "2026-11-23": {"subjects": [{"id": "art", "difficulty": "tricky"}]},  # unlinked
    }
    f = J.journal_focus(jr, TODAY)
    assert f["maths.fractions"] == pytest.approx(1.5, abs=0.01)
    assert f["english.spelling"] == pytest.approx(-0.3, abs=0.01)
    decay = 0.5 ** (4 / 7)
    assert f["english.punctuation"] == pytest.approx((0.4 + 0.2) * decay, abs=0.01)
    assert "maths.money" not in f
    assert "maths.addition" not in f
    reasons = J.tricky_reasons(jr, TODAY)
    assert reasons["maths.fractions"] == "2026-11-24"
    assert "maths.money" not in reasons


def test_journal_focus_is_clamped(jr):
    jr["entries"] = {
        f"2026-11-{d:02d}": {"subjects": [
            {"id": "maths", "difficulty": "tricky", "topics": ["maths.decimals"]}]}
        for d in range(15, 25)
    }
    assert J.journal_focus(jr, TODAY)["maths.decimals"] == J.FOCUS_MAX
