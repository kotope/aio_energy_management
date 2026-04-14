"""Energy management component init."""

from __future__ import annotations

import contextlib
import logging
from typing import Any

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
    CONF_ENTITY_EXCESS_SOLAR,
    CONF_EXCESS_SOLAR,
    CONF_GRID_POWER_SENSOR,
    CONF_IS_ON_SCHEDULE,
    CONF_MINIMUM_OFF_TIME,
    CONF_MINIMUM_ON_TIME,
    CONF_NAME,
    CONF_POWER_DEVICES,
    CONF_PRIORITY,
    CONF_UNIQUE_ID,
    COORDINATOR,
    DOMAIN,
    EXCESS_SOLAR_ENABLED_SWITCHES,
    EXCESS_SOLAR_MANAGER,
    EXCESS_SOLAR_SWITCH,
    YAML_EXCESS_SOLAR_INSTANCE_KEY,
)
from .coordinator import EnergyManagementCoordinator
from .excess_solar import (
    ExcessSolarMasterSwitch,
    build_sensors_from_config,
    create_manager_from_config,
)
from .services import async_setup_services

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
    Platform.NUMBER,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)

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
        vol.Optional(CONF_MINIMUM_ON_TIME, default=0): cv.positive_int,
        vol.Optional(CONF_MINIMUM_OFF_TIME): cv.positive_int,
    },
    extra=vol.REMOVE_EXTRA,
)

EXCESS_SOLAR_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_GRID_POWER_SENSOR): cv.entity_id,
        vol.Required(CONF_POWER_DEVICES): vol.All(
            cv.ensure_list, [POWER_DEVICE_SCHEMA]
        ),
        vol.Optional(CONF_BUFFER, default=0): cv.positive_int,
    },
    extra=vol.REMOVE_EXTRA,
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
    elif entry_type == CONF_ENTITY_EXCESS_SOLAR:
        await _async_setup_excess_solar_entry(hass, entry)
    else:
        _LOGGER.error("Unknown entry type: %s", entry_type)
        return False

    # Register update listener to reload when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def _async_setup_excess_solar_from_entry_data(
    hass: HomeAssistant,
    entry_data: dict[str, Any],
    storage_key: str,
    *,
    master_switch_unique_id: str,
) -> None:
    """Prepare excess solar manager and entities under hass.data[DOMAIN][storage_key]."""
    config = dict(entry_data)
    manager = create_manager_from_config(hass, config, [])
    sensors, number_entities, enabled_switches = build_sensors_from_config(
        hass, config, manager
    )
    manager.sensors = sensors
    manager.sort_sensors()

    master_switch = ExcessSolarMasterSwitch(
        manager=manager,
        unique_id=master_switch_unique_id,
        name=config.get(CONF_NAME, "Excess Solar"),
    )

    hass.data[DOMAIN][storage_key] = {
        EXCESS_SOLAR_MANAGER: manager,
        "excess_solar_sensors": sensors,
        "excess_solar_number_entities": number_entities,
        EXCESS_SOLAR_ENABLED_SWITCHES: enabled_switches,
        EXCESS_SOLAR_SWITCH: master_switch,
    }


async def _async_setup_excess_solar_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Set up excess solar from a config entry."""
    await _async_setup_excess_solar_from_entry_data(
        hass,
        dict(entry.data),
        entry.entry_id,
        master_switch_unique_id=f"excess_solar_master_switch_{entry.entry_id}",
    )

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SWITCH]
    )
    manager = hass.data[DOMAIN][entry.entry_id][EXCESS_SOLAR_MANAGER]
    await manager.async_start()
    _LOGGER.info(
        "Excess solar entry '%s' started with %d device(s)",
        entry.data.get(CONF_NAME),
        len(hass.data[DOMAIN][entry.entry_id]["excess_solar_sensors"]),
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
    elif entry_type == CONF_ENTITY_EXCESS_SOLAR:
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
            excess_entry = dict(EXCESS_SOLAR_SCHEMA(excess_solar_config))
            excess_entry["entry_type"] = CONF_ENTITY_EXCESS_SOLAR
            excess_entry.setdefault(CONF_NAME, "Excess Solar")
            excess_entry[CONF_UNIQUE_ID] = YAML_EXCESS_SOLAR_INSTANCE_KEY

            await _async_setup_excess_solar_from_entry_data(
                hass,
                excess_entry,
                YAML_EXCESS_SOLAR_INSTANCE_KEY,
                master_switch_unique_id="excess_solar_master_switch",
            )

            for platform in (
                Platform.BINARY_SENSOR,
                Platform.NUMBER,
                Platform.SWITCH,
            ):
                hass.async_create_task(
                    async_load_platform(hass, platform, DOMAIN, excess_entry, config)
                )

            manager = hass.data[DOMAIN][YAML_EXCESS_SOLAR_INSTANCE_KEY][
                EXCESS_SOLAR_MANAGER
            ]
            await manager.async_start()
            bucket = hass.data[DOMAIN][YAML_EXCESS_SOLAR_INSTANCE_KEY]
            _LOGGER.info(
                "Excess solar manager started with %d sensor(s), %d number entities, "
                "%d enabled switches, and master switch",
                len(bucket["excess_solar_sensors"]),
                len(bucket["excess_solar_number_entities"]),
                len(bucket[EXCESS_SOLAR_ENABLED_SWITCHES]),
            )
        except vol.Invalid as err:
            _LOGGER.error(
                "Failed to set up excess solar (invalid configuration): %s", err
            )
        except Exception:
            _LOGGER.exception("Failed to set up excess solar")

    return True


async def _async_stop_excess_solar(hass: HomeAssistant) -> None:
    """Stop and remove the excess solar manager if running."""
    if DOMAIN not in hass.data:
        return

    domain_data = hass.data[DOMAIN]
    bucket = domain_data.pop(YAML_EXCESS_SOLAR_INSTANCE_KEY, None)
    if bucket:
        manager = bucket.get(EXCESS_SOLAR_MANAGER)
        if manager is not None:
            await manager.async_stop()

    # Legacy layout before per-instance buckets
    manager = domain_data.pop(EXCESS_SOLAR_MANAGER, None)
    if manager is not None:
        await manager.async_stop()
    domain_data.pop("excess_solar_sensors", None)
    domain_data.pop("excess_solar_number_entities", None)
    domain_data.pop(EXCESS_SOLAR_ENABLED_SWITCHES, None)
    domain_data.pop(EXCESS_SOLAR_SWITCH, None)
