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
from .engine.journal import (
    DIFFICULTIES,
    MAX_COMMENT,
    MAX_NOTE,
    MAX_SUBJECT_NAME,
    MAX_TEXT,
    REACTIONS,
    JournalError,
)
from .engine.session import DEFAULT_LENGTH, SessionError

ERR_PROFILE_NOT_FOUND = "profile_not_found"
ERR_SESSION_NOT_FOUND = "session_not_found"
ERR_ARCADE_NOT_FOUND = "arcade_not_found"
ERR_INVALID_MODE = "invalid_mode"
ERR_NOT_PARENT = "not_parent"


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
    websocket_api.async_register_command(hass, ws_journal_get)
    websocket_api.async_register_command(hass, ws_journal_save_entry)
    websocket_api.async_register_command(hass, ws_journal_add_subject)
    websocket_api.async_register_command(hass, ws_journal_update_subject)
    websocket_api.async_register_command(hass, ws_journal_merge_subjects)
    websocket_api.async_register_command(hass, ws_journal_review)
    websocket_api.async_register_command(hass, ws_journal_mark_seen)


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
        user_id, _ = _user(connection)
        connection.send_result(msg["id"], coordinator.statistics_payload(user_id))


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


# ---------------------------------------------------------------- learning journal

ISO_DATE = vol.Match(r"^\d{4}-\d{2}-\d{2}$")
RATING = vol.Any(None, vol.All(int, vol.Range(min=1, max=5)))


def _short_text(limit: int):
    # Over-long text is trimmed server-side rather than rejected, so a long
    # paste never loses an entry; this cap just bounds the message size.
    return vol.All(str, vol.Length(max=limit * 4))


def _user(connection) -> tuple[str | None, str]:
    user = getattr(connection, "user", None)
    if user is None:
        return None, "Parent"
    return user.id, user.name or "Parent"


def _require_parent(coordinator, connection, msg) -> bool:
    user_id, _ = _user(connection)
    if coordinator.is_parent(user_id):
        return True
    connection.send_error(
        msg["id"], ERR_NOT_PARENT,
        "Only parents set in the Learning Games options can do this",
    )
    return False


def _journal_error(connection, msg, err: JournalError) -> None:
    connection.send_error(msg["id"], err.code, str(err))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/get",
        vol.Required("profile_id"): str,
        vol.Optional("date"): vol.Any(None, ISO_DATE),
    }
)
@callback
def ws_journal_get(hass, connection, msg) -> None:
    if coordinator := _get_coordinator(hass, connection, msg):
        user_id, _ = _user(connection)
        connection.send_result(
            msg["id"], coordinator.journal_payload(msg.get("date"), user_id)
        )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/save_entry",
        vol.Required("profile_id"): str,
        vol.Required("date"): ISO_DATE,
        vol.Optional("mood"): RATING,
        vol.Optional("subjects", default=[]): vol.All(
            [
                {
                    vol.Required("id"): vol.All(str, vol.Length(max=64)),
                    vol.Optional("enjoy"): RATING,
                    vol.Optional("difficulty"): vol.Any(None, vol.In(DIFFICULTIES)),
                    vol.Optional("note", default=""): _short_text(MAX_NOTE),
                    vol.Optional("topics", default=[]): vol.All(
                        [vol.All(str, vol.Length(max=64))], vol.Length(max=20)
                    ),
                }
            ],
            vol.Length(max=30),
        ),
        vol.Optional("did", default=""): _short_text(MAX_TEXT),
        vol.Optional("enjoyed", default=""): _short_text(MAX_TEXT),
        vol.Optional("tricky", default=""): _short_text(MAX_TEXT),
    }
)
@callback
def ws_journal_save_entry(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    payload = {k: v for k, v in msg.items() if k not in ("id", "type", "profile_id")}
    try:
        result = coordinator.save_journal_entry(payload)
    except JournalError as err:
        _journal_error(connection, msg, err)
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/add_subject",
        vol.Required("profile_id"): str,
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=MAX_SUBJECT_NAME * 2)),
        vol.Optional("emoji", default=""): vol.All(str, vol.Length(max=16)),
        vol.Optional("force", default=False): bool,
    }
)
@callback
def ws_journal_add_subject(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    try:
        result = coordinator.add_journal_subject(msg["name"], msg["emoji"], msg["force"])
    except JournalError as err:
        _journal_error(connection, msg, err)
        return
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/update_subject",
        vol.Required("profile_id"): str,
        vol.Required("subject_id"): str,
        vol.Optional("name"): vol.All(str, vol.Length(min=1, max=MAX_SUBJECT_NAME * 2)),
        vol.Optional("emoji"): vol.All(str, vol.Length(max=16)),
        vol.Optional("hidden"): bool,
        vol.Optional("skills"): vol.All([vol.All(str, vol.Length(max=64))], vol.Length(max=40)),
    }
)
@callback
def ws_journal_update_subject(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    if not _require_parent(coordinator, connection, msg):
        return
    changes = {k: msg[k] for k in ("name", "emoji", "hidden", "skills") if k in msg}
    try:
        subject = coordinator.update_journal_subject(msg["subject_id"], **changes)
    except JournalError as err:
        _journal_error(connection, msg, err)
        return
    connection.send_result(msg["id"], subject)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/merge_subjects",
        vol.Required("profile_id"): str,
        vol.Required("source_id"): str,
        vol.Required("target_id"): str,
    }
)
@callback
def ws_journal_merge_subjects(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    if not _require_parent(coordinator, connection, msg):
        return
    try:
        subject = coordinator.merge_journal_subjects(msg["source_id"], msg["target_id"])
    except JournalError as err:
        _journal_error(connection, msg, err)
        return
    connection.send_result(msg["id"], subject)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/review",
        vol.Required("profile_id"): str,
        vol.Required("date"): ISO_DATE,
        vol.Optional("reaction"): vol.Any(None, vol.In(REACTIONS)),
        vol.Optional("comment", default=""): vol.All(str, vol.Length(max=MAX_COMMENT * 2)),
    }
)
@callback
def ws_journal_review(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    if not _require_parent(coordinator, connection, msg):
        return
    user_id, user_name = _user(connection)
    try:
        entry = coordinator.review_journal_entry(
            msg["date"], msg.get("reaction"), msg["comment"], user_id, user_name
        )
    except JournalError as err:
        _journal_error(connection, msg, err)
        return
    connection.send_result(msg["id"], entry)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/journal/mark_seen",
        vol.Required("profile_id"): str,
        vol.Optional("date"): vol.Any(None, ISO_DATE),
    }
)
@callback
def ws_journal_mark_seen(hass, connection, msg) -> None:
    if not (coordinator := _get_coordinator(hass, connection, msg)):
        return
    # Parents browsing the journal shouldn't clear Lizzie's "new sticker" banner.
    user_id, _ = _user(connection)
    if not coordinator.is_parent(user_id):
        coordinator.mark_reviews_seen(msg.get("date"))
    connection.send_result(msg["id"], {"ok": True})
