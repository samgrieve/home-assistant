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
    assert len(stats["modes"]) == 8
    assert len(stats["skills"]) == 15

    await client.send_json(
        {"id": 2, "type": f"{DOMAIN}/get_badges", "profile_id": entry.entry_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["earned"] == []
    assert len(msg["result"]["locked"]) == 16


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
