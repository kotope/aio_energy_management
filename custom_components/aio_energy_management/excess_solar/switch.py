"""Excess Solar switch entities.

Provides two switch types:
- ``ExcessSolarMasterSwitch``: one per excess-solar entry, enables/disables the
  entire manager.
- ``ExcessSolarDeviceEnabledSwitch``: one per configured power device, allows
  individual devices to be included or excluded from solar management.

Both switches use ``RestoreEntity`` so their state survives HA restarts.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .manager import ExcessSolarManager

_LOGGER = logging.getLogger(__name__)


class ExcessSolarMasterSwitch(RestoreEntity, SwitchEntity):
    """Master on/off switch for the Excess Solar manager.

    Turning this switch **off** immediately deactivates all managed binary
    sensors and prevents the manager from taking any further actions until
    the switch is turned **on** again.

    State is automatically restored from Home Assistant's last known state
    across reboots.
    """

    def __init__(self, manager: ExcessSolarManager, unique_id: str, name: str) -> None:
        """Initialise the master switch."""
        self._manager = manager
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = "mdi:solar-power"
        self._attr_is_on = True  # enabled by default

    async def async_added_to_hass(self) -> None:
        """Restore state from the last known state on startup."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            is_on = last_state.state == "on"
            if is_on:
                self._manager.async_enable()
            else:
                await self._manager.async_disable()
            _LOGGER.info(
                "Excess Solar master switch restored to %s",
                "ON" if is_on else "OFF",
            )
        else:
            self._manager.async_enable()
            _LOGGER.info(
                "Excess Solar master switch initialized to ON (no previous state)"
            )

    @property
    def is_on(self) -> bool:
        """Return True if the manager is enabled."""
        return self._manager._enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the excess solar manager."""
        self._manager.async_enable()
        self.async_write_ha_state()
        _LOGGER.info("Excess Solar master switch turned ON")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the excess solar manager and deactivate all sensors."""
        await self._manager.async_disable()
        self.async_write_ha_state()
        _LOGGER.info("Excess Solar master switch turned OFF")


class ExcessSolarDeviceEnabledSwitch(RestoreEntity, SwitchEntity):
    """Per-device enabled/disabled switch for excess solar management.

    When turned **off**, the associated power device is excluded from solar
    excess management until the switch is turned **on** again.

    State is automatically restored from Home Assistant's last known state
    across reboots.
    """

    def __init__(self, unique_id: str, name: str) -> None:
        """Initialise the device enabled switch."""
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = "mdi:solar-power-variant"
        self._attr_is_on: bool = True  # enabled by default

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            self._attr_is_on = last_state.state == "on"
            _LOGGER.debug(
                "Device enabled switch '%s' restored to %s",
                self.name,
                "ON" if self._attr_is_on else "OFF",
            )

    @property
    def is_on(self) -> bool:
        """Return True if this device participates in solar management."""
        return bool(self._attr_is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable this device for solar management."""
        self._attr_is_on = True
        self.async_write_ha_state()
        _LOGGER.debug("Device enabled switch '%s' turned ON", self.name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable this device from solar management."""
        self._attr_is_on = False
        self.async_write_ha_state()
        _LOGGER.debug("Device enabled switch '%s' turned OFF", self.name)
