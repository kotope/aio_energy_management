"""Math functions for cheapest hours."""

from datetime import timedelta
import logging
import math

import numpy as np

import homeassistant.util.dt as dt_util

from ..enums import HourPriceType
from ..exceptions import InvalidInput, ValueNotFound
from ..models.hour_price import HourPrice

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

    When ``max_number_of_slots`` and ``flexible_price_limit`` (or
    ``max_price_delta``) are provided, the cheapest block of ``number_of_slots``
    is selected first (subject to the regular ``price_limit`` on its mean) and
    then grown at its edges, each time taking the best neighbour while its price
    stays within the flexible limit, up to ``max_number_of_slots`` slots in total
    (base slots included). The result is always a single contiguous block. A
    ``max_number_of_slots`` below ``number_of_slots`` is raised to
    ``number_of_slots``.
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

    if inversed:
        cheapest_price = MIN_PRICE_VALUE

    best_start = 0
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
        counter = sum(prices[i - number_of_slots : i])

        if (inversed and counter > cheapest_price) or (
            not inversed and counter < cheapest_price
        ):
            # If the price is 'better' than previous
            cheapest_price = counter
            mean_price = counter / number_of_slots
            best_start = i - number_of_slots

    # The regular price_limit applies to the base block only
    if price_limit is not None and (
        (not inversed and mean_price > price_limit)
        or (inversed and mean_price < price_limit)
    ):
        fd["list"] = []
        fd["extra"]["mean_price"] = None
        fd["extra"]["max_price"] = None
        fd["extra"]["min_price"] = None
        return (fd, not has_tomorrow)

    best_end = best_start + number_of_slots

    if max_number_of_slots is not None and max_number_of_slots < number_of_slots:
        _LOGGER.warning(
            "max_number_of_slots (%s) is less than number_of_slots (%s), "
            "using %s as max_number_of_slots",
            max_number_of_slots,
            number_of_slots,
            number_of_slots,
        )
        max_number_of_slots = number_of_slots

    # Grow the block with flexible slots at its edges
    if max_number_of_slots:
        limit = _get_flexible_limit(
            prices[starting:ending], flexible_price_limit, max_price_delta, inversed
        )
        if limit is not None:
            best_start, best_end = _extend_sequential_block(
                prices,
                best_start,
                best_end,
                starting,
                ending,
                max_number_of_slots - number_of_slots,
                limit,
                inversed,
            )

    block = prices[best_start:best_end]
    slot = timedelta(minutes=mtu)
    cheapest_hour = dt_util.start_of_local_day() + slot * best_start
    fd["list"] = [{"start": cheapest_hour, "end": cheapest_hour + slot * len(block)}]

    fd["extra"]["mean_price"] = sum(block) / len(block)
    fd["extra"]["max_price"] = max(block)
    fd["extra"]["min_price"] = min(block)
    return (fd, not has_tomorrow)


