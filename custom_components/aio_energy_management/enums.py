"""Enums."""

from enum import Enum


class HourPriceType(Enum):
    """Type of Hour Price."""

    NORDPOOL = "nordpool"
    ENTSOE = "entsoe"
