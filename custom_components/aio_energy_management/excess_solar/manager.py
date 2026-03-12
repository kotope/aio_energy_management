"""Excess Solar Manager.

Architecture
------------
One ``ExcessSolarBinarySensor`` is created per configured ``power_device``.
The sensor's state is **on** when the manager decides that excess solar should
be pushed into that device, and **off** otherwise.

The manager does NOT directly control any device.  Instead, users create HA
automations that listen to these binary sensors and turn actual devices on/off
accordingly.

Short-cycling protection, schedule awareness, is_full / enabled checks, and
priority queue logic all live in this module.
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
import homeassistant.util.dt as dt_util

from .binary_sensor import ExcessSolarBinarySensor

_LOGGER = logging.getLogger(__name__)

# Default delays
DEFAULT_ON_OFF_DEBOUNCE = 30  # seconds: debounce solar power transients


class ExcessSolarManager:
    """Manages excess solar distribution across registered binary sensors.

    Subscribes to grid power sensor state changes.  On each update (debounced):
    - If excess solar available (grid_power < -buffer) → activates the next
      eligible sensor in priority order.
    - If importing (grid_power > +buffer) → deactivates the lowest-priority
      currently active sensor.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        grid_sensor: str,
        sensors: list[ExcessSolarBinarySensor],
        buffer: int = 0,
    ) -> None:
        """Initialise the manager."""
        self._hass = hass
        self._grid_sensor = grid_sensor
        self._buffer = buffer
        # Sorted ascending by priority: lower number → higher priority
        self._sensors: list[ExcessSolarBinarySensor] = sorted(
            sensors, key=lambda s: s.priority
        )
        self._cancel_listener = None
        self._pending_handle: Any = None
        self._last_grid_power: float | None = None  # most recent reading
        self._enabled: bool = True  # master switch state

    async def async_start(self) -> None:
        """Subscribe to grid sensor state changes."""
        _LOGGER.debug(
            "ExcessSolarManager starting – monitoring %s, %d device(s), buffer=%dW",
            self._grid_sensor,
            len(self._sensors),
            self._buffer,
        )
        self._cancel_listener = async_track_state_change_event(
            self._hass,
            [self._grid_sensor],
            self._async_grid_sensor_changed,
        )

    async def async_stop(self) -> None:
        """Stop listening and cancel pending debounce."""
        if self._cancel_listener is not None:
            self._cancel_listener()
            self._cancel_listener = None
        if self._pending_handle is not None:
            self._pending_handle()  # async_call_later returns a cancel callable
            self._pending_handle = None
        _LOGGER.debug("ExcessSolarManager stopped.")

    def async_enable(self) -> None:
        """Enable the manager (master switch on)."""
        self._enabled = True
        _LOGGER.info("ExcessSolarManager enabled")

    async def async_disable(self) -> None:
        """Disable the manager (master switch off) and deactivate all sensors."""
        self._enabled = False
        _LOGGER.info("ExcessSolarManager disabled – deactivating all sensors")
        for sensor in self._sensors:
            if sensor.is_on:
                sensor.deactivate()

    @callback
    def _async_grid_sensor_changed(self, event) -> None:
        """Handle grid power sensor state change (debounced)."""
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable", None):
            return
        try:
            grid_power = float(new_state.state)
        except ValueError:
            _LOGGER.warning(
                "Cannot parse grid power from %s: '%s'",
                self._grid_sensor,
                new_state.state,
            )
            return

        _LOGGER.debug("Grid power: %.1fW (buffer ±%dW)", grid_power, self._buffer)

        # Always store the latest reading so the evaluation uses fresh data
        self._last_grid_power = grid_power

        # Leading throttle: if a timer is already scheduled, let it run.
        # The timer will pick up _last_grid_power when it fires, so we don't
        # need to cancel/reschedule on every sensor update.  This ensures
        # _async_evaluate fires reliably even when the sensor updates every
        # few seconds (which would cause a trailing-edge debounce to never fire).
        if self._pending_handle is not None:
            return

        @callback
        def _fire(_now):
            self._pending_handle = None
            if self._last_grid_power is not None:
                self._hass.async_create_task(
                    self._async_evaluate(self._last_grid_power)
                )

        self._pending_handle = async_call_later(
            self._hass, DEFAULT_ON_OFF_DEBOUNCE, _fire
        )

    async def _async_evaluate(self, grid_power: float) -> None:
        """Evaluate grid power and update binary sensor states."""
        if not self._enabled:
            _LOGGER.debug("ExcessSolarManager is disabled – skipping evaluation")
            return
        available_solar = -grid_power  # positive → exporting (solar excess)

        _LOGGER.debug(
            "Evaluate: grid=%.1fW, available=%.1fW, buffer=%dW",
            grid_power,
            available_solar,
            self._buffer,
        )

        if available_solar > self._buffer:
            await self._activate_next(available_solar)
        elif available_solar < -self._buffer:
            await self._deactivate_last()
        else:
            _LOGGER.debug(
                "Grid power %.1fW within buffer ±%dW – no action",
                grid_power,
                self._buffer,
            )

    async def _activate_next(self, available_solar: float) -> None:
        """Activate the highest-priority eligible sensor."""
        for sensor in self._sensors:
            # Already active → skip
            if sensor.is_on:
                continue
            # Schedule or not enabled guard
            if sensor.is_on_schedule():
                _LOGGER.debug("%s is on schedule, skipping", sensor.name)
                continue
            if not sensor.is_enabled():
                _LOGGER.debug("%s is disabled, skipping", sensor.name)
                continue
            if sensor.is_full():
                _LOGGER.debug("%s is full, skipping", sensor.name)
                continue
            # Short-cycle guard
            if not sensor.can_turn_on():
                continue
            # Budget guard: skip if consumption exceeds net available
            consumption = sensor.get_consumption()
            if consumption > 0 and available_solar < (consumption - self._buffer):
                _LOGGER.debug(
                    "Not enough solar (%.1fW) for %s (%.1fW)",
                    available_solar,
                    sensor.name,
                    consumption,
                )
                continue

            _LOGGER.info(
                "Excess solar %.1fW: activating sensor for %s (priority %d, %.1fW)",
                available_solar,
                sensor.device_entity_id,
                sensor.priority,
                consumption,
            )
            sensor.activate()
            break  # one device per evaluation cycle

    async def _deactivate_last(self) -> None:
        """Deactivate the lowest-priority currently active sensor."""
        for sensor in reversed(self._sensors):
            if not sensor.is_on:
                continue
            # Don't interfere with schedule-controlled devices
            if sensor.is_on_schedule():
                _LOGGER.debug(
                    "%s is on schedule, not deactivating", sensor.name
                )
                continue
            # Minimum period guard
            if not sensor.can_turn_off():
                continue

            _LOGGER.info(
                "Grid importing: deactivating sensor for %s (priority %d)",
                sensor.device_entity_id,
                sensor.priority,
            )
            sensor.deactivate()
            break

    @property
    def diagnostic_info(self) -> dict:
        """Return diagnostic snapshot."""
        return {
            "grid_sensor": self._grid_sensor,
            "buffer": self._buffer,
            "sensors": [
                {
                    "name": s.name,
                    "device_entity": s.device_entity_id,
                    "priority": s.priority,
                    "is_on": s.is_on,
                }
                for s in self._sensors
            ],
        }


