"""Excess Solar Binary Sensor entity."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

if TYPE_CHECKING:
    from .switch import ExcessSolarDeviceEnabledSwitch

_LOGGER = logging.getLogger(__name__)

# Default delays
DEFAULT_MINIMUM_OFF_TIME = 1  # minute: minimum wait after "off" before turning "on"


class ExcessSolarBinarySensor(BinarySensorEntity):
    """Binary sensor for a single excess-solar-managed power device.

    State is **on**  → use solar power for this device.
    State is **off** → do not use solar power for this device.

    The sensor tracks:
    - ``_is_on``         – current managed state
    - ``_last_turned_on``  – timestamp when turned on by manager
    - ``_last_turned_off`` – timestamp when turned off by manager
    """

    def __init__(
        self,
        hass: HomeAssistant,
        device_entity_id: str,
        consumption: int,
        consumption_entity: str | None,
        unique_id: str,
        name: str,
        priority: int = 100,
        is_on_schedule_entity: str | None = None,
        enabled_switch: ExcessSolarDeviceEnabledSwitch | None = None,
        minimum_on_time: int = 0,  # minutes
        minimum_off_time: int = DEFAULT_MINIMUM_OFF_TIME,  # minutes
        priority_number_entity: Any = None,
    ) -> None:
        """Initialise the excess solar binary sensor."""
        self.hass = hass
        self.device_entity_id = device_entity_id
        self._consumption = consumption
        self._consumption_entity = consumption_entity
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = "mdi:solar-power-variant"
        self._initial_priority = priority
        self._priority_number_entity = priority_number_entity
        self.is_on_schedule_entity = is_on_schedule_entity
        self._enabled_switch = enabled_switch
        self.minimum_on_time = timedelta(minutes=minimum_on_time)
        self.minimum_off_time = timedelta(minutes=minimum_off_time)

        self._attr_is_on: bool = False
        self._last_turned_on: Any = None
        self._last_turned_off: Any = None

    # ------------------------------------------------------------------
    # State helpers used by the manager
    # ------------------------------------------------------------------

    @property
    def priority(self) -> int:
        """Return current priority from number entity or initial value."""
        if self._priority_number_entity is not None:
            return self._priority_number_entity.get_priority()
        return self._initial_priority

    def get_consumption(self) -> float:
        """Return device consumption in Watts.

        When ``consumption_entity`` is configured, its current HA state value
        is used.  Otherwise the static ``consumption`` wattage is returned
        while the sensor is **on**, and ``0 W`` is returned while it is **off**
        (an inactive device consumes nothing from the solar budget).
        """
        if self._consumption_entity is not None:
            state = self.hass.states.get(self._consumption_entity)
            if state is None:
                _LOGGER.warning(
                    "Consumption entity %s not found for %s, falling back to static value",
                    self._consumption_entity,
                    self.name,
                )
            else:
                try:
                    return float(state.state)
                except ValueError:
                    _LOGGER.warning(
                        "Cannot parse consumption from %s: '%s', falling back to static value",
                        self._consumption_entity,
                        state.state,
                    )

        # No consumption_entity (or entity unavailable): only count watts while on.
        if not self._attr_is_on:
            return 0.0
        try:
            return float(self._consumption)
        except TypeError, ValueError:
            _LOGGER.error(
                "Invalid consumption value for %s: %r – check your configuration",
                self.name,
                self._consumption,
            )
            return 0.0

    def get_expected_consumption(self) -> float:
        """Return the static configured consumption in Watts for budget planning.

        This always returns the configured ``consumption`` wattage regardless of
        the current on/off state or any ``consumption_entity`` reading.
        The manager uses this value to decide whether there is enough solar
        surplus to activate a sensor *before* it is turned on.
        """
        try:
            return float(self._consumption)
        except TypeError, ValueError:
            _LOGGER.error(
                "Invalid consumption value for %s: %r – check your configuration",
                self.name,
                self._consumption,
            )
            return 0.0

    def is_on_schedule(self) -> bool:
        """Return True if device is on its own schedule (manager hands off)."""
        if self.is_on_schedule_entity is None:
            return False
        state = self.hass.states.get(self.is_on_schedule_entity)
        return state is not None and state.state in ("on", "true", "True", "1")

    def is_enabled(self) -> bool:
        """Return True if this device participates in solar management."""
        if self._enabled_switch is None:
            return True
        return self._enabled_switch.is_on

    def can_turn_on(self) -> bool:
        """Return True if minimum_off_time since last turn-off has elapsed."""
        if self._last_turned_off is None:
            return True
        elapsed = dt_util.now() - self._last_turned_off
        if elapsed < self.minimum_off_time:
            _LOGGER.debug(
                "Sensor %s: minimum_off_time not elapsed (%s remaining)",
                self.name,
                self.minimum_off_time - elapsed,
            )
            return False
        return True

    def can_turn_off(self) -> bool:
        """Return True if the device is allowed to turn off.

        The ``minimum_on_time`` guard must pass: an optional user-configured
        minimum run time that prevents the device from being turned off before
        it has run for the required duration.
        """
        if self._last_turned_on is None:
            return True
        elapsed = dt_util.now() - self._last_turned_on
        if elapsed < self.minimum_on_time:
            _LOGGER.debug(
                "Sensor %s: minimum_on_time not elapsed (%s remaining)",
                self.name,
                self.minimum_on_time - elapsed,
            )
            return False
        return True

    def activate(self) -> None:
        """Mark sensor as active (turn on) and record timestamp."""
        self._attr_is_on = True
        self._last_turned_on = dt_util.now()
        self.async_write_ha_state()

    def deactivate(self) -> None:
        """Mark sensor as inactive (turn off) and record timestamp."""
        self._attr_is_on = False
        self._last_turned_off = dt_util.now()
        self.async_write_ha_state()

    # ------------------------------------------------------------------
    # BinarySensorEntity
    # ------------------------------------------------------------------

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        attrs = {
            "device_entity": self.device_entity_id,
            "priority": self.priority,
            "consumption_w": self.get_consumption(),
            "is_on_schedule": self.is_on_schedule(),
            "is_enabled": self.is_enabled(),
            "last_turned_on": (
                self._last_turned_on.isoformat() if self._last_turned_on else None
            ),
            "last_turned_off": (
                self._last_turned_off.isoformat() if self._last_turned_off else None
            ),
        }

        if self._priority_number_entity is not None:
            entity_ref = (
                getattr(self._priority_number_entity, "entity_id", None)
                or self._priority_number_entity._attr_unique_id
            )
            attrs["priority_entity"] = entity_ref
        return attrs
