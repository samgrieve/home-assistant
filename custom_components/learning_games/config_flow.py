"""Config flow: one entry per kid profile."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from homeassistant.helpers.selector import SelectOptionDict
from homeassistant.util import dt as dt_util

from .engine import curriculum

YEAR_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[
            SelectOptionDict(value=str(y), label=curriculum.label(y))
            for y in curriculum.SETTABLE_YEARS
        ],
        mode=SelectSelectorMode.DROPDOWN,
    )
)

from .const import (
    AVATARS,
    CONF_AVATAR,
    CONF_DAILY_GOAL,
    CONF_NAME,
    CONF_PARENT_USERS,
    CONF_SCHOOL_YEAR,
    CONF_SCHOOL_YEAR_SET_IN,
    DEFAULT_DAILY_GOAL,
    DOMAIN,
)

AVATAR_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=AVATARS, mode=SelectSelectorMode.DROPDOWN, translation_key="avatar"
    )
)
GOAL_SELECTOR = NumberSelector(
    NumberSelectorConfig(min=5, max=100, step=5, mode=NumberSelectorMode.SLIDER)
)


class LearningGamesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a profile."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            else:
                await self.async_set_unique_id(f"{DOMAIN}_{name.lower()}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_AVATAR: user_input[CONF_AVATAR],
                        CONF_DAILY_GOAL: int(user_input[CONF_DAILY_GOAL]),
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): TextSelector(),
                    vol.Required(CONF_AVATAR, default="fox"): AVATAR_SELECTOR,
                    vol.Required(CONF_DAILY_GOAL, default=DEFAULT_DAILY_GOAL): GOAL_SELECTOR,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Adjust avatar, daily goal and which HA users are parents."""

    def __init__(self, config_entry) -> None:
        # Newer cores expose self.config_entry as a property; older ones need it set.
        if not hasattr(config_entries.OptionsFlow, "config_entry"):
            self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_AVATAR: user_input[CONF_AVATAR],
                    CONF_DAILY_GOAL: int(user_input[CONF_DAILY_GOAL]),
                    CONF_PARENT_USERS: list(user_input.get(CONF_PARENT_USERS, [])),
                    CONF_SCHOOL_YEAR: int(user_input.get(CONF_SCHOOL_YEAR, curriculum.DEFAULT_YEAR)),
                    # Counted from now: the year moves up every 1 September after this.
                    CONF_SCHOOL_YEAR_SET_IN: curriculum.academic_year_start(
                        dt_util.now().date()
                    ),
                },
            )
        entry = self.config_entry
        users = [
            u for u in await self.hass.auth.async_get_users()
            if not u.system_generated and u.is_active
        ]
        user_options = [
            SelectOptionDict(value=u.id, label=u.name or u.id)
            for u in sorted(users, key=lambda u: (u.name or "").lower())
        ]
        known_ids = {u.id for u in users}
        current_year = curriculum.current_school_year(
            int(entry.options.get(CONF_SCHOOL_YEAR, curriculum.DEFAULT_YEAR)),
            entry.options.get(CONF_SCHOOL_YEAR_SET_IN),
            dt_util.now().date(),
        )
        current_year = min(max(current_year, min(curriculum.SETTABLE_YEARS)),
                           max(curriculum.SETTABLE_YEARS))
        current_parents = [
            uid for uid in entry.options.get(CONF_PARENT_USERS, []) if uid in known_ids
        ]
        current_avatar = entry.options.get(CONF_AVATAR, entry.data.get(CONF_AVATAR, "fox"))
        current_goal = entry.options.get(
            CONF_DAILY_GOAL, entry.data.get(CONF_DAILY_GOAL, DEFAULT_DAILY_GOAL)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AVATAR, default=current_avatar): AVATAR_SELECTOR,
                    vol.Required(CONF_DAILY_GOAL, default=current_goal): GOAL_SELECTOR,
                    vol.Required(CONF_SCHOOL_YEAR, default=str(current_year)): YEAR_SELECTOR,
                    vol.Optional(CONF_PARENT_USERS, default=current_parents): SelectSelector(
                        SelectSelectorConfig(
                            options=user_options,
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )
