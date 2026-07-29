"""Tests for math."""

from datetime import datetime, timedelta
import zoneinfo

from custom_components.aio_energy_management.exceptions import InvalidInput
from custom_components.aio_energy_management.cheapest_hours.math import (
    calculate_non_sequential_cheapest_hours,
    calculate_sequential_cheapest_hours,
    ValueNotFound,
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
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        False,
        0,
        23,
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        False,
        11,
        20,
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        True,
        21,
        18,
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 23, inversed=True
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 21, 8, inversed=True
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, last_hour
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 18, inversed=True
    )
    assert expires_today_only is False

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
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, True, 18, 6, inversed=True
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=2.0
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=0.1
    )
    assert expires_today_only is False
    lis = result.get("list")
    assert np.size(lis) == 0
    assert result["extra"]["mean_price"] is None
    assert result["extra"]["min_price"] is None
    assert result["extra"]["max_price"] is None


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_cheapest_hours_min_price(today_valid, tomorrow_valid) -> None:
    """Test non-sequential with max price."""
    # Start of tomorrow
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, inversed=True, price_limit=4.75
    )
    assert expires_today_only is False
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
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, inversed=True, price_limit=28
    )
    assert expires_today_only is False
    lis = result.get("list")
    assert np.size(lis) == 0
    assert result["extra"]["mean_price"] is None
    assert result["extra"]["min_price"] is None
    assert result["extra"]["max_price"] is None


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_cheapest_hours_price_limit(today_valid, tomorrow_valid) -> None:
    """Test sequential with price_limit."""
    # Cheapest 10-slot window has mean ~3.276; price_limit below that → empty list
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=2.0
    )
    assert result["list"] == []
    assert result["extra"]["mean_price"] is None
    assert result["extra"]["max_price"] is None
    assert result["extra"]["min_price"] is None

    # price_limit above mean → normal result
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, price_limit=4.0
    )
    assert expires_today_only is False
    assert len(result["list"]) == 1
    assert result["extra"]["mean_price"] is not None


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_add_flexible_stops_at_limit(
    today_valid, tomorrow_valid
) -> None:
    """Flexible slots extend the base until a slot exceeds the price limit.

    Base 2 cheapest tomorrow slots are 10 (1.547) and 13 (1.71). The next
    cheapest is 12 (1.851) which is below 1.9 so it is added; the following
    candidate (2.461) exceeds the limit so extension stops. The result is the
    same set of slots as requesting 3 fixed slots (10, 12, 13).
    """
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        2,
        False,
        0,
        23,
        max_number_of_slots=5,
        flexible_price_limit=1.9,
    )
    assert expires_today_only is False
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
def test_non_sequential_add_flexible_extends_by_max_extra_slots(
    today_valid, tomorrow_valid
) -> None:
    """max_number_of_slots counts extra slots added on top of the base slots."""
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        2,
        False,
        0,
        23,
        max_number_of_slots=4,
        flexible_price_limit=3.0,
    )
    assert expires_today_only is False
    lis: list = result.get("list")
    # Base 2 cheapest: 10 (1.547), 13 (1.71). Up to 4 extra slots are added while
    # each stays within 3.0: 12 (1.851), 1 (2.461), 3 (2.859), 2 (2.967). Total 6
    # slots across hours 1, 2, 3, 10, 12, 13. Hours 1-3 merge into one item, hour
    # 10 stands alone, and hours 12-13 merge into one item.
    assert np.size(lis) == 3
    assert lis[0]["start"] == datetime(
        2024, 7, 23, 1, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert lis[0]["end"] == datetime(
        2024, 7, 23, 4, 0, tzinfo=zoneinfo.ZoneInfo(key="Europe/Helsinki")
    )
    assert result["extra"]["min_price"] == 1.547
    assert result["extra"]["max_price"] == 2.967


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_add_flexible_base_slots_ignore_flexible_limit(
    today_valid, tomorrow_valid
) -> None:
    """Base slots are always kept (subject only to price_limit), not the flexible limit."""
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        2,
        False,
        0,
        23,
        price_limit=2.0,
        max_number_of_slots=5,
        flexible_price_limit=1.6,
    )
    assert expires_today_only is False
    lis: list = result.get("list")
    # Base 10 (1.547) and 13 (1.71) are kept even though 13 exceeds the flexible
    # limit of 1.6; no extra slot is added since 12 (1.851) exceeds it too.
    assert np.size(lis) == 2
    assert result["extra"]["min_price"] == 1.547
    assert result["extra"]["max_price"] == 1.71


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_add_flexible_inversed(today_valid, tomorrow_valid) -> None:
    """Flexible extension works for inversed (expensive) calculation."""
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        2,
        False,
        0,
        23,
        inversed=True,
        max_number_of_slots=5,
        flexible_price_limit=4.6,
    )
    assert expires_today_only is False
    # Base 11 (25.874), 14 (4.774); extra 15 (4.706) is >= 4.6 so added; the
    # next candidate 16 (4.598) is below 4.6 so extension stops.
    assert result["extra"]["mean_price"] == 11.784666666666666
    assert result["extra"]["min_price"] == 4.706
    assert result["extra"]["max_price"] == 25.874


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_add_flexible_noop_without_both_params(
    today_valid, tomorrow_valid
) -> None:
    """Without both max and flexible price limit the base slots are returned."""
    base, base_expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 2, False, 0, 23
    )
    only_max, only_max_expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 2, False, 0, 23, max_number_of_slots=5
    )
    only_limit, only_limit_expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        2,
        False,
        0,
        23,
        flexible_price_limit=1.9,
    )
    assert base_expires_today_only is False
    assert only_max_expires_today_only is False
    assert only_limit_expires_today_only is False
    assert only_max["list"] == base["list"]
    assert only_limit["list"] == base["list"]


