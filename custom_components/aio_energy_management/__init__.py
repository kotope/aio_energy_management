"""Energy management component init."""

import logging

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import CONF_ENTITY_CALENDAR, CONF_ENTITY_CHEAPEST_HOURS, COORDINATOR, DOMAIN
from .coordinator import EnergyManagementCoordinator

PLATFORMS = ["binary_sensor", "calendar"]

_LOGGER = logging.getLogger(__name__)

# TODO:
# - Cheapeast hours trigger time
# - Solar energy forecast best hours
# - Cheapest hours multi-state sensor (low, high, normal) to avoid expensive and boost cheapest!


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the Energy Management component."""
    # Set level to debug for dev time (debug purposes only)
    # _LOGGER.setLevel(logging.DEBUG)

    coordinator = EnergyManagementCoordinator(hass)

    # Clear store (debug purposes only)
    # await coordinator.async_clear_store()

    await coordinator.async_load_data()

    hass.data[DOMAIN] = {COORDINATOR: coordinator}

    # Cheapest hours
    if cheapest_hours_entries := config[DOMAIN].get(CONF_ENTITY_CHEAPEST_HOURS):
        for entry in cheapest_hours_entries:
            entry["entry_type"] = CONF_ENTITY_CHEAPEST_HOURS
            hass.async_create_task(
                async_load_platform(hass, Platform.BINARY_SENSOR, DOMAIN, entry, config)
            )

    # Calendar
    if calendar_entry := config[DOMAIN].get(CONF_ENTITY_CALENDAR):
        calendar_entry["entry_type"] = CONF_ENTITY_CALENDAR
        hass.async_create_task(
            async_load_platform(hass, Platform.CALENDAR, DOMAIN, calendar_entry, config)
        )

    return True
