"""Config and options flow tests."""
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.learning_games.const import (
    CONF_AVATAR,
    CONF_DAILY_GOAL,
    CONF_NAME,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    yield


async def test_create_profile(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Maya", CONF_AVATAR: "unicorn", CONF_DAILY_GOAL: 25},
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Maya"
    assert result["data"] == {
        CONF_NAME: "Maya",
        CONF_AVATAR: "unicorn",
        CONF_DAILY_GOAL: 25,
    }


async def test_duplicate_name_aborts(hass: HomeAssistant):
    MockConfigEntry(
        domain=DOMAIN,
        title="Maya",
        unique_id=f"{DOMAIN}_maya",
        data={CONF_NAME: "Maya", CONF_AVATAR: "fox", CONF_DAILY_GOAL: 20},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "maya", CONF_AVATAR: "owl", CONF_DAILY_GOAL: 20},
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maya",
        unique_id=f"{DOMAIN}_maya",
        data={CONF_NAME: "Maya", CONF_AVATAR: "fox", CONF_DAILY_GOAL: 20},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_AVATAR: "dragon", CONF_DAILY_GOAL: 30}
    )
    assert result["type"] == "create_entry"
    assert entry.options == {CONF_AVATAR: "dragon", CONF_DAILY_GOAL: 30}
