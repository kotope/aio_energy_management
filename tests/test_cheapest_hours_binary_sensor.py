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


def _setup_nordpool_official_mock(
    hass: HomeAssistant, fixture_today: str, fixture_tomorrow: str
) -> None:
    """Set up the Nordpool official mock service."""
    mocked_nordpool_official_today = json.loads(load_fixture(fixture_today, DOMAIN))
    mocked_nordpool_official_tomorrow = json.loads(
        load_fixture(fixture_tomorrow, DOMAIN)
    )
    call_counter = 0

    async def mock_service_call(service_call):
        nonlocal call_counter
        call_counter += 1
        if call_counter == 1:
            return mocked_nordpool_official_today
        return mocked_nordpool_official_tomorrow

    hass.services.async_register(
        "nordpool",
        "get_prices_for_date",
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
        2025, 3, 15, 2, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 5, 0, tzinfo=tzinfo
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
        2025, 3, 15, 10, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 12, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 14, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
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
        2025, 3, 15, 9, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 9, 45, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 10, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 12, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][2]["start"] == datetime(
        2025, 3, 15, 14, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][2]["end"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
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
        2025, 3, 15, 9, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 12, 15, tzinfo=tzinfo
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
        2025, 3, 15, 9, 30, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][0]["end"] == datetime(
        2025, 3, 15, 9, 45, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][1]["start"] == datetime(
        2025, 3, 15, 10, 15, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][1]["end"] == datetime(
        2025, 3, 15, 12, 0, tzinfo=tzinfo
    )

    assert sensor.extra_state_attributes["list"][2]["start"] == datetime(
        2025, 3, 15, 14, 0, tzinfo=tzinfo
    )
    assert sensor.extra_state_attributes["list"][2]["end"] == datetime(
        2025, 3, 15, 15, 0, tzinfo=tzinfo
    )
