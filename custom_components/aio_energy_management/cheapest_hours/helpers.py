# custom_components/aio_energy_management/helpers.py

# 1. validation checks (_validate_offset_integer_fields, etc.)
# 2. Cleanup logic (_validate_and_clean_offset_fields)
# 3. Input processors (_process_offset_input)

"""Cheapest hours configuration flow helpers and validation logic."""

from __future__ import annotations

from typing import Any

from custom_components.aio_energy_management.const import (
    CONF_ADD_FLEXIBLE,
    CONF_END,
    CONF_END_HOURS_ENTITY,
    CONF_END_MINUTES_ENTITY,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_FLEXIBLE_PRICE_LIMIT,
    CONF_FLEXIBLE_PRICE_LIMIT_ENTITY,
    CONF_HOURS,
    CONF_LAST_HOUR,
    CONF_MAX_NUMBER_OF_SLOTS,
    CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
    CONF_MIN_SEQ_SLOTS,
    CONF_MINUTES,
    CONF_MTU,
    CONF_NUMBER_OF_BLOCKS,
    CONF_NUMBER_OF_SLOTS,
    CONF_NUMBER_OF_SLOTS_ENTITY,
    CONF_PRICE_LIMIT,
    CONF_PRICE_LIMIT_ENTITY,
    CONF_START,
    CONF_START_HOURS_ENTITY,
    CONF_START_MINUTES_ENTITY,
    CONF_TRIGGER_HOUR,
    CONF_TRIGGER_HOUR_ENTITY,
)


def _get_val(
    data: dict, key: str, flex_key: str | None = None, default: Any = None
) -> Any:
    """Retrieve the suggested value from user_input, add_flexible, or the default."""
    flex_data = data.get(CONF_ADD_FLEXIBLE) or {}
    val = flex_data.get(flex_key) if flex_key else None
    if val is None:
        val = data.get(key)
    return val if val is not None else default


def _mtu_default(user_input: dict[str, Any] | None) -> str:
    """Return the MTU dropdown default as a string."""
    if user_input and user_input.get(CONF_MTU) is not None:
        return str(user_input[CONF_MTU])
    return "60"


def _coerce_mtu(user_input: dict[str, Any]) -> None:
    """Coerce the MTU dropdown value (a string) back to an int in place."""
    if user_input.get(CONF_MTU) is not None:
        user_input[CONF_MTU] = int(user_input[CONF_MTU])


def _normalize_optional_keys(user_input: dict[str, Any], keys: list[str]) -> None:
    """Ensure every optional key is present (as None) so clearing it in the UI overwrites the stored value."""
    for key in keys:
        user_input.setdefault(key, None)


def sanitize_cheapest_hours_input(user_input: dict[str, Any]) -> dict[str, Any]:
    """Convert form input numbers from float to int before saving."""
    cleaned = dict(user_input)
    int_keys = [
        CONF_FIRST_HOUR,
        CONF_LAST_HOUR,
        CONF_NUMBER_OF_SLOTS,
        CONF_FAILSAFE_STARTING_HOUR,
        CONF_TRIGGER_HOUR,
        CONF_MIN_SEQ_SLOTS,
        CONF_NUMBER_OF_BLOCKS,
        CONF_MAX_NUMBER_OF_SLOTS,
        CONF_START_HOURS_ENTITY,
        CONF_START_MINUTES_ENTITY,
        CONF_END_HOURS_ENTITY,
        CONF_END_MINUTES_ENTITY,
    ]
    for key in int_keys:
        if key in cleaned and cleaned[key] is not None:
            try:
                cleaned[key] = int(cleaned[key])
            except ValueError, TypeError:
                pass
    return cleaned


def _validate_and_clean_static_or_entity(
    user_input: dict[str, Any],
    static_key: str,
    entity_key: str,
    field_name: str,
    allow_both_empty: bool = False,
) -> dict[str, str]:
    """Validate and clean configuration where either static value or entity can be used."""
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
    """Validate and clean number of slots configuration."""
    return _validate_and_clean_static_or_entity(
        user_input,
        CONF_NUMBER_OF_SLOTS,
        CONF_NUMBER_OF_SLOTS_ENTITY,
        "slots",
        allow_both_empty=False,
    )


