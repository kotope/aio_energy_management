"""Tests for integer field validation helpers in cheapest_hours_config_flow."""

import sys
import os

# Allow importing the custom component without a full HA environment
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "custom_components"),
)

from aio_energy_management.cheapest_hours.config_flow import (  # noqa: E402
    CONF_FLEXIBLE_PRICE_LIMIT,
    CONF_FLEXIBLE_PRICE_LIMIT_ENTITY,
    _get_cheapest_hours_advanced_schema,
    _validate_advanced_integer_fields,
    _validate_and_build_add_flexible,
    _validate_basic_integer_fields,
    _validate_offset_integer_fields,
)
from aio_energy_management.const import (  # noqa: E402
    CONF_ADD_FLEXIBLE,
    CONF_END,
    CONF_FAILSAFE_STARTING_HOUR,
    CONF_FIRST_HOUR,
    CONF_LAST_HOUR,
    CONF_MAX_NUMBER_OF_SLOTS,
    CONF_MAX_NUMBER_OF_SLOTS_ENTITY,
    CONF_MINUTES,
    CONF_NUMBER_OF_SLOTS,
    CONF_PRICE_LIMIT,
    CONF_PRICE_LIMIT_ENTITY,
    CONF_START,
    CONF_TRIGGER_HOUR,
)


# ---------------------------------------------------------------------------
# _validate_basic_integer_fields
# ---------------------------------------------------------------------------


class TestValidateBasicIntegerFields:
    """Tests for _validate_basic_integer_fields."""

    def _make_input(self, first_hour=0, last_hour=23, number_of_slots=1):
        return {
            CONF_FIRST_HOUR: first_hour,
            CONF_LAST_HOUR: last_hour,
            CONF_NUMBER_OF_SLOTS: number_of_slots,
        }

    # --- valid cases ---

    def test_valid_typical(self):
        errors = _validate_basic_integer_fields(self._make_input(0, 23, 4))
        assert not errors

    def test_valid_first_hour_boundary_low(self):
        errors = _validate_basic_integer_fields(self._make_input(0, 23, 1))
        assert not errors

    def test_valid_first_hour_boundary_high(self):
        errors = _validate_basic_integer_fields(self._make_input(23, 23, 1))
        assert not errors

    def test_valid_last_hour_equals_first_hour(self):
        errors = _validate_basic_integer_fields(self._make_input(10, 10, 1))
        assert not errors

    def test_valid_number_of_slots_zero(self):
        # 0 is allowed (use entity instead)
        errors = _validate_basic_integer_fields(self._make_input(0, 23, 0))
        assert not errors

    def test_valid_number_of_slots_large(self):
        errors = _validate_basic_integer_fields(self._make_input(0, 23, 96))
        assert not errors

    def test_missing_fields_no_errors(self):
        # Fields that are None (omitted) should not raise errors
        errors = _validate_basic_integer_fields({})
        assert not errors

    # --- first_hour ---

    def test_invalid_first_hour_too_high(self):
        errors = _validate_basic_integer_fields(self._make_input(24, 23, 1))
        assert CONF_FIRST_HOUR in errors
        assert errors[CONF_FIRST_HOUR] == "first_hour_out_of_range"

    def test_invalid_first_hour_negative(self):
        errors = _validate_basic_integer_fields(self._make_input(-1, 23, 1))
        assert CONF_FIRST_HOUR in errors
        assert errors[CONF_FIRST_HOUR] == "first_hour_out_of_range"

    # --- last_hour ---

    def test_invalid_last_hour_too_high(self):
        errors = _validate_basic_integer_fields(self._make_input(0, 24, 1))
        assert CONF_LAST_HOUR in errors
        assert errors[CONF_LAST_HOUR] == "last_hour_out_of_range"

    def test_invalid_last_hour_negative(self):
        errors = _validate_basic_integer_fields(self._make_input(0, -1, 1))
        assert CONF_LAST_HOUR in errors
        assert errors[CONF_LAST_HOUR] == "last_hour_out_of_range"

    def test_valid_last_hour_before_first_hour_overnight_window(self):
        # last_hour < first_hour is allowed to support overnight windows
        # e.g. first_hour=22, last_hour=6 means 22:00 -> 06:00
        errors = _validate_basic_integer_fields(self._make_input(22, 6, 1))
        assert not errors

    def test_last_hour_out_of_range_not_reported_as_before_first_hour(
        self,
    ):
        # If last_hour is already flagged as out of range, it is the only error
        # (the removed cross-field check would never have fired anyway for this case).
        errors = _validate_basic_integer_fields(self._make_input(10, 25, 1))
        assert errors[CONF_LAST_HOUR] == "last_hour_out_of_range"

    def test_first_hour_out_of_range_does_not_prevent_last_hour_range_check(
        self,
    ):
        # When first_hour is invalid, last_hour is still checked independently.
        errors = _validate_basic_integer_fields(self._make_input(25, 5, 1))
        assert CONF_FIRST_HOUR in errors
        # last_hour 5 is in-range, so no error expected for it
        assert CONF_LAST_HOUR not in errors

    # --- number_of_slots ---

    def test_invalid_number_of_slots_negative(self):
        errors = _validate_basic_integer_fields(self._make_input(0, 23, -1))
        assert CONF_NUMBER_OF_SLOTS in errors
        assert errors[CONF_NUMBER_OF_SLOTS] == "number_of_slots_negative"

    def test_multiple_errors_returned_simultaneously(self):
        errors = _validate_basic_integer_fields(
            {CONF_FIRST_HOUR: 25, CONF_LAST_HOUR: 25, CONF_NUMBER_OF_SLOTS: -5}
        )
        assert CONF_FIRST_HOUR in errors
        assert CONF_LAST_HOUR in errors
        assert CONF_NUMBER_OF_SLOTS in errors


