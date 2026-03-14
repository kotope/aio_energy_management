"""Excess Solar switch platform setup."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_EXCESS_SOLAR,
    DOMAIN,
    EXCESS_SOLAR_ENABLED_SWITCHES,
    EXCESS_SOLAR_SWITCH,
)
from .excess_solar import ExcessSolarDeviceEnabledSwitch, ExcessSolarMasterSwitch
from .excess_solar.config_flow import ENTRY_TYPE_EXCESS_SOLAR

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up excess solar switches from a config entry."""
    if entry.data.get("entry_type") != ENTRY_TYPE_EXCESS_SOLAR:
        return

    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})

    switch: ExcessSolarMasterSwitch | None = entry_data.get(EXCESS_SOLAR_SWITCH)
    if switch is None:
        _LOGGER.warning(
            "Excess solar master switch not found in hass.data for entry '%s'",
            entry.title,
        )
        return

    enabled_switches: list[ExcessSolarDeviceEnabledSwitch] = entry_data.get(
        EXCESS_SOLAR_ENABLED_SWITCHES, []
    )

    async_add_entities([switch, *enabled_switches])


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up excess solar switches from discovery (YAML legacy path)."""
    if discovery_info is None:
        return
    if discovery_info.get("entry_type") != CONF_EXCESS_SOLAR:
        return

    domain_data = hass.data.get(DOMAIN, {})

    switch: ExcessSolarMasterSwitch | None = domain_data.get(EXCESS_SOLAR_SWITCH)
    if switch is None:
        _LOGGER.warning(
            "Excess solar switch platform loaded but no master switch found in hass.data"
        )
        return

    enabled_switches: list[ExcessSolarDeviceEnabledSwitch] = domain_data.get(
        EXCESS_SOLAR_ENABLED_SWITCHES, []
    )

    async_add_entities([switch, *enabled_switches])