@freeze_time("2024-07-22 14:25+03:00")
def test_non_sequential_add_flexible_max_smaller_than_base(
    today_valid, tomorrow_valid
) -> None:
    """max_number_of_slots may be smaller than number_of_slots (it is a count of extra slots)."""
    base, base_expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 3, False, 0, 23
    )
    result, expires_today_only = calculate_non_sequential_cheapest_hours(
        today_valid,
        tomorrow_valid,
        3,
        False,
        0,
        23,
        max_number_of_slots=2,
        flexible_price_limit=10.0,
    )
    assert base_expires_today_only is False
    assert expires_today_only is False
    # Base 3 slots (10, 12, 13) get 2 extra slots (1, 3) appended.
    assert result["list"] != base["list"]
    assert result["extra"]["min_price"] == 1.547
    assert result["extra"]["max_price"] == 2.859


def test_non_sequential_add_flexible_invalid_max(today_valid, tomorrow_valid) -> None:
    """max_number_of_slots above the MTU cap is rejected."""
    with pytest.raises(InvalidInput):
        calculate_non_sequential_cheapest_hours(
            today_valid,
            tomorrow_valid,
            2,
            False,
            0,
            23,
            max_number_of_slots=25,
            flexible_price_limit=1.0,
        )


@freeze_time("2024-07-22 14:25+03:00")
def test_sequential_expensive_hours_price_limit(today_valid, tomorrow_valid) -> None:
    """Test sequential with inversed=True and price_limit."""
    # Most expensive 10-slot window has mean ~6.154; price_limit above that → empty list
    result = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, inversed=True, price_limit=7.0
    )
    assert result["list"] == []
    assert result["extra"]["mean_price"] is None
    assert result["extra"]["max_price"] is None
    assert result["extra"]["min_price"] is None

    # price_limit below mean → normal result
    result, expires_today_only = calculate_sequential_cheapest_hours(
        today_valid, tomorrow_valid, 10, False, 0, 23, inversed=True, price_limit=5.0
    )
    assert expires_today_only is False
    assert len(result["list"]) == 1
    assert result["extra"]["mean_price"] is not None


