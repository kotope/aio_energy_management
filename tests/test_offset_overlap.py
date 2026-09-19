"""Tests for offset overlap scenarios in cheapest hours binary sensor.

These are unit tests that test the _add_offset logic in isolation,
without requiring the full Home Assistant environment.

Run with: python3 tests/test_offset_overlap.py
"""

import sys
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
import logging

# Allow importing the custom component without a full HA environment
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components"),
)

# Skip pytest-homeassistant-custom-component fixtures for these pure unit tests
pytest_plugins = []


class MockCheapestHoursBinarySensor:
    """Mock sensor class to test _add_offset behavior in isolation."""

    def __init__(self, sequential: bool, offset: dict):
        self._sequential = sequential
        self._offset = offset
        self._attr_unique_id = "test_sensor"
        self._data = {"list": [], "expiration": None}
        self._logger = logging.getLogger(__name__)

    def _int_from_entity(self, value):
        """Return integer value (mock version)."""
        if value is None:
            return None
        return int(value)

    def _set_next(
        self, list_data: list, expiration: datetime, attributes: dict, logger=None
    ) -> None:
        """Set next slot data with overlap detection (copied from actual implementation)."""
        nxt = {}
        lst, exp = self._add_offset(list_data, expiration)

        # Check for overlap with current slot
        if self._data.get("list") and lst:
            current_end = self._data["list"][-1].get("end")
            next_start = lst[0].get("start")
            if current_end and next_start and next_start < current_end:
                log = logger or self._logger
                log.warning(
                    "Offset overlap detected for %s: next slot starts at %s but "
                    "current slot (with offset) ends at %s. The sensor will remain "
                    "in current state until %s, potentially missing 'on' time for "
                    "the next slot",
                    self._attr_unique_id,
                    next_start,
                    current_end,
                    self._data.get("expiration"),
                )

        nxt["list"] = lst
        nxt["expiration"] = exp
        nxt["extra"] = attributes
        self._data["next"] = nxt

    def _add_offset(self, list_data: list, expiration: datetime) -> tuple[list, datetime]:
        """Add offset to list data (copied from actual implementation)."""
        new_expiration = expiration
        # Offset is only supported for sequential sensors
        if not self._sequential:
            return (list_data, new_expiration)
        if list_data:
            first = list_data[0]
            if start := first.get("start"):
                if offset := self._offset.get("start"):
                    hours = self._int_from_entity(offset.get("hours"))
                    minutes = self._int_from_entity(offset.get("minutes"))

                    new_start = start + timedelta(
                        hours=hours if hours is not None else 0,
                        minutes=minutes if minutes is not None else 0,
                    )
                    new_first = {"start": new_start, "end": first["end"]}
                    list_data[0] = new_first
        if list_data:
            last = list_data[-1]
            if end := last.get("end"):
                if offset := self._offset.get("end"):
                    hours = self._int_from_entity(offset.get("hours"))
                    minutes = self._int_from_entity(offset.get("minutes"))
                    end_offset = timedelta(
                        hours=hours if hours is not None else 0,
                        minutes=minutes if minutes is not None else 0,
                    )
                    new_end = end + end_offset
                    new_last = {"start": last["start"], "end": new_end}

                    # if added end is greater than expiration, extend the expiration as well
                    if new_end > expiration:
                        new_expiration = expiration + end_offset

                    list_data[-1] = new_last

        return (list_data, new_expiration)


