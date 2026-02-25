"""Energy management component init."""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_RELOAD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
    async_reload_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AREA,
    CONF_CALENDAR,
    CONF_END,
    CONF_ENTITY_CALENDAR,
    CONF_ENTITY_CHEAPEST_HOURS,
    CONF_ENTSOE_ENTITY,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_HOURS,
    CONF_INVERSED,
    CONF_LAST_HOUR,
    CONF_MINUTES,
    CONF_MTU,
    CONF_NAME,
    CONF_NORDPOOL_ENTITY,
    CONF_NORDPOOL_OFFICIAL_CONFIG_ENTRY,
    CONF_NUMBER_OF_HOURS,
    CONF_NUMBER_OF_SLOTS,
    CONF_OFFSET,
    CONF_PRICE_LIMIT,
    CONF_PRICE_MODIFICATIONS,
    CONF_RETENTION_DAYS,
    CONF_SEQUENTIAL,
    CONF_START,
    CONF_STARTING_TODAY,
    CONF_TRIGGER_HOUR,
    CONF_UNIQUE_ID,
    COORDINATOR,
    DOMAIN,
)
from .coordinator import EnergyManagementCoordinator
from .services import async_setup_services

if TYPE_CHECKING:
    pass

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR]

_LOGGER = logging.getLogger(__name__)

# TODO:
# - Solar energy forecast best hours
# - Cheapest hours multi-state sensor (low, high, normal) to avoid expensive and boost cheapest!

# YAML configuration schema for backward compatibility
CALENDAR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


async def async_setup(hass: core.HomeAssistant, config: ConfigType) -> bool:
    """Set up the Energy Management component from YAML (legacy support)."""
    # Initialize coordinator if not already present
    if DOMAIN not in hass.data:
        coordinator = EnergyManagementCoordinator(hass)
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
        coordinator = hass.data[DOMAIN][COORDINATOR]
        await coordinator.async_load_data()
        if conf.get(DOMAIN):
            await _async_process_config(hass, conf)

    # Services
    await async_setup_services(hass)
    hass.services.async_register(
        DOMAIN, SERVICE_RELOAD, reload_service_handler, schema=vol.Schema({})
    )

    # Process YAML config if present (legacy support)
    if DOMAIN in config:
        return await _async_process_config(hass, config)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AIO Energy Management from a config entry."""
    # Initialize coordinator if not already present
    if DOMAIN not in hass.data:
        coordinator = EnergyManagementCoordinator(hass)
        await coordinator.async_load_data()
        hass.data[DOMAIN] = {COORDINATOR: coordinator}
        # Services
        await async_setup_services(hass)

    # Determine which platform to set up based on entry type
    entry_type = entry.data.get("entry_type")

    if entry_type == CONF_ENTITY_CHEAPEST_HOURS:
        await hass.config_entries.async_forward_entry_setups(
            entry, [Platform.BINARY_SENSOR]
        )
    elif entry_type == CONF_ENTITY_CALENDAR:
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.CALENDAR])
    else:
        _LOGGER.error("Unknown entry type: %s", entry_type)
        return False

    # Register update listener to reload when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    entry_type = entry.data.get("entry_type")

    if entry_type == CONF_ENTITY_CHEAPEST_HOURS:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, [Platform.BINARY_SENSOR]
        )
    elif entry_type == CONF_ENTITY_CALENDAR:
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, [Platform.CALENDAR]
        )
    else:
        unload_ok = True

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    # Clear coordinator data for cheapest hours entities when config changes
    entry_type = entry.data.get("entry_type")
    if entry_type == CONF_ENTITY_CHEAPEST_HOURS:
        unique_id = entry.data.get(CONF_UNIQUE_ID)
        if unique_id and DOMAIN in hass.data:
            coordinator = hass.data[DOMAIN][COORDINATOR]
            await coordinator.async_clear_data(unique_id)
            _LOGGER.debug("Configuration modified and data cleared for %s", unique_id)

    await hass.config_entries.async_reload(entry.entry_id)


async def _async_process_config(hass: HomeAssistant, config: dict) -> bool:
    """Process YAML configuration (legacy support)."""
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
