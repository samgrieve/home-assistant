"""Persistent profile storage built on homeassistant.helpers.storage.Store."""
from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_MINOR_VERSION, STORAGE_VERSION
from .engine import ALL_SKILLS

SAVE_DELAY_SECONDS = 2


def default_data(name: str, avatar: str, created: str) -> dict:
    return {
        "profile": {"name": name, "avatar": avatar, "created": created},
        "xp": {"total": 0, "level": 1},
        "streak": {
            "current": 0,
            "best": 0,
            "last_goal_date": None,
            "freezes": 0,
            "freeze_log": [],
        },
        "daily": _default_daily(created),
        "weekly": _default_weekly(created),
        "skills": {skill: _default_skill() for skill in ALL_SKILLS},
        "badges": {},
        "history": [],
        "daily_log": {},  # {iso_date: {"q": int, "c": int, "xp": int}} — last ~5 weeks
        "arcade": {"games": 0, "wins": 0, "best_round": 0, "categories_won": []},
    }


def _default_daily(date: str) -> dict:
    return {
        "date": date,
        "questions": 0,
        "correct": 0,
        "rounds": 0,
        "xp_today": 0,
        "goal_met": False,
        "met_at": None,
        "modes_played": [],
    }


def _default_weekly(week_start: str) -> dict:
    return {
        "week_start": week_start,
        "questions": 0,
        "correct": 0,
        "rounds": 0,
        "per_day": {},
        "modes_played": [],
        "challenges": [],
    }


def _default_skill() -> dict:
    return {"band": 1, "mastery": 0.0, "window": [], "attempts": 0, "correct": 0}


def merge_defaults(data: dict, name: str, avatar: str, created: str) -> dict:
    """Fill any missing keys (new skills/fields added in later versions)."""
    defaults = default_data(name, avatar, created)
    for key, value in defaults.items():
        data.setdefault(key, value)
        if isinstance(value, dict) and isinstance(data[key], dict):
            for sub_key, sub_value in value.items():
                data[key].setdefault(sub_key, sub_value)
    return data


class ProfileStore:
    """One Store per profile (config entry)."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            f"{DOMAIN}.{entry_id}",
            minor_version=STORAGE_MINOR_VERSION,
        )
        self._data: dict | None = None

    async def async_load(self, name: str, avatar: str, created: str) -> dict:
        data = await self._store.async_load()
        if data is None:
            data = default_data(name, avatar, created)
        else:
            data = merge_defaults(data, name, avatar, created)
        self._data = data
        return data

    def schedule_save(self) -> None:
        self._store.async_delay_save(lambda: self._data, SAVE_DELAY_SECONDS)

    async def async_save_now(self) -> None:
        if self._data is not None:
            await self._store.async_save(self._data)

    async def async_remove(self) -> None:
        await self._store.async_remove()
