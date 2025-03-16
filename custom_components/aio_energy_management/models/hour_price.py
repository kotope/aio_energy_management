"""Defines a cheapest hours model."""

import datetime

from ..enums import HourPriceType
from ..helpers import from_str_to_datetime


class HourPrice:
    """Cheapest hour model."""

    def __init__(
        self,
        value: float,
        start: datetime,
        type=HourPriceType.NORDPOOL,
        length: int = 60,
    ) -> None:
        self.start = start
        self.value = value
        self.type = type

    @classmethod
    def from_dict(cls, dict: dict, type=HourPriceType.NORDPOOL) -> None:
        """Init Hour Price model with selected type. Single item."""
        if type is HourPriceType.ENTSOE:
            return cls(
                dict["price"], from_str_to_datetime(dict["time"]), type, length=60
            )
        elif type is HourPriceType.NORDPOOL_OFFICIAL:
            return cls(
                dict["price"],
                from_str_to_datetime(dict["start"]),
                type,
                length=60,
            )
        return cls(dict["value"], from_str_to_datetime(dict["start"]), type, length=60)
