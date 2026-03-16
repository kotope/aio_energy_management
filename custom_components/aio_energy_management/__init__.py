"""Energy management component init."""

from __future__ import annotations

import contextlib
import logging

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
    CONF_BUFFER,
    CONF_CONSUMPTION,
    CONF_ENTITY_CALENDAR,
    CONF_ENTITY_CHEAPEST_HOURS,
    CONF_EXCESS_SOLAR,
    CONF_GRID_POWER_SENSOR,
    CONF_IS_ON_SCHEDULE,
    CONF_MINIMUM_PERIOD,
    CONF_NAME,
    CONF_POWER_DEVICES,
    CONF_PRIORITY,
    CONF_TURN_ON_DELAY,
    CONF_UNIQUE_ID,
    COORDINATOR,
    DOMAIN,
    EXCESS_SOLAR_ENABLED_SWITCHES,
    EXCESS_SOLAR_MANAGER,
    EXCESS_SOLAR_SWITCH,
)
from .coordinator import EnergyManagementCoordinator
from .excess_solar import (
    ExcessSolarMasterSwitch,
    build_sensors_from_config,
    create_manager_from_config,
)
from .excess_solar.config_flow import ENTRY_TYPE_EXCESS_SOLAR
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.NUMBER,
    Platform.SWITCH,
]

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

# Excess solar YAML schema
POWER_DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_CONSUMPTION): vol.Any(vol.Coerce(int), cv.entity_id),
        vol.Optional(CONF_PRIORITY, default=100): cv.positive_int,
        vol.Optional(CONF_IS_ON_SCHEDULE): cv.entity_id,
        vol.Optional(CONF_MINIMUM_PERIOD, default=0): cv.positive_int,
        vol.Optional(CONF_TURN_ON_DELAY): cv.positive_int,
    }
)

EXCESS_SOLAR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GRID_POWER_SENSOR): cv.entity_id,
        vol.Required(CONF_POWER_DEVICES): vol.All(
            cv.ensure_list, [POWER_DEVICE_SCHEMA]
        ),
        vol.Optional(CONF_BUFFER, default=0): cv.positive_int,
        vol.Optional(CONF_TURN_ON_DELAY, default=60): cv.positive_int,
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
        # Stop existing excess solar manager if any before reload
        await _async_stop_excess_solar(hass)
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
    elif entry_type == ENTRY_TYPE_EXCESS_SOLAR:
        await _async_setup_excess_solar_entry(hass, entry)
    else:
        _LOGGER.error("Unknown entry type: %s", entry_type)
        return False

    # Register update listener to reload when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def _async_setup_excess_solar_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Set up excess solar from a config entry."""
    config = dict(entry.data)
    manager = create_manager_from_config(hass, config, [])
    sensors, number_entities, enabled_switches = build_sensors_from_config(
        hass, config, manager
    )
    manager.sensors = sensors
    manager.sort_sensors()

    master_switch = ExcessSolarMasterSwitch(
        manager=manager,
        unique_id=f"excess_solar_master_switch_{entry.entry_id}",
        name=entry.data.get(CONF_NAME, "Excess Solar"),
    )

    # Store per-entry data to avoid conflicts between multiple excess solar entries
    hass.data[DOMAIN][entry.entry_id] = {
        EXCESS_SOLAR_MANAGER: manager,
        "excess_solar_sensors": sensors,
        "excess_solar_number_entities": number_entities,
        EXCESS_SOLAR_ENABLED_SWITCHES: enabled_switches,
        EXCESS_SOLAR_SWITCH: master_switch,
    }

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SWITCH]
    )
    await manager.async_start()
    _LOGGER.info(
        "Excess solar entry '%s' started with %d device(s)",
        entry.data.get(CONF_NAME),
        len(sensors),
    )


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
    elif entry_type == ENTRY_TYPE_EXCESS_SOLAR:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        manager = entry_data.get(EXCESS_SOLAR_MANAGER)
        if manager is not None:
            await manager.async_stop()
        unload_ok = await hass.config_entries.async_unload_platforms(
            entry, [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SWITCH]
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

    # Excess solar
    if excess_solar_config := config[DOMAIN].get(CONF_EXCESS_SOLAR):
        try:
            validated = EXCESS_SOLAR_SCHEMA(excess_solar_config)
            # Create manager first (without sensors)
            manager = create_manager_from_config(hass, validated, [])
            # Build sensors, number entities, and enabled switches with manager reference
            sensors, number_entities, enabled_switches = build_sensors_from_config(
                hass, validated, manager
            )
            # Update manager with sensors
            manager.sensors = sensors
            manager.sort_sensors()
            # Master switch
            master_switch = ExcessSolarMasterSwitch(
                manager=manager,
                unique_id="excess_solar_master_switch",
                name="Excess Solar",
            )
            hass.data[DOMAIN][EXCESS_SOLAR_MANAGER] = manager
            hass.data[DOMAIN]["excess_solar_sensors"] = sensors
            hass.data[DOMAIN]["excess_solar_number_entities"] = number_entities
            hass.data[DOMAIN][EXCESS_SOLAR_ENABLED_SWITCHES] = enabled_switches
            hass.data[DOMAIN][EXCESS_SOLAR_SWITCH] = master_switch
            # Load binary sensor platform
            discovery = {"entry_type": CONF_EXCESS_SOLAR}
            hass.async_create_task(
                async_load_platform(
                    hass, Platform.BINARY_SENSOR, DOMAIN, discovery, config
                )
            )
            # Load number platform
            hass.async_create_task(
                async_load_platform(hass, Platform.NUMBER, DOMAIN, discovery, config)
            )
            # Load switch platform
            hass.async_create_task(
                async_load_platform(hass, Platform.SWITCH, DOMAIN, discovery, config)
            )
            await manager.async_start()
            _LOGGER.info(
                "Excess solar manager started with %d sensor(s), %d number entities, "
                "%d enabled switches, and master switch",
                len(sensors),
                len(number_entities),
                len(enabled_switches),
            )
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to set up excess solar: %s", e)

    return True


async def _async_stop_excess_solar(hass: HomeAssistant) -> None:
    """Stop and remove the excess solar manager if running."""
    if DOMAIN in hass.data:
        manager = hass.data[DOMAIN].pop(EXCESS_SOLAR_MANAGER, None)
        if manager is not None:
            await manager.async_stop()