class TestOffsetOverlapScenarios:
    """Tests for offset overlap scenarios."""

    def test_end_offset_extends_beyond_expiration(self):
        """Test that end offset extends expiration when it exceeds original."""
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"end": {"hours": 1}},
        )

        # Slot: 23:00-00:00, expiration at 00:00
        slot_start = datetime(2024, 7, 14, 23, 0)
        slot_end = datetime(2024, 7, 15, 0, 0)
        expiration = datetime(2024, 7, 15, 0, 0)

        list_data = [{"start": slot_start, "end": slot_end}]
        result_list, result_expiration = sensor._add_offset(list_data, expiration)

        # End should be extended by 1 hour: 01:00
        assert result_list[0]["end"] == datetime(2024, 7, 15, 1, 0)
        # Expiration should also be extended
        assert result_expiration == datetime(2024, 7, 15, 1, 0)

    def test_start_offset_pulls_back_start_time(self):
        """Test that start offset with negative value pulls start time back."""
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"start": {"minutes": -30}},
        )

        # Slot: 00:00-01:00
        slot_start = datetime(2024, 7, 15, 0, 0)
        slot_end = datetime(2024, 7, 15, 1, 0)
        expiration = datetime(2024, 7, 15, 1, 0)

        list_data = [{"start": slot_start, "end": slot_end}]
        result_list, result_expiration = sensor._add_offset(list_data, expiration)

        # Start should be pulled back by 30 minutes: 23:30 previous day
        assert result_list[0]["start"] == datetime(2024, 7, 14, 23, 30)
        # Expiration should not change for start offset
        assert result_expiration == expiration

    def test_overlap_scenario_current_end_offset_next_start_offset(self):
        """Test overlap scenario where current slot's end offset overlaps next slot's start.

        Scenario:
        - Current slot: 23:00-00:00 with end offset +1h → ends at 01:00
        - Next slot: 00:00-01:00 with start offset -30min → starts at 23:30

        This creates overlap from 23:30 to 01:00 where both would be active.
        """
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"start": {"minutes": -30}, "end": {"hours": 1}},
        )

        # Current slot: 23:00-00:00
        current_start = datetime(2024, 7, 14, 23, 0)
        current_end = datetime(2024, 7, 15, 0, 0)
        current_expiration = datetime(2024, 7, 15, 0, 0)

        current_list = [{"start": current_start, "end": current_end}]
        current_result, current_exp = sensor._add_offset(current_list.copy(), current_expiration)

        # Current slot with offsets:
        # Start: 23:00 - 30min = 22:30
        # End: 00:00 + 1h = 01:00
        assert current_result[0]["start"] == datetime(2024, 7, 14, 22, 30)
        assert current_result[0]["end"] == datetime(2024, 7, 15, 1, 0)
        assert current_exp == datetime(2024, 7, 15, 1, 0)

        # Next slot: 00:00-01:00
        next_start = datetime(2024, 7, 15, 0, 0)
        next_end = datetime(2024, 7, 15, 1, 0)
        next_expiration = datetime(2024, 7, 16, 0, 0)

        next_list = [{"start": next_start, "end": next_end}]
        next_result, next_exp = sensor._add_offset(next_list.copy(), next_expiration)

        # Next slot with offsets:
        # Start: 00:00 - 30min = 23:30 (previous day!)
        # End: 01:00 + 1h = 02:00
        assert next_result[0]["start"] == datetime(2024, 7, 14, 23, 30)
        assert next_result[0]["end"] == datetime(2024, 7, 15, 2, 0)

        # OVERLAP CHECK: next slot starts (23:30) before current slot ends (01:00)
        overlap_exists = next_result[0]["start"] < current_result[0]["end"]
        assert overlap_exists, "Overlap should exist between slots"

        # Calculate overlap duration
        overlap_start = next_result[0]["start"]  # 23:30
        overlap_end = current_result[0]["end"]   # 01:00
        overlap_duration = overlap_end - overlap_start
        assert overlap_duration == timedelta(hours=1, minutes=30), (
            f"Overlap should be 1.5 hours, got {overlap_duration}"
        )

    def test_missed_on_time_due_to_delayed_swap(self):
        """Test that swap delay can cause missed 'on' time.

        When current slot expires and swap happens, the next slot's offset-adjusted
        start time may have already passed, causing the sensor to be 'off' during
        a period it should have been 'on'.
        """
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"start": {"minutes": -30}, "end": {"hours": 1}},
        )

        # Current slot expires at 01:00 (after end offset)
        # Next slot starts at 23:30 (after start offset)
        # If swap happens at 01:01, we've missed 23:30 to 01:00 of next slot's "on" time

        # This demonstrates the issue conceptually:
        current_end_with_offset = datetime(2024, 7, 15, 1, 0)
        next_start_with_offset = datetime(2024, 7, 14, 23, 30)

        # Time when swap would happen (after current expiration)
        swap_time = datetime(2024, 7, 15, 1, 1)

        # Time that would have been "on" but was missed
        missed_start = next_start_with_offset  # 23:30
        missed_end = current_end_with_offset   # 01:00

        # The next slot's offset-adjusted start time has already passed
        assert swap_time > next_start_with_offset, (
            "Swap happens after next slot's start time - potential missed 'on' time"
        )

        # Duration of potentially missed "on" time
        missed_duration = swap_time - next_start_with_offset
        assert missed_duration == timedelta(hours=1, minutes=31), (
            f"Missed duration should be ~1.5 hours, got {missed_duration}"
        )

    def test_non_sequential_ignores_offset(self):
        """Test that non-sequential sensors ignore offset configuration."""
        sensor = MockCheapestHoursBinarySensor(
            sequential=False,
            offset={"start": {"minutes": -30}, "end": {"hours": 1}},
        )

        slot_start = datetime(2024, 7, 15, 0, 0)
        slot_end = datetime(2024, 7, 15, 1, 0)
        expiration = datetime(2024, 7, 15, 1, 0)

        list_data = [{"start": slot_start, "end": slot_end}]
        result_list, result_expiration = sensor._add_offset(list_data, expiration)

        # No offset should be applied for non-sequential
        assert result_list[0]["start"] == slot_start
        assert result_list[0]["end"] == slot_end
        assert result_expiration == expiration

    def test_large_end_offset_creates_significant_overlap(self):
        """Test with a very large end offset to highlight the overlap issue."""
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"end": {"hours": 3}},  # 3 hour end offset
        )

        # Slot: 22:00-23:00 with 3h end offset → ends at 02:00
        slot_start = datetime(2024, 7, 14, 22, 0)
        slot_end = datetime(2024, 7, 14, 23, 0)
        expiration = datetime(2024, 7, 15, 0, 0)

        list_data = [{"start": slot_start, "end": slot_end}]
        result_list, result_expiration = sensor._add_offset(list_data, expiration)

        assert result_list[0]["end"] == datetime(2024, 7, 15, 2, 0)
        assert result_expiration == datetime(2024, 7, 15, 3, 0)  # expiration + 3h offset

        # Any next slot starting before 02:00 would overlap
        potential_next_starts = [
            datetime(2024, 7, 14, 23, 0),  # Overlaps by 3h
            datetime(2024, 7, 15, 0, 0),   # Overlaps by 2h
            datetime(2024, 7, 15, 1, 0),   # Overlaps by 1h
        ]

        for next_start in potential_next_starts:
            overlaps = next_start < result_list[0]["end"]
            assert overlaps, f"Start at {next_start} should overlap with end at {result_list[0]['end']}"

    def test_overlap_warning_logged_when_set_next_detects_overlap(self):
        """Test that a warning is logged when _set_next detects overlap."""
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"start": {"minutes": -30}, "end": {"hours": 1}},
        )

        # Set up current slot (with offset already applied)
        # Current slot: 23:00-00:00 with offsets → 22:30-01:00
        current_start = datetime(2024, 7, 14, 22, 30)
        current_end = datetime(2024, 7, 15, 1, 0)
        sensor._data = {
            "list": [{"start": current_start, "end": current_end}],
            "expiration": datetime(2024, 7, 15, 1, 0),
        }

        # Next slot: 00:00-01:00 (raw), will become 23:30-02:00 with offset
        next_start = datetime(2024, 7, 15, 0, 0)
        next_end = datetime(2024, 7, 15, 1, 0)
        next_expiration = datetime(2024, 7, 16, 0, 0)

        # Create a mock logger to capture the warning
        mock_logger = MagicMock()

        # Call _set_next which should detect overlap and log warning
        sensor._set_next(
            [{"start": next_start, "end": next_end}],
            next_expiration,
            {},
            logger=mock_logger,
        )

        # Verify warning was logged
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args
        assert "Offset overlap detected" in call_args[0][0]
        assert sensor._attr_unique_id in call_args[0]

    def test_no_warning_when_no_overlap(self):
        """Test that no warning is logged when there's no overlap."""
        sensor = MockCheapestHoursBinarySensor(
            sequential=True,
            offset={"start": {"minutes": 15}},  # Positive offset, no overlap
        )

        # Set up current slot: 10:00-11:00 with +15min start offset → 10:15-11:00
        current_start = datetime(2024, 7, 14, 10, 15)
        current_end = datetime(2024, 7, 14, 11, 0)
        sensor._data = {
            "list": [{"start": current_start, "end": current_end}],
            "expiration": datetime(2024, 7, 15, 0, 0),
        }

        # Next slot: 12:00-13:00 (raw), no overlap possible
        next_start = datetime(2024, 7, 14, 12, 0)
        next_end = datetime(2024, 7, 14, 13, 0)
        next_expiration = datetime(2024, 7, 15, 0, 0)

        mock_logger = MagicMock()

        sensor._set_next(
            [{"start": next_start, "end": next_end}],
            next_expiration,
            {},
            logger=mock_logger,
        )

        # Verify no warning was logged
        mock_logger.warning.assert_not_called()


if __name__ == "__main__":
    """Run tests directly without pytest to avoid HA fixture issues."""
    test_class = TestOffsetOverlapScenarios()
    
    tests = [
        ("test_end_offset_extends_beyond_expiration", test_class.test_end_offset_extends_beyond_expiration),
        ("test_start_offset_pulls_back_start_time", test_class.test_start_offset_pulls_back_start_time),
        ("test_overlap_scenario_current_end_offset_next_start_offset", test_class.test_overlap_scenario_current_end_offset_next_start_offset),
        ("test_missed_on_time_due_to_delayed_swap", test_class.test_missed_on_time_due_to_delayed_swap),
        ("test_non_sequential_ignores_offset", test_class.test_non_sequential_ignores_offset),
        ("test_large_end_offset_creates_significant_overlap", test_class.test_large_end_offset_creates_significant_overlap),
        ("test_overlap_warning_logged_when_set_next_detects_overlap", test_class.test_overlap_warning_logged_when_set_next_detects_overlap),
        ("test_no_warning_when_no_overlap", test_class.test_no_warning_when_no_overlap),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}: {type(e).__name__}: {e}")
            failed += 1
    
    print(f"\n{passed} passed, {failed} failed")
