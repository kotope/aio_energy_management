"""Cheapest hours config flow handlers and helpers."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ALLOW_DYNAMIC_ENTITIES,
    CONF_AREA,
    CONF_CALENDAR,
    CONF_DATA_PROVIDER_TYPE,
    CONF_END,
    CONF_END_HOURS_ENTITY,
    CONF_END_MINUTES_ENTITY,
    CONF_ENTSOE_ENTITY,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_HOURS,
    CONF_INVERSED,
    CONF_LAST_HOUR,
    CONF_MINUTES,
    CONF_MTU,
    CONF_NORDPOOL_ENTITY,
    CONF_NORDPOOL_OFFICIAL_CONFIG_ENTRY,
    CONF_NUMBER_OF_SLOTS,
    CONF_NUMBER_OF_SLOTS_ENTITY,
    CONF_OFFSET,
    CONF_PRICE_LIMIT,
    CONF_PRICE_LIMIT_ENTITY,
    CONF_PRICE_MODIFICATIONS,
    CONF_RETENTION_DAYS,
    CONF_SEQUENTIAL,
    CONF_START,
    CONF_START_HOURS_ENTITY,
    CONF_START_MINUTES_ENTITY,
    CONF_TRIGGER_HOUR,
    CONF_TRIGGER_HOUR_ENTITY,
    CONF_UNIQUE_ID,
    CONF_USE_OFFSET,
    DATA_PROVIDER_ENTSOE,
    DATA_PROVIDER_NORDPOOL,
    DATA_PROVIDER_NORDPOOL_OFFICIAL,
)

_LOGGER = logging.getLogger(__name__)

CONF_ENTRY_TYPE = "entry_type"
ENTRY_TYPE_CHEAPEST_HOURS = "cheapest_hours"



def _get_data_provider_type_schema(default: str | None = None) -> vol.Schema:
    """Get data provider type selection schema."""
    if default:
        field = vol.Required(CONF_DATA_PROVIDER_TYPE, default=default)
    else:
        field = vol.Required(CONF_DATA_PROVIDER_TYPE)

    return vol.Schema(
        {
            field: vol.In(
                {
                    DATA_PROVIDER_NORDPOOL: "Nord Pool",
                    DATA_PROVIDER_NORDPOOL_OFFICIAL: "Nord Pool official",
                    DATA_PROVIDER_ENTSOE: "Entso-E",
                }
            ),
        }
    )


def _get_nordpool_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get Nord Pool entity selection schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NORDPOOL_ENTITY,
                description={
                    "suggested_value": user_input.get(CONF_NORDPOOL_ENTITY)
                    if user_input
                    else None
                },
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                )
            ),
            vol.Optional(
                CONF_MTU,
                default=user_input.get(CONF_MTU) if user_input else 60,
            ): vol.In([15, 60]),
            vol.Required(
                CONF_ALLOW_DYNAMIC_ENTITIES,
                default=user_input.get(CONF_ALLOW_DYNAMIC_ENTITIES)
                if user_input
                else False,
            ): cv.boolean,
        }
    )


def _get_nordpool_official_schema(
    hass,
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Get Nord Pool official config entry ID schema."""
    existing_entries = hass.config_entries.async_entries("nordpool")

    options = {entry.entry_id: entry.title for entry in existing_entries}
    return vol.Schema(
        {
            vol.Required(CONF_NORDPOOL_OFFICIAL_CONFIG_ENTRY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in options.items()],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Optional(
                CONF_AREA,
                description={
                    "suggested_value": user_input.get(CONF_AREA) if user_input else None
                },
            ): cv.string,
            vol.Optional(
                CONF_MTU,
                default=user_input.get(CONF_MTU) if user_input else 60,
            ): vol.In([15, 60]),
            vol.Optional(
                CONF_ALLOW_DYNAMIC_ENTITIES,
                default=user_input.get(CONF_ALLOW_DYNAMIC_ENTITIES)
                if user_input
                else True,
            ): cv.boolean,
        }
    )


def _get_entsoe_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get Entso-E entity selection schema."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ENTSOE_ENTITY,
                description={
                    "suggested_value": user_input.get(CONF_ENTSOE_ENTITY)
                    if user_input
                    else None
                },
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                )
            ),
            vol.Optional(
                CONF_MTU,
                default=user_input.get(CONF_MTU) if user_input else 60,
            ): vol.In([15, 60]),
            vol.Optional(
                CONF_ALLOW_DYNAMIC_ENTITIES,
                default=user_input.get(CONF_ALLOW_DYNAMIC_ENTITIES)
                if user_input
                else True,
            ): cv.boolean,
        }
    )


