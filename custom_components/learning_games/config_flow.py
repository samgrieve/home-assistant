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

from .const import AVATARS, CONF_AVATAR, CONF_DAILY_GOAL, CONF_NAME, DEFAULT_DAILY_GOAL, DOMAIN

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
    """Adjust avatar and daily goal."""

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
                },
            )
        entry = self.config_entry
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
                }
            ),
        )
