"""Tests for global price modifications and the per-sensor source selection."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.aio_energy_management import async_reload_entry
from custom_components.aio_energy_management.binary_sensor import (
    _create_cheapest_hours_entity,
)
from custom_components.aio_energy_management.cheapest_hours import (
    CheapestHoursBinarySensor,
)
from custom_components.aio_energy_management.cheapest_hours.helpers import (
    get_global_price_modifications,
    get_price_modifications_mode,
    validate_price_modifications_fields,
)
from custom_components.aio_energy_management.const import (
    CONF_ENABLE_CALENDAR,
    CONF_ENTITY_CHEAPEST_HOURS,
    CONF_ENTRY_TYPE,
    CONF_PRICE_MODIFICATIONS,
    CONF_PRICE_MODIFICATIONS_MODE,
    CONF_UNIQUE_ID,
    COORDINATOR,
    DOMAIN,
    ENTRY_TYPE_GLOBAL_SETTINGS,
    PRICE_MODIFICATIONS_MODE_CUSTOM,
    PRICE_MODIFICATIONS_MODE_GLOBAL,
    PRICE_MODIFICATIONS_MODE_NONE,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry

from .test_cheapest_hours_binary_sensor import (
    _setup_coordinator_mock,
    _setup_nordpool_official_mock,
)

GLOBAL_TEMPLATE = "{{ price * 2 }}"
CUSTOM_TEMPLATE = "{{ price + 1 }}"


def _global_entry(template: str | None = GLOBAL_TEMPLATE) -> MockConfigEntry:
    options = {CONF_ENABLE_CALENDAR: False}
    if template is not None:
        options[CONF_PRICE_MODIFICATIONS] = template
    return MockConfigEntry(
        domain=DOMAIN,
        title="Global Settings",
        unique_id=ENTRY_TYPE_GLOBAL_SETTINGS,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_GLOBAL_SETTINGS,
            CONF_UNIQUE_ID: ENTRY_TYPE_GLOBAL_SETTINGS,
        },
        options=options,
    )


def _cheapest_entry(unique_id: str, **extra) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=unique_id,
        unique_id=unique_id,
        data={
            CONF_ENTRY_TYPE: CONF_ENTITY_CHEAPEST_HOURS,
            CONF_UNIQUE_ID: unique_id,
            **extra,
        },
    )


# ---------------------------------------------------------------------------
# Mode and global template
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({}, PRICE_MODIFICATIONS_MODE_NONE),
        ({CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE}, PRICE_MODIFICATIONS_MODE_CUSTOM),
        ({CONF_PRICE_MODIFICATIONS: ""}, PRICE_MODIFICATIONS_MODE_NONE),
        (
            {CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_GLOBAL},
            PRICE_MODIFICATIONS_MODE_GLOBAL,
        ),
        (
            {
                CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_NONE,
                CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE,
            },
            PRICE_MODIFICATIONS_MODE_NONE,
        ),
        ({CONF_PRICE_MODIFICATIONS_MODE: "bogus"}, PRICE_MODIFICATIONS_MODE_NONE),
    ],
)
def test_get_price_modifications_mode(config, expected) -> None:
    """Missing modes fall back to the behaviour before modes existed."""
    assert get_price_modifications_mode(config) == expected


async def test_global_template_read_from_global_settings(hass: HomeAssistant) -> None:
    """The global template comes from the Global Settings options."""
    _global_entry().add_to_hass(hass)
    assert get_global_price_modifications(hass) == GLOBAL_TEMPLATE


@pytest.mark.parametrize("template", [None, "", "   "])
async def test_global_template_empty(hass: HomeAssistant, template) -> None:
    """An empty global template means no modifications."""
    _global_entry(template=template).add_to_hass(hass)
    assert get_global_price_modifications(hass) is None


async def test_global_template_without_global_settings(hass: HomeAssistant) -> None:
    """A missing Global Settings entry means no modifications."""
    assert get_global_price_modifications(hass) is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_custom_requires_template() -> None:
    """Custom mode without a template is an error."""
    user_input = {
        CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_CUSTOM,
        CONF_PRICE_MODIFICATIONS: "  ",
    }
    errors = validate_price_modifications_fields(user_input)
    assert errors == {CONF_PRICE_MODIFICATIONS: "custom_template_required"}


def test_validate_global_keeps_custom_template() -> None:
    """Choosing global keeps the custom template so switching back loses nothing."""
    user_input = {
        CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_GLOBAL,
        CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE,
    }
    assert validate_price_modifications_fields(user_input) == {}
    assert user_input[CONF_PRICE_MODIFICATIONS] == CUSTOM_TEMPLATE


def test_validate_none_without_template() -> None:
    """None mode needs no template."""
    user_input = {CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_NONE}
    assert validate_price_modifications_fields(user_input) == {}


# ---------------------------------------------------------------------------
# Global Settings options flow
# ---------------------------------------------------------------------------


async def test_global_settings_saves_template(hass: HomeAssistant) -> None:
    """The global template is stored in the Global Settings options."""
    entry = _global_entry(template=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "global_settings_options"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ENABLE_CALENDAR: False,
            "name": "Energy Management",
            CONF_PRICE_MODIFICATIONS: GLOBAL_TEMPLATE,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PRICE_MODIFICATIONS] == GLOBAL_TEMPLATE


async def test_global_settings_rejects_invalid_template(hass: HomeAssistant) -> None:
    """An invalid global template is rejected by the form and not saved."""
    entry = _global_entry(template=None)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_ENABLE_CALENDAR: False,
                "name": "Energy Management",
                CONF_PRICE_MODIFICATIONS: "{{ price * }}",
            },
        )
    assert CONF_PRICE_MODIFICATIONS not in entry.options


async def test_global_settings_clears_template(hass: HomeAssistant) -> None:
    """Clearing the global template removes it."""
    entry = _global_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_ENABLE_CALENDAR: False, "name": "Energy Management"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_PRICE_MODIFICATIONS] is None


# ---------------------------------------------------------------------------
# Global Settings changes keep calculated data
# ---------------------------------------------------------------------------


async def test_global_change_keeps_sensor_data(hass: HomeAssistant) -> None:
    """Saving Global Settings neither clears nor reloads cheapest hours sensors."""
    global_entry = _global_entry()
    global_mode = _cheapest_entry(
        "global_mode",
        **{CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_GLOBAL},
    )
    for entry in (global_entry, global_mode):
        entry.add_to_hass(hass)

    coordinator = MagicMock(async_clear_data=AsyncMock())
    hass.data[DOMAIN] = {COORDINATOR: coordinator}

    with patch.object(
        hass.config_entries, "async_reload", AsyncMock(return_value=True)
    ) as reload:
        await async_reload_entry(hass, global_entry)

    reloaded = [call.args[0] for call in reload.call_args_list]
    assert reloaded == [global_entry.entry_id]
    coordinator.async_clear_data.assert_not_awaited()


async def test_global_change_applies_from_next_calculation(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A changed global template leaves the valid plan as it is.

    The sensor reads the template when it next calculates, which for valid
    data only happens once the plan expires.
    """
    global_entry = _global_entry()
    global_entry.add_to_hass(hass)
    _setup_nordpool_official_mock(
        hass,
        "nordpool_official_service_20250313.json",
        "nordpool_official_service_20250314.json",
        "nordpool_official_service_20250315.json",
    )
    sensor = CheapestHoursBinarySensor(
        hass=hass,
        nordpool_official_config_entry="DUMMY",
        unique_id="my_sensor",
        name="My Sensor",
        first_hour=0,
        last_hour=23,
        starting_today=False,
        number_of_hours=3,
        sequential=False,
        failsafe_starting_hour=0,
        use_global_price_modifications=True,
        coordinator=_setup_coordinator_mock(),
    )
    freezer.move_to("2025-03-14 14:30+03:00")
    await sensor.async_update()
    plan = list(sensor.extra_state_attributes["list"])
    expiration = sensor.extra_state_attributes["expiration"]
    assert plan

    # Inverting the prices would pick completely different slots
    hass.config_entries.async_update_entry(
        global_entry,
        options={**global_entry.options, CONF_PRICE_MODIFICATIONS: "{{ -price }}"},
    )
    freezer.move_to("2025-03-14 15:30+03:00")
    await sensor.async_update()

    assert sensor.extra_state_attributes["list"] == plan
    assert sensor.extra_state_attributes["expiration"] == expiration
    assert sensor._get_price_modifications().template == "{{ -price }}"


