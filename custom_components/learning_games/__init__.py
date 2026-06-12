"""Learning Games: maths & English games for kids with stats, streaks and rewards."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import CARD_FILENAME, DOMAIN, FRONTEND_URL_BASE, VERSION
from .coordinator import ProfileCoordinator
from .engine.wordlists import load_banks
from .websocket import async_register_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    hass.data.setdefault(DOMAIN, {"coordinators": {}})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    domain_data = hass.data.setdefault(DOMAIN, {"coordinators": {}})

    if "banks" not in domain_data:
        # Blocking JSON reads — load once, off the event loop.
        domain_data["banks"] = await hass.async_add_executor_job(load_banks)

    if not domain_data.get("frontend_registered"):
        await _async_register_frontend(hass)
        async_register_commands(hass)
        domain_data["frontend_registered"] = True

    coordinator = ProfileCoordinator(hass, entry, domain_data["banks"])
    await coordinator.async_setup()
    domain_data["coordinators"][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: ProfileCoordinator = hass.data[DOMAIN]["coordinators"].pop(
            entry.entry_id
        )
        await coordinator.async_unload()
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete the profile's stored stats when the entry is removed."""
    from .storage import ProfileStore

    await ProfileStore(hass, entry.entry_id).async_remove()


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator: ProfileCoordinator = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    coordinator._notify()


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the card JS and inject it into every dashboard."""
    frontend_dir = Path(__file__).parent / "frontend"
    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_URL_BASE, str(frontend_dir), cache_headers=True)]
        )
    except ImportError:
        # Cores older than 2024.6 only have the sync API.
        hass.http.register_static_path(
            FRONTEND_URL_BASE, str(frontend_dir), cache_headers=True
        )
    # ?v= busts the aggressive cache in the Companion app webview on upgrades.
    add_extra_js_url(hass, f"{FRONTEND_URL_BASE}/{CARD_FILENAME}?v={VERSION}")
