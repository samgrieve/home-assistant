"""Daily-goal binary sensor — the prime automation hook."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ProfileCoordinator
from .entity import LearningGamesEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: ProfileCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    async_add_entities([DailyGoalMetSensor(coordinator)])


class DailyGoalMetSensor(LearningGamesEntity, BinarySensorEntity):
    _attr_name = "Daily goal met"
    _attr_icon = "mdi:flag-checkered"

    def __init__(self, coordinator: ProfileCoordinator) -> None:
        super().__init__(coordinator, "daily_goal_met")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data["daily"]["goal_met"])

    @property
    def extra_state_attributes(self):
        daily = self.coordinator.data["daily"]
        return {
            "goal": self.coordinator.daily_goal,
            "progress": daily["questions"],
            "met_at": daily["met_at"],
        }
