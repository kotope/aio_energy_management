"""Tests for the Excess Solar Manager and Binary Sensor entities."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.aio_energy_management.excess_solar import (
    ExcessSolarBinarySensor,
    ExcessSolarDeviceEnabledSwitch,
    ExcessSolarManager,
    ExcessSolarMasterSwitch,
    build_sensors_from_config,
    create_manager_from_config,
)
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_enabled_switch(enabled: bool = True) -> ExcessSolarDeviceEnabledSwitch:
    """Create a device enabled switch with the given state."""
    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_test_device_enabled",
        name="Test Device Enabled",
    )
    switch._attr_is_on = enabled
    return switch


def _make_sensor(
    hass: HomeAssistant,
    device_entity_id: str = "switch.device",
    consumption: int = 1000,
    priority: int = 1,
    is_on_schedule_entity: str | None = None,
    enabled_switch: ExcessSolarDeviceEnabledSwitch | None = None,
    minimum_period: int = 0,
    turn_on_delay: int = 0,  # 0 for tests to avoid timing complexity
) -> ExcessSolarBinarySensor:
    """Create a test binary sensor."""
    return ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id=device_entity_id,
        consumption=consumption,
        unique_id=f"excess_solar_{device_entity_id.replace('.', '_')}",
        name=f"Excess Solar – {device_entity_id}",
        priority=priority,
        is_on_schedule_entity=is_on_schedule_entity,
        enabled_switch=enabled_switch,
        minimum_period=minimum_period,
        turn_on_delay=turn_on_delay,
    )


def _make_manager(
    hass: HomeAssistant,
    grid_sensor: str = "sensor.grid_power",
    sensors: list[ExcessSolarBinarySensor] | None = None,
    buffer: int = 50,
) -> ExcessSolarManager:
    """Create a test manager."""
    if sensors is None:
        sensors = [_make_sensor(hass)]
    return ExcessSolarManager(
        hass=hass,
        grid_sensor=grid_sensor,
        sensors=sensors,
        buffer=buffer,
    )


def _set_state(hass: HomeAssistant, entity_id: str, state: str) -> None:
    hass.states.async_set(entity_id, state)


# ---------------------------------------------------------------------------
# ExcessSolarBinarySensor unit tests
# ---------------------------------------------------------------------------


async def test_sensor_get_consumption_static(hass: HomeAssistant) -> None:
    """Static watt consumption value is returned correctly."""
    sensor = _make_sensor(hass, consumption=2000)
    assert sensor.get_consumption() == 2000.0


async def test_sensor_get_consumption_from_entity(hass: HomeAssistant) -> None:
    """Consumption is read from a HA entity state."""
    _set_state(hass, "sensor.ev_power", "3500")
    sensor = _make_sensor(hass, consumption="sensor.ev_power")
    assert sensor.get_consumption() == 3500.0


async def test_sensor_get_consumption_entity_unavailable(hass: HomeAssistant) -> None:
    """Missing consumption entity → 0W (safe default)."""
    sensor = _make_sensor(hass, consumption="sensor.missing")
    assert sensor.get_consumption() == 0.0


async def test_sensor_is_on_schedule_true(hass: HomeAssistant) -> None:
    """Sensor correctly reports on-schedule state."""
    _set_state(hass, "binary_sensor.schedule", "on")
    sensor = _make_sensor(hass, is_on_schedule_entity="binary_sensor.schedule")
    assert sensor.is_on_schedule() is True


async def test_sensor_is_enabled_false_via_switch(hass: HomeAssistant) -> None:
    """Sensor is disabled when its enabled switch is off."""
    switch = _make_enabled_switch(enabled=False)
    sensor = _make_sensor(hass, enabled_switch=switch)
    assert sensor.is_enabled() is False


async def test_sensor_is_enabled_true_via_switch(hass: HomeAssistant) -> None:
    """Sensor is enabled when its enabled switch is on."""
    switch = _make_enabled_switch(enabled=True)
    sensor = _make_sensor(hass, enabled_switch=switch)
    assert sensor.is_enabled() is True


async def test_sensor_is_enabled_no_switch(hass: HomeAssistant) -> None:
    """No enabled switch → always enabled."""
    sensor = _make_sensor(hass)
    assert sensor.is_enabled() is True


async def test_sensor_can_turn_on_no_history(hass: HomeAssistant) -> None:
    """Device with no history can always turn on."""
    sensor = _make_sensor(hass, turn_on_delay=60)
    assert sensor.can_turn_on() is True


@freeze_time("2024-01-01 12:00:00+00:00")
async def test_sensor_can_turn_on_delay_not_elapsed(hass: HomeAssistant) -> None:
    """Device turn-on is blocked during the delay period."""
    sensor = _make_sensor(hass, turn_on_delay=120)
    sensor.async_write_ha_state = MagicMock()
    sensor.deactivate()  # turn off at t=0
    assert sensor.can_turn_on() is False


async def test_sensor_can_turn_on_delay_elapsed(
    freezer: FrozenDateTimeFactory, hass: HomeAssistant
) -> None:
    """Device can turn on once delay has elapsed."""
    sensor = _make_sensor(hass, turn_on_delay=60)
    sensor.async_write_ha_state = MagicMock()
    freezer.move_to("2024-01-01 12:00:00+00:00")
    sensor.deactivate()

    freezer.move_to("2024-01-01 12:00:30+00:00")
    assert sensor.can_turn_on() is False

    freezer.move_to("2024-01-01 12:01:01+00:00")
    assert sensor.can_turn_on() is True


async def test_sensor_minimum_period_blocks_deactivation(
    freezer: FrozenDateTimeFactory, hass: HomeAssistant
) -> None:
    """Sensor deactivation is blocked during the minimum period."""
    sensor = _make_sensor(hass, minimum_period=5)  # 5 minutes
    sensor.async_write_ha_state = MagicMock()
    freezer.move_to("2024-01-01 12:00:00+00:00")
    sensor.activate()

    freezer.move_to("2024-01-01 12:03:00+00:00")
    assert sensor.can_turn_off() is False

    freezer.move_to("2024-01-01 12:05:01+00:00")
    assert sensor.can_turn_off() is True


async def test_sensor_activate_deactivate_state(hass: HomeAssistant) -> None:
    """Activate/deactivate correctly toggle the sensor state."""
    sensor = _make_sensor(hass)
    sensor.hass = hass
    sensor.async_write_ha_state = MagicMock()

    assert sensor.is_on is False
    sensor.activate()
    assert sensor.is_on is True
    assert sensor._last_turned_on is not None

    sensor.deactivate()
    assert sensor.is_on is False
    assert sensor._last_turned_off is not None


async def test_sensor_extra_state_attributes(hass: HomeAssistant) -> None:
    """Extra attributes include expected keys."""
    sensor = _make_sensor(hass)
    attrs = sensor.extra_state_attributes
    assert "device_entity" in attrs
    assert "priority" in attrs
    assert "consumption_w" in attrs
    assert "is_on_schedule" in attrs
    assert "is_enabled" in attrs
    assert "is_full" not in attrs


# ---------------------------------------------------------------------------
# ExcessSolarManager tests
# ---------------------------------------------------------------------------


async def test_manager_activates_sensor_with_excess_solar(
    hass: HomeAssistant,
) -> None:
    """Manager activates sensor when grid_power < -buffer."""
    # 500W consumption, 2000W available (well over budget)
    sensor = _make_sensor(hass, consumption=500, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=50)

    # -2000W grid → 2000W excess > buffer 50W, 2000 >= 500
    await manager._async_evaluate(-2000.0)

    assert sensor.is_on is True


async def test_manager_no_action_within_buffer(hass: HomeAssistant) -> None:
    """No action taken when grid power is within the hysteresis buffer."""
    sensor = _make_sensor(hass, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=100)

    await manager._async_evaluate(-50.0)  # within ±100W buffer

    assert sensor.is_on is False


async def test_manager_deactivates_lowest_priority_when_importing(
    hass: HomeAssistant,
) -> None:
    """When importing, the lowest priority active sensor is deactivated first."""
    hi = _make_sensor(hass, device_entity_id="switch.hi", priority=1, minimum_period=0)
    lo = _make_sensor(hass, device_entity_id="switch.lo", priority=10, minimum_period=0)
    for s in [hi, lo]:
        s.async_write_ha_state = MagicMock()
        s.activate()

    manager = _make_manager(hass, sensors=[hi, lo], buffer=50)

    await manager._async_evaluate(300.0)  # importing 300W

    # Lowest priority (lo) deactivated first
    assert lo.is_on is False
    assert hi.is_on is True  # high priority remains active


async def test_manager_skips_disabled_sensor(hass: HomeAssistant) -> None:
    """Disabled sensor is skipped when enabled switch is off."""
    switch = _make_enabled_switch(enabled=False)
    sensor = _make_sensor(hass, enabled_switch=switch, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    await manager._async_evaluate(-500.0)

    assert sensor.is_on is False


async def test_manager_activates_enabled_sensor(hass: HomeAssistant) -> None:
    """Enabled sensor (switch is on) is activated normally."""
    switch = _make_enabled_switch(enabled=True)
    sensor = _make_sensor(hass, consumption=500, enabled_switch=switch, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    await manager._async_evaluate(-1000.0)

    assert sensor.is_on is True


async def test_manager_skips_scheduled_sensor_on_activation(
    hass: HomeAssistant,
) -> None:
    """Sensor on schedule is not activated by the manager."""
    _set_state(hass, "binary_sensor.schedule", "on")
    sensor = _make_sensor(
        hass, is_on_schedule_entity="binary_sensor.schedule", turn_on_delay=0
    )
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    await manager._async_evaluate(-500.0)

    assert sensor.is_on is False


async def test_manager_skips_scheduled_sensor_on_deactivation(
    hass: HomeAssistant,
) -> None:
    """Manager does not turn off a sensor that is on a schedule."""
    _set_state(hass, "binary_sensor.schedule", "on")
    sensor = _make_sensor(
        hass, is_on_schedule_entity="binary_sensor.schedule", minimum_period=0
    )
    sensor.async_write_ha_state = MagicMock()
    sensor.activate()  # mark as active
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    await manager._async_evaluate(500.0)  # heavy import

    assert sensor.is_on is True  # left alone


async def test_manager_short_cycle_prevention(
    freezer: FrozenDateTimeFactory, hass: HomeAssistant
) -> None:
    """Sensor cannot be reactivated during the turn_on_delay window."""
    # 500W consumption, 3000W available → budget always passes when not blocked
    sensor = _make_sensor(hass, consumption=500, turn_on_delay=60)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    freezer.move_to("2024-01-01 12:00:00+00:00")
    sensor.deactivate()

    # 30s later – still blocked
    freezer.move_to("2024-01-01 12:00:30+00:00")
    await manager._async_evaluate(-3000.0)
    assert sensor.is_on is False

    # 61s later – now allowed
    freezer.move_to("2024-01-01 12:01:01+00:00")
    await manager._async_evaluate(-3000.0)
    assert sensor.is_on is True


async def test_manager_minimum_period_blocks_deactivation(
    freezer: FrozenDateTimeFactory, hass: HomeAssistant
) -> None:
    """Manager cannot deactivate a sensor before minimum_period has passed."""
    sensor = _make_sensor(hass, minimum_period=5)  # 5 min
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    freezer.move_to("2024-01-01 12:00:00+00:00")
    sensor.activate()

    freezer.move_to("2024-01-01 12:03:00+00:00")
    await manager._async_evaluate(500.0)
    assert sensor.is_on is True  # still on

    freezer.move_to("2024-01-01 12:05:01+00:00")
    await manager._async_evaluate(500.0)
    assert sensor.is_on is False  # now deactivated


async def test_manager_priority_order_activation(hass: HomeAssistant) -> None:
    """Highest priority (lowest number) sensor is activated first."""
    lo_prio = _make_sensor(
        hass, device_entity_id="switch.lo_prio", priority=10, turn_on_delay=0
    )
    hi_prio = _make_sensor(
        hass, device_entity_id="switch.hi_prio", priority=1, turn_on_delay=0
    )
    for s in [lo_prio, hi_prio]:
        s.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[lo_prio, hi_prio], buffer=0)

    await manager._async_evaluate(-5000.0)  # lots of solar

    assert hi_prio.is_on is True
    assert lo_prio.is_on is False  # not yet – one per evaluation cycle


async def test_manager_budget_skips_too_large_device(hass: HomeAssistant) -> None:
    """A device whose consumption exceeds available solar is skipped."""
    big = _make_sensor(
        hass,
        device_entity_id="switch.big",
        consumption=2000,
        priority=1,
        turn_on_delay=0,
    )
    small = _make_sensor(
        hass,
        device_entity_id="switch.small",
        consumption=400,
        priority=2,
        turn_on_delay=0,
    )
    for s in [big, small]:
        s.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[big, small], buffer=50)

    # 500W available, buffer 50W → effective 450W; big (2000W) skipped
    await manager._async_evaluate(-500.0)

    assert big.is_on is False
    assert small.is_on is True  # fits within budget


async def test_manager_start_and_stop(hass: HomeAssistant) -> None:
    """Manager subscribes on start and unsubscribes on stop."""
    manager = _make_manager(hass)

    await manager.async_start()
    assert manager._cancel_listener is not None

    await manager.async_stop()
    assert manager._cancel_listener is None


async def test_manager_diagnostic_info(hass: HomeAssistant) -> None:
    """Diagnostic info contains expected keys."""
    manager = _make_manager(hass)
    info = manager.diagnostic_info
    assert "grid_sensor" in info
    assert "buffer" in info
    assert isinstance(info["sensors"], list)
    assert "device_entity" in info["sensors"][0]


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


async def test_build_sensors_from_config(hass: HomeAssistant) -> None:
    """build_sensors_from_config creates one sensor per power_device."""
    config = {
        "sensor": "sensor.grid_power",
        "buffer": 100,
        "turn_on_delay": 30,
        "power_devices": [
            {
                "name": "Water Heater",
                "consumption": 2000,
                "priority": 1,
                "minimum_period": 10,
            },
            {
                "name": "EV Charger",
                "consumption": 7400,
                "priority": 2,
                "minimum_period": 30,
            },
        ],
    }
    sensors, number_entities, enabled_switches = build_sensors_from_config(hass, config)
    assert len(sensors) == 2
    assert len(enabled_switches) == 2
    assert sensors[0].device_entity_id == "Water Heater"
    assert sensors[0].get_consumption() == 2000.0
    assert sensors[0].priority == 1
    assert sensors[1].device_entity_id == "EV Charger"
    assert sensors[1].priority == 2


async def test_create_manager_from_config(hass: HomeAssistant) -> None:
    """create_manager_from_config wires sensors correctly."""
    config = {
        "sensor": "sensor.grid_power",
        "buffer": 80,
        "turn_on_delay": 60,
        "power_devices": [],
    }
    sensors = [_make_sensor(hass)]
    manager = create_manager_from_config(hass, config, sensors)
    assert manager._grid_sensor == "sensor.grid_power"
    assert manager._buffer == 80
    assert len(manager._sensors) == 1


# ---------------------------------------------------------------------------
# ExcessSolarMasterSwitch tests
# ---------------------------------------------------------------------------


async def test_master_switch_starts_enabled(hass: HomeAssistant) -> None:
    """Manager is enabled by default."""
    manager = _make_manager(hass)
    assert manager._enabled is True


async def test_master_switch_disable_skips_evaluation(hass: HomeAssistant) -> None:
    """While disabled, _async_evaluate should not activate any sensor."""
    sensor = _make_sensor(hass, consumption=500, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    await manager.async_disable()
    assert manager._enabled is False

    await manager._async_evaluate(-5000.0)  # lots of excess solar
    assert sensor.is_on is False  # must remain off


async def test_master_switch_disable_deactivates_active_sensors(
    hass: HomeAssistant,
) -> None:
    """Disabling the manager immediately deactivates all active sensors."""
    s1 = _make_sensor(hass, device_entity_id="switch.a", turn_on_delay=0)
    s2 = _make_sensor(hass, device_entity_id="switch.b", turn_on_delay=0)
    for s in [s1, s2]:
        s.async_write_ha_state = MagicMock()
        s.activate()

    manager = _make_manager(hass, sensors=[s1, s2], buffer=0)

    await manager.async_disable()

    assert s1.is_on is False
    assert s2.is_on is False


async def test_master_switch_enable_resumes_operation(hass: HomeAssistant) -> None:
    """Re-enabling the manager allows subsequent evaluations to act."""
    sensor = _make_sensor(hass, consumption=500, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    manager = _make_manager(hass, sensors=[sensor], buffer=0)

    await manager.async_disable()
    manager.async_enable()
    assert manager._enabled is True

    await manager._async_evaluate(-5000.0)
    assert sensor.is_on is True


async def test_master_switch_entity_turn_off(hass: HomeAssistant) -> None:
    """ExcessSolarMasterSwitch.async_turn_off disables manager and deactivates sensors."""
    sensor = _make_sensor(hass, turn_on_delay=0)
    sensor.async_write_ha_state = MagicMock()
    sensor.activate()

    manager = _make_manager(hass, sensors=[sensor], buffer=0)
    switch = ExcessSolarMasterSwitch(
        manager=manager, unique_id="test_switch", name="Test"
    )
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_off()

    assert switch.is_on is False
    assert sensor.is_on is False
    assert manager._enabled is False


async def test_master_switch_entity_turn_on(hass: HomeAssistant) -> None:
    """ExcessSolarMasterSwitch.async_turn_on re-enables the manager."""
    manager = _make_manager(hass)
    await manager.async_disable()

    switch = ExcessSolarMasterSwitch(
        manager=manager, unique_id="test_switch", name="Test"
    )
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()

    assert switch.is_on is True
    assert manager._enabled is True


# ---------------------------------------------------------------------------
# ExcessSolarDeviceEnabledSwitch tests
# ---------------------------------------------------------------------------


async def test_device_enabled_switch_defaults_to_on(hass: HomeAssistant) -> None:
    """Device enabled switch is on by default."""
    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_device_enabled",
        name="Device Enabled",
    )
    assert switch.is_on is True


async def test_device_enabled_switch_turn_off(hass: HomeAssistant) -> None:
    """Turning off device enabled switch marks device as disabled."""
    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_device_enabled",
        name="Device Enabled",
    )
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_off()

    assert switch.is_on is False
    switch.async_write_ha_state.assert_called_once()


async def test_device_enabled_switch_turn_on(hass: HomeAssistant) -> None:
    """Turning on device enabled switch marks device as enabled."""
    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_device_enabled",
        name="Device Enabled",
    )
    switch._attr_is_on = False
    switch.async_write_ha_state = MagicMock()

    await switch.async_turn_on()

    assert switch.is_on is True
    switch.async_write_ha_state.assert_called_once()


async def test_device_enabled_switch_restores_state(hass: HomeAssistant) -> None:
    """Device enabled switch restores previous state after restart."""
    from unittest.mock import patch

    from homeassistant.core import State

    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_device_enabled",
        name="Device Enabled",
    )

    mock_state = State(
        entity_id="switch.device_enabled",
        state="off",
    )

    with patch.object(switch, "async_get_last_state", return_value=mock_state):
        await switch.async_added_to_hass()

    assert switch.is_on is False


async def test_device_enabled_switch_restores_on_state(hass: HomeAssistant) -> None:
    """Device enabled switch restores 'on' state after restart."""
    from unittest.mock import patch

    from homeassistant.core import State

    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_device_enabled",
        name="Device Enabled",
    )
    switch._attr_is_on = False  # start as off

    mock_state = State(
        entity_id="switch.device_enabled",
        state="on",
    )

    with patch.object(switch, "async_get_last_state", return_value=mock_state):
        await switch.async_added_to_hass()

    assert switch.is_on is True


async def test_device_enabled_switch_no_previous_state(hass: HomeAssistant) -> None:
    """Device enabled switch defaults to on when no previous state exists."""
    from unittest.mock import patch

    switch = ExcessSolarDeviceEnabledSwitch(
        unique_id="excess_solar_device_enabled",
        name="Device Enabled",
    )

    with patch.object(switch, "async_get_last_state", return_value=None):
        await switch.async_added_to_hass()

    assert switch.is_on is True


# ---------------------------------------------------------------------------
# Priority Number Entity tests
# ---------------------------------------------------------------------------


async def test_priority_number_entity_creation(hass: HomeAssistant) -> None:
    """Priority number entity is created with correct attributes."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Water Heater",
        unique_id="excess_solar_water_heater",
        initial_priority=50,
    )

    assert number._attr_unique_id == "excess_solar_water_heater_priority"
    assert number._attr_name == "Water Heater Priority"
    assert number._attr_native_value == 50.0
    assert number._attr_native_min_value == 1
    assert number._attr_native_max_value == 100
    assert number._attr_native_step == 1
    assert number.get_priority() == 50


