"""Math functions for cheapest hours."""

from datetime import timedelta
import logging

import numpy as np
import math

import homeassistant.util.dt as dt_util

from ..enums import HourPriceType
from ..exceptions import InvalidInput, ValueNotFound
from ..models.hour_price import HourPrice

_LOGGER = logging.getLogger(__name__)

MAX_PRICE_VALUE = 99999.9
MIN_PRICE_VALUE = -99999.9


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
) -> (dict, bool):
    """Calculate sequential cheapest hours."""
    if (
        _is_cheapest_hours_input_valid(
            number_of_slots, starting_today, first_hour, last_hour, mtu
        )
        is False
    ):
        _LOGGER.error("Invalid configuration for sequential cheapest hours sensor")
        raise InvalidInput

    fd: dict = {}  # Final data dictionary
    fd["extra"] = {}

    # Check daylight savings & TODAY is mandatory
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
            # Check daylight savings
            tm_temp = _check_day_light_savings(tomorrow, mtu=mtu)
            if _is_valid_data_length(tm_temp, mtu):
                tm = tm_temp
                has_tomorrow = True
        except Exception:
            _LOGGER.debug(
                "Tomorrow's data is invalid or empty. Proceeding with today's data only"
            )

    # Function specific variables
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
    if not starting_today and has_tomorrow:
        starting = first_hour + 24

    # Check if an overnight window has been configured, to prevent undesired calculations
    if first_hour > last_hour and not has_tomorrow:
        _LOGGER.debug(
            "Overnight window first_hour=%s, last_hour=%s crosses midnight, but tomorrow's prices are not available yet. "
            "Skipping calculation to preserve current calendar events",
            first_hour,
            last_hour,
        )
        raise ValueNotFound

    if has_tomorrow:
        ending = last_hour + 1 + 24
    else:
        ending = last_hour + 1

    if starting >= ending:
        _LOGGER.warning(
            "No valid hours to check in the current window (possibly overnight window without tomorrow's prices yet)"
        )
        raise ValueNotFound

    if mtu == 15:
        starting = starting * 4
        ending = ending * 4

    # Extra safety check if the number of slots fits within the amounts of slots we have.
    if (starting + number_of_slots) > ending:
        _LOGGER.warning(
            "The search window is too small for the requested number of sequential slots (e.g. overnight window capped to today's end)"
        )
        raise ValueNotFound

    for i in range(starting + number_of_slots, ending + 1):
        counter = 0.0
        max_temp = MIN_PRICE_VALUE
        min_temp = MAX_PRICE_VALUE

        for j in range(i - number_of_slots, i):
            counter += prices[j]
            max_temp = max(max_temp, prices[j])
            min_temp = min(min_temp, prices[j])

        if (inversed and counter > cheapest_price) or (
            not inversed and counter < cheapest_price
        ):
            # If the price is 'better' than previous
            max_price = max_temp
            min_price = min_temp
            cheapest_price = counter
            mean_price = counter / number_of_slots
            delta = timedelta(hours=i - number_of_slots)

            if mtu == 15:
                delta = timedelta(minutes=15 * (i - number_of_slots))

            cheapest_hour = dt_util.start_of_local_day() + delta

    delta = timedelta(hours=number_of_slots)
    if mtu == 15:
        delta = timedelta(minutes=15 * number_of_slots)

    if price_limit is not None and (
        (not inversed and mean_price > price_limit)
        or (inversed and mean_price < price_limit)
    ):
        fd["list"] = []
        fd["extra"]["mean_price"] = None
        fd["extra"]["max_price"] = None
        fd["extra"]["min_price"] = None
        return fd

    fd["list"] = [{"start": cheapest_hour, "end": cheapest_hour + delta}]

    fd["extra"]["mean_price"] = mean_price
    fd["extra"]["max_price"] = max_price
    fd["extra"]["min_price"] = min_price
    return (fd, not has_tomorrow)


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
) -> (dict, bool):
    """Calculate non-sequential cheapest hours.

    When ``max_number_of_slots`` and ``flexible_price_limit`` are both provided,
    the base ``number_of_slots`` cheapest slots are always selected (subject to
    the regular ``price_limit``) and then extended with up to
    ``max_number_of_slots`` additional next-cheapest slots while their individual
    price stays below ``flexible_price_limit`` (above it when ``inversed``), for
    at most ``number_of_slots + max_number_of_slots`` slots in total.
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
        _LOGGER.error("Invalid configuration for non-sequential cheapest hours sensor")
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

    arr = [
        {
            "price": item.value,
            "start": item.start,
            "end": item.end,
        }
        for item in td + tm
    ]  # combined array with tomorrow and today.

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

    if has_tomorrow:
        ending = last_hour + 1 + 24
    else:
        ending = last_hour + 1

    if starting >= ending:
        _LOGGER.warning(
            "No valid hours to check in the current window (possibly overnight window without tomorrow's prices yet)"
        )
        raise ValueNotFound

    data = []
    fd: dict = {}  # Final data dictionary
    fd["extra"] = {}

    # TODO: This could be refactored to use less code duplication.
    # arr contains all necessary data already, just need to take first_hour and last_hour into account
    if mtu == 15:
        for i in range(starting * 4, ending * 4):
            start = dt_util.start_of_local_day() + timedelta(minutes=i * 15)
            end = dt_util.start_of_local_day() + timedelta(minutes=(i + 1) * 15)
            data += [{"start": start, "end": end, "price": arr[i]["price"]}]
    else:
        for i in range(starting, ending):
            start = dt_util.start_of_local_day() + timedelta(hours=i)
            end = dt_util.start_of_local_day() + timedelta(hours=i + 1)
            data += [{"start": start, "end": end, "price": arr[i]["price"]}]

    # Save all available slots unsorted --> replaced data.sort(key=lambda x: (x["price"], x["start"], x["end"]), reverse=inversed)
    all_window_slots = list(data)

    # Initialize max_seq_slots to None by default
    max_seq_slots: int | None = None

    # Translate number_of_blocks to min_seq_slots and max_seq_slots if provided
    if number_of_blocks and number_of_blocks > 0:
        if min_seq_slots > 1:
            _LOGGER.debug(
                "Both number_of_blocks and min_seq_slots were provided. "
                "number_of_blocks will take precedence."
            )
        effective_blocks = min(number_of_blocks, number_of_slots)
        min_seq_slots = number_of_slots // effective_blocks
        max_seq_slots = math.ceil(number_of_slots / effective_blocks)

    # Select base slots according to min_seq_slots info.
    base_slots = _select_slots_with_min_seq_slot_size(
        all_window_slots,
        number_of_slots,
        min_seq_slots=min_seq_slots,
        max_seq_slots=max_seq_slots,
        inversed=inversed,
    )

    # 2. Extend base slots with possible flexible slots according to flexible_price_limit
    data = _select_flexible_slots(
        all_window_slots,
        base_slots,
        max_number_of_slots,
        flexible_price_limit,
        inversed,
    )

    data.sort(key=lambda x: x["start"])
    if inversed:
        if mp := price_limit:
            data = [d for d in data if d["price"] >= mp]
    elif mp := price_limit:
        data = [d for d in data if d["price"] <= mp]

    fd["extra"]["mean_price"] = _get_average(data)
    fd["extra"]["max_price"] = _get_max(data)
    fd["extra"]["min_price"] = _get_min(data)

    # Combine sequential slots
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
    return (fd, not has_tomorrow)


def _select_flexible_slots(
    all_slots: list[dict],
    base_slots_or_count: list[dict] | int,
    max_number_of_slots: int | None,
    flexible_price_limit: float | None,
    inversed: bool,
) -> list[dict]:
    """Select base slots and optionally extend them with flexible slots.

    The base ``number_of_slots`` slots are always selected (the caller applies the
    regular ``price_limit`` to them afterwards). When both
    ``max_number_of_slots`` and ``flexible_price_limit`` are provided, up to
    ``max_number_of_slots`` additional slots are appended while their price
    stays within ``flexible_price_limit``, for at most
    ``number_of_slots + max_number_of_slots`` slots in total.
    """
    mult = -1 if inversed else 1

    # Support both base_slots (list) and int (for backwards compatibility)
    if isinstance(base_slots_or_count, int):
        selected = sorted(all_slots, key=lambda x: (x["price"] * mult, x["start"]))[
            :base_slots_or_count
        ]
    else:
        selected = list(base_slots_or_count)

    if max_number_of_slots is None or flexible_price_limit is None:
        return selected

    base_starts = {s["start"] for s in selected}

    # Which slots of the day are NOT part of an already chosen slot?
    remaining_candidates = sorted(
        [s for s in all_slots if s["start"] not in base_starts],
        key=lambda x: (x["price"] * mult, x["start"]),
    )

    for slot in remaining_candidates[:max_number_of_slots]:
        within_limit = (
            slot["price"] >= flexible_price_limit
            if inversed
            else slot["price"] <= flexible_price_limit
        )
        if not within_limit:
            # Data is sorted, so no later slot can satisfy the limit either.
            break
        selected.append(slot)

    return selected


def _would_exceed_max_seq(
    selected: set[int], new_indices: set[int], max_seq: int | None
) -> bool:
    """Check if adding new_indices to selected creates a contiguous block larger than max_seq."""
    if max_seq is None:
        return False

    combined = selected | new_indices
    for idx in new_indices:
        left = idx
        while (left - 1) in combined:
            left -= 1
        right = idx
        while (right + 1) in combined:
            right += 1

        if (right - left + 1) > max_seq:
            return True
    return False


def _select_slots_with_min_seq_slot_size(
    data: list[dict],
    number_of_slots: int,
    min_seq_slots: int = 1,
    max_seq_slots: int | None = None,
    inversed: bool = False,
) -> list[dict]:
    """Select base slots with min_seq_slots, max_seq_slots, and inversed logic."""

    # IF min_seq_slots == 1: keep original behavior
    if min_seq_slots <= 1 and max_seq_slots is None:
        sorted_data = sorted(data, key=lambda x: x["price"], reverse=inversed)
        return sorted_data[:number_of_slots]

    # IF min_seq_slots > 1: set inversed * -1 to keep inversed functionality
    mult = -1 if inversed else 1
    total_available = len(data)
    selected_indices: set[int] = set()
    needed = number_of_slots

    # Phase A: Select blocks based on min_seq_slots (respecting max_seq_slots)
    while needed >= min_seq_slots:
        best_idx = -1
        best_score = float("inf")

        for i in range(total_available - min_seq_slots + 1):
            window = set(range(i, i + min_seq_slots))
            if window & selected_indices:
                continue  # Continue on overlapping slots which are already part of the selected_indices

            # Check if adding this window would merge with an adjacent block and exceed max_seq_slots
            if _would_exceed_max_seq(selected_indices, window, max_seq_slots):
                continue

            avg_price = sum(data[j]["price"] for j in window) / min_seq_slots
            score = avg_price * mult

            if score < best_score:
                best_score = score
                best_idx = i

        if best_idx == -1:
            break

        selected_indices.update(range(best_idx, best_idx + min_seq_slots))
        needed -= min_seq_slots

    # Phase B: Add remaining slots to the current borders of selected slots to keep the min_seq_slots rule (respecting max_seq_slots).
    while needed > 0 and len(selected_indices) < total_available:
        best_idx = -1
        best_score = float("inf")

        for i in range(total_available):
            if i in selected_indices:
                continue

            # Check if selected slot is next to an already chosen slot
            if (i - 1 in selected_indices) or (i + 1 in selected_indices):
                # Check max_seq_slots limit before attaching to border
                if _would_exceed_max_seq(selected_indices, {i}, max_seq_slots):
                    continue

                score = data[i]["price"] * mult
                if score < best_score:
                    best_score = score
                    best_idx = i

        if best_idx != -1:
            selected_indices.add(best_idx)
            needed -= 1
        else:
            # Failsafe: in case no match to attach remaining slots to borders, just select the cheapest slots. This could happen when min_seq_slots is higher than number_of_slots while don't violating max_seq_slots
            remaining = [
                i
                for i in range(total_available)
                if i not in selected_indices
                and not _would_exceed_max_seq(selected_indices, {i}, max_seq_slots)
            ]
            remaining.sort(key=lambda idx: data[idx]["price"] * mult)
            for idx in remaining:
                if needed == 0:
                    break
                if not _would_exceed_max_seq(selected_indices, {idx}, max_seq_slots):
                    selected_indices.add(idx)
                    needed -= 1
            break

    return [data[i] for i in sorted(selected_indices)]


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
        if item.start not in seen_starts:
            result.append(item)
            seen_starts.add(item.start)

    return result
