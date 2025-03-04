"""Tests for math."""

from datetime import datetime, timedelta
import zoneinfo

from custom_components.aio_energy_management.exceptions import InvalidInput
from custom_components.aio_energy_management.math import (
    calculate_non_sequential_cheapest_hours,
    calculate_sequential_cheapest_hours,
)
from custom_components.aio_energy_management.models.hour_price import HourPrice
from freezegun import freeze_time
import numpy as np
import pytest


@pytest.fixture
def today_valid() -> list:
    """Fixture of today prices."""
    return [
        HourPrice(3.809, datetime.strptime("2025-01-02 00:00", "%Y-%m-%d %H:%M")),  # 0
        HourPrice(3.435, datetime.strptime("2025-01-02 01:00", "%Y-%m-%d %H:%M")),  # 1
        HourPrice(3.295, datetime.strptime("2025-01-02 02:00", "%Y-%m-%d %H:%M")),  # 2
        HourPrice(3.169, datetime.strptime("2025-01-02 03:00", "%Y-%m-%d %H:%M")),  # 3
        HourPrice(3.08, datetime.strptime("2025-01-02 04:00", "%Y-%m-%d %H:%M")),  # 4
        HourPrice(3.16, datetime.strptime("2025-01-02 05:00", "%Y-%m-%d %H:%M")),  # 5
        HourPrice(3.355, datetime.strptime("2025-01-02 06:00", "%Y-%m-%d %H:%M")),  # 6
        HourPrice(3.436, datetime.strptime("2025-01-02 07:00", "%Y-%m-%d %H:%M")),  # 7
        HourPrice(3.752, datetime.strptime("2025-01-02 08:00", "%Y-%m-%d %H:%M")),  # 8
        HourPrice(3.768, datetime.strptime("2025-01-02 09:00", "%Y-%m-%d %H:%M")),  # 9
        HourPrice(3.577, datetime.strptime("2025-01-02 10:00", "%Y-%m-%d %H:%M")),  # 10
        HourPrice(3.549, datetime.strptime("2025-01-02 11:00", "%Y-%m-%d %H:%M")),  # 11
        HourPrice(3.463, datetime.strptime("2025-01-02 12:00", "%Y-%m-%d %H:%M")),  # 12
        HourPrice(3.6, datetime.strptime("2025-01-02 13:00", "%Y-%m-%d %H:%M")),  # 13
        HourPrice(3.585, datetime.strptime("2025-01-02 14:00", "%Y-%m-%d %H:%M")),  # 14
        HourPrice(3.541, datetime.strptime("2025-01-02 15:00", "%Y-%m-%d %H:%M")),  # 15
        HourPrice(3.229, datetime.strptime("2025-01-02 16:00", "%Y-%m-%d %H:%M")),  # 16
        HourPrice(3.019, datetime.strptime("2025-01-02 17:00", "%Y-%m-%d %H:%M")),  # 17
        HourPrice(
            10.287, datetime.strptime("2025-01-02 18:00", "%Y-%m-%d %H:%M")
        ),  # 18 Expensive
        HourPrice(3.369, datetime.strptime("2025-01-02 19:00", "%Y-%m-%d %H:%M")),  # 19
        HourPrice(3.435, datetime.strptime("2025-01-02 20:00", "%Y-%m-%d %H:%M")),  # 20
        HourPrice(
            0.434, datetime.strptime("2025-01-02 21:00", "%Y-%m-%d %H:%M")
        ),  # 21, Cheap
        HourPrice(1.391, datetime.strptime("2025-01-02 22:00", "%Y-%m-%d %H:%M")),  # 22
        HourPrice(2.567, datetime.strptime("2025-01-02 23:00", "%Y-%m-%d %H:%M")),  # 23
    ]


