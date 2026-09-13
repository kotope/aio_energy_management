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
from homeassistant.helpers import selector
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
)

from .cheapest_hours import ENTRY_TYPE_CHEAPEST_HOURS, CheapestHoursConfigFlowMixin
from .const import (
    CONF_CALENDAR,
    CONF_DATA_PROVIDER_TYPE,
    CONF_ENABLE_CALENDAR,
    CONF_ENTITY_EXCESS_SOLAR,
    CONF_UNIQUE_ID,
    DOMAIN,
)
from .excess_solar.config_flow import ExcessSolarConfigFlowMixin

_LOGGER = logging.getLogger(__name__)

CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_GLOBAL_SETTINGS = "global_settings"


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
    CheapestHoursConfigFlowMixin,
    ExcessSolarConfigFlowMixin,
    ConfigFlow,
    domain=DOMAIN,
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
        # Check if Global Settings already exists
        has_global_settings = any(
            entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_GLOBAL_SETTINGS
            for entry in self._async_current_entries()
        )

        # Create Global Settings for new installations
        if not has_global_settings:
            return await self.async_step_global_settings()

        if user_input is not None:
            self._entry_type = user_input[CONF_ENTRY_TYPE]

            if self._entry_type == ENTRY_TYPE_CHEAPEST_HOURS:
                return await self.async_step_cheapest_hours_data_provider()
            if self._entry_type == CONF_ENTITY_EXCESS_SOLAR:
                return await self.async_step_excess_solar_global()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ENTRY_TYPE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                ENTRY_TYPE_CHEAPEST_HOURS,
                                CONF_ENTITY_EXCESS_SOLAR,
                            ],
                            translation_key="entry_type",
                        )
                    ),
                }
            ),
        )

    async def async_step_global_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create global settings entry."""
        await self.async_set_unique_id(ENTRY_TYPE_GLOBAL_SETTINGS)
        self._abort_if_unique_id_configured()

        migrated_unique_id = (user_input or {}).get(CONF_UNIQUE_ID)

        return self.async_create_entry(
            title="⚙️ Global Settings",
            data={
                CONF_UNIQUE_ID: migrated_unique_id or ENTRY_TYPE_GLOBAL_SETTINGS,
                CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL_SETTINGS,
            },
        )


# Options flow (modify existing configuration)
class AIOEnergyManagementOptionsFlow(
    CheapestHoursConfigFlowMixin,
    ExcessSolarConfigFlowMixin,
    OptionsFlow,
):
    """Handle options flow for AIO Energy Management."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._config_entry = config_entry
        self._entry_type = config_entry.data.get(CONF_ENTRY_TYPE)
        self._data_provider_type = config_entry.data.get(CONF_DATA_PROVIDER_TYPE)
        self._config_data = dict(config_entry.data)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow based on entry type."""
        if self._entry_type == ENTRY_TYPE_CHEAPEST_HOURS:
            return await self.async_step_cheapest_hours_menu()
        if self._entry_type == ENTRY_TYPE_GLOBAL_SETTINGS:
            return await self.async_step_global_settings_options()

        return self.async_abort(reason="unknown_entry_type")

    async def async_step_global_settings_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage global settings"""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_options = {**self._config_entry.data, **self._config_entry.options}
        current_enable_calendar = current_options.get(CONF_ENABLE_CALENDAR, False)
        current_name = current_options.get(CONF_NAME, "Energy Management")

        return self.async_show_form(
            step_id="global_settings_options",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_CALENDAR,
                        default=current_enable_calendar,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_NAME,
                        default=current_name,
                    ): selector.TextSelector(),
                }
            ),
        )

    async def async_step_cheapest_hours_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the cheapest hours settings menu."""
        return self.async_show_menu(
            step_id="cheapest_hours_menu",
            menu_options=[
                "cheapest_hours_data_provider",
                "cheapest_hours_basic",
                "cheapest_hours_advanced",
                "cheapest_hours_offset",
            ],
        )
