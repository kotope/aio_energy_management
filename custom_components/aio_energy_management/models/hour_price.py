"""Defines a cheapest hours model."""

import datetime

from ..enums import HourPriceType  # noqa: TID252
from ..helpers import from_str_to_datetime  # noqa: TID252


class HourPrice:
    """Cheapest hour model."""

    def __init__(
        self,
        value: float,
        start: datetime.datetime,
        end: datetime.datetime | None = None,
        type=HourPriceType.NORDPOOL,
    ) -> None:
        """Initialize HourPrice with value, start time, end time, type, and length.

        Args:
            value (float): The price value.
            start (datetime): The start time of the price item.
            end (datetime): The end time of the price item. If None, it will be set to start + 1 hour.
            type (HourPriceType): The type of the hour price (default: NORDPOOL).

        """
        self.start = start
        self.end = end
        if end is None:
            self.end = start + datetime.timedelta(hours=1)
        else:
            self.end = end
        self.value = value
        self.type = type

    @classmethod
    def from_dict(cls, dict: dict, type=HourPriceType.NORDPOOL) -> None:
        """Init Hour Price model with selected type. Single item."""
        if type is HourPriceType.ENTSOE:
            return cls(
                dict["price"],
                from_str_to_datetime(dict["time"]),
                from_str_to_datetime(dict["time"]) + datetime.timedelta(hours=1),
                type,
            )
        if type is HourPriceType.NORDPOOL_OFFICIAL:
            return cls(
                dict["price"],
                from_str_to_datetime(dict["start"]),
                type,
            )
        return cls(
            dict["value"],
            from_str_to_datetime(dict["start"]),
            type,
        )
