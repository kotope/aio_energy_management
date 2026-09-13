# custom_components/aio_energy_management/schemas.py

# 1. Selectors & Helpers for schemas (_opt, _req)
# 2. Basic / Advanced / Offset Schema's (_get_cheapest_hours_basic_schema, etc.)
# 3. Provider Schema's (_get_nordpool_schema, etc.)

"""Cheapest hours UI schema definitions."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import selector

from custom_components.aio_energy_management.const import (
    CONF_AREA,
    CONF_CALENDAR,
    CONF_DATA_PROVIDER_TYPE,
    CONF_END,
    CONF_END_HOURS_ENTITY,
    CONF_END_MINUTES_ENTITY,
    CONF_ENTSOE_ENTITY,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_FLEXIBLE_PRICE_LIMIT,
    CONF_FLEXIBLE_PRICE_LIMIT_ENTITY,
    CONF_HOURS,
    CONF_INVERSED,
    CONF_LAST_HOUR,
    CONF_MAX_NUMBER_OF_SLOTS,
    CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
    CONF_MIN_SEQ_SLOTS,
    CONF_MINUTES,
    CONF_MTU,
    CONF_NORDPOOL_ENTITY,
    CONF_NORDPOOL_OFFICIAL_CONFIG_ENTRY,
    CONF_NUMBER_OF_BLOCKS,
    CONF_NUMBER_OF_SLOTS,
    CONF_NUMBER_OF_SLOTS_ENTITY,
    CONF_PRICE_LIMIT,
    CONF_PRICE_LIMIT_ENTITY,
    CONF_PRICE_MODIFICATIONS,
    CONF_RETENTION_DAYS,
    CONF_SEQUENTIAL,
    CONF_START,
    CONF_START_HOURS_ENTITY,
    CONF_START_MINUTES_ENTITY,
    CONF_STROMLIGNING_ENTITY,
    CONF_STROMLIGNING_TOMORROW_ENTITY,
    CONF_TRIGGER_HOUR,
    CONF_TRIGGER_HOUR_ENTITY,
    DATA_PROVIDER_ENTSOE,
    DATA_PROVIDER_NORDPOOL,
    DATA_PROVIDER_NORDPOOL_OFFICIAL,
    DATA_PROVIDER_STROMLIGNING,
)
from .helpers import _get_val, _mtu_default

# Reusable selectors
SEL_HOUR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=23, mode=selector.NumberSelectorMode.BOX, step=1
    )
)
SEL_FLOAT = selector.NumberSelector(
    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step="any")
)
SEL_INT = selector.NumberSelector(
    selector.NumberSelectorConfig(min=1, mode=selector.NumberSelectorMode.BOX, step=1)
)
SEL_ENTITY = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
)
SEL_INT_0 = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, mode=selector.NumberSelectorMode.BOX, step=1)
)
SEL_INT_ANY = selector.NumberSelector(
    selector.NumberSelectorConfig(mode=selector.NumberSelectorMode.BOX, step=1)
)
SEL_SENSOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
SEL_BINARY_SENSOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="binary_sensor")
)


def _req(key: str, data: dict, default: Any = None) -> vol.Required:
    """Create a `vol.Required` key with a `default` or `suggested_value`."""
    val = data.get(key)
    if default is not None:
        return vol.Required(key, default=val if val is not None else default)
    desc = {"suggested_value": val} if val is not None else {}
    return vol.Required(key, description=desc)


def _opt(
    key: str, data: dict, flex_key: str | None = None, default: Any = None
) -> vol.Optional:
    """Create a `vol.Optional` key with the suggested value in a single line."""
    val = _get_val(data, key, flex_key, default)
    if key == CONF_MTU and val is not None:
        val = str(val)
    desc = {"suggested_value": val} if val is not None else {}
    return vol.Optional(key, description=desc)


def _mtu_selector() -> selector.SelectSelector:
    """Return the MTU dropdown selector."""
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=["15", "60"],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _get_data_provider_type_schema(default: str | None = None) -> vol.Schema:
    """Get data provider type selection schema."""
    req_key = (
        vol.Required(CONF_DATA_PROVIDER_TYPE, default=default)
        if default
        else vol.Required(CONF_DATA_PROVIDER_TYPE)
    )
    return vol.Schema(
        {
            req_key: vol.In(
                {
                    DATA_PROVIDER_NORDPOOL: "Nord Pool",
                    DATA_PROVIDER_NORDPOOL_OFFICIAL: "Nord Pool official",
                    DATA_PROVIDER_ENTSOE: "Entso-E",
                    DATA_PROVIDER_STROMLIGNING: "Strømligning",
                }
            ),
        }
    )


def _get_nordpool_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get Nord Pool entity selection schema."""
    data = user_input or {}
    return vol.Schema(
        {
            _req(CONF_NORDPOOL_ENTITY, data): SEL_SENSOR,
            _opt(CONF_MTU, data, default=_mtu_default(user_input)): _mtu_selector(),
        }
    )


