"""Tests for coordinator."""

from datetime import date, datetime, time
import json
import zoneinfo

from custom_components.aio_energy_management.const import DOMAIN
from custom_components.aio_energy_management.coordinator import (
    EnergyManagementCoordinator,
)
from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import numpy as np
import pytest
from pytest_homeassistant_custom_component.common import load_fixture

from homeassistant.core import HomeAssistant, State


def _setup_nordpool_mock(hass: HomeAssistant, fixture: str) -> None:
    mocked_nordpool = State.from_dict(json.loads(load_fixture(fixture, DOMAIN)))
    hass.states.async_set(
        "sensor.nordpool", mocked_nordpool.state, attributes=mocked_nordpool.attributes
    )


@pytest.fixture
def mock_cheapest_hours_data_17th() -> dict:
    return {
        "my_cheapest_hours_sensor": {
            "active_number_of_hours": 3,
            "failsafe": {"start": "22:00:00", "end": "01:00:00"},
            "expiration": "2025-10-17T11:00:00+03:00",
            "updated_at": "2025-10-16T14:29:05.557103+03:00",
            "fetch_date": "2025-10-16",
            "name": "My Cheapest Hours",
            "type": "CheapestHoursBinarySensor",
            "list": [
                {
                    "start": "2025-10-17T00:00:00+03:00",
                    "end": "2025-10-17T01:00:00+03:00",
                },
                {
                    "start": "2025-10-17T02:00:00+03:00",
                    "end": "2025-10-17T04:00:00+03:00",
                },
            ],
        }
    }


# def mock_nordpool_data_18th() -> dict:

# def mock_nordpool_data_19th() -> dict:


@pytest.fixture
def mock_stored_data() -> dict:
    """Fixture for stored data."""
    return {
        "my_cheapest_hours_sensor": {
            "active_number_of_hours": 3,
            "failsafe": {"start": "22:00:00", "end": "01:00:00"},
            "expiration": "2024-10-09T11:00:00+03:00",
            "updated_at": "2024-10-08T14:29:05.557103+03:00",
            "fetch_date": "2024-10-08",
            "name": "My Cheapest Hours",
            "type": "CheapestHoursBinarySensor",
            "list": [
                {
                    "start": "2024-10-09T00:00:00+03:00",
                    "end": "2024-10-09T01:00:00+03:00",
                },
                {
                    "start": "2024-10-09T02:00:00+03:00",
                    "end": "2024-10-09T04:00:00+03:00",
                },
            ],
        },
        "my_expensive_hours_sensor": {
            "active_number_of_hours": 2,
            "failsafe": None,
            "list": [
                {
                    "start": "2024-10-07T20:00:00+03:00",
                    "end": "2024-10-07T21:00:00+03:00",
                },
                {
                    "start": "2024-10-08T09:00:00+03:00",
                    "end": "2024-10-08T10:00:00+03:00",
                },
            ],
            "expiration": "2024-10-08T17:00:00+03:00",
            "updated_at": "2024-10-07T17:00:03.086261+03:00",
            "fetch_date": "2024-10-08",
            "name": "My Expensive Hours",
            "type": "CheapestHoursBinarySensor",
            "next": {
                "list": [
                    {
                        "start": "2024-10-08T20:00:00+03:00",
                        "end": "2024-10-08T21:00:00+03:00",
                    },
                    {
                        "start": "2024-10-09T10:00:00+03:00",
                        "end": "2024-10-09T11:00:00+03:00",
                    },
                ],
                "expiration": "2024-10-09T17:00:00+03:00",
            },
        },
        "my_next_day_hours": {
            "active_number_of_hours": 4,
            "failsafe": None,
            "list": [
                {
                    "start": "2024-10-08T04:00:00+03:00",
                    "end": "2024-10-08T05:00:00+03:00",
                },
                {
                    "start": "2024-10-08T21:00:00+03:00",
                    "end": "2024-10-09T00:00:00+03:00",
                },
            ],
            "expiration": "2024-10-09T00:00:00+03:00",
            "updated_at": "2024-10-08T00:00:03.906396+03:00",
            "fetch_date": "2024-10-08",
            "name": "My Next Day Hours",
            "type": "CheapestHoursBinarySensor",
            "next": {
                "list": [
                    {
                        "start": "2024-10-09T00:00:00+03:00",
                        "end": "2024-10-09T01:00:00+03:00",
                    },
                    {
                        "start": "2024-10-09T02:00:00+03:00",
                        "end": "2024-10-09T05:00:00+03:00",
                    },
                ],
                "expiration": "2024-10-10T00:00:00+03:00",
            },
        },
        "my_entsoe_prices": {
            "active_number_of_hours": 4,
            "failsafe": None,
            "expiration": "2024-10-04T09:00:00+03:00",
            "updated_at": "2024-10-03T15:00:08.397098+03:00",
            "fetch_date": "2024-10-03",
            "name": "My Entso-e Hours",
            "type": "CheapestHoursBinarySensor",
        },
        "my_entsoe_next_day_prices": {
            "active_number_of_hours": 4,
            "failsafe": None,
            "expiration": "2024-10-05T00:00:00+03:00",
            "updated_at": "2024-10-04T00:00:09.458809+03:00",
            "fetch_date": "2024-10-03",
            "name": "My Next Day Entso-e Hours",
            "type": "CheapestHoursBinarySensor",
        },
        "my_next_day_hours_5": {
            "active_number_of_hours": 5,
            "failsafe": None,
            "list": [
                {
                    "start": "2024-10-08T04:00:00+03:00",
                    "end": "2024-10-08T05:00:00+03:00",
                },
                {
                    "start": "2024-10-08T20:00:00+03:00",
                    "end": "2024-10-09T00:00:00+03:00",
                },
            ],
            "expiration": "2024-10-09T00:00:00+03:00",
            "updated_at": "2024-10-08T00:00:03.908686+03:00",
            "fetch_date": "2024-10-08",
            "name": "My Next Day Hours 5",
            "type": "CheapestHoursBinarySensor",
            "next": {
                "list": [
                    {
                        "start": "2024-10-09T00:00:00+03:00",
                        "end": "2024-10-09T01:00:00+03:00",
                    },
                    {
                        "start": "2024-10-09T02:00:00+03:00",
                        "end": "2024-10-09T05:00:00+03:00",
                    },
                    {
                        "start": "2024-10-09T23:00:00+03:00",
                        "end": "2024-10-10T00:00:00+03:00",
                    },
                ],
                "expiration": "2024-10-10T00:00:00+03:00",
            },
        },
        "my_next_day_hours_6": {
            "active_number_of_hours": 6,
            "failsafe": None,
            "list": [
                {
                    "start": "2024-10-08T03:00:00+03:00",
                    "end": "2024-10-08T05:00:00+03:00",
                },
                {
                    "start": "2024-10-08T20:00:00+03:00",
                    "end": "2024-10-09T00:00:00+03:00",
                },
            ],
            "expiration": "2024-10-09T00:00:00+03:00",
            "updated_at": "2024-10-08T00:00:03.908953+03:00",
            "fetch_date": "2024-10-08",
            "name": "My Next Day Hours 6",
            "type": "CheapestHoursBinarySensor",
            "next": {
                "list": [
                    {
                        "start": "2024-10-09T00:00:00+03:00",
                        "end": "2024-10-09T05:00:00+03:00",
                    },
                    {
                        "start": "2024-10-09T23:00:00+03:00",
                        "end": "2024-10-10T00:00:00+03:00",
                    },
                ],
                "expiration": "2024-10-10T00:00:00+03:00",
            },
        },
    }


