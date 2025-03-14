"""Helpers."""

from datetime import datetime, time
import logging

import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)


def convert_datetime(items: list | None) -> list | None:
    """Convert array datetime str to datetime obj if existing."""
    if items is None:
        return None

    def apply(x):
        start = x.get("start")
        end = x.get("end")
        if isinstance(start, str):
            x["start"] = from_str_to_datetime(start)
        if isinstance(end, str):
            x["end"] = from_str_to_datetime(end)
        return x

    return list(map(apply, items))


def from_str_to_time(value) -> time | None:
    """Convert time str to time."""
    if value is None:
        return None

    if isinstance(value, str):
        value = dt_util.parse_time(value)

    return datetime.combine(datetime.today(), value).timetz()


def from_str_to_datetime(value) -> datetime | None:
    """Convert str to datetime."""
    if value is None:
        return None

    if isinstance(value, str):
        return dt_util.parse_datetime(value)
    return value


def time_in_between(now, start, end):
    """Check if time is in between two values."""
    if start <= end:
        return start <= now < end
    # over midnight e.g., 23:30-04:15
    return start <= now or now < end


def merge_two_dicts(x, y):
    """Merge two dictionaries."""
    z = x.copy()  # start with keys and values of x
    z.update(y)  # modifies z with keys and values of y
    return z


def get_first(iterable, default=None):
    """Get first item of array."""
    if iterable:
        for item in iterable:
            return item
    return default


def get_last(iterable, default=None):
    """Get last item of array."""
    if not iterable:
        return None
    return iterable[-1]
