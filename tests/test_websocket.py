"""End-to-end WebSocket tests: full rounds, events, entity updates."""
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.learning_games.const import (
    CONF_AVATAR,
    CONF_DAILY_GOAL,
    CONF_NAME,
    DOMAIN,
    EVENT_DAILY_GOAL,
    EVENT_SESSION_COMPLETE,
)


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    yield


async def setup_profile(hass: HomeAssistant, daily_goal=5):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maya",
        unique_id=f"{DOMAIN}_maya",
        data={CONF_NAME: "Maya", CONF_AVATAR: "fox", CONF_DAILY_GOAL: daily_goal},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_get_profiles(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/get_profiles"})
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == [
        {
            "profile_id": entry.entry_id,
            "name": "Maya",
            "avatar": "fox",
            "level": 1,
            "streak": 0,
        }
    ]


async def test_get_stats_and_badges(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/get_stats", "profile_id": entry.entry_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    stats = msg["result"]
    assert stats["daily"]["goal"] == 5
    assert len(stats["modes"]) == 12
    assert len(stats["skills"]) == 17
    assert len(stats["challenges"]) == 3
    assert stats["arcade"]["games"] == 0

    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/get_badges", "profile_id": entry.entry_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["earned"] == []
    assert len(msg["result"]["locked"]) == 30


async def test_get_statistics_empty_profile(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/get_statistics", "profile_id": entry.entry_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    stats = msg["result"]
    # A full contiguous 30-day window, all empty for a fresh profile.
    assert len(stats["days"]) == 30
    assert all(d["questions"] == 0 for d in stats["days"])
    assert stats["totals"]["questions"] == 0
    assert stats["totals"]["active_days"] == 0
    assert stats["totals"]["accuracy"] is None
    assert stats["max_day"] == 0
    assert len(stats["skills"]) == 17
    # Nothing practised yet, so no strongest/weakest.
    assert stats["strongest"] == []
    assert stats["weakest"] == []


async def test_get_statistics_after_a_round(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass, daily_goal=5)
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/start_session",
            "profile_id": entry.entry_id,
            "mode": "times_tables_blitz",
            "length": 10,
        }
    )
    msg = await client.receive_json()
    session_id = msg["result"]["session_id"]
    question = msg["result"]["question"]

    msg_id = 2
    for _ in range(10):
        correct = coordinator.sessions[session_id].current.answer
        await client.send_json(
            {
                "id": msg_id,
                "type": f"{DOMAIN}/submit_answer",
                "profile_id": entry.entry_id,
                "session_id": session_id,
                "question_id": question["question_id"],
                "answer": correct,
                "elapsed_ms": 1500,
            }
        )
        msg = await client.receive_json()
        msg_id += 1
        if "results" in msg["result"]:
            break
        question = msg["result"]["next_question"]

    await hass.async_block_till_done()

    await client.send_json(
        {"id": 99, "type": f"{DOMAIN}/get_statistics", "profile_id": entry.entry_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    stats = msg["result"]

    today = stats["days"][-1]
    assert today["questions"] == 10
    assert today["correct"] == 10
    assert today["xp"] > 0
    assert stats["totals"]["questions"] == 10
    assert stats["totals"]["active_days"] == 1
    assert stats["totals"]["accuracy"] == 100
    assert stats["max_day"] == 10
    # Times Table Blitz only trains one skill, so it's the strongest practised.
    assert stats["strongest"]
    assert stats["strongest"][0]["skill"] == "maths.times_tables"
    assert stats["strongest"][0]["accuracy"] == 100


async def test_unknown_profile_errors(hass: HomeAssistant, hass_ws_client):
    await setup_profile(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": f"{DOMAIN}/get_stats", "profile_id": "nope"}
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "profile_not_found"


async def test_full_round_with_events_and_entities(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass, daily_goal=5)
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    client = await hass_ws_client(hass)

    events = {EVENT_DAILY_GOAL: [], EVENT_SESSION_COMPLETE: []}
    for event_type in events:
        hass.bus.async_listen(
            event_type, lambda e, t=event_type: events[t].append(e.data)
        )

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/start_session",
            "profile_id": entry.entry_id,
            "mode": "times_tables_blitz",
            "length": 10,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    session_id = msg["result"]["session_id"]
    question = msg["result"]["question"]
    assert question["index"] == 1
    assert "answer" not in question  # never leak the answer

    msg_id = 2
    results = None
    for _ in range(10):
        # Cheat from the server side so we always answer correctly.
        correct = coordinator.sessions[session_id].current.answer
        await client.send_json(
            {
                "id": msg_id,
                "type": f"{DOMAIN}/submit_answer",
                "profile_id": entry.entry_id,
                "session_id": session_id,
                "question_id": question["question_id"],
                "answer": correct,
                "elapsed_ms": 1500,
            }
        )
        msg = await client.receive_json()
        assert msg["success"]
        assert msg["result"]["correct"] is True
        msg_id += 1
        if "results" in msg["result"]:
            results = msg["result"]["results"]
            break
        question = msg["result"]["next_question"]

    await hass.async_block_till_done()
    assert results is not None
    assert results["correct"] == 10
    assert results["daily_goal_met"] is True
    assert any(b["id"] == "first_steps" for b in results["new_badges"])
    assert any(b["id"] == "perfect_10" for b in results["new_badges"])
    assert any(b["id"] == "speedster" for b in results["new_badges"])

    assert len(events[EVENT_SESSION_COMPLETE]) == 1
    assert len(events[EVENT_DAILY_GOAL]) == 1
    assert events[EVENT_DAILY_GOAL][0]["streak"] == 1

    # Entities reflect the round.
    assert hass.states.get("sensor.maya_s_learning_games_questions_today").state == "10"
    assert hass.states.get("binary_sensor.maya_s_learning_games_daily_goal_met").state == "on"
    streak_state = hass.states.get("sensor.maya_s_learning_games_streak")
    assert streak_state.state == "1"
    badge_state = hass.states.get("sensor.maya_s_learning_games_last_badge")
    assert badge_state.state != "none"
    assert hass.states.get("sensor.maya_s_learning_games_maths_mastery").state not in (
        "unknown",
        "0.0",
    )

    # Session is gone once finished.
    assert session_id not in coordinator.sessions


async def test_submit_to_dead_session_errors(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/submit_answer",
            "profile_id": entry.entry_id,
            "session_id": "gone",
            "question_id": "q1",
            "answer": "1",
            "elapsed_ms": 1000,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "session_not_found"


async def test_abandon_session(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/start_session",
            "profile_id": entry.entry_id,
            "mode": "spelling_star",
            "length": 10,
        }
    )
    msg = await client.receive_json()
    session_id = msg["result"]["session_id"]
    assert session_id in coordinator.sessions

    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/abandon_session",
            "profile_id": entry.entry_id,
            "session_id": session_id,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert session_id not in coordinator.sessions


async def test_arcade_full_flow(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass, daily_goal=5)
    client = await hass_ws_client(hass)

    events = []
    hass.bus.async_listen(EVENT_SESSION_COMPLETE, lambda e: events.append(e.data))

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/start_arcade",
            "profile_id": entry.entry_id,
            "category": "synonyms",
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    start = msg["result"]
    assert start["rounds"] == 6
    assert len(start["rounds_data"]) == 6
    assert start["skill"] == "english.vocabulary"
    assert len(start["travel_s"]) == 6

    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/finish_arcade",
            "profile_id": entry.entry_id,
            "arcade_id": start["arcade_id"],
            "rounds_completed": 6,
            "rounds_played": 7,
            "correct": 9999,  # absurd — must be clamped
            "wrong": 500,
            "won": True,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    result = msg["result"]
    assert result["won"] is True
    assert result["correct_counted"] <= 12 * 7  # clamp applied
    assert result["xp_gained"] > 0
    assert any(b["id"] == "fly_snapper" for b in result["new_badges"])
    assert any(b["id"] == "frog_champion" for b in result["new_badges"])

    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0]["mode"] == "fly_snap"

    coordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    assert coordinator.data["arcade"]["games"] == 1
    assert coordinator.data["arcade"]["wins"] == 1
    assert coordinator.data["daily"]["questions"] > 0
    assert coordinator.data["daily"]["goal_met"] is True

    # A second finish for the same arcade id must fail.
    await client.send_json(
        {
            "id": 3,
            "type": f"{DOMAIN}/finish_arcade",
            "profile_id": entry.entry_id,
            "arcade_id": start["arcade_id"],
            "rounds_completed": 6,
            "rounds_played": 6,
            "correct": 10,
            "wrong": 0,
            "won": True,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "arcade_not_found"


async def test_boss_battle_multiplier_and_challenges(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass, daily_goal=50)
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/start_session",
            "profile_id": entry.entry_id,
            "mode": "boss_battle",
            "length": 10,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    session_id = msg["result"]["session_id"]
    question = msg["result"]["question"]

    await client.send_json(
        {
            "id": 2,
            "type": f"{DOMAIN}/submit_answer",
            "profile_id": entry.entry_id,
            "session_id": session_id,
            "question_id": question["question_id"],
            "answer": "deliberately wrong answer",
            "elapsed_ms": 1500,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    # Effort XP is 1; the boss multiplier makes it ceil(1 * 1.5) = 2.
    assert msg["result"]["xp_delta"] == 2

    # Challenge progress is visible in stats.
    await client.send_json(
        {"id": 3, "type": f"{DOMAIN}/get_stats", "profile_id": entry.entry_id}
    )
    msg = await client.receive_json()
    challenges = msg["result"]["challenges"]
    assert len(challenges) == 3
    assert all({"name", "icon", "desc", "target", "progress", "done"} <= set(c) for c in challenges)


async def test_invalid_mode_errors(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": f"{DOMAIN}/start_session",
            "profile_id": entry.entry_id,
            "mode": "fortnite",
            "length": 10,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == "invalid_mode"


# ---------------------------------------------------------------- learning journal


async def test_journal_entry_flow(hass: HomeAssistant, hass_ws_client):
    from pytest_homeassistant_custom_component.common import async_capture_events

    entry = await setup_profile(hass)
    pid = entry.entry_id
    client = await hass_ws_client(hass)
    events = async_capture_events(hass, "learning_games_journal_entry")
    goal_events = async_capture_events(hass, EVENT_DAILY_GOAL)

    await client.send_json({"id": 1, "type": f"{DOMAIN}/journal/get", "profile_id": pid})
    msg = await client.receive_json()
    assert msg["success"]
    j = msg["result"]
    assert j["entry"] is None and j["is_parent"] is False
    assert len(j["editable_dates"]) == 3
    assert any(s["id"] == "science" for s in j["subjects"])
    today = j["today"]

    save = {
        "type": f"{DOMAIN}/journal/save_entry",
        "profile_id": pid,
        "date": today,
        "mood": 5,
        "subjects": [{"id": "science", "enjoy": 5, "difficulty": "easy", "note": "Magnets"}],
        "did": "Made a compass with a magnet",
        "enjoyed": "",
        "tricky": "",
    }
    await client.send_json({"id": 2, **save})
    msg = await client.receive_json()
    assert msg["success"], msg
    res = msg["result"]
    assert res["xp_gained"] == 15 and res["is_update"] is False
    assert "dear_diary" in [b["id"] for b in res["new_badges"]]

    # Editing doesn't award XP again and flags the event as an update.
    await client.send_json({"id": 3, **save, "tricky": "North vs south pole"})
    msg = await client.receive_json()
    assert msg["result"]["xp_gained"] == 0 and msg["result"]["is_update"] is True
    await hass.async_block_till_done()

    assert [e.data["is_update"] for e in events] == [False, True]
    assert events[0].data["subjects"] == ["Science"]
    assert events[0].data["url"] == f"?lg=journal&date={today}"
    assert events[0].data["snippet"] == "Made a compass with a magnet"
    # Journal never counts toward the daily question goal.
    assert goal_events == []
    assert hass.states.get("binary_sensor.maya_s_learning_games_daily_goal_met").state == "off"
    level = hass.states.get("sensor.maya_s_learning_games_level")
    assert level.attributes["xp_total"] == 15

    state = hass.states.get("sensor.maya_s_learning_games_journal")
    assert state.state == today
    assert state.attributes["total_entries"] == 1
    assert state.attributes["journal_streak"] == 1
    assert state.attributes["unreviewed_count"] == 1
    assert state.attributes["subjects"]["Science"]["count"] == 1
    assert "did" not in str(state.attributes["last_entry"])  # no free text in the recorder

    # Back-filling 3 days ago is refused.
    from datetime import date, timedelta

    old = (date.fromisoformat(today) - timedelta(days=3)).isoformat()
    await client.send_json({"id": 4, **save, "date": old})
    msg = await client.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "date_locked"


async def test_journal_add_subject_dedupes(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    client = await hass_ws_client(hass)
    base = {"type": f"{DOMAIN}/journal/add_subject", "profile_id": entry.entry_id}

    await client.send_json({"id": 1, **base, "name": "science"})
    msg = await client.receive_json()
    assert msg["result"]["status"] == "exists"

    await client.send_json({"id": 2, **base, "name": "Sciense"})
    msg = await client.receive_json()
    assert msg["result"]["status"] == "similar"
    assert msg["result"]["similar"][0]["name"] == "Science"

    await client.send_json({"id": 3, **base, "name": "Piano", "emoji": "🎹"})
    msg = await client.receive_json()
    assert msg["result"]["status"] == "added"


async def test_journal_review_requires_parent(
    hass: HomeAssistant, hass_ws_client, hass_admin_user,
    hass_read_only_user, hass_read_only_access_token,
):
    from pytest_homeassistant_custom_component.common import async_capture_events

    entry = await setup_profile(hass)
    pid = entry.entry_id
    reviewed = async_capture_events(hass, "learning_games_journal_reviewed")
    kid = await hass_ws_client(hass, access_token=hass_read_only_access_token)
    await kid.send_json({"id": 1, "type": f"{DOMAIN}/journal/get", "profile_id": pid})
    today = (await kid.receive_json())["result"]["today"]
    await kid.send_json({
        "id": 2, "type": f"{DOMAIN}/journal/save_entry", "profile_id": pid,
        "date": today, "subjects": [{"id": "art", "enjoy": 4}],
    })
    assert (await kid.receive_json())["success"]

    review = {"type": f"{DOMAIN}/journal/review", "profile_id": pid,
              "date": today, "reaction": "⭐", "comment": "Lovely!"}
    await kid.send_json({"id": 3, **review})
    msg = await kid.receive_json()
    assert not msg["success"] and msg["error"]["code"] == "not_parent"

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, "parent_users": [hass_admin_user.id]}
    )
    await hass.async_block_till_done()
    parent = await hass_ws_client(hass)
    await parent.send_json({"id": 1, "type": f"{DOMAIN}/journal/get", "profile_id": pid})
    assert (await parent.receive_json())["result"]["is_parent"] is True
    await parent.send_json({"id": 2, **review})
    msg = await parent.receive_json()
    assert msg["success"], msg
    assert msg["result"]["reviews"][0]["reaction"] == "⭐"
    await hass.async_block_till_done()
    assert reviewed[0].data["comment"] == "Lovely!"

    # Lizzie sees the sticker on her home screen until she opens it.
    await kid.send_json({"id": 4, "type": f"{DOMAIN}/get_stats", "profile_id": pid})
    stats = (await kid.receive_json())["result"]
    assert stats["journal"]["done_today"] is True
    assert stats["journal"]["unseen_reviews"][0]["date"] == today
    await kid.send_json({"id": 5, "type": f"{DOMAIN}/journal/mark_seen", "profile_id": pid})
    assert (await kid.receive_json())["success"]
    await kid.send_json({"id": 6, "type": f"{DOMAIN}/get_stats", "profile_id": pid})
    assert (await kid.receive_json())["result"]["journal"]["unseen_reviews"] == []

    # Only parents may merge subjects.
    merge = {"type": f"{DOMAIN}/journal/merge_subjects", "profile_id": pid,
             "source_id": "art", "target_id": "music"}
    await kid.send_json({"id": 7, **merge})
    assert (await kid.receive_json())["error"]["code"] == "not_parent"
    await parent.send_json({"id": 3, **merge})
    assert (await parent.receive_json())["success"]


# ---------------------------------------------------------------- v1.4: focus & summary


async def test_tricky_journal_topic_drives_todays_focus(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    pid = entry.entry_id
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/journal/get", "profile_id": pid})
    j = (await client.receive_json())["result"]
    maths = next(s for s in j["subjects"] if s["id"] == "maths")
    assert "maths.fractions" in maths["skills"]
    assert j["topics"]["maths.long_multiplication"] == "Long multiplication"

    await client.send_json({
        "id": 2, "type": f"{DOMAIN}/journal/save_entry", "profile_id": pid,
        "date": j["today"],
        "subjects": [{"id": "maths", "enjoy": 2, "difficulty": "tricky",
                      "topics": ["maths.fractions"]}],
    })
    assert (await client.receive_json())["success"]

    await client.send_json({"id": 3, "type": f"{DOMAIN}/get_stats", "profile_id": pid})
    stats = (await client.receive_json())["result"]
    assert stats["focus"][0]["skill"] == "maths.fractions"
    assert stats["focus"][0]["reason"] == "tricky"
    assert stats["school_year"] == 5
    assert "todays_focus" in stats["modes"]

    # A full Today's Focus round runs end to end and leans on fractions.
    await client.send_json({"id": 4, "type": f"{DOMAIN}/start_session",
                            "profile_id": pid, "mode": "todays_focus", "length": 10})
    msg = await client.receive_json()
    assert msg["success"], msg
    session_id = msg["result"]["session_id"]
    question = msg["result"]["question"]
    for i in range(10):
        await client.send_json({
            "id": 10 + i, "type": f"{DOMAIN}/submit_answer", "profile_id": pid,
            "session_id": session_id, "question_id": question["question_id"],
            "answer": "0", "elapsed_ms": 4000,
        })
        res = (await client.receive_json())["result"]
        question = res.get("next_question")
    assert res["results"]["mode"] == "todays_focus"
    assert res["results"]["total"] == 10


async def test_weekly_summary_sensor(hass: HomeAssistant, hass_ws_client):
    entry = await setup_profile(hass)
    pid = entry.entry_id
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": f"{DOMAIN}/journal/get", "profile_id": pid})
    today = (await client.receive_json())["result"]["today"]
    await client.send_json({
        "id": 2, "type": f"{DOMAIN}/journal/save_entry", "profile_id": pid,
        "date": today, "did": "Secret diary words",
        "subjects": [{"id": "art", "enjoy": 5}, {"id": "maths", "difficulty": "tricky",
                                                 "topics": ["maths.decimals"]}],
    })
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()

    state = hass.states.get("sensor.maya_s_learning_games_weekly_summary")
    attrs = state.attributes
    assert state.state == attrs["week_start"]
    assert attrs["journal"]["entries"] == 1
    assert attrs["journal"]["favourite"] == "Art"
    assert attrs["journal"]["trickiest"] == "Maths"
    assert attrs["journal"]["tricky_topics"] == ["Decimals"]
    assert attrs["journal"]["new_subjects"] == []
    assert "Dear Diary" in attrs["badges"]
    assert attrs["needs_work"][0]["name"] == "Decimals"
    assert "Maya's week" in attrs["parent_title"]
    assert "found Maths (Decimals) tricky" in attrs["parent_text"]
    assert "wrote in your journal 1 time" in attrs["kid_text"]
    assert "Secret diary words" not in str(attrs)  # her writing never leaves the card

    await client.send_json({"id": 3, "type": f"{DOMAIN}/get_statistics", "profile_id": pid})
    st = (await client.receive_json())["result"]
    assert st["week"]["journal"]["entries"] == 1


async def test_topic_challenges_progress_and_focus_rounds(hass: HomeAssistant, hass_ws_client):
    from custom_components.learning_games.engine import challenges as ch

    entry = await setup_profile(hass)
    pid = entry.entry_id
    c = hass.data[DOMAIN]["coordinators"][pid]
    weekly = c.data["weekly"]
    # Fresh profiles already get one topic challenge.
    assert sum(1 for x in weekly["challenges"] if x["type"] in ch.TOPIC_TYPES) == 1

    ws = weekly["week_start"]
    weekly["challenges"] = [
        {"id": f"{ws}-topic_correct", "type": "topic_correct", "target": 10,
         "progress": 0, "done": False, "skill": "maths.times_tables"},
        {"id": f"{ws}-topic_raise", "type": "topic_raise", "target": 5,
         "progress": 0, "done": False, "skill": "english.spelling", "start": 0.0},
        {"id": f"{ws}-xp", "type": "xp", "target": 99999, "progress": 0, "done": False},
    ]
    client = await hass_ws_client(hass)

    async def play(mode, rid):
        await client.send_json({"id": rid, "type": f"{DOMAIN}/start_session",
                                "profile_id": pid, "mode": mode, "length": 10})
        res = (await client.receive_json())["result"]
        sid, q = res["session_id"], res["question"]
        for i in range(10):
            sess = c.sessions[sid]
            await client.send_json({
                "id": rid + 1 + i, "type": f"{DOMAIN}/submit_answer", "profile_id": pid,
                "session_id": sid, "question_id": q["question_id"],
                "answer": sess.current.answer, "elapsed_ms": 2000,
            })
            r = (await client.receive_json())["result"]
            q = r.get("next_question")
        return r

    await play("times_tables_blitz", 100)
    await play("word_wizard", 200)  # vocabulary: must not count for times tables
    topic_correct = weekly["challenges"][0]
    assert topic_correct["progress"] == 10 and topic_correct["done"] is True

    c.skills["english.spelling"].mastery = 6.4
    await play("spelling_star", 300)
    raise_ch = weekly["challenges"][1]
    # 10 right answers lift spelling well past +5: completed, then it stops tracking.
    assert raise_ch["done"] is True and raise_ch["progress"] >= 5

    await play("todays_focus", 400)
    assert c.data["focus_rounds"] == 1
    await hass.async_block_till_done()
    attrs = hass.states.get(
        "sensor.maya_s_learning_games_weekly_challenges_done").attributes
    assert attrs["challenges"][0]["skill"] == "maths.times_tables"
    assert attrs["challenges"][0]["desc"] == "Get 10 Times tables answers right"
    assert set(attrs["challenges"][2]) == {
        "id", "type", "name", "icon", "desc", "target", "progress", "done"}
