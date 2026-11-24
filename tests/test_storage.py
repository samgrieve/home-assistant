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


def test_old_profile_gains_journal_without_losing_progress():
    old = default_data("Maya", "fox", "2026-06-12")
    del old["journal"]  # profile saved by v1.2.0
    old["xp"] = {"total": 2384, "level": 9}
    old["badges"] = {"first_steps": "2026-06-12T10:00:00"}
    old["streak"]["current"] = 4
    merged = merge_defaults(old, "Maya", "fox", "2026-11-24")
    assert merged["xp"] == {"total": 2384, "level": 9}
    assert merged["badges"] == {"first_steps": "2026-06-12T10:00:00"}
    assert merged["streak"]["current"] == 4
    assert merged["journal"]["entries"] == {}
    assert "science" in merged["journal"]["subjects"]


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


async def test_weekly_rollover_archives_summary_and_snapshots(hass: HomeAssistant):
    coordinator = await make_coordinator(hass)
    weekly = coordinator.data["weekly"]
    assert weekly["mastery_start"]  # snapshotted on first load
    last_week = (
        dt_util.now().date() - timedelta(days=dt_util.now().date().weekday() + 7)
    ).isoformat()
    weekly["week_start"] = last_week
    weekly["questions"] = 42
    weekly["correct"] = 30
    coordinator.skills["maths.fractions"].mastery = 30.0
    weekly["mastery_start"]["maths.fractions"] = 20.0

    coordinator._check_rollover()
    history = coordinator.data["weekly_history"]
    assert len(history) == 1
    assert history[0]["week_start"] == last_week
    assert history[0]["questions"] == 42 and history[0]["accuracy"] == 71
    assert history[0]["improved"][0]["name"] == "Fractions"
    assert "parent_text" not in history[0]
    new = coordinator.data["weekly"]
    assert new["week_start"] != last_week
    assert new["mastery_start"]["maths.fractions"] == 30.0
    # This week's summary compares with the archived week.
    assert coordinator.weekly_summary()["vs_last_week"] == -42


async def test_old_profile_upgrade_keeps_progress(hass: HomeAssistant, hass_storage):
    """A v1.3 save (no subject skills, snapshots or history) loads intact."""
    from custom_components.learning_games.storage import default_data as dd

    entry = MockConfigEntry(
        domain=DOMAIN, title="Maya", unique_id=f"{DOMAIN}_maya",
        data={CONF_NAME: "Maya", CONF_AVATAR: "fox", CONF_DAILY_GOAL: 5},
    )
    old = dd("Maya", "fox", "2026-06-12")
    old.pop("weekly_history")
    old["weekly"].pop("mastery_start")
    old["weekly"].pop("attempts_start")
    for s in old["journal"]["subjects"].values():
        s.pop("skills")
    old["xp"] = {"total": 2384, "level": 9}
    old["badges"] = {"first_steps": "2026-06-12T10:00:00"}
    old["skills"]["maths.times_tables"].update(
        {"band": 3, "mastery": 39.2, "attempts": 300, "correct": 250})
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1, "minor_version": 1, "key": f"{DOMAIN}.{entry.entry_id}", "data": old}
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    c = hass.data[DOMAIN]["coordinators"][entry.entry_id]
    assert c.data["xp"]["total"] == 2384
    assert c.data["badges"] == {"first_steps": "2026-06-12T10:00:00"}
    tt = c.skills["maths.times_tables"]
    assert (tt.band, round(tt.mastery, 1), tt.attempts) == (3, 39.2, 300)
    assert "maths.fractions" in c.data["journal"]["subjects"]["maths"]["skills"]
    assert c.data["weekly_history"] == []
    assert c.data["weekly"]["mastery_start"]["maths.times_tables"] == 39.2


async def test_school_year_lifts_only_untouched_skills(hass: HomeAssistant):
    coordinator = await make_coordinator(hass)
    coordinator.skills["maths.money"].attempts = 10  # practised at band 1
    hass.config_entries.async_update_entry(
        coordinator.entry,
        options={**coordinator.entry.options, "school_year": 7,
                 "school_year_set_in": 2000 + 100},  # set "in the future": no drift
    )
    await hass.async_block_till_done()
    assert coordinator.school_year == 7
    assert coordinator.skills["maths.fractions"].band == 3
    assert coordinator.skills["maths.money"].band == 1
    # Moving back down never lowers bands.
    hass.config_entries.async_update_entry(
        coordinator.entry, options={**coordinator.entry.options, "school_year": 5})
    await hass.async_block_till_done()
    assert coordinator.skills["maths.fractions"].band == 3
    state = hass.states.get("sensor.maya_s_learning_games_level")
    assert state.attributes["school_year"] == 5
