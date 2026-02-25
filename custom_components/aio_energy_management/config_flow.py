"""Config flow for AIO Energy Management integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .cheapest_hours_config_flow import (
    ENTRY_TYPE_CHEAPEST_HOURS,
    CheapestHoursConfigFlowMixin,
)
from .const import CONF_CALENDAR, CONF_UNIQUE_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_CALENDAR = "calendar"


def _get_calendar_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get calendar configuration schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=user_input.get(CONF_NAME)
                if user_input
                else "Energy Management",
            ): cv.string,
        }
    )


# Configuration flow
class AIOEnergyManagementConfigFlow(
    CheapestHoursConfigFlowMixin, ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for AIO Energy Management."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._entry_type: str | None = None
        self._data_provider_type: str | None = None
        self._config_data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AIOEnergyManagementOptionsFlow:
        """Get the options flow for this handler."""
        return AIOEnergyManagementOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - select entry type."""
        if user_input is not None:
            self._entry_type = user_input[CONF_ENTRY_TYPE]

            if self._entry_type == ENTRY_TYPE_CHEAPEST_HOURS:
                return await self.async_step_cheapest_hours_data_provider()
            if self._entry_type == ENTRY_TYPE_CALENDAR:
                return await self.async_step_calendar()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTRY_TYPE): vol.In(
                        {
                            ENTRY_TYPE_CHEAPEST_HOURS: "Cheapest hours sensor",
                            ENTRY_TYPE_CALENDAR: "Calendar",
                        }
                    ),
                }
            ),
        )

    async def async_step_calendar(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure calendar. Only one calendar entry is allowed."""
        # Use a fixed unique ID so only a single calendar entry can ever be created.
        await self.async_set_unique_id(ENTRY_TYPE_CALENDAR)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}

        if user_input is not None:
            user_input[CONF_UNIQUE_ID] = ENTRY_TYPE_CALENDAR
            user_input[CONF_ENTRY_TYPE] = ENTRY_TYPE_CALENDAR

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="calendar",
            data_schema=_get_calendar_schema(user_input),
            errors=errors,
        )


# Options flow (modify existing configuration)
class AIOEnergyManagementOptionsFlow(CheapestHoursConfigFlowMixin, OptionsFlow):
    """Handle options flow for AIO Energy Management."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._config_entry = config_entry
        self._entry_type = config_entry.data.get(CONF_ENTRY_TYPE)
        self._data_provider_type: str | None = None
        self._config_data: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if self._entry_type == ENTRY_TYPE_CHEAPEST_HOURS:
            self._config_data[CONF_CALENDAR] = self._config_entry.data.get(
                CONF_CALENDAR, True
            )
            return await self.async_step_cheapest_hours_data_provider()
        if self._entry_type == ENTRY_TYPE_CALENDAR:
            return await self.async_step_calendar_options()

        return self.async_abort(reason="unknown_entry_type")

    async def async_step_calendar_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle calendar options."""
        if user_input is not None:
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="calendar_options",
            data_schema=vol.Schema({}),
            description_placeholders={
                "info": "Calendar configuration has no additional options.",
            },
        )
