"""Binary sensor(s) for aio energy management."""

import logging

import voluptuous as vol
from voluptuous import ALLOW_EXTRA, Invalid, Schema

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .cheapest_hours_binary_sensor import CheapestHoursBinarySensor
from .const import (
    CONF_CALENDAR,
    CONF_ENTITY_CHEAPEST_HOURS,
    CONF_ENTSOE_ENTITY,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_INVERSED,
    CONF_LAST_HOUR,
    CONF_MAX_PRICE,
    CONF_NAME,
    CONF_NORDPOOL_ENTITY,
    CONF_NUMBER_OF_HOURS,
    CONF_PRICE_LIMIT,
    CONF_SEQUENTIAL,
    CONF_STARTING_TODAY,
    CONF_TRIGGER_HOUR,
    CONF_TRIGGER_TIME,
    CONF_UNIQUE_ID,
    COORDINATOR,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

CHEAPEST_HOURS_PLATFORM_SCHEMA = Schema(
    {
        vol.Optional(CONF_NORDPOOL_ENTITY): cv.entity_id,
        vol.Optional(CONF_ENTSOE_ENTITY): cv.entity_id,
        vol.Required(CONF_UNIQUE_ID): vol.All(vol.Coerce(str)),
        vol.Required(CONF_NAME): vol.All(vol.Coerce(str)),
        vol.Required(CONF_STARTING_TODAY): bool,
        vol.Required(CONF_FIRST_HOUR): int,
        vol.Required(CONF_LAST_HOUR): int,
        vol.Required(CONF_SEQUENTIAL): bool,
        vol.Required(CONF_NUMBER_OF_HOURS): vol.Any(int, cv.entity_id),
        vol.Optional(CONF_FAILSAFE_STARTING_HOUR): int,
        vol.Optional(CONF_INVERSED): bool,
        vol.Optional(CONF_TRIGGER_TIME): vol.All(vol.Coerce(str)),
        vol.Optional(CONF_TRIGGER_HOUR): vol.Any(int, cv.entity_id),
        vol.Optional(CONF_MAX_PRICE): vol.Any(float, cv.entity_id),
        vol.Optional(CONF_PRICE_LIMIT): vol.Any(float, cv.entity_id),
        vol.Optional(CONF_CALENDAR): bool,
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
            entities.append(_create_cheapest_hours_entity(hass, discovery_info))
        except Invalid as e:
            _LOGGER.error(
                "Configuration validation error for nord pool cheapest hours sensor: %s",
                e,
            )

    async_add_entities(entities)


def _create_cheapest_hours_entity(
    hass: HomeAssistant, discovery_info: DiscoveryInfoType | None = None
) -> CheapestHoursBinarySensor:
    nordpool_entity = discovery_info.get(CONF_NORDPOOL_ENTITY)
    entsoe_entity = discovery_info.get(CONF_ENTSOE_ENTITY)
    unique_id = discovery_info[CONF_UNIQUE_ID]
    name = discovery_info[CONF_NAME]
    first_hour = discovery_info[CONF_FIRST_HOUR]
    last_hour = discovery_info[CONF_LAST_HOUR]
    starting_today = discovery_info[CONF_STARTING_TODAY]
    sequential = discovery_info[CONF_SEQUENTIAL]
    number_of_hours = discovery_info[CONF_NUMBER_OF_HOURS]
    failsafe_starting_hour = discovery_info.get(CONF_FAILSAFE_STARTING_HOUR)
    inversed = discovery_info.get(CONF_INVERSED) or False
    trigger_time = discovery_info.get(CONF_TRIGGER_TIME)
    price_limit = discovery_info.get(
        CONF_MAX_PRICE
    )  # DEPRECATED: replaced by price_limit. Keep here for few releases.
    trigger_hour = discovery_info.get(CONF_TRIGGER_HOUR)
    calendar = discovery_info.get(CONF_CALENDAR)
    if calendar is None:
        calendar = True
    if pl := discovery_info.get(CONF_PRICE_LIMIT):
        price_limit = pl

    return CheapestHoursBinarySensor(
        hass=hass,
        entsoe_entity=entsoe_entity,
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
        trigger_time=trigger_time,
        trigger_hour=trigger_hour,
        price_limit=price_limit,
        calendar=calendar,
    )
