"""Math functions for cheapest hours."""

from datetime import timedelta
import logging

import homeassistant.util.dt as dt_util

from ..enums import HourPriceType
from ..exceptions import InvalidInput, ValueNotFound
from ..models.hour_price import HourPrice
from .selection import SelectionRules, select_slots

_LOGGER = logging.getLogger(__name__)

MAX_PRICE_VALUE = 99999.9
MIN_PRICE_VALUE = -99999.9

# Guards against floating point noise when comparing against min price + delta,
# e.g. -0.15 + 0.03 must still include a slot priced exactly -0.12.
PRICE_DELTA_TOLERANCE = 1e-9


def calculate_sequential_cheapest_hours(
    today: list,
    tomorrow: list,
    number_of_slots: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
    inversed: bool = False,
    price_limit: float | None = None,
    mtu: int = 60,
    max_number_of_slots: int | None = None,
    flexible_price_limit: float | None = None,
    max_price_delta: float | None = None,
) -> (dict, bool):
    """Calculate sequential cheapest hours.

    The result is always a single contiguous block. The cheapest block of
    ``number_of_slots`` is selected first (``price_limit`` applies to its mean)
    and, when ``max_number_of_slots`` and ``flexible_price_limit`` (or
    ``max_price_delta``) are provided, grown at its edges while the neighbours stay
    within the flexible limit, up to ``max_number_of_slots`` slots in total.
    """
    window, has_tomorrow = _load_window(
        today,
        tomorrow,
        number_of_slots,
        starting_today,
        first_hour,
        last_hour,
        mtu,
        max_number_of_slots,
        "sequential",
    )

    # Extra safety check if the number of slots fits within the amounts of slots we have.
    if number_of_slots > len(window):
        _LOGGER.warning(
            "The search window is too small for the requested number of sequential slots (e.g. overnight window capped to today's end)"
        )
        raise ValueNotFound

    rules = _build_rules(
        window,
        number_of_slots,
        inversed,
        price_limit,
        max_number_of_slots,
        flexible_price_limit,
        max_price_delta,
        single_block=True,
    )
    return (_build_result(select_slots(window, rules)), not has_tomorrow)


def calculate_non_sequential_cheapest_hours(
    today: list,
    tomorrow: list,
    number_of_slots: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
    inversed: bool = False,
    price_limit: float | None = None,
    mtu: int = 60,
    max_number_of_slots: int | None = None,
    flexible_price_limit: float | None = None,
    min_seq_slots: int = 1,  # defaults to 1 for backwards compatibility
    number_of_blocks: int | None = None,
    max_price_delta: float | None = None,
) -> (dict, bool):
    """Calculate non-sequential cheapest hours.

    The cheapest ``number_of_slots`` slots are selected, subject to ``price_limit``
    (per slot). When ``max_number_of_slots`` and ``flexible_price_limit`` are both
    provided, the selection is extended with the next-cheapest slots while their
    individual price stays within ``flexible_price_limit`` (above it when
    ``inversed``), for at most ``max_number_of_slots`` slots in total.

    Instead of a fixed ``flexible_price_limit``, ``max_price_delta`` makes the limit
    relative: extra slots are added while their price is within ``max_price_delta``
    of the cheapest price (most expensive when ``inversed``) in the search window.
    If both are given, ``flexible_price_limit`` wins.

    ``min_seq_slots`` and ``number_of_blocks`` bound the length of every block of
    consecutive slots. All rules are solved together (see ``select_slots``), so
    when they cannot all be met the number of slots drops instead of a rule being
    broken. ``number_of_blocks`` takes precedence over ``min_seq_slots``.
    """
    window, has_tomorrow = _load_window(
        today,
        tomorrow,
        number_of_slots,
        starting_today,
        first_hour,
        last_hour,
        mtu,
        max_number_of_slots,
        "non-sequential",
    )

    if number_of_blocks and number_of_blocks > 0 and min_seq_slots > 1:
        _LOGGER.debug(
            "Both number_of_blocks and min_seq_slots were provided. "
            "number_of_blocks will take precedence."
        )

    rules = _build_rules(
        window,
        number_of_slots,
        inversed,
        price_limit,
        max_number_of_slots,
        flexible_price_limit,
        max_price_delta,
        min_seq_slots=min_seq_slots,
        number_of_blocks=number_of_blocks,
    )
    return (_build_result(select_slots(window, rules)), not has_tomorrow)


