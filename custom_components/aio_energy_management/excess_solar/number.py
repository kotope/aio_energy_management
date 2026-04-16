"""Excess Solar Number entity for priority control."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)


class ExcessSolarPriorityNumber(NumberEntity, RestoreEntity):
    """Number entity to control power device priority dynamically.

    Lower numbers = higher priority.
    Range: 1-100, default 100.
    """

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 1
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_icon = "mdi:priority-high"

    def __init__(
        self,
        hass: HomeAssistant,
        device_name: str,
        unique_id: str,
        initial_priority: int = 100,
        on_priority_change_callback: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the priority number entity."""
        self.hass = hass
        self._attr_unique_id = f"{unique_id}_priority"
        self._attr_name = f"{device_name} Priority"
        self._attr_native_value = float(initial_priority)
        self._initial_priority = initial_priority
        self._on_priority_change = on_priority_change_callback

    async def async_added_to_hass(self) -> None:
        """Restore previous state when entity is added to hass."""
        await super().async_added_to_hass()

        # Try to restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                try:
                    restored_value = float(last_state.state)
                    # Validate restored value is within bounds
                    if (
                        self._attr_native_min_value
                        <= restored_value
                        <= self._attr_native_max_value
                    ):
                        self._attr_native_value = restored_value
                        _LOGGER.debug(
                            "Restored priority for %s: %d",
                            self.name,
                            int(restored_value),
                        )
                    else:
                        _LOGGER.warning(
                            "Restored priority %d for %s is out of bounds, using initial value %d",
                            int(restored_value),
                            self.name,
                            self._initial_priority,
                        )
                except (ValueError, TypeError):
                    _LOGGER.warning(
                        "Could not restore priority for %s, using initial value %d",
                        self.name,
                        self._initial_priority,
                    )

    async def async_set_native_value(self, value: float) -> None:
        """Update the priority value."""
        old_value = self._attr_native_value
        self._attr_native_value = value
        self.async_write_ha_state()

        _LOGGER.debug(
            "Priority changed for %s: %d -> %d",
            self.name,
            int(old_value),
            int(value),
        )

        if self._on_priority_change:
            self._on_priority_change()

    def get_priority(self) -> int:
        """Return current priority as integer."""
        return int(self._attr_native_value)
