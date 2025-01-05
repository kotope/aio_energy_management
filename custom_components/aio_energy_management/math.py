"""Math functions for cheapest hours."""

from datetime import timedelta
import logging

import numpy as np

import homeassistant.util.dt as dt_util

from .exceptions import InvalidInput

_LOGGER = logging.getLogger(__name__)


# TODO: Support for daylight saving days.. e.g. not hard coded 24h
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

    # Function specific varialbes
    prices = today + tomorrow
    cheapest_price = 999.99
    mean_price: float = 0.0
    max_price: float | None = None
    min_price: float | None = None

    if inversed:
        cheapest_price = -999.99

    cheapest_hour = dt_util.start_of_local_day()
    counter = 0.00
    starting = first_hour
    ending = last_hour + 1 + 24

    if starting_today is False:
        starting = first_hour + 24
    for i in range(starting + number_of_hours, ending + 1):
        counter = 0.0
        max_temp = -999.0
        min_temp = 999.99

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


# TODO: Support for daylight saving days.. e.g. not hard coded 24h
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

    arr = today + tomorrow
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