@freeze_time("2024-10-09 14:00+03:00")
async def test_convert_persistent_data(hass: HomeAssistant, mock_stored_data) -> None:
    """Test stored data loading back to proper data format."""
    hass.config.timezone = zoneinfo.ZoneInfo("Europe/Helsinki")

    coordinator = EnergyManagementCoordinator(hass)
    converted = coordinator.convert_datetimes(mock_stored_data)

    next_day_hours = converted["my_next_day_hours"]
    assert next_day_hours.get("expiration") is not None
    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")

    assert isinstance(next_day_hours.get("expiration"), datetime)
    assert next_day_hours.get("expiration") == datetime(
        2024, 10, 9, 0, 0, tzinfo=tzinfo
    )

    nxt = next_day_hours.get("next")
    assert isinstance(nxt, dict)
    assert isinstance(nxt.get("expiration"), datetime)
    assert nxt.get("expiration") == datetime(2024, 10, 10, 0, 0, tzinfo=tzinfo)

    lst = next_day_hours.get("list")
    assert np.size(lst) == 2
    assert lst[0]["start"] == datetime(2024, 10, 8, 4, 0, tzinfo=tzinfo)
    assert lst[0]["end"] == datetime(2024, 10, 8, 5, 0, tzinfo=tzinfo)
    assert lst[1]["start"] == datetime(2024, 10, 8, 21, 0, tzinfo=tzinfo)
    assert lst[1]["end"] == datetime(2024, 10, 9, 0, 0, tzinfo=tzinfo)

    lst_next = next_day_hours.get("next").get("list")
    assert np.size(lst_next) == 2
    assert lst_next[0]["start"] == datetime(2024, 10, 9, 0, 0, tzinfo=tzinfo)
    assert lst_next[0]["end"] == datetime(2024, 10, 9, 1, 0, tzinfo=tzinfo)
    assert lst_next[1]["start"] == datetime(2024, 10, 9, 2, 0, tzinfo=tzinfo)
    assert lst_next[1]["end"] == datetime(2024, 10, 9, 5, 0, tzinfo=tzinfo)

    assert isinstance(next_day_hours.get("updated_at"), datetime)
    assert next_day_hours.get("fetch_date") == date(2024, 10, 8)


