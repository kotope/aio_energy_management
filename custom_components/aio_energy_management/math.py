"""Math functions for cheapest hours."""

from datetime import timedelta
import logging

import numpy as np

import homeassistant.util.dt as dt_util

from .exceptions import InvalidInput, ValueNotFound
from .models.hour_price import HourPrice

_LOGGER = logging.getLogger(__name__)

MAX_PRICE_VALUE = 999.9
MIN_PRICE_VALUE = -999.9


def calculate_sequential_cheapest_hours(
    today: list,
    tomorrow: list,
    number_of_hours: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
    inversed: bool = False,
    price_limit: float | None = None,
) -> dict:
    """Calculate sequential cheapest hours."""
    if price_limit is not None:  # Max price is not supported on seuqantial calculations
        _LOGGER.error(
            "Invalid configuration: price_limit not supported by sequential cheapest hours"
        )
        raise InvalidInput

    if (
        _is_cheapest_hours_input_valid(
            number_of_hours, starting_today, first_hour, last_hour
        )
        is False
    ):
        _LOGGER.error("Invalid configuration for sequential cheapest hours sensor")
        raise InvalidInput

    fd: dict = {}  # Final data dictionary
    fd["extra"] = {}

    # Check daylight saivings
    td = _check_day_light_savings(today)
    tm = _check_day_light_savings(tomorrow)

    if len(td) != 24 or len(tm) != 24:
        _LOGGER.error(
            "Data provided for calculation has invalid amount of values. This is most probably error in data provider"
        )
        raise ValueNotFound

    # Function specific varialbes
    prices = [item.value for item in td] + [item.value for item in tm]
    cheapest_price = MAX_PRICE_VALUE
    mean_price: float = 0.0
    max_price: float | None = None
    min_price: float | None = None

    if inversed:
        cheapest_price = MIN_PRICE_VALUE

    cheapest_hour = dt_util.start_of_local_day()
    counter = 0.00
    starting = first_hour
    ending = last_hour + 1 + 24

    if starting_today is False:
        starting = first_hour + 24
    for i in range(starting + number_of_hours, ending + 1):
        counter = 0.0
        max_temp = MIN_PRICE_VALUE
        min_temp = MAX_PRICE_VALUE

        for j in range(i - number_of_hours, i):
            counter += prices[j]
            if prices[j] > max_temp:
                max_temp = prices[j]
            if prices[j] < min_temp:
                min_temp = prices[j]

        if (
            inversed
            and counter > cheapest_price
            or not inversed
            and counter < cheapest_price
        ):
            # If the price is 'better' than previous
            max_price = max_temp
            min_price = min_temp
            cheapest_price = counter
            mean_price = counter / number_of_hours
            cheapest_hour = dt_util.start_of_local_day() + timedelta(
                hours=i - number_of_hours
            )

    fd["list"] = [
        {
            "start": cheapest_hour,
            "end": cheapest_hour + timedelta(hours=number_of_hours),
        }
    ]

    fd["extra"]["mean_price"] = mean_price
    fd["extra"]["max_price"] = max_price
    fd["extra"]["min_price"] = min_price
    return fd


