"""Excess Solar Binary Sensor entity."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Default delays
DEFAULT_TURN_ON_DELAY = 60  # seconds: minimum wait after "off" before turning "on"


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
        consumption: int | str,
        unique_id: str,
        name: str,
        priority: int = 100,
        is_full_entity: str | None = None,
        is_on_schedule_entity: str | None = None,
        enabled_entity: str | None = None,
        minimum_period: int = 0,  # minutes
        turn_on_delay: int = DEFAULT_TURN_ON_DELAY,  # seconds
        priority_number_entity: Any = None,
    ) -> None:
        """Initialise the excess solar binary sensor."""
        self.hass = hass
        self.device_entity_id = device_entity_id
        self._consumption = consumption
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_icon = "mdi:solar-power-variant"
        self._initial_priority = priority
        self._priority_number_entity = priority_number_entity
        self.is_full_entity = is_full_entity
        self.is_on_schedule_entity = is_on_schedule_entity
        self.enabled_entity = enabled_entity
        self.minimum_period = timedelta(minutes=minimum_period)
        self.turn_on_delay = timedelta(seconds=turn_on_delay)

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
        """Return device consumption in Watts (static int or entity state)."""
        if (
            isinstance(self._consumption, str)
            and not self._consumption.lstrip("-").isdigit()
        ):
            state = self.hass.states.get(self._consumption)
            if state is None:
                _LOGGER.warning(
                    "Consumption entity %s not found for %s, assuming 0W",
                    self._consumption,
                    self.name,
                )
                return 0.0
            try:
                return float(state.state)
            except ValueError:
                return 0.0
        try:
            return float(self._consumption)
        except (TypeError, ValueError):
            return 0.0

    def is_full(self) -> bool:
        """Return True if device is full and should not receive more power."""
        if self.is_full_entity is None:
            return False
        state = self.hass.states.get(self.is_full_entity)
        return state is not None and state.state in ("on", "true", "True", "1")

    def is_on_schedule(self) -> bool:
        """Return True if device is on its own schedule (manager hands off)."""
        if self.is_on_schedule_entity is None:
            return False
        state = self.hass.states.get(self.is_on_schedule_entity)
        return state is not None and state.state in ("on", "true", "True", "1")

    def is_enabled(self) -> bool:
        """Return True if this device participates in solar management."""
        if self.enabled_entity is None:
            return True
        state = self.hass.states.get(self.enabled_entity)
        if state is None:
            return True
        return state.state in ("on", "true", "True", "1")

    def can_turn_on(self) -> bool:
        """Return True if turn_on_delay since last turn-off has elapsed."""
        if self._last_turned_off is None:
            return True
        elapsed = dt_util.now() - self._last_turned_off
        if elapsed < self.turn_on_delay:
            _LOGGER.debug(
                "Sensor %s: turn_on_delay not elapsed (%s remaining)",
                self.name,
                self.turn_on_delay - elapsed,
            )
            return False
        return True

    def can_turn_off(self) -> bool:
        """Return True if minimum_period since last turn-on has elapsed."""
        if self._last_turned_on is None:
            return True
        elapsed = dt_util.now() - self._last_turned_on
        if elapsed < self.minimum_period:
            _LOGGER.debug(
                "Sensor %s: minimum_period not elapsed (%s remaining)",
                self.name,
                self.minimum_period - elapsed,
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
            "is_full": self.is_full(),
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
            # Use entity_id if available (when registered), otherwise unique_id
            entity_ref = getattr(
                self._priority_number_entity, "entity_id", None
            ) or self._priority_number_entity._attr_unique_id
            attrs["priority_entity"] = entity_ref
        return attrs
