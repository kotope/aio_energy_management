"""Excess solar config flow handlers and helpers."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from ..const import (
    CONF_BUFFER,
    CONF_CONSUMPTION,
    CONF_GRID_POWER_SENSOR,
    CONF_IS_ON_SCHEDULE,
    CONF_MINIMUM_PERIOD,
    CONF_NAME,
    CONF_POWER_DEVICES,
    CONF_PRIORITY,
    CONF_TURN_ON_DELAY,
    CONF_UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)

ENTRY_TYPE_EXCESS_SOLAR = "excess_solar"

# UI-only config keys (not stored in config entry data)
CONF_CONSUMPTION_ENTITY = "consumption_entity"
CONF_ADD_ANOTHER = "add_another"
CONF_DEVICES_ACTION = "devices_action"
CONF_DEVICES_TO_REMOVE = "devices_to_remove"

# Options-flow action values
ACTION_EDIT_SETTINGS = "edit_settings"
ACTION_ADD_DEVICE = "add_device"
ACTION_REMOVE_DEVICES = "remove_devices"


def _get_excess_solar_global_schema(
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Get global excess solar configuration schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=(user_input.get(CONF_NAME) if user_input else "Excess Solar"),
            ): cv.string,
            vol.Required(
                CONF_GRID_POWER_SENSOR,
                description={
                    "suggested_value": (
                        user_input.get(CONF_GRID_POWER_SENSOR) if user_input else None
                    )
                },
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_BUFFER,
                default=(user_input.get(CONF_BUFFER, 0) if user_input else 0),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10000,
                    step=10,
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _get_excess_solar_edit_settings_schema(
    entry_data: dict[str, Any],
) -> vol.Schema:
    """Get global excess solar edit settings schema prefilled from config entry."""
    return vol.Schema(
        {
            vol.Required(
                CONF_GRID_POWER_SENSOR,
                description={"suggested_value": entry_data.get(CONF_GRID_POWER_SENSOR)},
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
            vol.Optional(
                CONF_BUFFER,
                default=int(entry_data.get(CONF_BUFFER, 0)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=10000,
                    step=10,
                    unit_of_measurement="W",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _build_device_schema_defaults(
    user_input: dict[str, Any] | None,
) -> dict[str, Any]:
    """Extract form defaults for the device schema from user_input or empty."""
    if not user_input:
        return {
            "name": "",
            "consumption": 0,
            "consumption_entity": None,
            "priority": 100,
            "is_on_schedule": None,
            "minimum_period": 0,
            "turn_on_delay": None,
        }

    # When consumption is an entity string from a previous submission
    consumption = user_input.get(CONF_CONSUMPTION, 0)
    consumption_entity = user_input.get(CONF_CONSUMPTION_ENTITY)
    if isinstance(consumption, str) and not consumption.lstrip("-").isdigit():
        consumption_entity = consumption
        consumption = 0

    return {
        "name": user_input.get(CONF_NAME, ""),
        "consumption": int(consumption) if consumption else 0,
        "consumption_entity": consumption_entity,
        "priority": int(user_input.get(CONF_PRIORITY, 100)),
        "is_on_schedule": user_input.get(CONF_IS_ON_SCHEDULE),
        "minimum_period": int(user_input.get(CONF_MINIMUM_PERIOD, 0)),
        "turn_on_delay": user_input.get(CONF_TURN_ON_DELAY),
    }


def _get_excess_solar_device_schema(
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Get power device configuration schema."""
    d = _build_device_schema_defaults(user_input)

    schema_dict: dict = {
        vol.Required(CONF_NAME, default=d["name"]): cv.string,
        vol.Optional(
            CONF_CONSUMPTION,
            default=d["consumption"],
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=100000,
                step=10,
                unit_of_measurement="W",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_CONSUMPTION_ENTITY,
            description={"suggested_value": d["consumption_entity"]},
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
        vol.Optional(
            CONF_PRIORITY,
            default=d["priority"],
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=1,
                max=999,
                step=1,
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_IS_ON_SCHEDULE,
            description={"suggested_value": d["is_on_schedule"]},
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["binary_sensor", "input_boolean"])
        ),
        vol.Optional(
            CONF_MINIMUM_PERIOD,
            default=d["minimum_period"],
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=1440,
                step=1,
                unit_of_measurement="min",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
        vol.Optional(
            CONF_TURN_ON_DELAY,
            description={"suggested_value": d["turn_on_delay"]},
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=3600,
                step=1,
                unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        ),
    }

    return vol.Schema(schema_dict)


def _process_device_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Validate and clean device user input.

    Returns:
        Tuple of (cleaned_device_dict, errors_dict).
    """
    errors: dict[str, str] = {}
    device: dict[str, Any] = {}

    device[CONF_NAME] = user_input.get(CONF_NAME, "").strip()
    if not device[CONF_NAME]:
        errors[CONF_NAME] = "device_name_required"
        return device, errors

    consumption_watts = user_input.get(CONF_CONSUMPTION, 0)
    consumption_entity = user_input.get(CONF_CONSUMPTION_ENTITY)

    if consumption_entity and consumption_watts and int(consumption_watts) > 0:
        errors["base"] = "both_consumption_configured"
        return device, errors

    if consumption_entity:
        device[CONF_CONSUMPTION] = consumption_entity
    else:
        device[CONF_CONSUMPTION] = int(consumption_watts) if consumption_watts else 0

    device[CONF_PRIORITY] = int(user_input.get(CONF_PRIORITY, 100))
    device[CONF_MINIMUM_PERIOD] = int(user_input.get(CONF_MINIMUM_PERIOD, 0))

    for optional_key in [CONF_IS_ON_SCHEDULE]:
        val = user_input.get(optional_key)
        if val:
            device[optional_key] = val

    turn_on_delay = user_input.get(CONF_TURN_ON_DELAY)
    if turn_on_delay is not None:
        device[CONF_TURN_ON_DELAY] = int(turn_on_delay)

    return device, errors


class ExcessSolarConfigFlowMixin:
    """Mixin providing excess solar config flow steps.

    Works for both the initial config flow and the options flow.
    The options flow sets ``self._config_entry`` in its ``__init__``.
    """

    # ------------------------------------------------------------------
    # Initial config flow: global settings → device(s) → create entry
    # ------------------------------------------------------------------

    async def async_step_excess_solar_global(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure global excess solar settings (first step for new entries)."""
        if user_input is not None:
            user_input[CONF_BUFFER] = int(user_input.get(CONF_BUFFER, 0))
            user_input[CONF_TURN_ON_DELAY] = int(user_input.get(CONF_TURN_ON_DELAY, 60))
            self._config_data.update(user_input)
            self._config_data[CONF_POWER_DEVICES] = []
            return await self.async_step_excess_solar_device()

        return self.async_show_form(
            step_id="excess_solar_global",
            data_schema=_get_excess_solar_global_schema(user_input),
        )

    async def async_step_excess_solar_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure a power device to manage with excess solar."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device, errors = _process_device_input(user_input)
            if not errors:
                if CONF_POWER_DEVICES not in self._config_data:
                    self._config_data[CONF_POWER_DEVICES] = []
                self._config_data[CONF_POWER_DEVICES].append(device)
                return await self.async_step_excess_solar_another_device()

        device_number = len(self._config_data.get(CONF_POWER_DEVICES, [])) + 1
        return self.async_show_form(
            step_id="excess_solar_device",
            data_schema=_get_excess_solar_device_schema(user_input if errors else None),
            errors=errors,
            description_placeholders={"device_number": str(device_number)},
        )

    async def async_step_excess_solar_another_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask whether to add another device."""
        is_options_flow = hasattr(self, "_config_entry")

        if user_input is not None:
            if user_input.get(CONF_ADD_ANOTHER):
                return await self.async_step_excess_solar_device()
            if is_options_flow:
                return await self._async_finish_excess_solar_add_device()
            return await self._async_finish_excess_solar_new()

        devices = self._config_data.get(CONF_POWER_DEVICES, [])
        device_names = ", ".join(d[CONF_NAME] for d in devices)
        return self.async_show_form(
            step_id="excess_solar_another_device",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADD_ANOTHER, default=False): cv.boolean}
            ),
            description_placeholders={
                "device_count": str(len(devices)),
                "device_names": device_names,
            },
        )

    async def _async_finish_excess_solar_new(self) -> ConfigFlowResult:
        """Finalise a new excess solar config entry."""
        unique_id = self._config_data[CONF_NAME].lower().replace(" ", "_")
        self._config_data[CONF_UNIQUE_ID] = unique_id
        self._config_data["entry_type"] = ENTRY_TYPE_EXCESS_SOLAR

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._config_data[CONF_NAME],
            data=self._config_data,
        )

    # ------------------------------------------------------------------
    # Options flow: main menu → edit settings / add device / remove devices
    # ------------------------------------------------------------------

    async def async_step_excess_solar_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show main options menu for excess solar."""
        if user_input is not None:
            action = user_input.get(CONF_DEVICES_ACTION)
            if action == ACTION_EDIT_SETTINGS:
                return await self.async_step_excess_solar_edit_settings()
            if action == ACTION_ADD_DEVICE:
                if CONF_POWER_DEVICES not in self._config_data:
                    self._config_data[CONF_POWER_DEVICES] = list(
                        self._config_entry.data.get(CONF_POWER_DEVICES, [])
                    )
                return await self.async_step_excess_solar_device()
            if action == ACTION_REMOVE_DEVICES:
                return await self.async_step_excess_solar_remove_devices()

        existing = self._config_entry.data
        devices = existing.get(CONF_POWER_DEVICES, [])
        return self.async_show_form(
            step_id="excess_solar_menu",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES_ACTION): vol.In(
                        {
                            ACTION_EDIT_SETTINGS: "Edit global settings",
                            ACTION_ADD_DEVICE: "Add a device",
                            ACTION_REMOVE_DEVICES: "Remove device(s)",
                        }
                    )
                }
            ),
            description_placeholders={
                "device_count": str(len(devices)),
                "device_names": (", ".join(d[CONF_NAME] for d in devices) or "none"),
            },
        )

    async def async_step_excess_solar_edit_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit global excess solar settings (options flow)."""
        if user_input is not None:
            new_data = dict(self._config_entry.data)
            new_data[CONF_GRID_POWER_SENSOR] = user_input[CONF_GRID_POWER_SENSOR]
            new_data[CONF_BUFFER] = int(user_input.get(CONF_BUFFER, 0))
            new_data[CONF_TURN_ON_DELAY] = int(user_input.get(CONF_TURN_ON_DELAY, 60))

            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="excess_solar_edit_settings",
            data_schema=_get_excess_solar_edit_settings_schema(
                dict(self._config_entry.data)
            ),
        )

    async def async_step_excess_solar_add_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a device in the options flow - delegates to the shared device step."""
        if CONF_POWER_DEVICES not in self._config_data:
            self._config_data[CONF_POWER_DEVICES] = list(
                self._config_entry.data.get(CONF_POWER_DEVICES, [])
            )
        return await self.async_step_excess_solar_device(user_input)

    async def async_step_excess_solar_remove_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one or more devices from the options flow."""
        existing_devices: list[dict[str, Any]] = list(
            self._config_entry.data.get(CONF_POWER_DEVICES, [])
        )

        if not existing_devices:
            return self.async_abort(reason="no_devices_to_remove")

        if user_input is not None:
            names_to_remove = set(user_input.get(CONF_DEVICES_TO_REMOVE, []))
            updated_devices = [
                d for d in existing_devices if d[CONF_NAME] not in names_to_remove
            ]
            new_data = {**self._config_entry.data, CONF_POWER_DEVICES: updated_devices}
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        device_options = [
            selector.SelectOptionDict(value=d[CONF_NAME], label=d[CONF_NAME])
            for d in existing_devices
        ]
        return self.async_show_form(
            step_id="excess_solar_remove_devices",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICES_TO_REMOVE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=device_options,
                            multiple=True,
                        )
                    )
                }
            ),
        )

    async def _async_finish_excess_solar_add_device(self) -> ConfigFlowResult:
        """Finalise adding a device in the options flow."""
        new_data = {
            **self._config_entry.data,
            CONF_POWER_DEVICES: self._config_data[CONF_POWER_DEVICES],
        }
        self.hass.config_entries.async_update_entry(self._config_entry, data=new_data)
        return self.async_create_entry(title="", data={})
