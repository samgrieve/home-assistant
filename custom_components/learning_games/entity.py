"""Shared entity base for Learning Games sensors."""
from __future__ import annotations

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, SIGNAL_PROFILE_UPDATED
from .coordinator import ProfileCoordinator


class LearningGamesEntity(Entity):
    """Base entity: device grouping + dispatcher-driven updates."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator: ProfileCoordinator, key: str) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"{coordinator.name}'s Learning Games",
            manufacturer="Learning Games",
            model="Profile",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_PROFILE_UPDATED}_{self.coordinator.entry.entry_id}",
                self.async_write_ha_state,
            )
        )
