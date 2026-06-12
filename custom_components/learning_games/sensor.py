"""Sensors exposing progress, streaks and mastery for automations."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ProfileCoordinator, level_progress
from .engine import challenges
from .engine.badges import badge_public
from .entity import LearningGamesEntity


@dataclass(frozen=True)
class LearningGamesSensorDescription:
    key: str
    name: str
    icon: str
    unit: str | None
    value_fn: Callable[[ProfileCoordinator], object]
    attrs_fn: Callable[[ProfileCoordinator], dict]


def _level_value(c: ProfileCoordinator):
    return level_progress(c.data["xp"]["total"])[0]


def _level_attrs(c: ProfileCoordinator):
    level, into, to_next = level_progress(c.data["xp"]["total"])
    return {"xp_total": c.data["xp"]["total"], "xp_into_level": into, "xp_to_next": to_next}


def _accuracy_value(c: ProfileCoordinator):
    daily = c.data["daily"]
    if not daily["questions"]:
        return None
    return round(daily["correct"] / daily["questions"] * 100)


def _last_badge_value(c: ProfileCoordinator):
    if not c.data["badges"]:
        return "none"
    badge_id = max(c.data["badges"], key=lambda b: c.data["badges"][b])
    return badge_public(badge_id, c.data["badges"][badge_id])["name"]


def _last_badge_attrs(c: ProfileCoordinator):
    badges = [badge_public(b, ts) for b, ts in sorted(
        c.data["badges"].items(), key=lambda item: item[1])]
    return {
        "earned_count": len(badges),
        "badges": [b["name"] for b in badges],
        "last_earned_ts": badges[-1]["ts"] if badges else None,
    }


SENSORS: tuple[LearningGamesSensorDescription, ...] = (
    LearningGamesSensorDescription(
        "level", "Level", "mdi:trophy", None, _level_value, _level_attrs
    ),
    LearningGamesSensorDescription(
        "streak", "Streak", "mdi:fire", "days",
        lambda c: c.data["streak"]["current"],
        lambda c: {
            "best_streak": c.data["streak"]["best"],
            "freezes_remaining": c.data["streak"]["freezes"],
            "last_goal_date": c.data["streak"]["last_goal_date"],
        },
    ),
    LearningGamesSensorDescription(
        "questions_today", "Questions today", "mdi:comment-question", "questions",
        lambda c: c.data["daily"]["questions"],
        lambda c: {
            "correct_today": c.data["daily"]["correct"],
            "rounds_today": c.data["daily"]["rounds"],
            "xp_today": c.data["daily"]["xp_today"],
            "daily_goal": c.daily_goal,
            "accuracy_today": _accuracy_value(c),
        },
    ),
    LearningGamesSensorDescription(
        "accuracy_today", "Accuracy today", "mdi:target", "%",
        _accuracy_value, lambda c: {},
    ),
    LearningGamesSensorDescription(
        "maths_mastery", "Maths mastery", "mdi:calculator", "%",
        lambda c: c.maths_mastery()[0], lambda c: c.maths_mastery()[1],
    ),
    LearningGamesSensorDescription(
        "english_mastery", "English mastery", "mdi:book-open-variant", "%",
        lambda c: c.english_mastery()[0], lambda c: c.english_mastery()[1],
    ),
    LearningGamesSensorDescription(
        "last_badge", "Last badge", "mdi:medal", None,
        _last_badge_value, _last_badge_attrs,
    ),
    LearningGamesSensorDescription(
        "weekly_challenges", "Weekly challenges done", "mdi:trophy-outline", None,
        lambda c: sum(
            1 for ch in c.data["weekly"].get("challenges", []) if ch["done"]
        ),
        lambda c: {
            "challenges": [
                challenges.describe(ch)
                for ch in c.data["weekly"].get("challenges", [])
            ],
            "week_start": c.data["weekly"]["week_start"],
        },
    ),
    LearningGamesSensorDescription(
        "weekly_questions", "Weekly questions", "mdi:calendar-week", "questions",
        lambda c: c.data["weekly"]["questions"],
        lambda c: {
            "correct": c.data["weekly"]["correct"],
            "accuracy": round(c.data["weekly"]["correct"] / c.data["weekly"]["questions"] * 100)
            if c.data["weekly"]["questions"] else None,
            "rounds": c.data["weekly"]["rounds"],
            "per_day": c.data["weekly"]["per_day"],
            "modes_played": c.data["weekly"]["modes_played"],
            "week_start": c.data["weekly"]["week_start"],
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ProfileCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities(
        LearningGamesSensor(coordinator, description) for description in SENSORS
    )


class LearningGamesSensor(LearningGamesEntity, SensorEntity):
    def __init__(self, coordinator: ProfileCoordinator,
                 description: LearningGamesSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_native_unit_of_measurement = description.unit

    @property
    def native_value(self):
        return self.description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self):
        return self.description.attrs_fn(self.coordinator)
