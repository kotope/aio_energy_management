"""Calendar component for aio energy management platform."""

from __future__ import annotations

from datetime import datetime
import logging

import voluptuous as vol
from voluptuous import ALLOW_EXTRA, Invalid, Schema

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util

from .const import CONF_ENTITY_CALENDAR, CONF_NAME, CONF_UNIQUE_ID, COORDINATOR, DOMAIN
from .coordinator import EnergyManagementCoordinator

_LOGGER = logging.getLogger(__name__)

ENERGY_MANAGEMENT_CALENDAR_PLATFORM_SCHEMA = Schema(
    {
        vol.Required(CONF_UNIQUE_ID): vol.All(vol.Coerce(str)),
        vol.Required(CONF_NAME): vol.All(vol.Coerce(str)),
    },
    extra=ALLOW_EXTRA,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up calendar from a config entry."""
    _LOGGER.debug("Create energy management calendar entity from config entry")

    try:
        async_add_entities(
            [
                EnergyManagementCalendar(
                    hass=hass,
                    unique_id=entry.data[CONF_UNIQUE_ID],
                    name=entry.data[CONF_NAME],
                    coordinator=hass.data[DOMAIN][COORDINATOR],
                )
            ]
        )
    except Exception as e:
        _LOGGER.error(
            "Error setting up calendar from config entry: %s",
            e,
        )


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Sensor containing amount of cheapest hours marked in the configuration (YAML legacy)."""
    entry_type = discovery_info["entry_type"]
    # Configure cheapest hours binary sensor
    if entry_type == CONF_ENTITY_CALENDAR:
        _LOGGER.debug("Create energy management calendar entity")

        try:
            ENERGY_MANAGEMENT_CALENDAR_PLATFORM_SCHEMA(discovery_info)
            async_add_entities(
                [
                    EnergyManagementCalendar(
                        hass=hass,
                        unique_id=discovery_info[CONF_UNIQUE_ID],
                        name=discovery_info[CONF_NAME],
                        coordinator=hass.data[DOMAIN][COORDINATOR],
                    )
                ]
            )
        except Invalid as e:
            _LOGGER.error(
                "Configuration validation error for nord pool cheapest hours sensor: %s",
                e,
            )


class EnergyManagementCalendar(CalendarEntity):
    """Calendar entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        name: str,
        coordinator: EnergyManagementCoordinator,
    ) -> None:
        """Init."""
        self.hass = hass
        self._attr_unique_id = unique_id.replace(" ", "_")
        self._attr_name = name
        self._coordinator = coordinator
        self._events = []

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        now = dt_util.now()

        # First check for current event
        for event in self._events:
            if event.start <= now <= event.end:
                return event

        # If no current event, find the next upcoming event
        future_events = [event for event in self._events if event.start > now]
        if not future_events:
            return None

        # Return the earliest upcoming event
        return min(future_events, key=lambda x: x.start)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            event
            for event in self._events
            if event.start <= end_date and event.end >= start_date
        ]

    async def async_update(self) -> None:
        """Update loop of calendar. Only update when data is changed."""
        if self._coordinator.requires_calendar_update is True:
            self._events = self._get_all_events()
            self._coordinator.requires_calendar_update = False

    def _get_all_events(
        self,
    ) -> list[CalendarEvent]:
        """Get calendar events within a datetime range."""
        events: list[CalendarEvent] = []

        for k, v in self._coordinator.data.items():
            # Don't add to calendar if disabled by config
            if v.get("calendar") is False:
                continue
            # Combine current and archived data
            combined_data = v.get("list", []) + v.get("archived", [])

            if combined_data:
                for value in combined_data:
                    start = value.get("start")
                    end = value.get("end")
                    if start is not None and end is not None:
                        events.append(
                            CalendarEvent(
                                summary=v.get("name") or k,
                                start=start,
                                end=end,
                                uid=self._uid(k, start, end),
                                description="",
                            )
                        )
            if next_data := v.get("next"):
                if next_list := next_data.get("list", []):
                    for value in next_list:
                        start = value.get("start")
                        end = value.get("end")
                        if start is not None and end is not None:
                            events.append(
                                CalendarEvent(
                                    summary=v.get("name") or k,
                                    start=start,
                                    end=end,
                                    uid=self._uid(k, start, end),
                                    description="",
                                )
                            )

        # Sort events by start time
        events.sort(key=lambda x: x.start)

        return events

    def _uid(
        self, unqiue_id: str, event_start_time: datetime, event_end_time: datetime
    ) -> str:
        """Generate a deterministic unique id for an event.

        The uid is generated from the event start and end times converted to
        UTC and formatted as YYYYmmddTHHMMSSZ for compactness and stability.
        """
        # Ensure we work with timezone-aware UTC datetimes for stability
        start_utc = dt_util.as_utc(event_start_time)
        end_utc = dt_util.as_utc(event_end_time)

        start_str = start_utc.strftime("%Y%m%dT%H%M%SZ")
        end_str = end_utc.strftime("%Y%m%dT%H%M%SZ")

        return f"{unqiue_id}_{start_str}_{end_str}"
