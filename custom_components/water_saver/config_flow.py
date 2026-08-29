from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_EXCLUDE_ENTITIES,
    CONF_EXCLUDE_GRACE_MIN,
    CONF_LEAK_HOURS,
    CONF_NAME,
    CONF_SNOOZE_DEFAULT_HOURS,
    CONF_TODAY_HIGH_AFTER_HOUR,
    CONF_TODAY_HIGH_BUFFER_L,
    CONF_TODAY_HIGH_MIN_L,
    CONF_TODAY_HIGH_MULTIPLIER,
    CONF_TOPIC,
    CONF_UNAVAILABLE_TIMEOUT,
    DEFAULT_EXCLUDE_ENTITIES,
    DEFAULT_EXCLUDE_GRACE_MIN,
    DEFAULT_LEAK_HOURS,
    DEFAULT_NAME,
    DEFAULT_SNOOZE_DEFAULT_HOURS,
    DEFAULT_TODAY_HIGH_AFTER_HOUR,
    DEFAULT_TODAY_HIGH_BUFFER_L,
    DEFAULT_TODAY_HIGH_MIN_L,
    DEFAULT_TODAY_HIGH_MULTIPLIER,
    DEFAULT_TOPIC,
    DEFAULT_UNAVAILABLE_TIMEOUT,
    DOMAIN,
)


class WaterSaverConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_TOPIC, default=DEFAULT_TOPIC): str,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        await self.async_set_unique_id(f"{DOMAIN}:{user_input[CONF_TOPIC]}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WaterSaverOptionsFlow(config_entry)


class WaterSaverOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is None:
            data = self._entry.options or self._entry.data
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=data.get(CONF_NAME, DEFAULT_NAME),
                    ): str,
                    vol.Required(
                        CONF_TOPIC,
                        default=data.get(CONF_TOPIC, DEFAULT_TOPIC),
                    ): str,
                    vol.Optional(
                        CONF_UNAVAILABLE_TIMEOUT,
                        default=data.get(CONF_UNAVAILABLE_TIMEOUT, DEFAULT_UNAVAILABLE_TIMEOUT),
                    ): vol.All(int, vol.Range(min=5, max=1440)),
                    vol.Optional(
                        CONF_LEAK_HOURS,
                        default=data.get(CONF_LEAK_HOURS, DEFAULT_LEAK_HOURS),
                    ): vol.All(int, vol.Range(min=1, max=48)),
                    vol.Optional(
                        CONF_TODAY_HIGH_MULTIPLIER,
                        default=data.get(CONF_TODAY_HIGH_MULTIPLIER, DEFAULT_TODAY_HIGH_MULTIPLIER),
                    ): vol.All(vol.Coerce(float), vol.Range(min=1.1, max=10.0)),
                    vol.Optional(
                        CONF_TODAY_HIGH_MIN_L,
                        default=data.get(CONF_TODAY_HIGH_MIN_L, DEFAULT_TODAY_HIGH_MIN_L),
                    ): vol.All(int, vol.Range(min=50, max=5000)),
                    vol.Optional(
                        CONF_TODAY_HIGH_BUFFER_L,
                        default=data.get(CONF_TODAY_HIGH_BUFFER_L, DEFAULT_TODAY_HIGH_BUFFER_L),
                    ): vol.All(int, vol.Range(min=0, max=1000)),
                    vol.Optional(
                        CONF_TODAY_HIGH_AFTER_HOUR,
                        default=data.get(CONF_TODAY_HIGH_AFTER_HOUR, DEFAULT_TODAY_HIGH_AFTER_HOUR),
                    ): vol.All(int, vol.Range(min=0, max=23)),
                    vol.Optional(
                        CONF_SNOOZE_DEFAULT_HOURS,
                        default=data.get(CONF_SNOOZE_DEFAULT_HOURS, DEFAULT_SNOOZE_DEFAULT_HOURS),
                    ): vol.All(int, vol.Range(min=1, max=72)),
                    vol.Optional(
                        CONF_EXCLUDE_ENTITIES,
                        default=data.get(CONF_EXCLUDE_ENTITIES, DEFAULT_EXCLUDE_ENTITIES),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(multiple=True)
                    ),
                    vol.Optional(
                        CONF_EXCLUDE_GRACE_MIN,
                        default=data.get(CONF_EXCLUDE_GRACE_MIN, DEFAULT_EXCLUDE_GRACE_MIN),
                    ): vol.All(int, vol.Range(min=0, max=120)),
                }
            )
            return self.async_show_form(step_id="init", data_schema=schema)

        return self.async_create_entry(title="", data=user_input)
