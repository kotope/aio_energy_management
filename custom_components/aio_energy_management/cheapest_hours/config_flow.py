"""Cheapest hours config flow handlers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigFlowResult

from custom_components.aio_energy_management.const import (
    CONF_ADD_FLEXIBLE,
    CONF_AREA,
    CONF_DATA_PROVIDER_TYPE,
    CONF_END_HOURS_ENTITY,
    CONF_END_MINUTES_ENTITY,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FLEXIBLE_PRICE_LIMIT,
    CONF_FLEXIBLE_PRICE_LIMIT_ENTITY,
    CONF_MAX_NUMBER_OF_SLOTS,
    CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
    CONF_MIN_SEQ_SLOTS,
    CONF_MTU,
    CONF_NAME,
    CONF_NUMBER_OF_BLOCKS,
    CONF_NUMBER_OF_SLOTS,
    CONF_NUMBER_OF_SLOTS_ENTITY,
    CONF_OFFSET,
    CONF_PRICE_LIMIT,
    CONF_PRICE_LIMIT_ENTITY,
    CONF_PRICE_MODIFICATIONS,
    CONF_RETENTION_DAYS,
    CONF_SEQUENTIAL,
    CONF_START_HOURS_ENTITY,
    CONF_START_MINUTES_ENTITY,
    CONF_TRIGGER_HOUR,
    CONF_TRIGGER_HOUR_ENTITY,
    CONF_UNIQUE_ID,
    DATA_PROVIDER_ENTSOE,
    DATA_PROVIDER_NORDPOOL,
    DATA_PROVIDER_NORDPOOL_OFFICIAL,
    DATA_PROVIDER_STROMLIGNING,
)
from .helpers import (
    _coerce_mtu,
    _normalize_optional_keys,
    _process_offset_input,
    sanitize_cheapest_hours_input,
    _validate_advanced_integer_fields,
    _validate_and_build_add_flexible,
    _validate_and_clean_advanced_fields,
    _validate_and_clean_number_of_slots,
    _validate_and_clean_offset_fields,
    _validate_basic_integer_fields,
    _validate_offset_integer_fields,
)
from .schemas import (
    _get_cheapest_hours_advanced_schema,
    _get_cheapest_hours_basic_schema,
    _get_data_provider_type_schema,
    _get_entsoe_schema,
    _get_nordpool_official_schema,
    _get_nordpool_schema,
    _get_offset_schema,
    _get_stromligning_schema,
)

_LOGGER = logging.getLogger(__name__)

CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_CHEAPEST_HOURS = "cheapest_hours"


class CheapestHoursConfigFlowMixin:
    """Mixin for cheapest hours config flow steps."""

    def _save_options_entry(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Helper to save updated data directly during Options Flow."""
        cleaned_input = sanitize_cheapest_hours_input(user_input)

        new_data = {
            **self._config_entry.data,
            **cleaned_input,
        }
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            title=new_data.get(CONF_NAME, self._config_entry.title),
            data=new_data,
        )
        return self.async_create_entry(title="", data={})

    async def async_step_cheapest_hours_data_provider(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select data provider type for cheapest hours."""
        if user_input is not None:
            self._data_provider_type = user_input[CONF_DATA_PROVIDER_TYPE]
            self._config_data[CONF_DATA_PROVIDER_TYPE] = self._data_provider_type

            if self._data_provider_type == DATA_PROVIDER_NORDPOOL:
                return await self.async_step_cheapest_hours_nordpool()
            if self._data_provider_type == DATA_PROVIDER_NORDPOOL_OFFICIAL:
                return await self.async_step_cheapest_hours_nordpool_official()
            if self._data_provider_type == DATA_PROVIDER_ENTSOE:
                return await self.async_step_cheapest_hours_entsoe()
            if self._data_provider_type == DATA_PROVIDER_STROMLIGNING:
                return await self.async_step_cheapest_hours_stromligning()

        default = None
        if hasattr(self, "_config_entry"):
            default = self._config_entry.data.get(CONF_DATA_PROVIDER_TYPE)

        return self.async_show_form(
            step_id="cheapest_hours_data_provider",
            data_schema=_get_data_provider_type_schema(default=default),
        )

    async def async_step_cheapest_hours_nordpool(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure Nord Pool entity for cheapest hours."""
        if user_input is not None:
            _coerce_mtu(user_input)
            self._config_data.update(user_input)
            return await self.async_step_cheapest_hours_basic()

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        return self.async_show_form(
            step_id="cheapest_hours_nordpool",
            data_schema=_get_nordpool_schema(existing_data or user_input),
        )

    async def async_step_cheapest_hours_nordpool_official(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure Nord Pool official config entry for cheapest hours."""
        if user_input is not None:
            _coerce_mtu(user_input)

            if hasattr(self, "_config_entry"):
                _normalize_optional_keys(user_input, [CONF_AREA])
                return self._save_options_entry(user_input)

            self._config_data.update(user_input)
            return await self.async_step_cheapest_hours_basic()

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        return self.async_show_form(
            step_id="cheapest_hours_nordpool_official",
            data_schema=_get_nordpool_official_schema(
                self.hass, existing_data or user_input
            ),
        )

    async def async_step_cheapest_hours_entsoe(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure Entso-E entity for cheapest hours."""
        if user_input is not None:
            _coerce_mtu(user_input)
            self._config_data.update(user_input)
            return await self.async_step_cheapest_hours_basic()

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        return self.async_show_form(
            step_id="cheapest_hours_entsoe",
            data_schema=_get_entsoe_schema(existing_data or user_input),
        )

    async def async_step_cheapest_hours_stromligning(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure Strømligning entities for cheapest hours."""
        if user_input is not None:
            _coerce_mtu(user_input)
            self._config_data.update(user_input)
            return await self.async_step_cheapest_hours_basic()

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        return self.async_show_form(
            step_id="cheapest_hours_stromligning",
            data_schema=_get_stromligning_schema(existing_data or user_input),
        )

    async def async_step_cheapest_hours_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure basic cheapest hours settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if "dynamic_section" in user_input and isinstance(
                user_input["dynamic_section"], dict
            ):
                user_input.update(user_input.pop("dynamic_section"))
            errors = _validate_basic_integer_fields(user_input)
            slot_errors = _validate_and_clean_number_of_slots(user_input)
            errors.update(slot_errors)

            if not errors:
                if hasattr(self, "_config_entry"):
                    _normalize_optional_keys(
                        user_input,
                        [CONF_NUMBER_OF_SLOTS, CONF_NUMBER_OF_SLOTS_ENTITY],
                    )
                    if user_input.get(CONF_SEQUENTIAL) is True:
                        user_input[CONF_MIN_SEQ_SLOTS] = None
                        user_input[CONF_NUMBER_OF_BLOCKS] = None
                        user_input[CONF_ADD_FLEXIBLE] = None
                        user_input[CONF_MAX_NUMBER_OF_SLOTS] = None
                        user_input[CONF_MAX_NUMBER_OF_SLOTS_ENTITY] = None
                        user_input[CONF_FLEXIBLE_PRICE_LIMIT] = None
                        user_input[CONF_FLEXIBLE_PRICE_LIMIT_ENTITY] = None
                    return self._save_options_entry(user_input)

                self._config_data.update(user_input)

                unique_id = self._config_data[CONF_NAME].lower().replace(" ", "_")
                self._config_data[CONF_UNIQUE_ID] = unique_id
                self._config_data[CONF_ENTRY_TYPE] = ENTRY_TYPE_CHEAPEST_HOURS
                cleaned_data = sanitize_cheapest_hours_input(self._config_data)

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=cleaned_data[CONF_NAME],
                    data=cleaned_data,
                )

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        merged_input = {**(existing_data or {}), **(user_input or {})}

        return self.async_show_form(
            step_id="cheapest_hours_basic",
            data_schema=_get_cheapest_hours_basic_schema(merged_input),
            errors=errors,
        )

    async def async_step_cheapest_hours_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure advanced cheapest hours settings (Options Flow only)."""
        errors: dict[str, str] = {}
        entry_data = dict(self._config_entry.data)
        sequential = entry_data.get(CONF_SEQUENTIAL, False)

        if user_input is not None:
            if "dynamic_section" in user_input and isinstance(
                user_input["dynamic_section"], dict
            ):
                user_input.update(user_input.pop("dynamic_section"))

            errors = _validate_advanced_integer_fields(user_input)
            advanced_errors = _validate_and_clean_advanced_fields(user_input)
            errors.update(advanced_errors)

            if sequential:
                user_input.pop(CONF_FLEXIBLE_PRICE_LIMIT, None)
                user_input.pop(CONF_FLEXIBLE_PRICE_LIMIT_ENTITY, None)
            else:
                flexible_errors = _validate_and_build_add_flexible(
                    user_input,
                    entry_data.get(CONF_MTU) or 60,
                )
                errors.update(flexible_errors)

            if not errors:
                _normalize_optional_keys(
                    user_input,
                    [
                        CONF_FAILSAFE_STARTING_HOUR,
                        CONF_TRIGGER_HOUR,
                        CONF_TRIGGER_HOUR_ENTITY,
                        CONF_PRICE_LIMIT,
                        CONF_PRICE_LIMIT_ENTITY,
                        CONF_MIN_SEQ_SLOTS,
                        CONF_NUMBER_OF_BLOCKS,
                        CONF_PRICE_MODIFICATIONS,
                        CONF_MAX_NUMBER_OF_SLOTS,
                        CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
                        CONF_ADD_FLEXIBLE,
                        CONF_RETENTION_DAYS,
                    ],
                )
                return self._save_options_entry(user_input)

        merged_input = {**entry_data, **(user_input or {})}

        return self.async_show_form(
            step_id="cheapest_hours_advanced",
            data_schema=_get_cheapest_hours_advanced_schema(merged_input, sequential),
            errors=errors,
        )

    async def async_step_cheapest_hours_offset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure offset settings for cheapest hours (Options Flow only)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if "dynamic_section" in user_input and isinstance(
                user_input["dynamic_section"], dict
            ):
                user_input.update(user_input.pop("dynamic_section"))

            errors = _validate_offset_integer_fields(user_input)
            offset_errors = _validate_and_clean_offset_fields(user_input)
            errors.update(offset_errors)

            if not errors:
                offset, entities = _process_offset_input(user_input)

                save_data = {
                    CONF_OFFSET: offset if offset else None,
                    CONF_START_HOURS_ENTITY: entities.get(CONF_START_HOURS_ENTITY),
                    CONF_START_MINUTES_ENTITY: entities.get(CONF_START_MINUTES_ENTITY),
                    CONF_END_HOURS_ENTITY: entities.get(CONF_END_HOURS_ENTITY),
                    CONF_END_MINUTES_ENTITY: entities.get(CONF_END_MINUTES_ENTITY),
                }
                return self._save_options_entry(save_data)

        offset_data = {
            **(self._config_entry.data.get(CONF_OFFSET) or {}),
            **self._config_entry.data,
        }
        merged_input = {**offset_data, **(user_input or {})}

        return self.async_show_form(
            step_id="cheapest_hours_offset",
            data_schema=_get_offset_schema(merged_input),
            errors=errors,
        )