@pytest.fixture
def tomorrow_valid() -> list:
    """Fixture of tomorrow prices."""
    return [
        HourPrice(3.482, datetime.strptime("2025-01-02 00:00", "%Y-%m-%d %H:%M")),  # 0
        HourPrice(2.461, datetime.strptime("2025-01-02 01:00", "%Y-%m-%d %H:%M")),  # 1
        HourPrice(2.967, datetime.strptime("2025-01-02 02:00", "%Y-%m-%d %H:%M")),  # 2
        HourPrice(2.859, datetime.strptime("2025-01-02 03:00", "%Y-%m-%d %H:%M")),  # 3
        HourPrice(3.063, datetime.strptime("2025-01-02 04:00", "%Y-%m-%d %H:%M")),  # 4
        HourPrice(3.249, datetime.strptime("2025-01-02 05:00", "%Y-%m-%d %H:%M")),  # 5
        HourPrice(3.582, datetime.strptime("2025-01-02 06:00", "%Y-%m-%d %H:%M")),  # 6
        HourPrice(4.149, datetime.strptime("2025-01-02 07:00", "%Y-%m-%d %H:%M")),  # 7
        HourPrice(4.382, datetime.strptime("2025-01-02 08:00", "%Y-%m-%d %H:%M")),  # 8
        HourPrice(4.505, datetime.strptime("2025-01-02 09:00", "%Y-%m-%d %H:%M")),  # 9
        HourPrice(
            1.547, datetime.strptime("2025-01-02 10:00", "%Y-%m-%d %H:%M")
        ),  # 10, Cheap
        HourPrice(
            25.874, datetime.strptime("2025-01-02 11:00", "%Y-%m-%d %H:%M")
        ),  # 11 Expensive
        HourPrice(
            1.851, datetime.strptime("2025-01-02 12:00", "%Y-%m-%d %H:%M")
        ),  # 12, Cheap
        HourPrice(
            1.71, datetime.strptime("2025-01-02 13:00", "%Y-%m-%d %H:%M")
        ),  # 13, Cheap
        HourPrice(
            4.774, datetime.strptime("2025-01-02 14:00", "%Y-%m-%d %H:%M")
        ),  # 14 # Expensive
        HourPrice(
            4.706, datetime.strptime("2025-01-02 15:00", "%Y-%m-%d %H:%M")
        ),  # 15 # Expensive
        HourPrice(4.598, datetime.strptime("2025-01-02 16:00", "%Y-%m-%d %H:%M")),  # 16
        HourPrice(4.551, datetime.strptime("2025-01-02 17:00", "%Y-%m-%d %H:%M")),  # 17
        HourPrice(4.463, datetime.strptime("2025-01-02 18:00", "%Y-%m-%d %H:%M")),  # 18
        HourPrice(4.551, datetime.strptime("2025-01-02 19:00", "%Y-%m-%d %H:%M")),  # 19
        HourPrice(4.46, datetime.strptime("2025-01-02 20:00", "%Y-%m-%d %H:%M")),  # 20
        HourPrice(4.397, datetime.strptime("2025-01-02 21:00", "%Y-%m-%d %H:%M")),  # 21
        HourPrice(4.345, datetime.strptime("2025-01-02 22:00", "%Y-%m-%d %H:%M")),  # 22
        HourPrice(4.175, datetime.strptime("2025-01-02 23:00", "%Y-%m-%d %H:%M")),  # 23
    ]


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_cheapest_hours(today_valid, tomorrow_valid) -> None:
    """Test sequential."""
    # Start of tomorrow
    result = calculate_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        False,
        0,
        23,
    )
    lis: list = result.get("list")
    assert np.size(lis) == 1
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 1, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 4, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 2.762333333333333
    assert result["extra"]["min_price"] == 2.461
    assert result["extra"]["max_price"] == 2.967

    # Later tomorrow
    result = calculate_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        False,
        11,
        20,
    )
    lis = result.get("list")
    assert np.size(lis) == 1
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 15, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 2.7783333333333338
    assert result["extra"]["min_price"] == 1.71
    assert result["extra"]["max_price"] == 4.774

    # Starting today
    result = calculate_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        True,
        21,
        18,
    )
    lis = result.get("list")
    assert np.size(lis) == 1
    assert lis[0]["start"] == datetime(
        2024, 7, 22, 21, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 1.4640000000000002
    assert result["extra"]["min_price"] == 0.434
    assert result["extra"]["max_price"] == 2.567


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_expensive_hours(today_valid, tomorrow_valid) -> None:
    """Test sequential."""
    # Tomorrow expensive
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 23, inversed=True
    )
    lis: list = result.get("list")
    assert np.size(lis) == 1
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 9, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 10.642
    assert result["extra"]["min_price"] == 1.547
    assert result["extra"]["max_price"] == 25.874

    # Starting today expensive
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 21, 8, inversed=True
    )
    lis: list = result.get("list")
    assert np.size(lis) == 1
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 6, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 9, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 4.0376666666666665
    assert result["extra"]["min_price"] == 3.582
    assert result["extra"]["max_price"] == 4.382


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_cheapest_hours(today_valid, tomorrow_valid) -> None:
    """Test non-sequential."""
    last_hour = 18
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, last_hour
    )
    lis: list = result.get("list")
    assert np.size(lis) == 2
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 10, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert lis[1]["start"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[1]["end"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 1.7026666666666666
    assert result["extra"]["min_price"] == 1.547
    assert result["extra"]["max_price"] == 1.851


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_expensive_hours(today_valid, tomorrow_valid) -> None:
    """Test non-sequential."""
    # Tomorrow
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 18, inversed=True
    )

    lis: list = result.get("list")
    assert np.size(lis) == 2
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert lis[1]["start"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[1]["end"] == datetime(
        2024, 7, 23, 16, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 11.784666666666666
    assert result["extra"]["min_price"] == 4.706
    assert result["extra"]["max_price"] == 25.874

    # Also today
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 18, 6, inversed=True
    )
    lis = result.get("list")
    assert np.size(lis) == 3
    assert lis[0]["start"] == datetime(
        2024, 7, 22, 18, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 22, 19, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert lis[1]["start"] == datetime(
        2024, 7, 23, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[1]["end"] == datetime(
        2024, 7, 23, 1, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert lis[2]["start"] == datetime(
        2024, 7, 23, 6, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[2]["end"] == datetime(
        2024, 7, 23, 7, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 5.783666666666666
    assert result["extra"]["min_price"] == 3.482
    assert result["extra"]["max_price"] == 10.287


def test_invalid_input(today_valid, tomorrow_valid) -> None:
    """Tests invalid input."""
    with pytest.raises(InvalidInput):  # non-sequential, >24h
        calculate_non_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 25, False, 0, 17
        )
    with pytest.raises(InvalidInput):  # sequential, >24h
        calculate_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 25, False, 0, 17
        )
    with pytest.raises(InvalidInput):
        calculate_non_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 2, True, 21, 22
        )
    with pytest.raises(InvalidInput):
        calculate_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 2, True, 21, 22
        )
    with pytest.raises(InvalidInput):
        calculate_non_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 2, False, 22, 21
        )
    with pytest.raises(InvalidInput):
        calculate_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 2, False, 22, 21
        )


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_cheapest_hours_max_price(today_valid, tomorrow_valid) -> None:
    """Test non-sequential with max price."""
    # Start of tomorrow
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=2.0
    )
    lis: list = result.get("list")

    # Should only find three items in two slots (10, 12, 13)
    assert np.size(lis) == 2

    assert lis[0]["start"] == datetime(
        2024, 7, 23, 10, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert lis[1]["start"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[1]["end"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 1.7026666666666666
    assert result["extra"]["min_price"] == 1.547
    assert result["extra"]["max_price"] == 1.851

    # Test with zero values found as max_price set to very very low
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=0.1
    )
    lis = result.get("list")
    assert np.size(lis) == 0
    assert result["extra"]["mean_price"] is None
    assert result["extra"]["min_price"] is None
    assert result["extra"]["max_price"] is None


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_cheapest_hours_min_price(today_valid, tomorrow_valid) -> None:
    """Test non-sequential with max price."""
    # Start of tomorrow
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, inversed=True, price_limit=4.75
    )
    lis: list = result.get("list")

    # Should only find two items (11, 14)
    assert np.size(lis) == 2

    assert lis[0]["start"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert lis[1]["start"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[1]["end"] == datetime(
        2024, 7, 23, 15, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["mean_price"] == 15.324
    assert result["extra"]["min_price"] == 4.774
    assert result["extra"]["max_price"] == 25.874

    # Test with zero values found as min_price set to very very low
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, inversed=True, price_limit=28
    )
    lis = result.get("list")
    assert np.size(lis) == 0
    assert result["extra"]["mean_price"] is None
    assert result["extra"]["min_price"] is None
    assert result["extra"]["max_price"] is None


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_cheapest_hours_max_price(today_valid, tomorrow_valid) -> None:
    """Test non-sequential with max price."""
    with pytest.raises(InvalidInput):  # max price not supported on sequential
        calculate_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=2.0
        )