def _get_cheapest_hours_basic_schema(
    user_input: dict[str, Any] | None = None,
    allow_dynamic_entities: bool = True,
) -> vol.Schema:
    """Get basic cheapest hours configuration schema."""
    schema_dict = {
        vol.Required(
            CONF_NAME,
            default=user_input.get(CONF_NAME) if user_input else "Cheapest Hours",
        ): cv.string,
        vol.Optional(
            CONF_NUMBER_OF_SLOTS,
            description={
                "suggested_value": user_input.get(CONF_NUMBER_OF_SLOTS)
                if user_input
                else 0
            },
        ): int,
    }

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_NUMBER_OF_SLOTS_ENTITY,
                description={
                    "suggested_value": user_input.get(CONF_NUMBER_OF_SLOTS_ENTITY)
                    if user_input
                    else None
                },
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    schema_dict.update(
        {
            vol.Required(
                CONF_FIRST_HOUR,
                default=user_input.get(CONF_FIRST_HOUR) if user_input else 0,
            ): int,
            vol.Required(
                CONF_LAST_HOUR,
                default=user_input.get(CONF_LAST_HOUR) if user_input else 23,
            ): int,
            vol.Required(
                CONF_SEQUENTIAL,
                default=user_input.get(CONF_SEQUENTIAL) if user_input else False,
            ): cv.boolean,
        }
    )

    return vol.Schema(schema_dict)


def _get_cheapest_hours_advanced_schema(
    user_input: dict[str, Any] | None = None,
    allow_dynamic_entities: bool = True,
) -> vol.Schema:
    """Get advanced cheapest hours configuration schema."""
    schema_dict = {
        vol.Optional(
            CONF_FAILSAFE_STARTING_HOUR,
            description={
                "suggested_value": user_input.get(CONF_FAILSAFE_STARTING_HOUR)
                if user_input
                else None
            },
        ): int,
        vol.Optional(
            CONF_INVERSED,
            default=user_input.get(CONF_INVERSED) if user_input else False,
        ): cv.boolean,
        vol.Optional(
            CONF_TRIGGER_HOUR,
            description={
                "suggested_value": user_input.get(CONF_TRIGGER_HOUR)
                if user_input
                else None
            },
        ): int,
    }

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_TRIGGER_HOUR_ENTITY,
                description={
                    "suggested_value": user_input.get(CONF_TRIGGER_HOUR_ENTITY)
                    if user_input
                    else None
                },
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    schema_dict[
        vol.Optional(
            CONF_PRICE_LIMIT,
            description={
                "suggested_value": user_input.get(CONF_PRICE_LIMIT)
                if user_input
                else None
            },
        )
    ] = vol.Coerce(float)

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_PRICE_LIMIT_ENTITY,
                description={
                    "suggested_value": user_input.get(CONF_PRICE_LIMIT_ENTITY)
                    if user_input
                    else None
                },
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    schema_dict.update(
        {
            vol.Optional(
                CONF_CALENDAR,
                default=user_input.get(CONF_CALENDAR) if user_input else True,
            ): cv.boolean,
            vol.Optional(
                CONF_RETENTION_DAYS,
                default=user_input.get(CONF_RETENTION_DAYS) if user_input else 1,
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=365,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_PRICE_MODIFICATIONS,
                description={
                    "suggested_value": user_input.get(CONF_PRICE_MODIFICATIONS)
                    if user_input
                    else None
                },
            ): selector.TemplateSelector(),
            vol.Required(
                CONF_USE_OFFSET,
                default=user_input.get(CONF_USE_OFFSET) if user_input else False,
            ): cv.boolean,
        }
    )

    return vol.Schema(schema_dict)