async def test_priority_number_entity_set_value(hass: HomeAssistant) -> None:
    """Priority number entity value can be changed."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="EV Charger",
        unique_id="excess_solar_ev",
        initial_priority=10,
    )
    number.async_write_ha_state = MagicMock()

    await number.async_set_native_value(25.0)

    assert number._attr_native_value == 25.0
    assert number.get_priority() == 25
    number.async_write_ha_state.assert_called_once()


async def test_priority_number_entity_callback_triggered(hass: HomeAssistant) -> None:
    """Priority change callback is triggered when value changes."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    callback_triggered = False

    def priority_changed_callback():
        nonlocal callback_triggered
        callback_triggered = True

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device",
        unique_id="excess_solar_device",
        initial_priority=5,
        on_priority_change_callback=priority_changed_callback,
    )
    number.async_write_ha_state = MagicMock()

    await number.async_set_native_value(15.0)

    assert callback_triggered is True


async def test_binary_sensor_reads_priority_from_number_entity(
    hass: HomeAssistant,
) -> None:
    """Binary sensor reads priority from linked number entity."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device",
        unique_id="excess_solar_device",
        initial_priority=10,
    )

    sensor = ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id="switch.device",
        consumption=1000,
        unique_id="excess_solar_device",
        name="Device",
        priority=10,
        priority_number_entity=number,
    )

    assert sensor.priority == 10

    number._attr_native_value = 25.0

    assert sensor.priority == 25


async def test_binary_sensor_priority_without_number_entity(
    hass: HomeAssistant,
) -> None:
    """Binary sensor uses initial priority when no number entity is linked."""
    sensor = _make_sensor(hass, priority=15)
    assert sensor.priority == 15


async def test_manager_sorts_sensors_by_priority(hass: HomeAssistant) -> None:
    """Manager sorts sensors by priority (lower = higher priority)."""
    sensor_low = _make_sensor(hass, device_entity_id="switch.low", priority=1)
    sensor_mid = _make_sensor(hass, device_entity_id="switch.mid", priority=5)
    sensor_high = _make_sensor(hass, device_entity_id="switch.high", priority=10)

    # Create in wrong order
    manager = _make_manager(hass, sensors=[sensor_high, sensor_low, sensor_mid])

    # Manager should sort them: low (1), mid (5), high (10)
    assert manager._sensors[0] == sensor_low
    assert manager._sensors[1] == sensor_mid
    assert manager._sensors[2] == sensor_high


async def test_manager_resorts_on_priority_change(hass: HomeAssistant) -> None:
    """Manager re-sorts sensors when priority changes."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    manager = ExcessSolarManager(
        hass=hass,
        grid_sensor="sensor.grid_power",
        sensors=[],
        buffer=50,
    )

    number1 = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device 1",
        unique_id="excess_solar_device1",
        initial_priority=1,
        on_priority_change_callback=manager.on_priority_changed,
    )
    sensor1 = ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id="switch.device1",
        consumption=1000,
        unique_id="excess_solar_device1",
        name="Device 1",
        priority=1,
        priority_number_entity=number1,
    )

    number2 = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device 2",
        unique_id="excess_solar_device2",
        initial_priority=5,
        on_priority_change_callback=manager.on_priority_changed,
    )
    sensor2 = ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id="switch.device2",
        consumption=1000,
        unique_id="excess_solar_device2",
        name="Device 2",
        priority=5,
        priority_number_entity=number2,
    )

    manager.sensors = [sensor1, sensor2]
    manager.sort_sensors()

    assert manager._sensors[0] == sensor1
    assert manager._sensors[1] == sensor2

    number1._attr_native_value = 10.0
    number1.async_write_ha_state = MagicMock()
    await number1.async_set_native_value(10.0)

    assert manager._sensors[0] == sensor2
    assert manager._sensors[1] == sensor1