@freeze_time("2024-07-22 14:25+03:00")
@pytest.mark.parametrize(
    "first_hour, last_hour, starting_today, pass_tomorrow, expect_raise, test_id",
    [
        # CONFIGURATION 1: Regular window during day, no overnight hours
        (7, 19, False, True, False, "time_window_with_tomorrow"),
        (7, 19, False, False, False, "time_window_without_tomorrow"),
        # CONFIGURATION 2: Regular window during day, with overnight hours
        (22, 21, True, True, False, "overnight_window_with_tomorrow"),
        (22, 21, True, False, True, "overnight_window_without_tomorrow_must_fail"),
    ],
)
def test_cheapest_hours_scenarios(
    today_valid,
    tomorrow_valid,
    first_hour,
    last_hour,
    starting_today,
    pass_tomorrow,
    expect_raise,
    test_id,
) -> None:
    """Test combinations of regular and overnight window with and without tomorrow prices."""

    tomorrow_data = tomorrow_valid if pass_tomorrow else []

    # Scenarios where we expect a ValueNotFound
    if expect_raise:
        with pytest.raises(ValueNotFound):
            calculate_non_sequential_cheapest_hours(
                today=today_valid,
                tomorrow=tomorrow_data,
                number_of_slots=3,
                starting_today=starting_today,
                first_hour=first_hour,
                last_hour=last_hour,
            )

    # Scenarios with valid data
    else:
        result, expires_today_only = calculate_non_sequential_cheapest_hours(
            today=today_valid,
            tomorrow=tomorrow_data,
            number_of_slots=3,
            starting_today=starting_today,
            first_hour=first_hour,
            last_hour=last_hour,
        )

        assert expires_today_only is (not pass_tomorrow)
        assert isinstance(result, dict)
        assert "list" in result
        assert "extra" in result
        assert len(result["list"]) > 0


@pytest.mark.parametrize(
    "min_seq_slots, inversed, number_of_slots",
    [
        (1, False, 3),
        (2, False, 3),
        (3, False, 5),
        (4, False, 10),
    ],
)
def test_cheapest_hours_min_seq_slots_scenarios(
    today_valid,
    tomorrow_valid,
    min_seq_slots,
    inversed,
    number_of_slots,
) -> None:
    """Test non-sequential cheapest/expensive hours respecting min_seq_slots."""

    result, _ = calculate_non_sequential_cheapest_hours(
        today=today_valid,
        tomorrow=tomorrow_valid,
        number_of_slots=number_of_slots,
        starting_today=False,
        first_hour=0,
        last_hour=23,
        min_seq_slots=min_seq_slots,
        inversed=inversed,
    )

    # ------------------ PRINT STATEMENTS VOOR INZICHT ------------------
    mode_str = "DUURSTE (inversed)" if inversed else "GOEDKOOPSTE"
    print(f"\n\n================ SCENARIO TEST ================")
    print(
        f"Modus: {mode_str} | Min seq slots: {min_seq_slots} slots | Totaal slots: {number_of_slots}"
    )
    print(f"Aantal gevormde reeksen: {len(result['list'])}")
    print(f"Gemiddelde prijs: {result['extra'].get('mean_price'):.4f}")
    print("-" * 47)

    for i, seq_slots in enumerate(result["list"], 1):
        start_tijd = seq_slots["start"].strftime("%H:%M")
        eind_tijd = seq_slots["end"].strftime("%H:%M")
        duration_min = int((seq_slots["end"] - seq_slots["start"]).total_seconds() / 60)
        slots = duration_min // 60

        print(
            f"  Reeks {i}: {start_tijd} -> {eind_tijd} ({slots} slots / {duration_min} min)"
        )
    print("===============================================")
    # -------------------------------------------------------------------

    assert isinstance(result, dict)
    assert "list" in result
    assert "extra" in result
    assert len(result["list"]) > 0

    for seq_slots in result["list"]:
        duration_minutes = (seq_slots["end"] - seq_slots["start"]).total_seconds() / 60
        slots_count = int(duration_minutes / 60)
        assert slots_count >= min_seq_slots
