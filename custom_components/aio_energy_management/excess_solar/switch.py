"""Excess Solar Master Switch.

A single switch entity per ``excess_solar:`` block that enables or disables
the ExcessSolarManager.  When the switch is turned **off**:
- The manager stops evaluating grid power
- All active binary sensors are deactivated immediately

When turned **on** again the manager resumes normal operation on the next
grid power state change.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity

from .manager import ExcessSolarManager

_LOGGER = logging.getLogger(__name__)


class ExcessSolarMasterSwitch(SwitchEntity):
    """Master on/off switch for the Excess Solar manager.

    Turning this switch **off** immediately deactivates all managed binary
    sensors and prevents the manager from taking any further actions until
    the switch is turned **on** again.
    """

    def __init__(self, manager: ExcessSolarManager, unique_id: str, name: str) -> None:
        """Initialise the master switch."""
        self._manager = manager
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = "mdi:solar-power"
        self._attr_is_on = True  # enabled by default

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