def _process_offset_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Process offset input and build offset structure.

    Returns:
        Tuple of (offset_dict, entity_dict) where offset_dict contains static values
        and entity_dict contains entity references to be stored at root level.
    """
    offset = {}
    entities = {}

    if any(
        user_input.get(f"{CONF_START}_{key}") is not None
        for key in [CONF_HOURS, CONF_MINUTES]
    ):
        start_offset = {}
        if user_input.get(f"{CONF_START}_{CONF_HOURS}") is not None:
            start_offset[CONF_HOURS] = user_input[f"{CONF_START}_{CONF_HOURS}"]
        if user_input.get(f"{CONF_START}_{CONF_MINUTES}") is not None:
            start_offset[CONF_MINUTES] = user_input[f"{CONF_START}_{CONF_MINUTES}"]
        if start_offset:
            offset[CONF_START] = start_offset

    if user_input.get(CONF_START_HOURS_ENTITY):
        entities[CONF_START_HOURS_ENTITY] = user_input[CONF_START_HOURS_ENTITY]
    if user_input.get(CONF_START_MINUTES_ENTITY):
        entities[CONF_START_MINUTES_ENTITY] = user_input[CONF_START_MINUTES_ENTITY]

    if any(
        user_input.get(f"{CONF_END}_{key}") is not None
        for key in [CONF_HOURS, CONF_MINUTES]
    ):
        end_offset = {}
        if user_input.get(f"{CONF_END}_{CONF_HOURS}") is not None:
            end_offset[CONF_HOURS] = user_input[f"{CONF_END}_{CONF_HOURS}"]
        if user_input.get(f"{CONF_END}_{CONF_MINUTES}") is not None:
            end_offset[CONF_MINUTES] = user_input[f"{CONF_END}_{CONF_MINUTES}"]
        if end_offset:
            offset[CONF_END] = end_offset

    if user_input.get(CONF_END_HOURS_ENTITY):
        entities[CONF_END_HOURS_ENTITY] = user_input[CONF_END_HOURS_ENTITY]
    if user_input.get(CONF_END_MINUTES_ENTITY):
        entities[CONF_END_MINUTES_ENTITY] = user_input[CONF_END_MINUTES_ENTITY]

    return offset, entities


def _get_offset_schema(
    offset_data: dict[str, Any], allow_dynamic_entities: bool = True
) -> vol.Schema:
    """Get offset configuration schema."""
    start_offset = offset_data.get(CONF_START, {})
    end_offset = offset_data.get(CONF_END, {})

    schema_dict = {
        vol.Optional(
            f"{CONF_START}_{CONF_HOURS}",
            description={"suggested_value": start_offset.get(CONF_HOURS)},
        ): int,
    }

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_START_HOURS_ENTITY,
                description={
                    "suggested_value": offset_data.get(CONF_START_HOURS_ENTITY)
                },
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    schema_dict[
        vol.Optional(
            f"{CONF_START}_{CONF_MINUTES}",
            description={"suggested_value": start_offset.get(CONF_MINUTES)},
        )
    ] = int

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_START_MINUTES_ENTITY,
                description={
                    "suggested_value": offset_data.get(CONF_START_MINUTES_ENTITY)
                },
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    schema_dict[
        vol.Optional(
            f"{CONF_END}_{CONF_HOURS}",
            description={"suggested_value": end_offset.get(CONF_HOURS)},
        )
    ] = int

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_END_HOURS_ENTITY,
                description={"suggested_value": offset_data.get(CONF_END_HOURS_ENTITY)},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    schema_dict[
        vol.Optional(
            f"{CONF_END}_{CONF_MINUTES}",
            description={"suggested_value": end_offset.get(CONF_MINUTES)},
        )
    ] = int

    if allow_dynamic_entities:
        schema_dict[
            vol.Optional(
                CONF_END_MINUTES_ENTITY,
                description={
                    "suggested_value": offset_data.get(CONF_END_MINUTES_ENTITY)
                },
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "input_number"]),
        )

    return vol.Schema(schema_dict)


def _validate_and_clean_static_or_entity(
    user_input: dict[str, Any],
    static_key: str,
    entity_key: str,
    field_name: str,
    allow_both_empty: bool = False,
) -> dict[str, str]:
    """Validate and clean configuration where either static value or entity can be used.

    Args:
        user_input: The user input dictionary (will be modified to remove unused fields)
        static_key: Key for the static value field
        entity_key: Key for the entity field
        field_name: Human-readable field name for error messages
        allow_both_empty: If True, allows both fields to be empty

    Returns:
        Dict of errors (empty if validation passes).
    """
    errors: dict[str, str] = {}

    static_value = user_input.get(static_key)
    has_static = static_value is not None and (
        (isinstance(static_value, (int, float)) and static_value != 0)
        or (isinstance(static_value, str) and static_value.strip())
    )

    has_entity = bool(user_input.get(entity_key))

    if has_static and has_entity:
        errors["base"] = f"both_{field_name}_configured"
    elif not has_static and not has_entity and not allow_both_empty:
        errors["base"] = f"no_{field_name}_configured"
    else:
        if has_entity and static_key in user_input:
            user_input.pop(static_key, None)
        elif has_static and entity_key in user_input:
            user_input.pop(entity_key, None)
        elif not has_static and not has_entity and allow_both_empty:
            user_input.pop(static_key, None)
            user_input.pop(entity_key, None)

    return errors


def _validate_and_clean_number_of_slots(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate and clean number of slots configuration.

    Removes unused fields and returns a dict of errors (empty if validation passes).
    """
    return _validate_and_clean_static_or_entity(
        user_input,
        CONF_NUMBER_OF_SLOTS,
        CONF_NUMBER_OF_SLOTS_ENTITY,
        "slots",
        allow_both_empty=False,
    )