def _validate_and_clean_advanced_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate and clean advanced configuration fields."""
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


def _validate_and_build_add_flexible(
    user_input: dict[str, Any],
    mtu: int,
) -> dict[str, str]:
    """Validate flexible slot fields and assemble them into a nested dict."""
    errors: dict[str, str] = {}

    max_errors = _validate_and_clean_static_or_entity(
        user_input,
        CONF_MAX_NUMBER_OF_SLOTS,
        CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
        "max_number_of_slots",
        allow_both_empty=True,
    )
    errors.update(max_errors)

    price_errors = _validate_and_clean_static_or_entity(
        user_input,
        CONF_FLEXIBLE_PRICE_LIMIT,
        CONF_FLEXIBLE_PRICE_LIMIT_ENTITY,
        "flexible_price_limit",
        allow_both_empty=True,
    )
    errors.update(price_errors)

    if errors:
        return errors

    has_max = (
        CONF_MAX_NUMBER_OF_SLOTS in user_input
        or CONF_MAX_NUMBER_OF_SLOTS_ENTITY in user_input
    )
    has_price = (
        CONF_FLEXIBLE_PRICE_LIMIT in user_input
        or CONF_FLEXIBLE_PRICE_LIMIT_ENTITY in user_input
    )

    if has_max != has_price:
        errors["base"] = "add_flexible_incomplete"
        return errors

    max_slots = user_input.get(CONF_MAX_NUMBER_OF_SLOTS)
    if max_slots is not None:
        cap = 96 if mtu == 15 else 24
        if max_slots < 1 or max_slots > cap:
            errors[CONF_MAX_NUMBER_OF_SLOTS] = "max_number_of_slots_out_of_range"
            return errors

    flexible_price_limit = user_input.get(CONF_FLEXIBLE_PRICE_LIMIT)
    price_limit = user_input.get(CONF_PRICE_LIMIT)
    if (
        flexible_price_limit is not None
        and price_limit is not None
        and flexible_price_limit >= price_limit
    ):
        errors[CONF_FLEXIBLE_PRICE_LIMIT] = "flexible_price_limit_not_below_price_limit"
        return errors

    add_flexible: dict[str, Any] = {}
    if CONF_MAX_NUMBER_OF_SLOTS in user_input:
        add_flexible[CONF_MAX_NUMBER_OF_SLOTS] = user_input.pop(
            CONF_MAX_NUMBER_OF_SLOTS
        )
    if CONF_MAX_NUMBER_OF_SLOTS_ENTITY in user_input:
        add_flexible[CONF_MAX_NUMBER_OF_SLOTS_ENTITY] = user_input.pop(
            CONF_MAX_NUMBER_OF_SLOTS_ENTITY
        )
    if CONF_FLEXIBLE_PRICE_LIMIT in user_input:
        add_flexible[CONF_PRICE_LIMIT] = user_input.pop(CONF_FLEXIBLE_PRICE_LIMIT)
    if CONF_FLEXIBLE_PRICE_LIMIT_ENTITY in user_input:
        add_flexible[CONF_PRICE_LIMIT_ENTITY] = user_input.pop(
            CONF_FLEXIBLE_PRICE_LIMIT_ENTITY
        )

    if add_flexible:
        user_input[CONF_ADD_FLEXIBLE] = add_flexible
    else:
        user_input.pop(CONF_ADD_FLEXIBLE, None)

    return errors


def _validate_and_clean_offset_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate and clean offset configuration fields."""
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


def _validate_basic_integer_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate integer fields on the basic cheapest hours step."""
    errors: dict[str, str] = {}

    first_hour = user_input.get(CONF_FIRST_HOUR)
    last_hour = user_input.get(CONF_LAST_HOUR)
    number_of_slots = user_input.get(CONF_NUMBER_OF_SLOTS)

    if first_hour is not None and not (0 <= first_hour <= 23):
        errors[CONF_FIRST_HOUR] = "first_hour_out_of_range"

    if last_hour is not None and not (0 <= last_hour <= 23):
        errors[CONF_LAST_HOUR] = "last_hour_out_of_range"

    if number_of_slots is not None and number_of_slots < 0:
        errors[CONF_NUMBER_OF_SLOTS] = "number_of_slots_negative"

    return errors


def _validate_advanced_integer_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate optional integer fields on the advanced cheapest hours step."""
    errors: dict[str, str] = {}

    failsafe = user_input.get(CONF_FAILSAFE_STARTING_HOUR)
    if failsafe is not None and not (0 <= failsafe <= 23):
        errors[CONF_FAILSAFE_STARTING_HOUR] = "failsafe_starting_hour_out_of_range"

    trigger_hour = user_input.get(CONF_TRIGGER_HOUR)
    if trigger_hour is not None and not (0 <= trigger_hour <= 23):
        errors[CONF_TRIGGER_HOUR] = "trigger_hour_out_of_range"

    min_seq_slots = user_input.get(CONF_MIN_SEQ_SLOTS)
    if min_seq_slots is not None and min_seq_slots < 1:
        errors[CONF_MIN_SEQ_SLOTS] = "min_seq_slots_out_of_range"

    number_of_blocks = user_input.get(CONF_NUMBER_OF_BLOCKS)
    if number_of_blocks is not None and number_of_blocks < 1:
        errors[CONF_NUMBER_OF_BLOCKS] = "number_of_blocks_out_of_range"

    return errors


def _validate_offset_integer_fields(user_input: dict[str, Any]) -> dict[str, str]:
    """Validate optional integer fields on the offset step."""
    errors: dict[str, str] = {}

    start_minutes = user_input.get(f"{CONF_START}_{CONF_MINUTES}")
    if start_minutes is not None and not (-59 <= start_minutes <= 59):
        errors[f"{CONF_START}_{CONF_MINUTES}"] = "start_minutes_out_of_range"

    end_minutes = user_input.get(f"{CONF_END}_{CONF_MINUTES}")
    if end_minutes is not None and not (-59 <= end_minutes <= 59):
        errors[f"{CONF_END}_{CONF_MINUTES}"] = "end_minutes_out_of_range"

    return errors


def _process_offset_input(
    user_input: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Process offset input and build offset structure."""
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