# ---------------------------------------------------------------------------
# _validate_advanced_integer_fields
# ---------------------------------------------------------------------------


class TestValidateAdvancedIntegerFields:
    """Tests for _validate_advanced_integer_fields."""

    # --- valid cases ---

    def test_valid_no_fields_set(self):
        errors = _validate_advanced_integer_fields({})
        assert not errors

    def test_valid_failsafe_low_boundary(self):
        errors = _validate_advanced_integer_fields(
            {CONF_FAILSAFE_STARTING_HOUR: 0}
        )
        assert not errors

    def test_valid_failsafe_high_boundary(self):
        errors = _validate_advanced_integer_fields(
            {CONF_FAILSAFE_STARTING_HOUR: 23}
        )
        assert not errors

    def test_valid_trigger_hour(self):
        errors = _validate_advanced_integer_fields({CONF_TRIGGER_HOUR: 12})
        assert not errors

    def test_valid_both_fields(self):
        errors = _validate_advanced_integer_fields(
            {CONF_FAILSAFE_STARTING_HOUR: 6, CONF_TRIGGER_HOUR: 18}
        )
        assert not errors

    # --- failsafe_starting_hour ---

    def test_invalid_failsafe_too_high(self):
        errors = _validate_advanced_integer_fields(
            {CONF_FAILSAFE_STARTING_HOUR: 24}
        )
        assert CONF_FAILSAFE_STARTING_HOUR in errors
        assert (
            errors[CONF_FAILSAFE_STARTING_HOUR]
            == "failsafe_starting_hour_out_of_range"
        )

    def test_invalid_failsafe_negative(self):
        errors = _validate_advanced_integer_fields(
            {CONF_FAILSAFE_STARTING_HOUR: -1}
        )
        assert CONF_FAILSAFE_STARTING_HOUR in errors

    # --- trigger_hour ---

    def test_invalid_trigger_hour_too_high(self):
        errors = _validate_advanced_integer_fields({CONF_TRIGGER_HOUR: 24})
        assert CONF_TRIGGER_HOUR in errors
        assert errors[CONF_TRIGGER_HOUR] == "trigger_hour_out_of_range"

    def test_invalid_trigger_hour_negative(self):
        errors = _validate_advanced_integer_fields({CONF_TRIGGER_HOUR: -1})
        assert CONF_TRIGGER_HOUR in errors

    def test_both_fields_invalid(self):
        errors = _validate_advanced_integer_fields(
            {CONF_FAILSAFE_STARTING_HOUR: 99, CONF_TRIGGER_HOUR: -5}
        )
        assert CONF_FAILSAFE_STARTING_HOUR in errors
        assert CONF_TRIGGER_HOUR in errors


