"""Binary sensor(s) for aio energy management."""

import logging

import voluptuous as vol
from voluptuous import ALLOW_EXTRA, Invalid, Schema

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    CONF_ENTITY_CHEAPEST_HOURS,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_INVERSED,
    CONF_LAST_HOUR,
    CONF_NAME,
    CONF_NORDPOOL_ENTITY,
    CONF_NUMBER_OF_HOURS,
    CONF_SEQUENTIAL,
    CONF_STARTING_TODAY,
    CONF_UNIQUE_ID,
    COORDINATOR,
    DOMAIN,
)
from .nordpool_binary_sensor import NordPoolCheapestHoursBinarySensor

_LOGGER = logging.getLogger(__name__)

CHEAPEST_HOURS_PLATFORM_SCHEMA = Schema(
    {
        vol.Required(CONF_NORDPOOL_ENTITY): cv.entity_id,
        vol.Required(CONF_UNIQUE_ID): vol.All(vol.Coerce(str)),
        vol.Required(CONF_NAME): vol.All(vol.Coerce(str)),
        vol.Required(CONF_STARTING_TODAY): bool,
        vol.Required(CONF_FIRST_HOUR): int,
        vol.Required(CONF_LAST_HOUR): int,
        vol.Required(CONF_SEQUENTIAL): bool,
        vol.Required(CONF_NUMBER_OF_HOURS): vol.Any(int, cv.entity_id),
        vol.Optional(CONF_FAILSAFE_STARTING_HOUR): int,
        vol.Optional(CONF_INVERSED): bool,
    },
    extra=ALLOW_EXTRA,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Sensor containing amount of cheapest hours marked in the configuration."""
    entry_type = discovery_info["entry_type"]

    entities = []
    # Configure cheapest hours binary sensor
    if entry_type == CONF_ENTITY_CHEAPEST_HOURS:
        try:
            CHEAPEST_HOURS_PLATFORM_SCHEMA(discovery_info)
            entities.append(_create_nordpool_entity(hass, discovery_info))
        except Invalid as e:
            _LOGGER.error(
                "Configuration validation error for nord pool cheapest hours sensor: %s",
                e,
            )

    async_add_entities(entities)


def _create_nordpool_entity(
    hass: HomeAssistant, discovery_info: DiscoveryInfoType | None = None
) -> NordPoolCheapestHoursBinarySensor:
    nordpool_entity = discovery_info[CONF_NORDPOOL_ENTITY]
    unique_id = discovery_info[CONF_UNIQUE_ID]
    name = discovery_info[CONF_NAME]
    first_hour = discovery_info[CONF_FIRST_HOUR]
    last_hour = discovery_info[CONF_LAST_HOUR]
    starting_today = discovery_info[CONF_STARTING_TODAY]
    sequential = discovery_info[CONF_SEQUENTIAL]
    number_of_hours = discovery_info[CONF_NUMBER_OF_HOURS]
    failsafe_starting_hour = discovery_info.get(CONF_FAILSAFE_STARTING_HOUR)
    inversed = discovery_info.get(CONF_INVERSED) or False

    return NordPoolCheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity=nordpool_entity,
        unique_id=unique_id,
        name=name,
        first_hour=first_hour,
        last_hour=last_hour,
        starting_today=starting_today,
        number_of_hours=number_of_hours,
        coordinator=hass.data[DOMAIN][COORDINATOR],
        sequential=sequential,
        failsafe_starting_hour=failsafe_starting_hour,
        inversed=inversed,
    )
