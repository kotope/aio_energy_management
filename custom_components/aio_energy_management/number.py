"""Number platform for AIO Energy Management."""

from __future__ import annotations

import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import DOMAIN, EXCESS_SOLAR_MANAGER

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up number entities from discovery info."""
    if discovery_info is None:
        return

    entry_type = discovery_info.get("entry_type")

    if entry_type == "excess_solar":
        if DOMAIN in hass.data and "excess_solar_number_entities" in hass.data[DOMAIN]:
            number_entities = hass.data[DOMAIN]["excess_solar_number_entities"]
            async_add_entities(number_entities)
            _LOGGER.info("Added %d excess solar priority number entities", len(number_entities))
