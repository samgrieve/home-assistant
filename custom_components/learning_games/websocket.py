"""WebSocket API used by the Lovelace card.

No command requires admin — the kid's dashboard user is a normal user.
Answers are validated server-side; questions on the wire never contain the
correct answer.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .coordinator import ProfileCoordinator
from .engine.arcade import CATEGORIES
from .engine.session import DEFAULT_LENGTH, SessionError

ERR_PROFILE_NOT_FOUND = "profile_not_found"
ERR_SESSION_NOT_FOUND = "session_not_found"
ERR_ARCADE_NOT_FOUND = "arcade_not_found"
ERR_INVALID_MODE = "invalid_mode"


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_profiles)
    websocket_api.async_register_command(hass, ws_get_stats)
    websocket_api.async_register_command(hass, ws_get_statistics)
    websocket_api.async_register_command(hass, ws_get_badges)
    websocket_api.async_register_command(hass, ws_start_session)
    websocket_api.async_register_command(hass, ws_submit_answer)
    websocket_api.async_register_command(hass, ws_abandon_session)
    websocket_api.async_register_command(hass, ws_start_arcade)
    websocket_api.async_register_command(hass, ws_finish_arcade)


def _coordinators(hass: HomeAssistant) -> dict[str, ProfileCoordinator]:
    return hass.data.get(DOMAIN, {}).get("coordinators", {})


def _get_coordinator(hass, connection, msg) -> ProfileCoordinator | None:
    coordinator = _coordinators(hass).get(msg["profile_id"])
    if coordinator is None:
        connection.send_error(msg["id"], ERR_PROFILE_NOT_FOUND, "Unknown profile")
    return coordinator


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_profiles"})
@callback
def ws_get_profiles(hass, connection, msg) -> None:
    connection.send_result(
        msg["id"],
        [coordinator.profile_summary() for coordinator in _coordinators(hass).values()],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_stats",
        vol.Required("profile_id"): str,
    }
)
@callback
def ws_get_stats(hass, connection, msg) -> None:
    if coordinator := _get_coordinator(hass, connection, msg):
        connection.send_result(msg["id"], coordinator.stats_payload())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_statistics",
        vol.Required("profile_id"): str,
    }
)
@callback
def ws_get_statistics(hass, connection, msg) -> None:
    if coordinator := _get_coordinator(hass, connection, msg):
        connection.send_result(msg["id"], coordinator.statistics_payload())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/get_badges",
        vol.Required("profile_id"): str,
    }
)
@callback
def ws_get_badges(hass, connection, msg) -> None:
    if coordinator := _get_coordinator(hass, connection, msg):
        connection.send_result(msg["id"], coordinator.badges_payload())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/start_session",
        vol.Required("profile_id"): str,
        vol.Required("mode"): str,
        vol.Optional("length", default=DEFAULT_LENGTH): vol.All(int, vol.Range(min=3, max=30)),
    }
)
@callback
def ws_start_session(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    try:
        result = coordinator.start_session(msg["mode"], msg["length"])
    except ValueError:
        connection.send_error(msg["id"], ERR_INVALID_MODE, f"Unknown mode {msg['mode']}")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/submit_answer",
        vol.Required("profile_id"): str,
        vol.Required("session_id"): str,
        vol.Required("question_id"): str,
        vol.Required("answer"): str,
        vol.Required("elapsed_ms"): vol.All(int, vol.Range(min=0)),
    }
)
@callback
def ws_submit_answer(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    try:
        result = coordinator.submit_answer(
            msg["session_id"], msg["question_id"], msg["answer"], msg["elapsed_ms"]
        )
    except SessionError:
        connection.send_error(
            msg["id"], ERR_SESSION_NOT_FOUND, "Session expired — start a new round"
        )
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/start_arcade",
        vol.Required("profile_id"): str,
        vol.Required("category"): vol.In(CATEGORIES),
    }
)
@callback
def ws_start_arcade(hass, connection, msg) -> None:
    if coordinator := _get_coordinator(hass, connection, msg):
        connection.send_result(msg["id"], coordinator.start_arcade(msg["category"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/finish_arcade",
        vol.Required("profile_id"): str,
        vol.Required("arcade_id"): str,
        vol.Required("rounds_completed"): vol.All(int, vol.Range(min=0, max=6)),
        vol.Required("rounds_played"): vol.All(int, vol.Range(min=1, max=20)),
        vol.Required("correct"): vol.All(int, vol.Range(min=0)),
        vol.Required("wrong"): vol.All(int, vol.Range(min=0)),
        vol.Required("won"): bool,
    }
)
@callback
def ws_finish_arcade(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    try:
        result = coordinator.finish_arcade(
            msg["arcade_id"], msg["rounds_completed"], msg["rounds_played"],
            msg["correct"], msg["wrong"], msg["won"],
        )
    except SessionError:
        connection.send_error(msg["id"], ERR_ARCADE_NOT_FOUND, "Arcade game not found")
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/abandon_session",
        vol.Required("profile_id"): str,
        vol.Required("session_id"): str,
    }
)
@callback
def ws_abandon_session(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    coordinator.abandon_session(msg["session_id"])
    connection.send_result(msg["id"], {"ok": True})