def _load_window(
    today: list,
    tomorrow: list,
    number_of_slots: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
    mtu: int,
    max_number_of_slots: int | None,
    kind: str,
) -> tuple[list[dict], bool]:
    """Validate the input and return the slots of the search window.

    The slots are chronological and contiguous, as dicts with start, end and price.
    Also returns whether tomorrow's prices were available.
    """
    if (
        _is_cheapest_hours_input_valid(
            number_of_slots,
            starting_today,
            first_hour,
            last_hour,
            mtu,
            max_number_of_slots,
        )
        is False
    ):
        _LOGGER.error("Invalid configuration for %s cheapest hours sensor", kind)
        raise InvalidInput

    # TODAY is mandatory
    td = _check_day_light_savings(today, mtu=mtu)
    if not _is_valid_data_length(td, mtu):
        _LOGGER.error(
            "Today's data provided for calculation has invalid amount of values"
        )
        raise ValueNotFound

    # TOMORROW is optional
    has_tomorrow = False
    tm = []
    if tomorrow:
        try:
            tm_temp = _check_day_light_savings(tomorrow, mtu=mtu)
            if _is_valid_data_length(tm_temp, mtu):
                tm = tm_temp
                has_tomorrow = True
        except Exception:
            _LOGGER.debug(
                "Tomorrow's data is invalid or empty. Proceeding with today's data only"
            )

    starting = first_hour
    if not starting_today and has_tomorrow:
        starting = first_hour + 24

    # Check if an overnight window has been configured, to prevent undesired calculations
    if first_hour > last_hour and not has_tomorrow:
        _LOGGER.debug(
            "Overnight window (first_hour=%s to last_hour=%s) crosses midnight, but tomorrow's prices are not available yet. "
            "Skipping calculation to preserve current calendar events",
            first_hour,
            last_hour,
        )
        raise ValueNotFound

    ending = last_hour + 1 + 24 if has_tomorrow else last_hour + 1

    if starting >= ending:
        _LOGGER.warning(
            "No valid hours to check in the current window (possibly overnight window without tomorrow's prices yet)"
        )
        raise ValueNotFound

    prices = [item.value for item in td + tm]
    per_hour = 4 if mtu == 15 else 1
    slot = timedelta(minutes=15 if mtu == 15 else 60)
    day_start = dt_util.start_of_local_day()
    window = [
        {
            "start": day_start + slot * i,
            "end": day_start + slot * (i + 1),
            "price": prices[i],
        }
        for i in range(starting * per_hour, ending * per_hour)
    ]
    return window, has_tomorrow


def _build_rules(
    window: list[dict],
    number_of_slots: int,
    inversed: bool,
    price_limit: float | None,
    max_number_of_slots: int | None,
    flexible_price_limit: float | None,
    max_price_delta: float | None,
    **block_rules,
) -> SelectionRules:
    """Translate the sensor configuration into selection rules."""
    flexible_limit = None
    if max_number_of_slots is not None:
        if max_number_of_slots < number_of_slots:
            _LOGGER.warning(
                "max_number_of_slots (%s) is less than number_of_slots (%s), "
                "using %s as max_number_of_slots",
                max_number_of_slots,
                number_of_slots,
                number_of_slots,
            )
            max_number_of_slots = number_of_slots
        flexible_limit = _get_flexible_limit(
            [slot["price"] for slot in window],
            flexible_price_limit,
            max_price_delta,
            inversed,
        )
    return SelectionRules(
        number_of_slots=int(number_of_slots),
        inversed=inversed,
        price_limit=price_limit,
        max_number_of_slots=max_number_of_slots,
        flexible_limit=flexible_limit,
        **block_rules,
    )


def _build_result(selected: list[dict]) -> dict:
    """Build the sensor result: combined blocks and price statistics."""
    selected = sorted(selected, key=lambda x: x["start"])

    blocks: list[dict] = []
    for item in selected:
        if blocks and blocks[-1]["end"] == item["start"]:
            blocks[-1]["end"] = item["end"]
        else:
            blocks.append({"start": item["start"], "end": item["end"]})

    return {
        "extra": {
            "mean_price": _get_average(selected),
            "max_price": _get_max(selected),
            "min_price": _get_min(selected),
        },
        "list": blocks,
    }


def _get_flexible_limit(
    prices: list[float],
    flexible_price_limit: float | None,
    max_price_delta: float | None,
    inversed: bool,
) -> float | None:
    """Return the price limit for flexible slots.

    A fixed ``flexible_price_limit`` takes precedence. Otherwise the limit is
    derived from the best price in ``prices``: cheapest price + ``max_price_delta``
    (most expensive price - delta when ``inversed``).
    """
    if flexible_price_limit is not None:
        return flexible_price_limit
    if max_price_delta is not None and prices:
        if inversed:
            return max(prices) - max_price_delta - PRICE_DELTA_TOLERANCE
        return min(prices) + max_price_delta + PRICE_DELTA_TOLERANCE
    return None


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
    number_of_slots: int,
    starting_today: bool,
    first_hour: int,
    last_hour: int,
    mtu: int,
    max_number_of_slots: int | None = None,
) -> bool:
    if starting_today is False:
        if last_hour < first_hour:
            return False
    if starting_today is True:
        if first_hour < last_hour:
            return False

    cap = 96 if mtu == 15 else 24
    if number_of_slots > cap:
        return False
    if max_number_of_slots is not None and max_number_of_slots > cap:
        return False
    return True