# ---------------------------------------------------------------------------
# _validate_offset_integer_fields
# ---------------------------------------------------------------------------


class TestValidateOffsetIntegerFields:
    """Tests for _validate_offset_integer_fields."""

    START_MINUTES = f"{CONF_START}_{CONF_MINUTES}"
    END_MINUTES = f"{CONF_END}_{CONF_MINUTES}"

    # --- valid cases ---

    def test_valid_no_fields_set(self):
        errors = _validate_offset_integer_fields({})
        assert not errors

    def test_valid_start_minutes_boundaries(self):
        assert not _validate_offset_integer_fields({self.START_MINUTES: 0})
        assert not _validate_offset_integer_fields({self.START_MINUTES: 59})

    def test_valid_end_minutes_boundaries(self):
        assert not _validate_offset_integer_fields({self.END_MINUTES: 0})
        assert not _validate_offset_integer_fields({self.END_MINUTES: 59})

    def test_valid_hours_are_unrestricted(self):
        # Offset hours have no range restriction
        errors = _validate_offset_integer_fields(
            {
                f"{CONF_START}_hours": 48,
                f"{CONF_END}_hours": -12,
            }
        )
        assert not errors

    # --- start_minutes ---

    def test_invalid_start_minutes_too_high(self):
        errors = _validate_offset_integer_fields({self.START_MINUTES: 60})
        assert self.START_MINUTES in errors
        assert errors[self.START_MINUTES] == "start_minutes_out_of_range"

    def test_invalid_start_minutes_negative(self):
        errors = _validate_offset_integer_fields({self.START_MINUTES: -60})
        assert self.START_MINUTES in errors

    # --- end_minutes ---

    def test_invalid_end_minutes_too_high(self):
        errors = _validate_offset_integer_fields({self.END_MINUTES: 60})
        assert self.END_MINUTES in errors
        assert errors[self.END_MINUTES] == "end_minutes_out_of_range"

    def test_invalid_end_minutes_negative(self):
        errors = _validate_offset_integer_fields({self.END_MINUTES: -60})
        assert self.END_MINUTES in errors

    def test_both_minutes_invalid(self):
        errors = _validate_offset_integer_fields(
            {self.START_MINUTES: 61, self.END_MINUTES: -60}
        )
        assert self.START_MINUTES in errors
        assert self.END_MINUTES in errors


# ---------------------------------------------------------------------------
# _validate_and_build_add_flexible
# ---------------------------------------------------------------------------