def _validate_and_clean_advanced_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate and clean advanced configuration fields.

    Validates trigger_hour and price_limit (both optional, can use static or entity).
    """
    errors: dict[str, str] = {}

    trigger_errors = _validate_and_clean_static_or_entity(
        user_input,
        CONF_TRIGGER_HOUR,
        CONF_TRIGGER_HOUR_ENTITY,
        "trigger_hour",
        allow_both_empty=True,
    )
    if trigger_errors:
        errors.update(trigger_errors)

    price_errors = _validate_and_clean_static_or_entity(
        user_input,
        CONF_PRICE_LIMIT,
        CONF_PRICE_LIMIT_ENTITY,
        "price_limit",
        allow_both_empty=True,
    )
    if price_errors:
        errors.update(price_errors)

    return errors


def _validate_and_clean_offset_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate and clean offset configuration fields.

    Validates start/end hours and minutes (all optional, can use static or entity).
    """
    errors: dict[str, str] = {}

    start_hours_errors = _validate_and_clean_static_or_entity(
        user_input,
        f"{CONF_START}_{CONF_HOURS}",
        CONF_START_HOURS_ENTITY,
        "start_hours",
        allow_both_empty=True,
    )
    if start_hours_errors:
        errors.update(start_hours_errors)

    start_minutes_errors = _validate_and_clean_static_or_entity(
        user_input,
        f"{CONF_START}_{CONF_MINUTES}",
        CONF_START_MINUTES_ENTITY,
        "start_minutes",
        allow_both_empty=True,
    )
    if start_minutes_errors:
        errors.update(start_minutes_errors)

    end_hours_errors = _validate_and_clean_static_or_entity(
        user_input,
        f"{CONF_END}_{CONF_HOURS}",
        CONF_END_HOURS_ENTITY,
        "end_hours",
        allow_both_empty=True,
    )
    if end_hours_errors:
        errors.update(end_hours_errors)

    end_minutes_errors = _validate_and_clean_static_or_entity(
        user_input,
        f"{CONF_END}_{CONF_MINUTES}",
        CONF_END_MINUTES_ENTITY,
        "end_minutes",
        allow_both_empty=True,
    )
    if end_minutes_errors:
        errors.update(end_minutes_errors)

    return errors


# ---------------------------------------------------------------------------
# Integer validation helpers
# These perform custom validation instead of using vol.Range so that integer
# fields keep their text-box appearance (vol.Range would turn them into sliders).
# ---------------------------------------------------------------------------