def _check_day_light_savings(
    hours: list, inversed: bool = False, mtu: int = 60
) -> list:
    # mtu 15: two DST scenarios exist for 15-min data with 92 items:
    # 1. Data has a UTC gap (e.g. 03:00-03:45 UTC missing) → _add_missing_hour
    #    detects it and inserts 4 items at the correct position.
    # 2. Nord Pool Official delivers UTC-aligned data with NO gap (the 23-hour
    #    day simply has 92 consecutive items). _add_missing_hour finds nothing
    #    so we insert at the local wall-clock DST gap instead.
    if mtu == 15:
        if len(hours) == 92:
            result = _add_missing_hour(hours, inversed, mtu=mtu)
            if (
                len(result) == 92
                and hours
                and hours[0].type == HourPriceType.NORDPOOL_OFFICIAL
            ):
                return _insert_at_local_dst_gap(result, count=4, inversed=inversed)
            return result
        if len(hours) == 100:
            return _remove_duplicate_starts(hours)
        return hours

    # mtu 60: same two-scenario pattern as mtu=15 for Nord Pool Official data.
    # 1. Data has a detectable 2-hour UTC gap → _add_missing_hour handles it.
    # 2. UTC-aligned data (NORDPOOL_OFFICIAL) has no gap; 23-hour DST day gives
    #    23 consecutive items. Fall back to local wall-clock gap insertion.
    if len(hours) == 23:
        result = _add_missing_hour(hours, inversed, mtu=mtu)
        if (
            len(result) == 23
            and hours
            and hours[0].type == HourPriceType.NORDPOOL_OFFICIAL
        ):
            return _insert_at_local_dst_gap(result, count=1, inversed=inversed, mtu=mtu)
        return result
    if len(hours) == 25:
        return _remove_duplicate_starts(hours)
    return hours


def _is_valid_data_length(hours: list, mtu: int) -> bool:
    if mtu == 15:
        if len(hours) != 96:
            return False
    elif len(hours) != 24:  # mtu = 60
        return False
    return True


def _add_missing_hour(hours: list, inversed: bool, mtu: int = 60) -> list:
    """Add missing hour when turning to summer time. The new hour added has the value of max or min depending of inversed state."""
    # Find the missing entry's index by checking time difference.

    missing_indexes = []
    # missing_index = -1
    for i in range(len(hours) - 1):
        time_diff = hours[i + 1].start - hours[i].start
        time_diff_hours = time_diff.total_seconds() / 3600.0

        if mtu == 15:
            if time_diff_hours >= 1.25:
                missing_indexes.extend([i - 3, i - 2, i - 1, i])
                break
        elif time_diff_hours >= 2:
            # Missing one index
            missing_indexes.append(i + 1)
            break

    if len(missing_indexes) == 0:
        return hours  # No missing entry found

    # Create the missing entries
    for i in missing_indexes:
        delta = timedelta(hours=1)
        if mtu == 15:
            delta = timedelta(minutes=15, hours=1)
        missing_start_time = hours[i - 1].start + delta

        if inversed:
            missing_value = MIN_PRICE_VALUE
        else:
            missing_value = MAX_PRICE_VALUE

        # Insert the missing entries into the data
        if mtu == 15:
            hours.insert(
                i + 4, HourPrice(value=missing_value, start=missing_start_time)
            )
        else:
            hours.insert(i, HourPrice(value=missing_value, start=missing_start_time))

    return hours


def _insert_at_local_dst_gap(
    hours: list, count: int, inversed: bool, mtu: int = 15
) -> list:
    """Insert synthetic slots at the DST spring-forward gap in local wall-clock time.

    Used for NORDPOOL_OFFICIAL data where consecutive UTC entries at a DST
    spring-forward transition have no UTC gap but a local wall-clock gap.
    We detect the gap by comparing naive local hour×60+minute values; a jump
    of more than 60 minutes indicates the spring-forward point.
    The `mtu` parameter controls the time step for synthetic entry timestamps
    (15 minutes for 15-min data, 60 minutes for hourly data).
    """
    value = MIN_PRICE_VALUE if inversed else MAX_PRICE_VALUE
    prev_local_minutes: int | None = None
    for i in range(len(hours)):
        local_dt = dt_util.as_local(hours[i].start)
        local_minutes = local_dt.hour * 60 + local_dt.minute
        if prev_local_minutes is not None and local_minutes > prev_local_minutes + 60:
            # Found the spring-forward gap: insert count synthetic items here.
            insert_start = hours[i - 1].start + timedelta(minutes=mtu)
            for k in range(count):
                hours.insert(
                    i + k,
                    HourPrice(
                        value=value, start=insert_start + timedelta(minutes=k * mtu)
                    ),
                )
            return hours
        prev_local_minutes = local_minutes
    # Fallback: no gap found — pad at end.
    for _ in range(count):
        hours.append(
            HourPrice(value=value, start=hours[-1].start + timedelta(minutes=mtu))
        )
    return hours


def _remove_duplicate_starts(hours: list) -> list:
    """Remove duplicate hour when turning to winter time. Hour removed is the latter item."""
    seen_starts = set()
    result = []

    for item in hours:
        # Official prices have distinct UTC instants for the repeated local hour.
        # Other sources may already provide identical start timestamps.
        start = (
            dt_util.as_local(item.start).replace(tzinfo=None)
            if item.type == HourPriceType.NORDPOOL_OFFICIAL
            else item.start
        )
        if start not in seen_starts:
            result.append(item)
            seen_starts.add(start)

    return result