def _get_nordpool_official_schema(
    hass: HomeAssistant,
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Get Nord Pool official config entry ID schema."""
    data = user_input or {}
    existing_entries = hass.config_entries.async_entries("nordpool")
    options = [{"value": e.entry_id, "label": e.title} for e in existing_entries]

    return vol.Schema(
        {
            vol.Required(CONF_NORDPOOL_OFFICIAL_CONFIG_ENTRY): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            _opt(CONF_AREA, data): cv.string,
            _opt(CONF_MTU, data, default=_mtu_default(user_input)): _mtu_selector(),
        }
    )


def _get_entsoe_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get Entso-E entity selection schema."""
    data = user_input or {}
    return vol.Schema(
        {
            _req(CONF_ENTSOE_ENTITY, data): SEL_SENSOR,
            _opt(CONF_MTU, data, default=_mtu_default(user_input)): _mtu_selector(),
        }
    )


def _get_stromligning_schema(user_input: dict[str, Any] | None = None) -> vol.Schema:
    """Get Strømligning entity selection schema."""
    data = user_input or {}
    return vol.Schema(
        {
            _req(CONF_STROMLIGNING_ENTITY, data): SEL_SENSOR,
            _req(CONF_STROMLIGNING_TOMORROW_ENTITY, data): SEL_BINARY_SENSOR,
            _opt(CONF_MTU, data, default=_mtu_default(user_input)): _mtu_selector(),
        }
    )


def _get_cheapest_hours_basic_schema(
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Get basic cheapest hours configuration schema."""
    data = user_input or {}
    has_dynamic = bool(data.get(CONF_NUMBER_OF_SLOTS_ENTITY))

    schema_dict = {
        _req(CONF_NAME, data, default="Cheapest Hours"): cv.string,
        _opt(CONF_NUMBER_OF_SLOTS, data, default=0): SEL_INT_0,
        _req(CONF_FIRST_HOUR, data, default=0): SEL_HOUR,
        _req(CONF_LAST_HOUR, data, default=23): SEL_HOUR,
        _req(CONF_SEQUENTIAL, data, default=False): cv.boolean,
        _req(CONF_CALENDAR, data, default=True): cv.boolean,
        _req(CONF_INVERSED, data, default=False): cv.boolean,
        vol.Required("dynamic_section"): section(
            vol.Schema(
                {
                    _opt(CONF_NUMBER_OF_SLOTS_ENTITY, data): SEL_ENTITY,
                }
            ),
            {"collapsed": not has_dynamic},
        ),
    }

    return vol.Schema(schema_dict)


def _get_cheapest_hours_advanced_schema(
    user_input: dict[str, Any] | None = None,
    sequential: bool = False,
) -> vol.Schema:
    """Get advanced cheapest hours configuration schema."""
    data = user_input or {}

    schema_dict = {
        _opt(CONF_FAILSAFE_STARTING_HOUR, data): SEL_HOUR,
        _opt(CONF_TRIGGER_HOUR, data): SEL_HOUR,
        _opt(CONF_PRICE_LIMIT, data): SEL_FLOAT,
    }

    if not sequential:
        schema_dict.update(
            {
                _opt(
                    CONF_FLEXIBLE_PRICE_LIMIT, data, flex_key=CONF_PRICE_LIMIT
                ): SEL_FLOAT,
                _opt(
                    CONF_MAX_NUMBER_OF_SLOTS, data, flex_key=CONF_MAX_NUMBER_OF_SLOTS
                ): SEL_INT,
                _opt(CONF_MIN_SEQ_SLOTS, data): SEL_INT,
                _opt(CONF_NUMBER_OF_BLOCKS, data): SEL_INT,
            }
        )

    schema_dict.update(
        {
            _opt(CONF_RETENTION_DAYS, data, default=1): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=365, mode=selector.NumberSelectorMode.BOX, step=1
                )
            ),
            _opt(CONF_PRICE_MODIFICATIONS, data): selector.TemplateSelector(),
        }
    )

    dynamic_dict = {
        _opt(CONF_TRIGGER_HOUR_ENTITY, data): SEL_ENTITY,
        _opt(CONF_PRICE_LIMIT_ENTITY, data): SEL_ENTITY,
    }

    if not sequential:
        dynamic_dict.update(
            {
                _opt(
                    CONF_FLEXIBLE_PRICE_LIMIT_ENTITY,
                    data,
                    flex_key=CONF_PRICE_LIMIT_ENTITY,
                ): SEL_ENTITY,
                _opt(
                    CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
                    data,
                    flex_key=CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
                ): SEL_ENTITY,
            }
        )

    has_dynamic = any(
        _get_val(data, key, flex)
        for key, flex in [
            (CONF_TRIGGER_HOUR_ENTITY, None),
            (CONF_PRICE_LIMIT_ENTITY, None),
            (CONF_MAX_NUMBER_OF_SLOTS_ENTITY, CONF_MAX_NUMBER_OF_SLOTS_ENTITY),
            (CONF_FLEXIBLE_PRICE_LIMIT_ENTITY, CONF_PRICE_LIMIT_ENTITY),
        ]
    )

    schema_dict[vol.Required("dynamic_section")] = section(
        vol.Schema(dynamic_dict),
        {"collapsed": not has_dynamic},
    )

    return vol.Schema(schema_dict)


def _get_offset_schema(offset_data: dict[str, Any]) -> vol.Schema:
    """Get offset configuration schema."""
    start = offset_data.get(CONF_START, {})
    end = offset_data.get(CONF_END, {})

    data = {
        f"{CONF_START}_{CONF_HOURS}": start.get(CONF_HOURS),
        f"{CONF_START}_{CONF_MINUTES}": start.get(CONF_MINUTES),
        f"{CONF_END}_{CONF_HOURS}": end.get(CONF_HOURS),
        f"{CONF_END}_{CONF_MINUTES}": end.get(CONF_MINUTES),
        **offset_data,
    }

    schema_dict = {
        _opt(f"{CONF_START}_{CONF_HOURS}", data): SEL_INT_ANY,
        _opt(f"{CONF_START}_{CONF_MINUTES}", data): SEL_INT_ANY,
        _opt(f"{CONF_END}_{CONF_HOURS}", data): SEL_INT_ANY,
        _opt(f"{CONF_END}_{CONF_MINUTES}", data): SEL_INT_ANY,
    }

    dynamic_dict = {
        _opt(CONF_START_HOURS_ENTITY, data): SEL_ENTITY,
        _opt(CONF_START_MINUTES_ENTITY, data): SEL_ENTITY,
        _opt(CONF_END_HOURS_ENTITY, data): SEL_ENTITY,
        _opt(CONF_END_MINUTES_ENTITY, data): SEL_ENTITY,
    }

    has_dynamic = any(
        data.get(key)
        for key in (
            CONF_START_HOURS_ENTITY,
            CONF_START_MINUTES_ENTITY,
            CONF_END_HOURS_ENTITY,
            CONF_END_MINUTES_ENTITY,
        )
    )

    schema_dict[vol.Required("dynamic_section")] = section(
        vol.Schema(dynamic_dict),
        {"collapsed": not has_dynamic},
    )

    return vol.Schema(schema_dict)
