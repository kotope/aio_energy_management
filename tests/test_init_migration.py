"""Tests for config entry migration in aio_energy_management."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.aio_energy_management import (
    _async_migrate_legacy_calendar_entry,
)
from custom_components.aio_energy_management.const import (
    CONF_ENTITY_CALENDAR,
    DOMAIN,
)

from pytest_homeassistant_custom_component.common import MockConfigEntry


@pytest.fixture
def legacy_calendar_entry() -> MockConfigEntry:
    """Create a legacy calendar config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Energy Management Calendar",
        data={
            "entry_type": CONF_ENTITY_CALENDAR,
            "name": "Test Calendar",
        },
        options={"calendar": True},
    )


@pytest.fixture
def other_entry() -> MockConfigEntry:
    """Create another config entry (not a calendar)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Cheapest Hours",
        data={
            "entry_type": "cheapest_hours",
        },
    )


async def test_migration_schedules_removal_without_blocking(
    hass: HomeAssistant,
    legacy_calendar_entry: MockConfigEntry,
    other_entry: MockConfigEntry,
) -> None:
    """Test that migration schedules entry removal via async_create_task instead of awaiting.

    This prevents deadlock during bootstrap when multiple entries are set up
    concurrently and their setup_locks would block each other.
    """
    legacy_calendar_entry.add_to_hass(hass)
    other_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)

    created_tasks = []

    def track_create_task(coro, *args, **kwargs):
        created_tasks.append(coro)
        return AsyncMock()

    with (
        patch.object(hass, "async_create_task", side_effect=track_create_task),
        patch.object(
            hass.config_entries, "async_remove", new_callable=AsyncMock
        ) as mock_remove,
    ):
        removed_ids, migrated_data = await _async_migrate_legacy_calendar_entry(
            hass, entries
        )

    assert legacy_calendar_entry.entry_id in removed_ids
    assert migrated_data is not None
    assert migrated_data["name"] == "Test Calendar"

    assert len(created_tasks) == 1, (
        "Expected async_create_task to be called exactly once for scheduling removal"
    )

    mock_remove.assert_called_once_with(legacy_calendar_entry.entry_id)


async def test_migration_returns_empty_when_no_legacy_entries(
    hass: HomeAssistant,
    other_entry: MockConfigEntry,
) -> None:
    """Test migration returns empty results when no legacy calendar entries exist."""
    other_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)

    removed_ids, migrated_data = await _async_migrate_legacy_calendar_entry(
        hass, entries
    )

    assert removed_ids == []
    assert migrated_data is None


async def test_migration_extracts_correct_data(
    hass: HomeAssistant,
    legacy_calendar_entry: MockConfigEntry,
) -> None:
    """Test migration extracts the correct data from legacy calendar entry."""
    legacy_calendar_entry.add_to_hass(hass)

    entries = hass.config_entries.async_entries(DOMAIN)

    with patch.object(hass, "async_create_task"):
        removed_ids, migrated_data = await _async_migrate_legacy_calendar_entry(
            hass, entries
        )

    assert migrated_data.get("enable_calendar") is True
    assert migrated_data["name"] == "Test Calendar"