def calculate_non_sequential_cheapest_hours(
    today: list,
    tomorrow: list,
    number_of_hours: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
    inversed: bool = False,
    price_limit: float | None = None,
) -> dict:
    """Calculate non-sequential cheapest hours."""
    if (
        _is_cheapest_hours_input_valid(
            number_of_hours, starting_today, first_hour, last_hour
        )
        is False
    ):
        _LOGGER.error("Invalid configuration for non-sequential cheapest hours sensor")
        raise InvalidInput

    td = _check_day_light_savings(today)
    tm = _check_day_light_savings(tomorrow)

    if len(td) != 24 or len(tm) != 24:
        _LOGGER.error(
            "Data provided for calculation has invalid amount of values. This is most probably error in data provider"
        )
        raise ValueNotFound

    arr = [item.value for item in td] + [item.value for item in tm]
    starting = first_hour
    if not starting_today:
        starting = first_hour + 24
    ending = last_hour + 1 + 24
    data = []
    fd: dict = {}  # Final data dictionary
    fd["extra"] = {}

    for i in range(starting, ending):
        start = dt_util.start_of_local_day() + timedelta(hours=i)
        end = dt_util.start_of_local_day() + timedelta(hours=i + 1)
        data += [{"start": start, "end": end, "price": arr[i]}]

    data.sort(key=lambda x: (x["price"], x["start"]), reverse=inversed)

    data = data[:number_of_hours]
    data.sort(key=lambda x: (x["start"]))
    if inversed:
        if mp := price_limit:
            data = [d for d in data if d["price"] >= mp]
    elif mp := price_limit:
        data = [d for d in data if d["price"] <= mp]

    fd["extra"]["mean_price"] = _get_average(data)
    fd["extra"]["max_price"] = _get_max(data)
    fd["extra"]["min_price"] = _get_min(data)

    # Combine sequantial slots
    iterate = True
    while iterate is True:
        matched = False
        i = 0
        result = []

        while i < np.size(data):
            current_item = data[i]
            next_item = None
            if i < np.size(data) - 1:
                next_item = data[i + 1]

            if next_item is not None:
                if current_item["end"] == next_item["start"]:
                    # Match, combine these two
                    d = {"start": current_item["start"], "end": next_item["end"]}
                    i += 1  # skip next
                    matched = True
                    result += [d]
                else:
                    # No match, just set the single item
                    d = {"start": current_item["start"], "end": current_item["end"]}
                    result += [d]
            else:
                d = {"start": current_item["start"], "end": current_item["end"]}
                result += [d]

            i += 1  # Increase loop index

        data = result
        if not matched:
            iterate = False

    fd["list"] = data
    return fd


def _get_average(data: list) -> float | None:
    if len(data) == 0:
        return None
    total = sum(item["price"] for item in data)
    return total / len(data)


def _get_max(data: list) -> float | None:
    if len(data) == 0:
        return None
    return max(item["price"] for item in data)


def _get_min(data: list) -> float | None:
    if len(data) == 0:
        return None
    return min(item["price"] for item in data)


def _is_cheapest_hours_input_valid(
    number_of_hours: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
) -> bool:
    if starting_today is False:
        if last_hour < first_hour:
            return False
    if starting_today is True:
        if first_hour < last_hour:
            return False
    if number_of_hours > 24:
        return False

    return True


def _check_day_light_savings(hours: list, inversed: bool = False) -> list:
    if len(hours) == 23:
        return _add_missing_hour(hours, inversed)
    if len(hours) == 25:
        return _remove_duplicate_starts(hours)
    return hours


def _add_missing_hour(hours: list, inversed: bool) -> list:
    """Add missing hour when turning to summer time. The new hour added has the value of max or min depending of inversed state."""
    # Find the missing entry's index by checking time difference.
    missing_index = -1
    for i in range(len(hours) - 1):
        time_diff = hours[i + 1].start - hours[i].start
        time_diff_hours = time_diff.total_seconds() / 3600.0

        if time_diff_hours >= 2:
            # Missing one index
            missing_index = i + 1
            break

    if missing_index == -1:
        return hours  # No missing entry found

    # Create the missing entry
    missing_start_time = hours[missing_index - 1].start + timedelta(hours=1)
    if inversed:
        missing_value = MIN_PRICE_VALUE
    else:
        missing_value = MAX_PRICE_VALUE

    # Insert the missing entry into the data
    hours.insert(
        missing_index, HourPrice(value=missing_value, start=missing_start_time)
    )
    return hours


def _remove_duplicate_starts(hours: list) -> list:
    """Remove duplicate hour when turning to winter time. Hour removed is the latter item."""
    seen_starts = set()
    result = []

    for item in hours:
        if item.start not in seen_starts:
            result.append(item)
            seen_starts.add(item.start)

    return result
