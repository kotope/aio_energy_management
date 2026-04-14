"""Number platform for AIO Energy Management."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import (
    CONF_ENTITY_EXCESS_SOLAR,
    CONF_UNIQUE_ID,
    DOMAIN,
    YAML_EXCESS_SOLAR_INSTANCE_KEY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities from a config entry."""
    if entry.data.get("entry_type") != CONF_ENTITY_EXCESS_SOLAR:
        return

    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    number_entities = entry_data.get("excess_solar_number_entities", [])
    if number_entities:
        async_add_entities(number_entities)
        _LOGGER.debug(
            "Added %d excess solar priority number entities for entry '%s'",
            len(number_entities),
            entry.title,
        )


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

    if entry_type == CONF_ENTITY_EXCESS_SOLAR:
        storage_key = discovery_info.get(CONF_UNIQUE_ID, YAML_EXCESS_SOLAR_INSTANCE_KEY)
        entry_data = hass.data.get(DOMAIN, {}).get(storage_key, {})
        number_entities = entry_data.get("excess_solar_number_entities", [])
        if number_entities:
            async_add_entities(number_entities)
            _LOGGER.info(
                "Added %d excess solar priority number entities", len(number_entities)
            )