def _validate_basic_integer_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate integer fields on the basic cheapest hours step.

    Checks:
    - first_hour: 0-23
    - last_hour: 0-23
    - last_hour must be >= first_hour
    - number_of_slots: >= 0
    """
    errors: dict[str, str] = {}

    first_hour = user_input.get(CONF_FIRST_HOUR)
    last_hour = user_input.get(CONF_LAST_HOUR)
    number_of_slots = user_input.get(CONF_NUMBER_OF_SLOTS)

    if first_hour is not None and not (0 <= first_hour <= 23):
        errors[CONF_FIRST_HOUR] = "first_hour_out_of_range"

    if last_hour is not None and not (0 <= last_hour <= 23):
        errors[CONF_LAST_HOUR] = "last_hour_out_of_range"
    elif (
        first_hour is not None
        and last_hour is not None
        and CONF_FIRST_HOUR not in errors
        and last_hour < first_hour
    ):
        errors[CONF_LAST_HOUR] = "last_hour_before_first_hour"

    if number_of_slots is not None and number_of_slots < 0:
        errors[CONF_NUMBER_OF_SLOTS] = "number_of_slots_negative"

    return errors


def _validate_advanced_integer_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate optional integer fields on the advanced cheapest hours step.

    Checks:
    - failsafe_starting_hour: 0-23 (optional)
    - trigger_hour: 0-23 (optional)
    """
    errors: dict[str, str] = {}

    failsafe = user_input.get(CONF_FAILSAFE_STARTING_HOUR)
    if failsafe is not None and not (0 <= failsafe <= 23):
        errors[CONF_FAILSAFE_STARTING_HOUR] = "failsafe_starting_hour_out_of_range"

    trigger_hour = user_input.get(CONF_TRIGGER_HOUR)
    if trigger_hour is not None and not (0 <= trigger_hour <= 23):
        errors[CONF_TRIGGER_HOUR] = "trigger_hour_out_of_range"

    return errors


