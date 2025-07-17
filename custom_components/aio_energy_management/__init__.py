"""Energy management component init."""

import contextlib
import logging

import voluptuous as vol

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
    async_reload_integration_platforms,
)

from .const import CONF_ENTITY_CALENDAR, CONF_ENTITY_CHEAPEST_HOURS, COORDINATOR, DOMAIN
from .coordinator import EnergyManagementCoordinator
from .services import async_setup_services

PLATFORMS = ["binary_sensor", "calendar"]

_LOGGER = logging.getLogger(__name__)

# TODO:
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

    async def reload_service_handler(service: ServiceCall) -> None:
        """Remove all user-defined groups and load new ones from config."""
        conf = None
        with contextlib.suppress(HomeAssistantError):
            conf = await async_integration_yaml_config(hass, DOMAIN)
        if conf is None:
            return
        await async_reload_integration_platforms(hass, DOMAIN, PLATFORMS)
        await coordinator.async_load_data()
        await _async_process_config(hass, conf)

    # Services
    await async_setup_services(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    return await _async_process_config(hass, config)


async def _async_process_config(hass: HomeAssistant, config: dict) -> bool:
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