def _extend_sequential_block(
    prices: list[float],
    start: int,
    end: int,
    window_start: int,
    window_end: int,
    max_extra: int,
    limit: float,
    inversed: bool,
) -> tuple[int, int]:
    """Grow the block [start, end) with the best neighbouring slot while within limit.

    The block never grows beyond [window_start, window_end). On equal prices the
    earlier (left) slot is preferred.
    """
    mult = -1 if inversed else 1
    for _ in range(max_extra):
        candidates = []
        if start > window_start:
            candidates.append((prices[start - 1] * mult, 0))
        if end < window_end:
            candidates.append((prices[end] * mult, 1))
        if not candidates:
            break

        score, side = min(candidates)
        if score > limit * mult:
            # The best neighbour exceeds the limit, so the other one does too.
            break
        if side == 0:
            start -= 1
        else:
            end += 1
    return (start, end)


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

    When ``max_number_of_slots`` and ``flexible_price_limit`` are both provided,
    the base ``number_of_slots`` cheapest slots are always selected (subject to
    the regular ``price_limit``) and then extended with the next-cheapest slots
    while their individual price stays below ``flexible_price_limit`` (above it
    when ``inversed``), for at most ``max_number_of_slots`` slots in total. A
    ``max_number_of_slots`` below ``number_of_slots`` is raised to
    ``number_of_slots``.

    Instead of a fixed ``flexible_price_limit``, ``max_price_delta`` can be used
    to make the limit relative: extra slots are added while their price is within
    ``max_price_delta`` of the cheapest price (most expensive when ``inversed``)
    in the search window. If both are given, ``flexible_price_limit`` wins.
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

    # Base slots: the cheapest number_of_slots, subject to the regular price_limit.
    base_count = int(number_of_slots)

    if max_number_of_slots is not None and max_number_of_slots < number_of_slots:
        _LOGGER.warning(
            "max_number_of_slots (%s) is less than number_of_slots (%s), "
            "using %s as max_number_of_slots",
            max_number_of_slots,
            number_of_slots,
            number_of_slots,
        )
        max_number_of_slots = number_of_slots

    candidate_slots = _select_flexible_slots(
        all_window_slots,
        base_count,
        max_number_of_slots,
        flexible_price_limit,
        inversed,
        max_price_delta,
    )

    # The regular price_limit only applies to the base slots, which
    # _select_flexible_slots always returns first. Flexible slots (the rest)
    #  are only bound by flexible_price_limit / max_price_delta.
    base_part = candidate_slots[:base_count]
    flexible_part = candidate_slots[base_count:]
    if price_limit is not None:
        if inversed:
            base_part = [s for s in base_part if s["price"] >= price_limit]
        else:
            base_part = [s for s in base_part if s["price"] <= price_limit]

    actual_number_of_slots = len(base_part) + len(flexible_part)

    if actual_number_of_slots == 0:
        data = []
    else:
        # Initialize max_seq_slots to None by default
        max_seq_slots: int | None = None

        # Translate number_of_blocks to min_seq_slots and max_seq_slots if provided,
        # based on the actual number of slots instead of the configured number.
        if number_of_blocks and number_of_blocks > 0:
            if min_seq_slots > 1:
                _LOGGER.debug(
                    "Both number_of_blocks and min_seq_slots were provided. "
                    "number_of_blocks will take precedence."
                )
            effective_blocks = min(number_of_blocks, actual_number_of_slots)
            min_seq_slots = actual_number_of_slots // effective_blocks
            max_seq_slots = math.ceil(actual_number_of_slots / effective_blocks)

        # Select the final slots according to min_seq_slots / max_seq_slots.
        data = _select_slots_with_min_seq_slot_size(
            all_window_slots,
            actual_number_of_slots,
            min_seq_slots=min_seq_slots,
            max_seq_slots=max_seq_slots,
            inversed=inversed,
        )

    data.sort(key=lambda x: x["start"])

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
    max_price_delta: float | None = None,
) -> list[dict]:
    """Select base slots and optionally extend them with flexible slots.

    The base ``number_of_slots`` slots are always selected (the caller applies the
    regular ``price_limit`` to them afterwards). When both
    ``max_number_of_slots`` and ``flexible_price_limit`` are provided, extra
    slots are appended while their price stays within ``flexible_price_limit``,
    for at most ``max_number_of_slots`` slots in total (base slots included).

    Alternatively ``max_price_delta`` can be given instead of
    ``flexible_price_limit``. The limit is then derived from the best price in
    ``all_slots``: cheapest price + delta (most expensive price - delta when
    ``inversed``). If both are given, ``flexible_price_limit`` takes precedence.
    """
    mult = -1 if inversed else 1

    # Support both base_slots (list) and int (for backwards compatibility)
    if isinstance(base_slots_or_count, int):
        selected = sorted(all_slots, key=lambda x: (x["price"] * mult, x["start"]))[
            :base_slots_or_count
        ]
    else:
        selected = list(base_slots_or_count)

    if max_number_of_slots is None:
        return selected

    # Determine the limit for extra slots: fixed, or relative to the best price.
    limit = _get_flexible_limit(
        [s["price"] for s in all_slots],
        flexible_price_limit,
        max_price_delta,
        inversed,
    )
    if limit is None:
        return selected

    base_starts = {s["start"] for s in selected}

    # Which slots of the day are NOT part of an already chosen slot?
    remaining_candidates = sorted(
        [s for s in all_slots if s["start"] not in base_starts],
        key=lambda x: (x["price"] * mult, x["start"]),
    )

    extra_slots = max(0, max_number_of_slots - len(selected))
    for slot in remaining_candidates[:extra_slots]:
        within_limit = slot["price"] >= limit if inversed else slot["price"] <= limit
        if not within_limit:
            # Data is sorted, so no later slot can satisfy the limit either.
            break
        selected.append(slot)

    return selected


def _select_slots_with_min_seq_slot_size(
    data: list[dict],
    number_of_slots: int,
    min_seq_slots: int = 1,
    max_seq_slots: int | None = None,
    inversed: bool = False,
) -> list[dict]:
    """Select slots so that every consecutive block has a length within
    [min_seq_slots, max_seq_slots], minimising total price (or maximising if inversed).

    Assumes `data` is sorted chronologically and contiguous (index adjacency == time adjacency).
    """
    # IF min_seq_slots == 1: keep original behavior
    if min_seq_slots <= 1 and max_seq_slots is None:
        sorted_data = sorted(data, key=lambda x: x["price"], reverse=inversed)
        return sorted_data[:number_of_slots]

    n = len(data)
    target = min(number_of_slots, n)
    lo = max(min_seq_slots, 1)
    hi = max_seq_slots if max_seq_slots is not None else n
    mult = -1 if inversed else 1

    # Prefix sums of (signed) prices for O(1) block cost in order to calculate prices efficiently
    prefix = [0.0]
    for item in data:
        prefix.append(prefix[-1] + item["price"] * mult)

    # Setup Dynamic Programming tables
    INF = float("inf")
    # dp[i][k]: minimal cost to pick k more slots from slots i..n-1,
    # given slot i-1 is NOT selected (or i == 0).
    dp = [[INF] * (target + 1) for _ in range(n + 1)]
    choice = [
        [0] * (target + 1) for _ in range(n + 1)
    ]  # 0 = skip slot i, L>0 = block of length L
    dp[n][0] = 0.0

    # Start creating actual blocks
    for i in range(n - 1, -1, -1):
        for k in range(target + 1):
            # Option 1: skip slot i
            best = dp[i + 1][k]
            best_choice = 0

            # Option 2: start a block of length L at i (followed by a mandatory gap)
            for L in range(lo, min(hi, k, n - i) + 1):
                nxt = min(i + L + 1, n)
                rest = dp[nxt][k - L]
                if rest == INF:
                    continue
                cost = prefix[i + L] - prefix[i] + rest
                if cost < best:
                    best = cost
                    best_choice = L

            dp[i][k] = best
            choice[i][k] = best_choice

    if dp[0][target] == INF:
        # Constraints cannot be satisfied (e.g. target < min_seq_slots): fall back
        sorted_data = sorted(data, key=lambda x: x["price"], reverse=inversed)
        return sorted(sorted_data[:target], key=data.index)

    # Reconstruct selection
    selected: list[int] = []
    i, k = 0, target
    while i < n and k > 0:
        L = choice[i][k]
        if L == 0:
            i += 1
        else:
            selected.extend(range(i, i + L))
            k -= L
            i = min(i + L + 1, n)

    return [data[idx] for idx in selected]


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
