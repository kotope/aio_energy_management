"""Tests for input sanitization helpers in cheapest_hours helpers."""

import os
import sys

# Allow importing the custom component without a full HA environment
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components"),
)

from aio_energy_management.cheapest_hours.config_flow import (  # noqa: E402
    CONF_FLEXIBLE_PRICE_LIMIT,
)
from aio_energy_management.cheapest_hours.helpers import (  # noqa: E402
    sanitize_cheapest_hours_input,
)
from aio_energy_management.const import (  # noqa: E402
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_LAST_HOUR,
    CONF_MAX_NUMBER_OF_SLOTS,
    CONF_NAME,
    CONF_NUMBER_OF_BLOCKS,
    CONF_NUMBER_OF_SLOTS,
    CONF_PRICE_LIMIT,
    CONF_SEQUENTIAL,
    CONF_TRIGGER_HOUR,
)


# ---------------------------------------------------------------------------
# sanitize_cheapest_hours_input
# ---------------------------------------------------------------------------


class TestSanitizeCheapestHoursInput:
    """Tests for sanitize_cheapest_hours_input function."""

    def test_floats_coerced_to_ints_for_hour_and_slot_fields(self):
        """Float values coming from UI selectors should be converted to hard ints."""
        raw_input = {
            CONF_FIRST_HOUR: 0.0,
            CONF_LAST_HOUR: 23.0,
            CONF_NUMBER_OF_SLOTS: 4.0,
            CONF_FAILSAFE_STARTING_HOUR: 12.0,
            CONF_TRIGGER_HOUR: 18.0,
            CONF_NUMBER_OF_BLOCKS: 2.0,
            CONF_MAX_NUMBER_OF_SLOTS: 8.0,
        }

        sanitized = sanitize_cheapest_hours_input(raw_input)

        for key, expected_val in raw_input.items():
            assert isinstance(sanitized[key], int)
            assert sanitized[key] == int(expected_val)

    def test_price_limits_remain_floats(self):
        """Price limits must preserve float precision for decimals."""
        raw_input = {
            CONF_PRICE_LIMIT: 0.15,
            CONF_FLEXIBLE_PRICE_LIMIT: -0.05,
        }

        sanitized = sanitize_cheapest_hours_input(raw_input)

        assert isinstance(sanitized[CONF_PRICE_LIMIT], float)
        assert sanitized[CONF_PRICE_LIMIT] == 0.15
        assert isinstance(sanitized[CONF_FLEXIBLE_PRICE_LIMIT], float)
        assert sanitized[CONF_FLEXIBLE_PRICE_LIMIT] == -0.05

    def test_string_and_boolean_fields_unaffected(self):
        """Non-numeric fields should pass through unchanged."""
        raw_input = {
            CONF_NAME: "Cheapest Hours Test",
            CONF_SEQUENTIAL: True,
        }

        sanitized = sanitize_cheapest_hours_input(raw_input)

        assert sanitized[CONF_NAME] == "Cheapest Hours Test"
        assert sanitized[CONF_SEQUENTIAL] is True

    def test_none_and_missing_keys_handled_safely(self):
        """None values or missing keys should not raise exceptions."""
        raw_input = {
            CONF_FIRST_HOUR: None,
            CONF_NUMBER_OF_SLOTS: 2,
        }

        sanitized = sanitize_cheapest_hours_input(raw_input)

        assert sanitized[CONF_FIRST_HOUR] is None
        assert sanitized[CONF_NUMBER_OF_SLOTS] == 2
        assert CONF_LAST_HOUR not in sanitized

    def test_non_convertible_values_handled_gracefully(self):
        """Invalid non-numeric values should fail silently without crashing."""
        raw_input = {
            CONF_FIRST_HOUR: "invalid_string",
        }

        sanitized = sanitize_cheapest_hours_input(raw_input)

        assert sanitized[CONF_FIRST_HOUR] == "invalid_string"