def _validate_offset_integer_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate optional integer fields on the offset step.

    Checks:
    - start_minutes: 0-59 (optional)
    - end_minutes: 0-59 (optional)
    Hours fields are unrestricted integers (they can exceed 23 for multi-hour offsets).
    """
    errors: dict[str, str] = {}

    start_minutes = user_input.get(f"{CONF_START}_{CONF_MINUTES}")
    if start_minutes is not None and not (0 <= start_minutes <= 59):
        errors[f"{CONF_START}_{CONF_MINUTES}"] = "start_minutes_out_of_range"

    end_minutes = user_input.get(f"{CONF_END}_{CONF_MINUTES}")
    if end_minutes is not None and not (0 <= end_minutes <= 59):
        errors[f"{CONF_END}_{CONF_MINUTES}"] = "end_minutes_out_of_range"

    return errors


class CheapestHoursConfigFlowMixin:
    """Mixin for cheapest hours config flow steps."""

    async def async_step_cheapest_hours_data_provider(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select data provider type for cheapest hours."""
        if user_input is not None:
            self._data_provider_type = user_input[CONF_DATA_PROVIDER_TYPE]

            if self._data_provider_type == DATA_PROVIDER_NORDPOOL:
                return await self.async_step_cheapest_hours_nordpool()
            if self._data_provider_type == DATA_PROVIDER_NORDPOOL_OFFICIAL:
                return await self.async_step_cheapest_hours_nordpool_official()
            if self._data_provider_type == DATA_PROVIDER_ENTSOE:
                return await self.async_step_cheapest_hours_entsoe()

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
            self._config_data.update(user_input)
            return await self.async_step_cheapest_hours_basic()

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        return self.async_show_form(
            step_id="cheapest_hours_entsoe",
            data_schema=_get_entsoe_schema(existing_data or user_input),
        )

    async def async_step_cheapest_hours_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure basic cheapest hours settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            allow_dynamic = self._config_data.get(CONF_ALLOW_DYNAMIC_ENTITIES, True)
            if not allow_dynamic:
                user_input.pop(CONF_NUMBER_OF_SLOTS_ENTITY, None)
            errors = _validate_basic_integer_fields(user_input)
            slot_errors = _validate_and_clean_number_of_slots(user_input)
            errors.update(slot_errors)
            if not errors:
                self._config_data.update(user_input)
                return await self.async_step_cheapest_hours_advanced()

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = dict(self._config_entry.data)

        allow_dynamic = self._config_data.get(CONF_ALLOW_DYNAMIC_ENTITIES, True)
        return self.async_show_form(
            step_id="cheapest_hours_basic",
            data_schema=_get_cheapest_hours_basic_schema(
                existing_data or user_input, allow_dynamic
            ),
            errors=errors,
        )

    async def async_step_cheapest_hours_advanced(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure advanced cheapest hours settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            allow_dynamic = self._config_data.get(CONF_ALLOW_DYNAMIC_ENTITIES, True)
            if not allow_dynamic:
                user_input.pop(CONF_TRIGGER_HOUR_ENTITY, None)
                user_input.pop(CONF_PRICE_LIMIT_ENTITY, None)
            errors = _validate_advanced_integer_fields(user_input)
            advanced_errors = _validate_and_clean_advanced_fields(user_input)
            errors.update(advanced_errors)
            if not errors:
                use_offset = user_input.get(CONF_USE_OFFSET, False)
                if hasattr(self, "_config_entry"):
                    preserved_calendar = self._config_data.get(CONF_CALENDAR)
                    self._config_data.update(user_input)
                    if preserved_calendar is not None:
                        self._config_data[CONF_CALENDAR] = preserved_calendar
                else:
                    self._config_data.update(user_input)

                if use_offset:
                    return await self.async_step_cheapest_hours_offset()

                if hasattr(self, "_config_entry"):
                    new_data = {
                        **self._config_data,
                        CONF_ENTRY_TYPE: ENTRY_TYPE_CHEAPEST_HOURS,
                        CONF_UNIQUE_ID: self._config_entry.data.get(CONF_UNIQUE_ID),
                        CONF_NAME: self._config_entry.data.get(CONF_NAME),
                        CONF_DATA_PROVIDER_TYPE: self._data_provider_type,
                    }

                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data=new_data,
                    )
                    return self.async_create_entry(title="", data={})

                unique_id = self._config_data[CONF_NAME].lower().replace(" ", "_")
                self._config_data[CONF_UNIQUE_ID] = unique_id
                self._config_data[CONF_ENTRY_TYPE] = ENTRY_TYPE_CHEAPEST_HOURS

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._config_data[CONF_NAME],
                    data=self._config_data,
                )

        existing_data = None
        if hasattr(self, "_config_entry"):
            existing_data = {**self._config_entry.data}
            existing_data[CONF_CALENDAR] = self._config_data.get(CONF_CALENDAR, True)

        allow_dynamic = self._config_data.get(CONF_ALLOW_DYNAMIC_ENTITIES, True)
        return self.async_show_form(
            step_id="cheapest_hours_advanced",
            data_schema=_get_cheapest_hours_advanced_schema(
                existing_data or user_input, allow_dynamic
            ),
            errors=errors,
        )

    async def async_step_cheapest_hours_offset(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure offset settings for cheapest hours."""
        errors: dict[str, str] = {}

        if user_input is not None:
            allow_dynamic = self._config_data.get(CONF_ALLOW_DYNAMIC_ENTITIES, True)
            if not allow_dynamic:
                user_input.pop(CONF_START_HOURS_ENTITY, None)
                user_input.pop(CONF_START_MINUTES_ENTITY, None)
                user_input.pop(CONF_END_HOURS_ENTITY, None)
                user_input.pop(CONF_END_MINUTES_ENTITY, None)
            errors = _validate_offset_integer_fields(user_input)
            offset_errors = _validate_and_clean_offset_fields(user_input)
            errors.update(offset_errors)
            if not errors:
                offset, entities = _process_offset_input(user_input)
                if offset:
                    self._config_data[CONF_OFFSET] = offset
                self._config_data.update(entities)

                if hasattr(self, "_config_entry"):
                    new_data = {
                        **self._config_data,
                        CONF_ENTRY_TYPE: ENTRY_TYPE_CHEAPEST_HOURS,
                        CONF_UNIQUE_ID: self._config_entry.data.get(CONF_UNIQUE_ID),
                        CONF_NAME: self._config_entry.data.get(CONF_NAME),
                        CONF_DATA_PROVIDER_TYPE: self._data_provider_type,
                    }

                    self.hass.config_entries.async_update_entry(
                        self._config_entry,
                        data=new_data,
                    )
                    return self.async_create_entry(title="", data={})

                unique_id = self._config_data[CONF_NAME].lower().replace(" ", "_")
                self._config_data[CONF_UNIQUE_ID] = unique_id
                self._config_data[CONF_ENTRY_TYPE] = ENTRY_TYPE_CHEAPEST_HOURS

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=self._config_data[CONF_NAME],
                    data=self._config_data,
                )

        offset_data = {}
        if hasattr(self, "_config_entry"):
            offset_data = {
                **self._config_entry.data.get(CONF_OFFSET, {}),
                **self._config_entry.data,
            }
        else:
            offset_data = {
                **self._config_data.get(CONF_OFFSET, {}),
                **self._config_data,
            }

        allow_dynamic = self._config_data.get(CONF_ALLOW_DYNAMIC_ENTITIES, True)
        return self.async_show_form(
            step_id="cheapest_hours_offset",
            data_schema=_get_offset_schema(offset_data, allow_dynamic),
            errors=errors,
        )
