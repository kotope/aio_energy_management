"""Tests for math."""

from datetime import datetime
import zoneinfo

from custom_components.aio_energy_management.exceptions import InvalidInput
from custom_components.aio_energy_management.math import (
    calculate_non_sequential_cheapest_hours,
    calculate_sequential_cheapest_hours,
)
from freezegun import freeze_time
import numpy as np
import pytest


@pytest.fixture
def today_valid() -> list:
    """Fixture of today prices."""
    return [
        3.809,  # 0
        3.435,  # 1
        3.295,  # 2
        3.169,  # 3
        3.08,  # 4
        3.16,  # 5
        3.355,  # 6
        3.436,  # 7
        3.752,  # 8
        3.768,  # 9
        3.577,  # 10
        3.549,  # 11
        3.463,  # 12
        3.6,  # 13
        3.585,  # 14
        3.541,  # 15
        3.229,  # 16
        3.019,  # 17
        10.287,  # 18 Expensive
        3.369,  # 19
        3.435,  # 20
        0.434,  # 21, Cheap
        1.391,  # 22
        2.567,  # 23
    ]


@pytest.fixture
def tomorrow_valid() -> list:
    """Fixture of tomorrow prices."""
    return [
        3.482,  # 0
        2.461,  # 1
        2.967,  # 2
        2.859,  # 3
        3.063,  # 4
        3.249,  # 5
        3.582,  # 6
        4.149,  # 7
        4.382,  # 8
        4.505,  # 9
        1.547,  # 10, Cheap
        25.874,  # 11 Expensive
        1.851,  # 12, Cheap
        1.71,  # 13, Cheap
        4.774,  # 14 # Expensive
        4.706,  # 15 # Expensive
        4.598,  # 16
        4.551,  # 17
        4.463,  # 18
        4.551,  # 19
        4.46,  # 20
        4.397,  # 21
        4.345,  # 22
        4.175,  # 23
    ]


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_cheapest_hours(today_valid, tomorrow_valid) -> None:
    """Test sequential."""
    # Start of tomorrow
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 23
    )
    assert np.size(result) == 1
    assert result[0]["start"] == datetime(
        2024, 7, 23, 1, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 4, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    # Later tomorrow
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 11, 20
    )
    assert np.size(result) == 1
    assert result[0]["start"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 15, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    # Starting today
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 21, 18
    )
    assert np.size(result) == 1
    assert result[0]["start"] == datetime(
        2024, 7, 22, 21, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_expensive_hours(today_valid, tomorrow_valid) -> None:
    """Test sequential."""
    # Tomorrow expensive
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 23, inversed=True
    )
    assert np.size(result) == 1
    assert result[0]["start"] == datetime(
        2024, 7, 23, 9, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    # Starting today expensive
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 21, 8, inversed=True
    )
    assert np.size(result) == 1
    assert result[0]["start"] == datetime(
        2024, 7, 23, 6, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 9, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_cheapest_hours(today_valid, tomorrow_valid) -> None:
    """Test non-sequential."""
    last_hour = 18
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, last_hour
    )
    assert np.size(result) == 2
    assert result[0]["start"] == datetime(
        2024, 7, 23, 10, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert result[1]["start"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[1]["end"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_expensive_hours(today_valid, tomorrow_valid) -> None:
    """Test non-sequential."""
    # Tomorrow
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 18, inversed=True
    )
    assert np.size(result) == 2
    assert result[0]["start"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert result[1]["start"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[1]["end"] == datetime(
        2024, 7, 23, 16, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    # Also today
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 18, 6, inversed=True
    )
    assert np.size(result) == 3
    assert result[0]["start"] == datetime(
        2024, 7, 22, 18, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 22, 19, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert result[1]["start"] == datetime(
        2024, 7, 23, 0, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[1]["end"] == datetime(
        2024, 7, 23, 1, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert result[2]["start"] == datetime(
        2024, 7, 23, 6, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[2]["end"] == datetime(
        2024, 7, 23, 7, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )


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
        today_valid, tomorrow_valid, 10, False, 0, 23, max_price=2.0
    )

    # Should only find three items in two slots (10, 12, 13)
    assert np.size(result) == 2

    assert result[0]["start"] == datetime(
        2024, 7, 23, 10, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[0]["end"] == datetime(
        2024, 7, 23, 11, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    assert result[1]["start"] == datetime(
        2024, 7, 23, 12, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result[1]["end"] == datetime(
        2024, 7, 23, 14, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )

    # Test with zero values found as max_price set to very very low
    result = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, max_price=0.1
    )
    assert np.size(result) == 0


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_cheapest_hours_max_price(today_valid, tomorrow_valid) -> None:
    """Test non-sequential with max price."""
    with pytest.raises(InvalidInput):  # max price not supported on sequential
        calculate_sequential_cheapest_hours(
            today_valid, tomorrow_valid, 10, False, 0, 23, max_price=2.0
        )
