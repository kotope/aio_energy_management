"""Excess Solar Master Switch setup."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_EXCESS_SOLAR, DOMAIN, EXCESS_SOLAR_SWITCH
from .excess_solar import ExcessSolarMasterSwitch

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up excess solar switch from discovery (YAML legacy path)."""
    if discovery_info is None:
        return
    if discovery_info.get("entry_type") != CONF_EXCESS_SOLAR:
        return

    switch: ExcessSolarMasterSwitch | None = (
        hass.data.get(DOMAIN, {}).get(EXCESS_SOLAR_SWITCH)
    )
    if switch is None:
        _LOGGER.warning(
            "Excess solar switch platform loaded but no switch found in hass.data"
        )
        return

    async_add_entities([switch])