async def test_priority_change_affects_activation_order(hass: HomeAssistant) -> None:
    """Changing priority affects which device gets activated first."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    manager = ExcessSolarManager(
        hass=hass,
        grid_sensor="sensor.grid_power",
        sensors=[],
        buffer=0,
    )

    number1 = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device 1",
        unique_id="excess_solar_device1",
        initial_priority=10,
        on_priority_change_callback=manager.on_priority_changed,
    )
    sensor1 = ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id="switch.device1",
        consumption=500,
        unique_id="excess_solar_device1",
        name="Device 1",
        priority=10,
        turn_on_delay=0,
        priority_number_entity=number1,
    )
    sensor1.async_write_ha_state = MagicMock()

    number2 = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device 2",
        unique_id="excess_solar_device2",
        initial_priority=5,
        on_priority_change_callback=manager.on_priority_changed,
    )
    sensor2 = ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id="switch.device2",
        consumption=500,
        unique_id="excess_solar_device2",
        name="Device 2",
        priority=5,
        turn_on_delay=0,
        priority_number_entity=number2,
    )
    sensor2.async_write_ha_state = MagicMock()

    manager.sensors = [sensor1, sensor2]
    manager.sort_sensors()

    # With 1000W excess, sensor2 (priority 5) should activate first
    await manager._async_evaluate(-1000.0)
    assert sensor2.is_on is True
    assert sensor1.is_on is False

    # Reset
    sensor2.deactivate()

    # Change sensor1 priority to 1 (now highest priority)
    number1._attr_native_value = 1.0
    number1.async_write_ha_state = MagicMock()
    await number1.async_set_native_value(1.0)

    # Now sensor1 should activate first
    await manager._async_evaluate(-1000.0)
    assert sensor1.is_on is True
    assert sensor2.is_on is False


async def test_priority_in_extra_state_attributes(hass: HomeAssistant) -> None:
    """Priority is included in binary sensor extra state attributes."""
    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device",
        unique_id="excess_solar_device",
        initial_priority=7,
    )

    sensor = ExcessSolarBinarySensor(
        hass=hass,
        device_entity_id="switch.device",
        consumption=1000,
        unique_id="excess_solar_device",
        name="Device",
        priority=7,
        priority_number_entity=number,
    )

    attrs = sensor.extra_state_attributes

    assert "priority" in attrs
    assert attrs["priority"] == 7
    assert "priority_entity" in attrs
    assert attrs["priority_entity"] == "excess_solar_device_priority"


async def test_build_sensors_from_config_creates_number_entities(
    hass: HomeAssistant,
) -> None:
    """build_sensors_from_config creates sensors, number entities, and enabled switches."""
    config = {
        "sensor": "sensor.grid_power",
        "buffer": 100,
        "turn_on_delay": 60,
        "power_devices": [
            {
                "name": "Water Heater",
                "consumption": 400,
                "priority": 1,
            },
            {
                "name": "EV Charger",
                "consumption": 1000,
                "priority": 2,
            },
        ],
    }

    manager = ExcessSolarManager(
        hass=hass,
        grid_sensor="sensor.grid_power",
        sensors=[],
        buffer=100,
    )

    sensors, number_entities, enabled_switches = build_sensors_from_config(
        hass, config, manager
    )

    assert len(sensors) == 2
    assert len(number_entities) == 2
    assert len(enabled_switches) == 2

    # Check first sensor and number entity
    assert sensors[0].name == "Water Heater"
    assert sensors[0].priority == 1
    assert number_entities[0]._attr_name == "Water Heater Priority"
    assert number_entities[0].get_priority() == 1

    # Check second sensor and number entity
    assert sensors[1].name == "EV Charger"
    assert sensors[1].priority == 2
    assert number_entities[1]._attr_name == "EV Charger Priority"
    assert number_entities[1].get_priority() == 2

    # Verify sensors are linked to number entities and enabled switches
    assert sensors[0]._priority_number_entity == number_entities[0]
    assert sensors[1]._priority_number_entity == number_entities[1]
    assert sensors[0]._enabled_switch == enabled_switches[0]
    assert sensors[1]._enabled_switch == enabled_switches[1]

    # Enabled switches should be on by default
    assert enabled_switches[0].is_on is True
    assert enabled_switches[1].is_on is True

    # Check switch names and unique IDs
    assert enabled_switches[0]._attr_name == "Water Heater Enabled"
    assert enabled_switches[1]._attr_name == "EV Charger Enabled"


async def test_priority_number_entity_state_restoration(
    hass: HomeAssistant,
) -> None:
    """Priority number entity restores previous state after restart."""
    from unittest.mock import AsyncMock, patch

    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )
    from homeassistant.core import State

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Test Device",
        unique_id="excess_solar_test",
        initial_priority=10,
    )

    mock_state = State(
        entity_id="number.test_device_priority",
        state="25.0",
    )

    with patch.object(number, "async_get_last_state", return_value=mock_state):
        await number.async_added_to_hass()

    assert number._attr_native_value == 25.0
    assert number.get_priority() == 25


async def test_priority_number_entity_no_previous_state(
    hass: HomeAssistant,
) -> None:
    """Priority number entity uses initial value when no previous state exists."""
    from unittest.mock import patch

    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="New Device",
        unique_id="excess_solar_new",
        initial_priority=15,
    )

    with patch.object(number, "async_get_last_state", return_value=None):
        await number.async_added_to_hass()

    assert number._attr_native_value == 15.0
    assert number.get_priority() == 15


async def test_priority_number_entity_invalid_restored_state(
    hass: HomeAssistant,
) -> None:
    """Priority number entity handles invalid restored state gracefully."""
    from unittest.mock import patch

    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )
    from homeassistant.core import State

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device",
        unique_id="excess_solar_device",
        initial_priority=20,
    )

    mock_state = State(
        entity_id="number.device_priority",
        state="invalid",
    )

    with patch.object(number, "async_get_last_state", return_value=mock_state):
        await number.async_added_to_hass()

    assert number._attr_native_value == 20.0
    assert number.get_priority() == 20


async def test_priority_number_entity_out_of_bounds_restored_state(
    hass: HomeAssistant,
) -> None:
    """Priority number entity rejects out-of-bounds restored values."""
    from unittest.mock import patch

    from custom_components.aio_energy_management.excess_solar.number import (
        ExcessSolarPriorityNumber,
    )
    from homeassistant.core import State

    number = ExcessSolarPriorityNumber(
        hass=hass,
        device_name="Device",
        unique_id="excess_solar_device",
        initial_priority=50,
    )

    mock_state = State(
        entity_id="number.device_priority",
        state="150.0",
    )

    with patch.object(number, "async_get_last_state", return_value=mock_state):
        await number.async_added_to_hass()

    assert number._attr_native_value == 50.0
    assert number.get_priority() == 50
