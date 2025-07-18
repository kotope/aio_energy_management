"""Defines a cheapest hours model."""

import datetime

from ..enums import HourPriceType
from ..helpers import from_str_to_datetime


class HourPrice:
    """Cheapest hour model."""

    def __init__(
        self, value: float, start: datetime, type=HourPriceType.NORDPOOL
    ) -> None:
        """Initialize HourPrice with value, start time, type, and length.

        Args:
            value (float): The price value.
            start (datetime): The start time of the hour.
            type (HourPriceType): The type of the hour price (default: NORDPOOL).

        """
        self.start = start
        self.value = value
        self.type = type

    @classmethod
    def from_dict(cls, dict: dict, type=HourPriceType.NORDPOOL) -> None:
        """Init Hour Price model with selected type. Single item."""
        if type is HourPriceType.ENTSOE:
            return cls(dict["price"], from_str_to_datetime(dict["time"]), type)
        if type is HourPriceType.NORDPOOL_OFFICIAL:
            return cls(dict["price"], from_str_to_datetime(dict["start"]), type)
        return cls(dict["value"], from_str_to_datetime(dict["start"]), type)