class TestValidateAndBuildAddFlexible:
    """Tests for _validate_and_build_add_flexible."""

    def test_valid_static_builds_nested_dict(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 21,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.05,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert not errors
        assert user_input[CONF_ADD_FLEXIBLE] == {
            CONF_MAX_NUMBER_OF_SLOTS: 21,
            CONF_PRICE_LIMIT: 0.05,
        }
        # Flat fields are consumed.
        assert CONF_MAX_NUMBER_OF_SLOTS not in user_input
        assert CONF_FLEXIBLE_PRICE_LIMIT not in user_input

    def test_valid_entities_build_nested_dict(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS_ENTITY: "input_number.max_slots",
            CONF_FLEXIBLE_PRICE_LIMIT_ENTITY: "input_number.flex_limit",
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert not errors
        assert user_input[CONF_ADD_FLEXIBLE] == {
            CONF_MAX_NUMBER_OF_SLOTS_ENTITY: "input_number.max_slots",
            CONF_PRICE_LIMIT_ENTITY: "input_number.flex_limit",
        }

    def test_empty_is_noop(self):
        user_input = {}
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert not errors
        assert CONF_ADD_FLEXIBLE not in user_input

    def test_only_max_is_incomplete(self):
        user_input = {CONF_MAX_NUMBER_OF_SLOTS: 21}
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert errors.get("base") == "add_flexible_incomplete"

    def test_only_price_limit_is_incomplete(self):
        user_input = {CONF_FLEXIBLE_PRICE_LIMIT: 0.05}
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert errors.get("base") == "add_flexible_incomplete"

    def test_max_above_cap_60(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 25,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.05,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert (
            errors.get(CONF_MAX_NUMBER_OF_SLOTS) == "max_number_of_slots_out_of_range"
        )

    def test_max_within_cap_15(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 90,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.05,
        }
        errors = _validate_and_build_add_flexible(user_input, 15)
        assert not errors

    def test_max_smaller_than_number_of_slots_is_allowed(self):
        # max_number_of_slots now counts extra slots on top of the base slots,
        # so it may be smaller than number_of_slots without being an error.
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 3,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.05,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert not errors

    def test_both_max_static_and_entity(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 21,
            CONF_MAX_NUMBER_OF_SLOTS_ENTITY: "input_number.max_slots",
            CONF_FLEXIBLE_PRICE_LIMIT: 0.05,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert errors.get("base") == "both_max_number_of_slots_configured"

    def test_flexible_price_limit_not_below_price_limit(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 21,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.5,
            CONF_PRICE_LIMIT: 0.5,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert (
            errors.get(CONF_FLEXIBLE_PRICE_LIMIT)
            == "flexible_price_limit_not_below_price_limit"
        )

    def test_flexible_price_limit_below_price_limit_is_valid(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 21,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.4,
            CONF_PRICE_LIMIT: 0.5,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert not errors

    def test_flexible_price_limit_not_guarded_without_price_limit(self):
        user_input = {
            CONF_MAX_NUMBER_OF_SLOTS: 21,
            CONF_FLEXIBLE_PRICE_LIMIT: 0.5,
        }
        errors = _validate_and_build_add_flexible(user_input, 60)
        assert not errors


# ---------------------------------------------------------------------------
# _get_cheapest_hours_advanced_schema
# ---------------------------------------------------------------------------


def _schema_field_names(schema) -> set:
    return {getattr(key, "schema", key) for key in schema.schema}


class TestAdvancedSchemaSequential:
    """The flexible fields must only appear for non-sequential sensors."""

    def test_flexible_fields_present_when_not_sequential(self):
        fields = _schema_field_names(
            _get_cheapest_hours_advanced_schema(sequential=False)
        )
        assert CONF_MAX_NUMBER_OF_SLOTS in fields
        assert CONF_MAX_NUMBER_OF_SLOTS_ENTITY in fields
        assert CONF_FLEXIBLE_PRICE_LIMIT in fields
        assert CONF_FLEXIBLE_PRICE_LIMIT_ENTITY in fields

    def test_flexible_fields_absent_when_sequential(self):
        fields = _schema_field_names(
            _get_cheapest_hours_advanced_schema(sequential=True)
        )
        assert CONF_MAX_NUMBER_OF_SLOTS not in fields
        assert CONF_MAX_NUMBER_OF_SLOTS_ENTITY not in fields
        assert CONF_FLEXIBLE_PRICE_LIMIT not in fields
        assert CONF_FLEXIBLE_PRICE_LIMIT_ENTITY not in fields