# ---------------------------------------------------------------------------
# Entity creation
# ---------------------------------------------------------------------------


def _sensor_config(**extra) -> dict:
    return {
        CONF_UNIQUE_ID: "my_sensor",
        "name": "My Sensor",
        "nordpool_entity": "sensor.nordpool",
        "first_hour": 0,
        "last_hour": 23,
        "sequential": False,
        "number_of_slots": 3,
        **extra,
    }


@pytest.mark.parametrize(
    ("extra", "uses_global", "custom"),
    [
        (
            {
                CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_GLOBAL,
                CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE,
            },
            True,
            None,
        ),
        (
            {
                CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_CUSTOM,
                CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE,
            },
            False,
            CUSTOM_TEMPLATE,
        ),
        (
            {
                CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_NONE,
                CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE,
            },
            False,
            None,
        ),
        ({CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE}, False, CUSTOM_TEMPLATE),
        ({}, False, None),
    ],
)
async def test_entity_price_modifications_source(
    hass: HomeAssistant, extra: dict, uses_global: bool, custom: str | None
) -> None:
    """The sensor is set up according to its price modifications mode."""
    _global_entry().add_to_hass(hass)
    hass.data[DOMAIN] = {COORDINATOR: MagicMock()}

    sensor = _create_cheapest_hours_entity(hass, _sensor_config(**extra))

    assert sensor._use_global_price_modifications is uses_global
    if custom is None:
        assert sensor._price_modifications is None
    else:
        assert sensor._price_modifications.template == custom


async def test_entity_follows_global_template(hass: HomeAssistant) -> None:
    """A global-mode sensor always uses the current Global Settings template."""
    global_entry = _global_entry()
    global_entry.add_to_hass(hass)
    hass.data[DOMAIN] = {COORDINATOR: MagicMock()}
    sensor = _create_cheapest_hours_entity(
        hass,
        _sensor_config(
            **{CONF_PRICE_MODIFICATIONS_MODE: PRICE_MODIFICATIONS_MODE_GLOBAL}
        ),
    )

    first = sensor._get_price_modifications()
    assert first.template == GLOBAL_TEMPLATE
    assert sensor._get_price_modifications() is first  # compiled once

    hass.config_entries.async_update_entry(
        global_entry,
        options={**global_entry.options, CONF_PRICE_MODIFICATIONS: CUSTOM_TEMPLATE},
    )
    assert sensor._get_price_modifications().template == CUSTOM_TEMPLATE

    hass.config_entries.async_update_entry(
        global_entry,
        options={**global_entry.options, CONF_PRICE_MODIFICATIONS: None},
    )
    assert sensor._get_price_modifications() is None
