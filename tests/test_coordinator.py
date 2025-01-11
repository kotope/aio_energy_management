"""Tests for coordinator."""

from datetime import date, datetime
import zoneinfo

from custom_components.aio_energy_management.coordinator import (
    EnergyManagementCoordinator,
)
from freezegun import freeze_time
import numpy as np
import pytest

from homeassistant.core import HomeAssistant


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
            }
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
            }
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
            }
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
            }
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
    assert nxt.get("expiration") == datetime(
        2024, 10, 10, 0, 0, tzinfo=tzinfo
    )

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