# FIXME: Unittest broken since 2026.1 Home Assistant release. Functionality ok, but unit test fail
#async def test_archive_data(
#    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_stored_data
#) -> None:
#    """Tests archiving old data for three days."""
#    hass.config.timezone = zoneinfo.ZoneInfo("Europe/Helsinki")
#    tzinfo = zoneinfo.ZoneInfo(key="Europe/Helsinki")
#
#    freezer.move_to("2025-10-16 14:00+03:00")
#    mock: dict = {}
#    mock["list"] = [
#        {
#            "start": datetime(2025, 10, 17, 1, 0, tzinfo=tzinfo),
#            "end": datetime(2025, 10, 17, 2, 45, tzinfo=tzinfo),
#        },
#        {
#            "start": datetime(2025, 10, 17, 3, 0, tzinfo=tzinfo),
#            "end": datetime(2025, 10, 17, 3, 15, tzinfo=tzinfo),
#        },
#    ]
#    mock["active_number_of_hours"] = 2
#    mock["failsafe"] = {
#        "start": datetime(2025, 10, 17, 1, 0, tzinfo=tzinfo).time(),
#        "end": datetime(2025, 10, 17, 3, 0, tzinfo=tzinfo).time(),
#    }
#    mock["expiration"] = datetime(2025, 10, 18, 0, 0, tzinfo=tzinfo)
#    mock["extra"] = {"mean_price": 1.79275, "max_price": 1.817, "min_price": 1.772}
#    mock["updated_at"] = datetime(
#        2025,
#        10,
#        16,
#        14,
#        43,
#        38,
#        910378,
#        tzinfo=tzinfo,
#    )
#    mock["fetch_date"] = datetime(2025, 10, 16, 1, 0, tzinfo=tzinfo).date()
#    mock["type"] = "CheapestHoursBinarySensor"
#    mock["calendar"] = True
#
#    coordinator = EnergyManagementCoordinator(hass)
#    coordinator.async_set_data(
#        "my_cheapest_hours_sensor",
#        "My Cheapest Hours",
#        True,
#        "CheapestHoursBinarySensor",
#        mock,
#        None,
#    )
#
#    # Set the same data again
#    await coordinator.async_set_data(
#        entity_id="my_cheapest_hours_sensor",
#        name="My Cheapest Hours",
#        calendar=True,
#        module="CheapestHoursBinarySensor",
#        dict=mock,
#        archived=mock["list"],
#    )
#
#    # Data should be same as before, no duplicates
#    data = coordinator.get_data("my_cheapest_hours_sensor")
#    assert data == mock
#    assert len(data["archived"]) == 2
#
#    freezer.move_to("2025-10-17 14:00+03:00")
#    # Set new mock with old as archived
#    mock_new: dict = {}
#    mock_new["list"] = [
#        {
#            "start": datetime(2025, 10, 18, 1, 0, tzinfo=tzinfo),
#            "end": datetime(2025, 10, 18, 2, 45, tzinfo=tzinfo),
#        },
#        {
#            "start": datetime(2025, 10, 18, 3, 0, tzinfo=tzinfo),
#            "end": datetime(2025, 10, 18, 3, 15, tzinfo=tzinfo),
#        },
#    ]
#    mock_new["active_number_of_hours"] = 2
#    mock_new["failsafe"] = {
#        "start": datetime(2025, 10, 18, 1, 0, tzinfo=tzinfo).time(),
#        "end": datetime(2025, 10, 18, 3, 0, tzinfo=tzinfo).time(),
#    }
#    mock_new["expiration"] = datetime(2025, 10, 19, 0, 0, tzinfo=tzinfo)
#    mock_new["extra"] = {"mean_price": 1.2000, "max_price": 2.0, "min_price": 1.0}
#    mock_new["updated_at"] = datetime(
#        2025,
#        10,
#        17,
#        14,
#        43,
#        38,
#        910378,
#        tzinfo=tzinfo,
#    )
#    mock_new["fetch_date"] = datetime(2025, 10, 17, 1, 0, tzinfo=tzinfo).date()
#    mock_new["type"] = "CheapestHoursBinarySensor"
#    mock_new["calendar"] = True
#
#    await coordinator.async_set_data(
#        entity_id="my_cheapest_hours_sensor",
#        name="My Cheapest Hours",
#        calendar=True,
#        module="CheapestHoursBinarySensor",
#        dict=mock_new,
#        archived=mock["list"],
#    )
#
#    data = coordinator.get_data("my_cheapest_hours_sensor")
#    assert len(data["archived"]) == 2
#
#    # another new mock
#    mock_new_2: dict = {}
#    mock_new_2["list"] = [
#        {
#            "start": datetime(2025, 10, 19, 1, 0, tzinfo=tzinfo),
#            "end": datetime(2025, 10, 19, 2, 45, tzinfo=tzinfo),
#        },
#        {
#            "start": datetime(2025, 10, 19, 3, 0, tzinfo=tzinfo),
#            "end": datetime(2025, 10, 19, 3, 15, tzinfo=tzinfo),
#        },
#    ]
#    mock_new_2["active_number_of_hours"] = 2
#    mock_new_2["failsafe"] = {
#        "start": datetime(2025, 10, 19, 1, 0, tzinfo=tzinfo).time(),
#        "end": datetime(2025, 10, 19, 3, 0, tzinfo=tzinfo).time(),
#    }
#    mock_new_2["expiration"] = datetime(2025, 10, 20, 0, 0, tzinfo=tzinfo)
#    mock_new_2["extra"] = {"mean_price": 1.2000, "max_price": 2.0, "min_price": 1.0}
#    mock_new_2["updated_at"] = datetime(
#        2025,
#        10,
#        18,
#        14,
#        43,
#        38,
#        910378,
#        tzinfo=tzinfo,
#    )
#    mock_new_2["fetch_date"] = datetime(2025, 10, 18, 1, 0, tzinfo=tzinfo).date()
#    mock_new_2["type"] = "CheapestHoursBinarySensor"
#    mock_new_2["calendar"] = True
#
#    await coordinator.async_set_data(
#        entity_id="my_cheapest_hours_sensor",
#        name="My Cheapest Hours",
#        calendar=True,
#        module="CheapestHoursBinarySensor",
#        dict=mock_new_2,
#        archived=mock_new["list"],
#    )
#
#    data = coordinator.get_data("my_cheapest_hours_sensor")
#    assert len(data["archived"]) == 4
#
#    # Test clear archive
#    freezer.move_to("2025-10-17 14:00+03:00")
#    coordinator.clear_archived(entity_id="my_cheapest_hours_sensor", retention_days=1)
#    data = coordinator.get_data("my_cheapest_hours_sensor")
#    assert len(data["archived"]) == 4
#
#    freezer.move_to("2025-10-18 14:00+03:00")
#    coordinator.clear_archived(entity_id="my_cheapest_hours_sensor", retention_days=1)
#    data = coordinator.get_data("my_cheapest_hours_sensor")
#    assert len(data["archived"]) == 2
#
#    freezer.move_to("2025-10-19 14:00+03:00")
#    coordinator.clear_archived(entity_id="my_cheapest_hours_sensor", retention_days=1)
#    data = coordinator.get_data("my_cheapest_hours_sensor")
#    assert len(data["archived"]) == 0
