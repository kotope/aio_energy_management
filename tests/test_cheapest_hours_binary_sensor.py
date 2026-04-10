"""Tests for energy management integration binary sensors."""

from datetime import datetime
import json
from unittest.mock import AsyncMock, PropertyMock
import zoneinfo

from custom_components.aio_energy_management.binary_sensor import (
    CheapestHoursBinarySensor,
)
from custom_components.aio_energy_management.const import DOMAIN
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory

import numpy as np
from pytest_homeassistant_custom_component.common import load_fixture

from homeassistant.core import HomeAssistant, State, SupportsResponse
from homeassistant.helpers.template import Template
import homeassistant.util.dt as dt_util


def _setup_coordinator_mock() -> AsyncMock:
    mock = AsyncMock()
    mock.get_data = PropertyMock(return_value={"list": []})
    mock.set_data = PropertyMock()

    return mock


def _setup_nordpool_mock(hass: HomeAssistant, fixture: str) -> None:
    mocked_nordpool = State.from_dict(json.loads(load_fixture(fixture, DOMAIN)))
    hass.states.async_set(
        "sensor.nordpool", mocked_nordpool.state, attributes=mocked_nordpool.attributes
    )


def _setup_entsoe_mock(hass: HomeAssistant, fixture: str) -> None:
    mocked_entsoe = State.from_dict(json.loads(load_fixture(fixture, DOMAIN)))
    hass.states.async_set(
        "sensor.entsoe", mocked_entsoe.state, attributes=mocked_entsoe.attributes
    )


def _setup_stromligning_mock(
    hass: HomeAssistant, today_fixture: str, tomorrow_fixture: str
) -> None:
    mocked_today = State.from_dict(json.loads(load_fixture(today_fixture, DOMAIN)))
    hass.states.async_set(
        "sensor.stromligning_current_price_vat",
        mocked_today.state,
        attributes=mocked_today.attributes,
    )
    mocked_tomorrow = State.from_dict(
        json.loads(load_fixture(tomorrow_fixture, DOMAIN))
    )
    hass.states.async_set(
        "binary_sensor.stromligning_tomorrow_available_vat",
        mocked_tomorrow.state,
        attributes=mocked_tomorrow.attributes,
    )


def _setup_nordpool_official_mock(
    hass: HomeAssistant,
    fixture_yesterday: str,
    fixture_today: str,
    fixture_tomorrow: str,
) -> None:
    """Set up the Nordpool official mock service."""
    mocked_nordpool_official_yesterday = json.loads(
        load_fixture(fixture_yesterday, DOMAIN)
    )
    mocked_nordpool_official_today = json.loads(load_fixture(fixture_today, DOMAIN))
    mocked_nordpool_official_tomorrow = json.loads(
        load_fixture(fixture_tomorrow, DOMAIN)
    )
    call_counter = 0

    async def mock_service_call(service_call):
        nonlocal call_counter
        call_counter += 1
        if call_counter == 1:
            return mocked_nordpool_official_yesterday
        if call_counter == 2:
            return mocked_nordpool_official_today
        return mocked_nordpool_official_tomorrow

    hass.services.async_register(
        "nordpool",
        "get_price_indices_for_date",
        AsyncMock(side_effect=mock_service_call),
        supports_response=SupportsResponse.ONLY,
    )


@freeze_time("2024-07-13 14:25+03:00")
async def test_cheapest_hours_sequential_binary_sensors(hass: HomeAssistant) -> None:
    """Test binary sensors."""
    hass.config.timezone = zoneinfo.ZoneInfo("Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=20,
        last_hour=12,
        starting_today=True,
        number_of_hours=3,
        sequential=True,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes

    assert (
        attributes["failsafe"]["start"]
        == datetime.now().replace(hour=1, minute=0).time()
    )
    assert (
        attributes["failsafe"]["end"] == datetime.now().replace(hour=4, minute=0).time()
    )
    assert attributes["inversed"] is False


async def test_cheapest_hours_non_sequential_binary_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test binary sensors."""
    coordinator_mock = _setup_coordinator_mock()
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2024-07-13 14:25+03:00")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=18,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    assert (
        attributes["failsafe"]["start"]
        == datetime.now().replace(hour=19, minute=0).time()
    )
    assert (
        attributes["failsafe"]["end"]
        == datetime.now().replace(hour=22, minute=0).time()
    )

    # Expires after last hour
    assert attributes["expiration"] == datetime(2024, 7, 15, 0, 0, tzinfo=tzinfo)

    # List of data
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 18, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 19, 0, tzinfo=tzinfo)

    assert attributes["list"][1]["start"] == datetime(2024, 7, 14, 22, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["end"] == datetime(2024, 7, 15, 0, 0, tzinfo=tzinfo)

    assert sensor.is_on is False

    # Move to first slot
    freezer.move_to("2024-07-14 18:30+03:00")
    assert sensor.is_on is True

    # Move to non-cheapest
    freezer.move_to("2024-07-14 21:59+03:00")
    assert sensor.is_on is False

    # Move to second
    freezer.move_to("2024-07-14 22:01+03:00")
    assert sensor.is_on is True

    # Check expiration
    freezer.move_to("2024-07-15 00:01+03:00")
    await sensor.async_update()

    # TODO: Assert missing


async def test_expensive_hours_non_sequential_binary_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test binary sensors."""
    coordinator_mock = _setup_coordinator_mock()
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2024-07-13 14:25+03:00")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=18,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
        inversed=True,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    assert (
        attributes["failsafe"]["start"]
        == datetime.now().replace(hour=19, minute=0).time()
    )
    assert (
        attributes["failsafe"]["end"]
        == datetime.now().replace(hour=22, minute=0).time()
    )

    # Expires after last hour
    assert attributes["expiration"] == datetime(2024, 7, 15, 0, 0, tzinfo=tzinfo)

    # List of data
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 19, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 22, 0, tzinfo=tzinfo)

    assert sensor.is_on is False

    # Move to expensive
    freezer.move_to("2024-07-14 19:30+03:00")
    assert sensor.is_on is True

    # Move to almost end
    freezer.move_to("2024-07-14 21:59+03:00")
    assert sensor.is_on is True

    # Move off from expensive
    freezer.move_to("2024-07-14 22:01+03:00")
    assert sensor.is_on is False


