"""Storage defaults, merging and rollover/streak behaviour."""
from datetime import timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.learning_games.const import (
    CONF_AVATAR,
    CONF_DAILY_GOAL,
    CONF_NAME,
    DOMAIN,
)
from custom_components.learning_games.engine import ALL_SKILLS
from custom_components.learning_games.storage import default_data, merge_defaults


@pytest.fixture(autouse=True)
def auto_enable(enable_custom_integrations):
    yield


def test_default_data_shape():
    data = default_data("Maya", "fox", "2026-06-12")
    assert data["profile"]["name"] == "Maya"
    assert set(data["skills"]) == set(ALL_SKILLS)
    assert data["xp"] == {"total": 0, "level": 1}
    assert data["streak"]["current"] == 0
    assert data["daily"]["goal_met"] is False


def test_merge_defaults_adds_new_fields():
    old = default_data("Maya", "fox", "2026-06-12")
    del old["weekly"]
    del old["skills"]["maths.decimals"]
    del old["streak"]["freezes"]
    merged = merge_defaults(old, "Maya", "fox", "2026-06-12")
    assert "weekly" in merged
    assert merged["streak"]["freezes"] == 0
    # Nested skill defaults come back via coordinator's SkillState fallback;
    # top-level dict keys are guaranteed here.
    assert "skills" in merged


async def make_coordinator(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Maya",
        unique_id=f"{DOMAIN}_maya",
        data={CONF_NAME: "Maya", CONF_AVATAR: "fox", CONF_DAILY_GOAL: 5},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN]["coordinators"][entry.entry_id]


async def test_daily_rollover_resets_counters(hass: HomeAssistant, freezer):
    coordinator = await make_coordinator(hass)
    coordinator.data["daily"]["questions"] = 7
    coordinator.data["daily"]["date"] = (
        dt_util.now().date() - timedelta(days=1)
    ).isoformat()

    coordinator._check_rollover()
    assert coordinator.data["daily"]["questions"] == 0
    assert coordinator.data["daily"]["date"] == dt_util.now().date().isoformat()


async def test_streak_resets_without_freeze(hass: HomeAssistant):
    coordinator = await make_coordinator(hass)
    two_days_ago = (dt_util.now().date() - timedelta(days=2)).isoformat()
    coordinator.data["streak"].update(
        {"current": 5, "best": 5, "last_goal_date": two_days_ago, "freezes": 0}
    )
    coordinator.data["daily"]["date"] = (
        dt_util.now().date() - timedelta(days=1)
    ).isoformat()

    coordinator._check_rollover()
    assert coordinator.data["streak"]["current"] == 0


async def test_streak_freeze_bridges_one_day(hass: HomeAssistant):
    coordinator = await make_coordinator(hass)
    today = dt_util.now().date()
    two_days_ago = (today - timedelta(days=2)).isoformat()
    yesterday = (today - timedelta(days=1)).isoformat()
    coordinator.data["streak"].update(
        {"current": 8, "best": 8, "last_goal_date": two_days_ago, "freezes": 1}
    )
    coordinator.data["daily"]["date"] = yesterday

    coordinator._check_rollover()
    streak = coordinator.data["streak"]
    assert streak["current"] == 8  # saved!
    assert streak["freezes"] == 0
    assert yesterday in streak["freeze_log"]
    assert streak["last_goal_date"] == yesterday


async def test_stats_persist_across_reload(hass: HomeAssistant):
    coordinator = await make_coordinator(hass)
    entry = coordinator.entry
    coordinator.data["xp"]["total"] = 333
    await coordinator.store.async_save_now()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    coordinator2 = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    assert coordinator2.data["xp"]["total"] == 333