def build_sensors_from_config(
    hass: HomeAssistant, config: dict
) -> list[ExcessSolarBinarySensor]:
    """Build ``ExcessSolarBinarySensor`` objects from validated YAML config."""
    from ..const import (  # noqa: PLC0415
        CONF_CONSUMPTION,
        CONF_IS_FULL,
        CONF_IS_ON_SCHEDULE,
        CONF_MINIMUM_PERIOD,
        CONF_PRIORITY,
        CONF_TURN_ON_DELAY,
    )

    global_turn_on_delay = config.get(CONF_TURN_ON_DELAY, 60)
    sensors: list[ExcessSolarBinarySensor] = []

    for idx, dev_conf in enumerate(config.get("power_devices", [])):
        device_entity = dev_conf["entity"]
        slug = device_entity.replace(".", "_").replace("-", "_")
        unique_id = f"excess_solar_{slug}"
        name = f"Excess Solar – {device_entity}"

        sensor = ExcessSolarBinarySensor(
            hass=hass,
            device_entity_id=device_entity,
            consumption=dev_conf[CONF_CONSUMPTION],
            unique_id=unique_id,
            name=name,
            priority=dev_conf.get(CONF_PRIORITY, 100),
            is_full_entity=dev_conf.get(CONF_IS_FULL),
            is_on_schedule_entity=dev_conf.get(CONF_IS_ON_SCHEDULE),
            enabled_entity=dev_conf.get("enabled"),
            minimum_period=dev_conf.get(CONF_MINIMUM_PERIOD, 0),
            turn_on_delay=dev_conf.get(CONF_TURN_ON_DELAY, global_turn_on_delay),
        )
        sensors.append(sensor)

    return sensors


def create_manager_from_config(
    hass: HomeAssistant,
    config: dict,
    sensors: list[ExcessSolarBinarySensor],
) -> ExcessSolarManager:
    """Create an ``ExcessSolarManager`` from validated YAML config."""
    from ..const import CONF_BUFFER, CONF_GRID_POWER_SENSOR  # noqa: PLC0415

    return ExcessSolarManager(
        hass=hass,
        grid_sensor=config[CONF_GRID_POWER_SENSOR],
        sensors=sensors,
        buffer=config.get(CONF_BUFFER, 0),
    )