@freeze_time("2024-07-13 14:25+03:00")
async def test_cheapest_hours_full_day_binary_sensors(
    hass: HomeAssistant,
) -> None:
    """Test binary sensors."""
    coordinator_mock = _setup_coordinator_mock()
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes

    assert (
        attributes["failsafe"]["start"]
        == dt_util.now().replace(hour=19, minute=0).time()
    )
    assert (
        attributes["failsafe"]["end"] == dt_util.now().replace(hour=22, minute=0).time()
    )

    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 14, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 17, 0, tzinfo=tzinfo)
    assert attributes["expiration"] == datetime(2024, 7, 15, 0, 0, tzinfo=tzinfo)


async def test_cheapest_hours_update_binary_sensors(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor updating with new nordpool data."""
    coordinator_mock = _setup_coordinator_mock()
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2024-07-13 14:25+03:00")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=22,
        last_hour=8,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes

    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 2, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 5, 0, tzinfo=tzinfo)
    assert attributes["expiration"] == datetime(2024, 7, 14, 9, 0, tzinfo=tzinfo)

    # Check updating to the next day values
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240714.json")
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 23, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 15, 1, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["start"] == datetime(2024, 7, 15, 3, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["end"] == datetime(2024, 7, 15, 4, 0, tzinfo=tzinfo)

    assert attributes["expiration"] == datetime(2024, 7, 15, 9, 0, tzinfo=tzinfo)


async def test_cheapest_hours_failsafe_binary_sensors(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors failsafe."""
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=18,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes.get("list") == []
    assert (
        attributes["failsafe"]["start"]
        == dt_util.now().replace(hour=19, minute=0).time()
    )
    assert (
        attributes["failsafe"]["end"] == dt_util.now().replace(hour=22, minute=0).time()
    )

    assert attributes["failsafe_active"] is False

    freezer.move_to("2024-07-13 19:05+03:00")
    await sensor.async_update()
    assert sensor.extra_state_attributes["failsafe_active"] is True

    freezer.move_to("2024-07-13 22:05+03:00")
    await sensor.async_update()
    assert sensor.extra_state_attributes["failsafe_active"] is False


async def test_cheapest_hours_next_item(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors failsafe."""
    coordinator_mock = _setup_coordinator_mock()

    # Move to 13th 14:25, nord pool data is just received
    freezer.move_to("2024-07-13 14:25+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=18,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 18, 0, tzinfo=tzinfo)

    # Move to 14th 00:01, day changed. We're having proper data for this day
    freezer.move_to("2024-07-14 00:01+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240714.json")
    assert sensor
    await sensor.async_update()

    # Move to 14th 14:25. Nord pool data has just updated
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240714.json")
    assert sensor
    await sensor.async_update()

    # We should have list and next in here now
    attributes = sensor.extra_state_attributes
    assert attributes["list"] is not None
    assert attributes["next"] is not None
    assert attributes["expiration"] == datetime(2024, 7, 14, 23, 0, tzinfo=tzinfo)

    # Move to 14th 23:01, data expired
    freezer.move_to("2024-07-14 23:01+03:00")
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes["list"] is not None
    assert attributes.get("next") is None
    assert attributes["expiration"] == datetime(2024, 7, 15, 23, 0, tzinfo=tzinfo)

    # Move to 15th 00:01, day changed
    freezer.move_to("2024-07-15 00:01+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240715.json")
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes["list"] is not None
    assert attributes.get("next") is None
    assert attributes["expiration"] == datetime(2024, 7, 15, 23, 0, tzinfo=tzinfo)


async def test_cheapest_hours_next_nordpool_data_not_updated(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest hours binary sensors with nordpool. Simulate situation when nordpool data passes still old data after midmnight."""
    coordinator_mock = _setup_coordinator_mock()

    # Move to 13th 14:25, nord pool data is just received
    freezer.move_to("2024-07-13 14:25+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 14, 0, tzinfo=tzinfo)

    # Move to 14th 00:01, day changed. We're having proper data for this day
    freezer.move_to("2024-07-14 00:01+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240714.json")
    assert sensor
    await sensor.async_update()

    # Move to 14th 14:25. Nord pool data has just updated
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240714.json")
    assert sensor
    await sensor.async_update()

    # We should have list and next in here now
    attributes = sensor.extra_state_attributes
    assert attributes["list"] is not None
    assert attributes["next"] is not None
    assert attributes["expiration"] == datetime(2024, 7, 15, 0, 0, tzinfo=tzinfo)

    # Move to 15th 00:01, data expired
    # Simulate old data as we don't pass new mock object
    freezer.move_to("2024-07-15 00:01+03:00")
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes["list"] is not None
    assert attributes.get("next") is None
    assert attributes["expiration"] == datetime(2024, 7, 16, 0, 0, tzinfo=tzinfo)

    # Move to 15th 00:01, day changed
    freezer.move_to("2024-07-15 00:01+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240715.json")
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes["list"] is not None
    assert attributes.get("next") is None
    assert attributes["expiration"] == datetime(2024, 7, 16, 0, 0, tzinfo=tzinfo)


async def test_cheapest_hours_entsoe(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors failsafe."""
    coordinator_mock = _setup_coordinator_mock()

    freezer.move_to("2024-09-18 12:00+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    _setup_entsoe_mock(hass, "entsoe_tomorrow_not_valid_20240918.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        entsoe_entity="sensor.entsoe",
        nordpool_entity=None,
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=10,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    assert sensor.extra_state_attributes.get("list") == []
    assert (
        sensor.extra_state_attributes["failsafe"]["start"]
        == dt_util.now().replace(hour=19, minute=0).time()
    )
    assert (
        sensor.extra_state_attributes["failsafe"]["end"]
        == dt_util.now().replace(hour=22, minute=0).time()
    )

    freezer.move_to("2024-09-18 14:30+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    _setup_entsoe_mock(hass, "entsoe_happy_20240918.json")
    await sensor.async_update()
    assert sensor.extra_state_attributes.get("list") is not None
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2024, 9, 19, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2024, 9, 19, 16, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2024, 9, 19, 21, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2024, 9, 19, 23, 0, tzinfo=tzinfo
    )
    freezer.move_to("2024-09-19 14:30+03:00")
    assert sensor.is_on is False
    freezer.move_to("2024-09-19 15:30+03:00")
    await sensor.async_update()
    assert sensor.is_on is True
    freezer.move_to("2024-09-19 16:01+03:00")
    assert sensor.is_on is False


async def test_cheapest_hours_entsoe_over_night(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors over night."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2024-09-18 14:30+03:00")
    _setup_entsoe_mock(hass, "entsoe_happy_20240918.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        entsoe_entity="sensor.entsoe",
        nordpool_entity=None,
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=19,
        last_hour=8,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    assert sensor.extra_state_attributes.get("list") is not None

    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2024, 9, 18, 22, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2024, 9, 19, 1, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["expiration"] == datetime(
        2024, 9, 19, 9, 0, tzinfo=tzinfo
    )

    freezer.move_to("2024-09-19 00:01+03:00")
    _setup_entsoe_mock(hass, "entsoe_tomorrow_not_valid_20240919.json")
    await sensor.async_update()


async def test_cheapest_hours_entsoe_mtu15(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors failsafe."""
    coordinator_mock = _setup_coordinator_mock()

    freezer.move_to("2025-10-28 14:00+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    _setup_entsoe_mock(hass, "entsoe_today_mtu15_20251028.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        entsoe_entity="sensor.entsoe",
        nordpool_entity=None,
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=10,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        mtu=15,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    assert len(sensor.extra_state_attributes.get("list")) == 3
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 10, 29, 11, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 10, 29, 11, 45, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 10, 29, 13, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 10, 29, 15, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][2]["start"] == datetime(
        2025, 10, 29, 22, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][2]["end"] == datetime(
        2025, 10, 29, 23, 0, tzinfo=tzinfo
    )

    assert (
        sensor.extra_state_attributes["failsafe"]["start"]
        == dt_util.now().replace(hour=19, minute=0).time()
    )
    assert (
        sensor.extra_state_attributes["failsafe"]["end"]
        == dt_util.now().replace(hour=22, minute=0).time()
    )


async def test_cheapest_hours_entsoe_mtu15_conversion_to_mtu60(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors failsafe."""
    coordinator_mock = _setup_coordinator_mock()

    freezer.move_to("2025-10-28 14:00+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    _setup_entsoe_mock(hass, "entsoe_today_mtu15_20251028.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        entsoe_entity="sensor.entsoe",
        nordpool_entity=None,
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=10,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        mtu=60,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    assert len(sensor.extra_state_attributes.get("list")) == 2
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 10, 29, 13, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 10, 29, 15, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 10, 29, 22, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 10, 29, 23, 0, tzinfo=tzinfo
    )
    assert (
        sensor.extra_state_attributes["failsafe"]["start"]
        == dt_util.now().replace(hour=19, minute=0).time()
    )
    assert (
        sensor.extra_state_attributes["failsafe"]["end"]
        == dt_util.now().replace(hour=22, minute=0).time()
    )


async def test_trigger_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors trigger time."""
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=18,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
        trigger_time="17:00",
    )

    await sensor.async_update()
    assert sensor.extra_state_attributes.get("list") == []  # TODO:..

    freezer.move_to("2024-07-13 17:00+03:00")
    await sensor.async_update()
    assert sensor.extra_state_attributes.get("list") is not None


async def test_trigger_hour(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors trigger time."""
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=18,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=19,
        coordinator=coordinator_mock,
        trigger_hour=17,
    )

    await sensor.async_update()
    assert sensor.extra_state_attributes.get("list") == []

    freezer.move_to("2024-07-13 17:00+03:00")
    await sensor.async_update()
    assert sensor.extra_state_attributes.get("list") is not None


async def test_max_price(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test cheapest binary sensors max price."""
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        coordinator=coordinator_mock,
        price_limit=-0.7,
    )

    await sensor.async_update()

    # Only one hour should be found that is less than -0.7 max price value
    assert sensor.extra_state_attributes.get("list") is not None

    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2024, 7, 14, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2024, 7, 14, 16, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 1

async def test_price_limit_negative(
        hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors price limit with negative and no matchces."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_20250313.json",
        "nordpool_official_service_20250314.json",
        "nordpool_official_service_20250315.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=22,
        last_hour=7,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        price_limit=-10.0,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()
    assert np.size(sensor.extra_state_attributes["list"]) == 0

async def test_max_price_no_matches(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors max price."""
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Test zero matches
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        coordinator=coordinator_mock,
        price_limit=-0.8,
    )

    await sensor.async_update()

    # Only one hour should be found that is less than -0.7 max price value
    assert sensor.extra_state_attributes.get("list") is not None
    assert np.size(sensor.extra_state_attributes["list"]) == 0


async def test_failsafe(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test cheapest binary sensors failsafe functionality."""
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240714.json")

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=22,
        last_hour=8,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2024-07-14 23:01+03:00")
    await sensor.async_update()

    assert sensor.is_on is False
    assert sensor.extra_state_attributes.get("list") == []

    # Failsafe should be running
    freezer.move_to("2024-07-15 00:00+03:00")
    await sensor.async_update()
    assert sensor.is_on is True
    assert sensor.extra_state_attributes.get("list") == []
    freezer.move_to("2024-07-15 02:59+03:00")
    await sensor.async_update()
    assert sensor.is_on is True

    # Failsafe should be ended
    freezer.move_to("2024-07-15 03:00+03:00")
    await sensor.async_update()
    assert sensor.is_on is False
    assert sensor.extra_state_attributes.get("list") == []


async def test_failsafe_not_triggering_after_last_hour(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test cheapest binary sensors failsafe functionality."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2024-07-13 23:01+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2024, 7, 15, 0, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes.get("next") is None

    freezer.move_to("2024-07-14 00:01+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240714.json")
    await sensor.async_update()
    assert sensor.extra_state_attributes["expiration"] == datetime(
        2024, 7, 15, 0, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes.get("next") is None

    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240714.json")
    await sensor.async_update()
    assert sensor.extra_state_attributes["expiration"] == datetime(
        2024, 7, 15, 0, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["next"]["expiration"] == datetime(
        2024, 7, 16, 0, 0, tzinfo=tzinfo
    )

    freezer.move_to("2024-07-15 00:01+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240715.json")
    await sensor.async_update()
    assert sensor.extra_state_attributes["failsafe_active"] is False


async def test_cheapest_hours_binary_sensors_daylight_savings_sequential_summer_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test summer time binary sensors."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    hass.config.timezone = tzinfo
    coordinator_mock = _setup_coordinator_mock()

    # Test today summer time
    freezer.move_to("2024-07-13 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_tomorrow_summertime.json")
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=20,
        last_hour=12,
        starting_today=True,
        number_of_hours=3,
        sequential=True,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 10, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 13, 0, tzinfo=tzinfo)

    # Test today summer time
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_today_summertime.json")
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 23, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 15, 2, 0, tzinfo=tzinfo)


async def test_cheapest_hours_binary_sensors_daylight_savings_non_sequential_summer_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test summer time binary sensors."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    hass.config.timezone = tzinfo
    coordinator_mock = _setup_coordinator_mock()

    # Test today summer time
    freezer.move_to("2024-07-13 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_tomorrow_summertime.json")
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=20,
        last_hour=12,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes

    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 10, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 13, 0, tzinfo=tzinfo)

    # Test today summer time
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_today_summertime.json")
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert np.size(attributes["list"]) == 2
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 23, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 15, 1, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["start"] == datetime(2024, 7, 15, 3, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["end"] == datetime(2024, 7, 15, 4, 0, tzinfo=tzinfo)


async def test_cheapest_hours_offset(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test summer time binary sensors."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    hass.config.timezone = tzinfo
    coordinator_mock = _setup_coordinator_mock()

    # Test today summer time
    freezer.move_to("2024-07-13 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240713_cheapest_last.json")
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=1,
        sequential=True,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
        offset={"start": {"minutes": 30}, "end": {"minutes": 45}},
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(
        2024, 7, 14, 23, 30, tzinfo=tzinfo
    )

    # Move to next day
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_20240714_cheapest_first.json")
    await sensor.async_update()

    attributes = sensor.extra_state_attributes

    assert attributes["list"][0]["start"] == datetime(
        2024, 7, 14, 23, 30, tzinfo=tzinfo
    )
    assert attributes["list"][0]["end"] == datetime(2024, 7, 15, 0, 45, tzinfo=tzinfo)

    # Expiration needs to be extended
    assert attributes["expiration"] == datetime(2024, 7, 15, 0, 45, tzinfo=tzinfo)
    assert attributes["next"]["list"][0]["start"] == datetime(
        2024, 7, 15, 0, 30, tzinfo=tzinfo
    )
    assert attributes["next"]["list"][0]["end"] == datetime(
        2024, 7, 15, 1, 45, tzinfo=tzinfo
    )
    assert attributes["next"]["expiration"] == datetime(
        2024, 7, 16, 0, 0, tzinfo=tzinfo
    )

    # Move to after original expiration, but before new expiration. Previous list should still be kept
    freezer.move_to("2024-07-15 00:30+03:00")
    _setup_nordpool_mock(hass, "nordpool_tomorrow_not_valid_20240715.json")
    await sensor.async_update()
    assert sensor.extra_state_attributes == attributes

    # Move to after new expiration, list_swap should have been made
    freezer.move_to("2024-07-15 00:46+03:00")
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 15, 0, 30, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 15, 1, 45, tzinfo=tzinfo)
    assert attributes["expiration"] == datetime(2024, 7, 16, 0, 0, tzinfo=tzinfo)


async def test_cheapest_hours_binary_sensors_daylight_savings_non_sequential_winter_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test summer time binary sensors."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    hass.config.timezone = tzinfo
    coordinator_mock = _setup_coordinator_mock()

    # Test today summer time
    freezer.move_to("2024-07-13 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_tomorrow_wintertime.json")
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=20,
        last_hour=12,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()

    attributes = sensor.extra_state_attributes

    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 10, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 13, 0, tzinfo=tzinfo)

    # Test today summer time
    freezer.move_to("2024-07-14 14:25+03:00")
    _setup_nordpool_mock(hass, "nordpool_happy_today_wintertime.json")
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert np.size(attributes["list"]) == 2
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 23, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 15, 1, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["start"] == datetime(2024, 7, 15, 3, 0, tzinfo=tzinfo)
    assert attributes["list"][1]["end"] == datetime(2024, 7, 15, 4, 0, tzinfo=tzinfo)


async def test_nordpool_official(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_20250313.json",
        "nordpool_official_service_20250314.json",
        "nordpool_official_service_20250315.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 1
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 3, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 6, 0, tzinfo=tzinfo
    )


async def test_nordpool_official_15min_to_60min(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration and convert to 60min."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_15min_yesterday.json",
        "nordpool_official_service_15min_today.json",
        "nordpool_official_service_15min_tomorrow.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 2
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 11, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 13, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 16, 0, tzinfo=tzinfo
    )


async def test_nordpool_official_15min_mtu_non_sequential(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration, 15min mtu, non-sequential."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_15min_yesterday.json",
        "nordpool_official_service_15min_today.json",
        "nordpool_official_service_15min_tomorrow.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=15,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 3
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 10, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 10, 45, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 11, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 13, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][2]["start"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][2]["end"] == datetime(
        2025, 3, 15, 16, 0, tzinfo=tzinfo
    )


async def test_nordpool_official_15min_mtu_sequential(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration, 15min mtu, sequential."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_15min_yesterday.json",
        "nordpool_official_service_15min_today.json",
        "nordpool_official_service_15min_tomorrow.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=True,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=15,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 1
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 10, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 13, 15, tzinfo=tzinfo
    )


async def test_nordpool_official_15min_mtu_summer_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration, 15min mtu, non-sequential, summer time transition."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_15min_yesterday.json",
        "nordpool_official_service_15min_today.json",
        "nordpool_official_service_15min_tomorrow_summertime.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=15,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 3
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 10, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 10, 45, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 11, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 13, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][2]["start"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][2]["end"] == datetime(
        2025, 3, 15, 16, 0, tzinfo=tzinfo
    )


async def test_nordpool_official_15min_mtu_summer_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration, 15min mtu, non-sequential, DST spring-forward transition.

    On the spring-forward night (March 28→29), tomorrow has only 23 local hours.
    The fix ensures that all 92 fifteen-minute slots are correctly gathered from the
    combined yesterday+today+tomorrow data using time-range filtering, rather than
    date-equality filtering which incorrectly excluded UTC entries crossing local midnight.
    """
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    hass.config.timezone = zoneinfo.ZoneInfo("Europe/Helsinki")
    # Stay at 2026-03-28 to match the fixture dates (tomorrow = 2026-03-29, DST day)
    freezer.move_to("2026-03-28 14:25+02:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_dst_summer_15min_20260327.json",
        "nordpool_official_dst_summer_15min_20260328.json",
        "nordpool_official_dst_summer_15min_20260329.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_slots=8,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=15,
    )
    await sensor.async_update()

    # The list must have 6 cheapest non-sequential 15-min slots selected from
    # the DST spring-forward day (March 29, 2026, Helsinki EEST).
    # Before the fix, tomorrow_prices was [] due to date-equality filtering
    # excluding UTC entries that crossed local midnight on the spring-forward day.
    result_list = sensor.extra_state_attributes["list"]
    assert len(result_list) == 6

    assert result_list[0]["start"] == datetime(2026, 3, 29, 13, 30, tzinfo=tzinfo)
    assert result_list[0]["end"] == datetime(2026, 3, 29, 14, 0, tzinfo=tzinfo)

    assert result_list[1]["start"] == datetime(2026, 3, 29, 14, 30, tzinfo=tzinfo)
    assert result_list[1]["end"] == datetime(2026, 3, 29, 14, 45, tzinfo=tzinfo)

    assert result_list[2]["start"] == datetime(2026, 3, 29, 18, 0, tzinfo=tzinfo)
    assert result_list[2]["end"] == datetime(2026, 3, 29, 18, 15, tzinfo=tzinfo)

    assert result_list[3]["start"] == datetime(2026, 3, 29, 21, 45, tzinfo=tzinfo)
    assert result_list[3]["end"] == datetime(2026, 3, 29, 22, 0, tzinfo=tzinfo)

    assert result_list[4]["start"] == datetime(2026, 3, 29, 22, 45, tzinfo=tzinfo)
    assert result_list[4]["end"] == datetime(2026, 3, 29, 23, 0, tzinfo=tzinfo)

    assert result_list[5]["start"] == datetime(2026, 3, 29, 23, 30, tzinfo=tzinfo)
    assert result_list[5]["end"] == datetime(2026, 3, 30, 0, 0, tzinfo=tzinfo)

    # Expiration is midnight of the day after tomorrow (March 30 00:00 EET+3)
    assert sensor.extra_state_attributes["expiration"] == datetime(
        2026, 3, 30, 0, 0, tzinfo=tzinfo
    )


async def test_nordpool_official_60min_mtu_summer_time_starting_today(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration, 15min mtu, non-sequential, DST spring-forward transition.

    On the spring-forward night (March 28→29), tomorrow has only 23 local hours.
    The fix ensures that all 92 fifteen-minute slots are correctly gathered from the
    combined yesterday+today+tomorrow data using time-range filtering, rather than
    date-equality filtering which incorrectly excluded UTC entries crossing local midnight.
    """
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    hass.config.timezone = zoneinfo.ZoneInfo("Europe/Helsinki")
    # Stay at 2026-03-28 to match the fixture dates (tomorrow = 2026-03-29, DST day)
    freezer.move_to("2026-03-28 14:25+02:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_dst_summer_60min_20260327.json",
        "nordpool_official_dst_summer_60min_20260328.json",
        "nordpool_official_dst_summer_60min_20260329.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=20,
        last_hour=14,
        starting_today=True,
        number_of_slots=4,
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=60,
    )
    await sensor.async_update()

    # 4 cheapest non-sequential 1-hour slots (starting_today=True, spanning
    # today evening and the DST spring-forward day of March 29, 2026 Helsinki).
    result_list = sensor.extra_state_attributes["list"]
    assert len(result_list) == 2

    assert result_list[0]["start"] == datetime(2026, 3, 28, 23, 0, tzinfo=tzinfo)
    assert result_list[0]["end"] == datetime(2026, 3, 29, 1, 0, tzinfo=tzinfo)

    assert result_list[1]["start"] == datetime(2026, 3, 29, 13, 0, tzinfo=tzinfo)
    assert result_list[1]["end"] == datetime(2026, 3, 29, 15, 0, tzinfo=tzinfo)


async def test_nordpool_number_of_slots_mtu15(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    # Set Helsinki as default timezone so DST gap detection uses the correct local time.
    dt_util.set_default_time_zone(tzinfo)
    freezer.move_to("2024-07-13 14:25+03:00")

    # 15min mtu
    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_15min_yesterday.json",
        "nordpool_official_service_15min_today.json",
        "nordpool_official_service_15min_tomorrow_summertime.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_slots=2,  # Two slots, 15min each
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=15,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 1
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 15, 30, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["active_number_of_slots"] == 2
    assert (
        sensor.extra_state_attributes["failsafe"]["start"]
        == datetime.now().replace(hour=0, minute=0).time()
    )
    assert (
        sensor.extra_state_attributes["failsafe"]["end"]
        == datetime.now().replace(hour=0, minute=30).time()
    )


async def test_nordpool_number_of_slots_mtu60(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    # 15min mtu
    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_15min_yesterday.json",
        "nordpool_official_service_15min_today.json",
        "nordpool_official_service_15min_tomorrow_summertime.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_slots=2,  # Two slots, 60min each
        sequential=False,
        failsafe_starting_hour=0,
        coordinator=coordinator_mock,
        mtu=60,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 2
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 11, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 12, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 16, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["active_number_of_slots"] == 2
    assert (
        sensor.extra_state_attributes["failsafe"]["start"]
        == datetime.now().replace(hour=0, minute=0).time()
    )
    assert (
        sensor.extra_state_attributes["failsafe"]["end"]
        == datetime.now().replace(hour=2, minute=0).time()
    )

# =============================================
# Price modifications tests
# =============================================

async def test_price_modifications(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test official nord pool integration."""
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
    coordinator_mock = _setup_coordinator_mock()
    freezer.move_to("2024-07-13 14:25+03:00")

    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_20250313.json",
        "nordpool_official_service_20250314.json",
        "nordpool_official_service_20250315.json",
    )

    template = Template("""
            {%- set with_taxes = (price * 2) | float %}
        {%- if time.hour >= 22 or time.hour <= 7 %}
          {{ with_taxes + 10 }}
        {%- else %}
          {{ with_taxes + 5 }}
        {%- endif %}""", hass)

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        price_modifications=template,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["expiration"] == datetime(
        2025, 3, 16, 0, 0, tzinfo=tzinfo
    )

    assert np.size(sensor.extra_state_attributes["list"]) == 1
    assert sensor.extra_state_attributes["list"][0]["start"] == datetime(
        2025, 3, 15, 10, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 13, 0, tzinfo=tzinfo
    )

async def test_nordpool_official_price_modifications_timezone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test 60min vs 15min mtu."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    # --- Test with Nord Pool official integration
    freezer.move_to("2026-03-23 14:30+02:00")
    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_20260322_15min.json",
        "nordpool_official_20260323_15min.json",
        "nordpool_official_20260324_15min.json",
    )

    tmpl = Template(
        """
      {%- set as_snt = price / 10.0 %}
        {%- set with_taxes = (as_snt * 1.255) | float %}
        {%- if time.hour >= 22 or time.hour < 7 %}
          {{ with_taxes + 3.062 }}
        {%- else %}
          {{ with_taxes + 4.68 }}
        {%- endif %}""",
        hass,
    )

    # If price modifications would be UTC+0, the calculations would cause the +1 to all values
    # See https://github.com/kotope/aio_energy_management/issues/147 for more details
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=21,
        last_hour=7,
        starting_today=True,
        number_of_hours=3,
        sequential=True,
        failsafe_starting_hour=0,
        price_modifications=tmpl,
        coordinator=coordinator_mock,
    )

    freezer.move_to("2026-03-23 14:30+02:00")
    await sensor.async_update()

    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2026, 3, 23, 23, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2026, 3, 24, 2, 0, tzinfo=tzinfo)


async def test_nordpool_custom_price_modifications_timezone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test 60min vs 15min mtu."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    tmpl = Template(
        """
      {%- set as_snt = price / 10.0 %}
        {%- set with_taxes = (as_snt * 1.255) | float %}
        {%- if time.hour >= 22 or time.hour < 7 %}
          {{ with_taxes + 3.062 }}
        {%- else %}
          {{ with_taxes + 4.68 }}
        {%- endif %}""",
        hass,
    )

    # --- Test with nord pool custom integration
    _setup_nordpool_mock(hass, "nordpool_happy_20240713.json")

    # Create sensor to test
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_entity="sensor.nordpool",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=21,
        last_hour=7,
        starting_today=True,
        number_of_hours=3,
        sequential=True,
        failsafe_starting_hour=1,
        price_modifications=tmpl,
        coordinator=coordinator_mock,
    )
    freezer.move_to("2024-07-13 14:30+02:00")
    await sensor.async_update()
    attributes = sensor.extra_state_attributes
    assert attributes["list"][0]["start"] == datetime(2024, 7, 14, 2, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2024, 7, 14, 5, 0, tzinfo=tzinfo)



# =============================================
# Strømligning tests
# =============================================


async def test_cheapest_hours_stromligning_non_sequential(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Strømligning non-sequential cheapest hours."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2026-04-01 15:00+03:00")
    _setup_stromligning_mock(
        hass,
        "stromligning_today_20260401.json",
        "stromligning_tomorrow_20260402.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        stromligning_entity="sensor.stromligning_current_price_vat",
        stromligning_tomorrow_entity="binary_sensor.stromligning_tomorrow_available_vat",
        unique_id="my_stromligning_sensor",
        name="My Strømligning Sensor",
        first_hour=21,
        last_hour=8,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    assert attributes.get("list") is not None
    assert len(attributes["list"]) > 0
    assert attributes["inversed"] is False

    # The 3 cheapest hours between 21:00 today and 08:00 tomorrow should be
    # from the lowest prices in that range:
    # Today 21:00=1.650230, 22:00=1.420340, 23:00=1.280120
    # Tomorrow 00:00=1.380120, 01:00=1.250340, 02:00=1.180890,
    #          03:00=1.120450, 04:00=1.050230, 05:00=1.110340,
    #          06:00=1.380120, 07:00=1.720890
    # Cheapest 3: 04:00=1.050230, 05:00=1.110340, 03:00=1.120450
    assert attributes["list"][0]["start"] == datetime(2026, 4, 2, 3, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2026, 4, 2, 6, 0, tzinfo=tzinfo)

    # Verify sensor is off before cheapest hours
    freezer.move_to("2026-04-01 23:00+03:00")
    assert sensor.is_on is False

    # Move to cheapest hour (04:00)
    freezer.move_to("2026-04-02 05:30+03:00")
    assert sensor.is_on is True

    # Move past cheapest hours
    freezer.move_to("2026-04-02 07:30+03:00")
    assert sensor.is_on is False


async def test_cheapest_hours_stromligning_sequential(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Strømligning sequential cheapest hours."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2026-04-01 15:00+03:00")
    _setup_stromligning_mock(
        hass,
        "stromligning_today_20260401.json",
        "stromligning_tomorrow_20260402.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        stromligning_entity="sensor.stromligning_current_price_vat",
        stromligning_tomorrow_entity="binary_sensor.stromligning_tomorrow_available_vat",
        unique_id="my_stromligning_sequential",
        name="My Strømligning Sequential",
        first_hour=21,
        last_hour=8,
        starting_today=True,
        number_of_hours=3,
        sequential=True,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    assert attributes.get("list") is not None
    assert len(attributes["list"]) == 1

    # Sequential 3 hours: cheapest consecutive block between 21-08
    # 03:00=1.120450, 04:00=1.050230, 05:00=1.110340 => sum=3.281020
    assert attributes["list"][0]["start"] == datetime(2026, 4, 2, 3, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2026, 4, 2, 6, 0, tzinfo=tzinfo)

    # Verify is_on during sequential block
    freezer.move_to("2026-04-02 05:00+03:00")
    assert sensor.is_on is True

    freezer.move_to("2026-04-02 07:01+03:00")
    assert sensor.is_on is False


async def test_cheapest_hours_stromligning_tomorrow_not_available(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Strømligning when tomorrow prices are not yet available."""
    coordinator_mock = _setup_coordinator_mock()

    freezer.move_to("2026-04-01 11:00+03:00")
    _setup_stromligning_mock(
        hass,
        "stromligning_today_20260401.json",
        "stromligning_tomorrow_not_available.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        stromligning_entity="sensor.stromligning_current_price_vat",
        stromligning_tomorrow_entity="binary_sensor.stromligning_tomorrow_available_vat",
        unique_id="my_stromligning_no_tomorrow",
        name="My Strømligning No Tomorrow",
        first_hour=21,
        last_hour=8,
        starting_today=True,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=1,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    # Should have empty list since tomorrow data is not available
    assert attributes.get("list") == []
    assert (
        attributes["failsafe"]["start"]
        == datetime.now().replace(hour=1, minute=0).time()
    )
    assert (
        attributes["failsafe"]["end"] == datetime.now().replace(hour=4, minute=0).time()
    )


async def test_cheapest_hours_stromligning_expensive_hours(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Strømligning inversed (expensive hours)."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2026-04-01 15:00+03:00")
    _setup_stromligning_mock(
        hass,
        "stromligning_today_20260401.json",
        "stromligning_tomorrow_20260402.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        stromligning_entity="sensor.stromligning_current_price_vat",
        stromligning_tomorrow_entity="binary_sensor.stromligning_tomorrow_available_vat",
        unique_id="my_stromligning_expensive",
        name="My Strømligning Expensive",
        first_hour=16,
        last_hour=22,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=17,
        coordinator=coordinator_mock,
        inversed=True,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    assert attributes.get("list") is not None
    assert len(attributes["list"]) > 0
    assert attributes["inversed"] is True

    # Verify the expensive hours were found
    assert len(attributes["list"]) == 1

    # Check is_on outside expensive hours (before the block)
    freezer.move_to("2026-04-02 16:30+03:00")
    assert sensor.is_on is False

    # Check is_on during expensive hours
    freezer.move_to("2026-04-02 19:00+03:00")
    assert sensor.is_on is True


async def test_cheapest_hours_stromligning_daytime(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test Strømligning with daytime window (not overnight)."""
    coordinator_mock = _setup_coordinator_mock()
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    freezer.move_to("2026-04-01 15:00+03:00")
    _setup_stromligning_mock(
        hass,
        "stromligning_today_20260401.json",
        "stromligning_tomorrow_20260402.json",
    )

    sensor = CheapestHoursBinarySensor(
        hass=hass,
        stromligning_entity="sensor.stromligning_current_price_vat",
        stromligning_tomorrow_entity="binary_sensor.stromligning_tomorrow_available_vat",
        unique_id="my_stromligning_daytime",
        name="My Strømligning Daytime",
        first_hour=8,
        last_hour=16,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        coordinator=coordinator_mock,
    )
    await sensor.async_update()
    attributes = sensor.extra_state_attributes

    assert attributes.get("list") is not None
    assert len(attributes["list"]) > 0

    # Hours 8-16 Helsinki = 7-15 Copenhagen in tomorrow data
    # Helsinki 8=Cph7(1.72089), 9=Cph8(2.05045), 10=Cph9(2.18023),
    # 11=Cph10(1.95034), 12=Cph11(1.72012), 13=Cph12(1.55089),
    # 14=Cph13(1.42045), 15=Cph14(1.35023)
    # Cheapest 3: Hel15(1.35023), Hel14(1.42045), Hel13(1.55089)
    # Contiguous block: 13:00-16:00 Helsinki
    assert attributes["list"][0]["start"] == datetime(2026, 4, 2, 13, 0, tzinfo=tzinfo)
    assert attributes["list"][0]["end"] == datetime(2026, 4, 2, 16, 0, tzinfo=tzinfo)

    freezer.move_to("2026-04-02 14:30+03:00")
    assert sensor.is_on is True


