"""Calendar component for aio energy management platform."""

from datetime import datetime, timedelta
import logging

import voluptuous as vol
from voluptuous import ALLOW_EXTRA, Invalid, Schema

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Sensor containing amount of cheapest hours marked in the configuration."""
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

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = dt_util.now()

        events = self._get_events(
            start_date=now,
            end_date=now + timedelta(days=7),  # only need to check a week ahead
        )
        return next(iter(events), None)

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""

        return self._get_events(
            start_date=start_date,
            end_date=end_date,
        )

    def _get_events(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Get calendar events within a datetime range."""
        events: list[CalendarEvent] = []

        for k, v in self._coordinator.data.items():
            # Don't add to calendar if disabled by config
            if v.get("calendar") is False:
                continue

            if d := v.get("list"):
                for value in d:
                    start = value.get("start")
                    end = value.get("end")
                    if (
                        start is not None
                        and end is not None
                        and self._is_in_range(start, start_date, end_date)
                    ):
                        events.append(
                            CalendarEvent(
                                summary=v.get("name") or k, start=start, end=end
                            )
                        )
            if next := v.get("next"):
                if d := next.get("list"):
                    for value in d:
                        start = value.get("start")
                        end = value.get("end")
                        if (
                            start is not None
                            and end is not None
                            and self._is_in_range(start, start_date, end_date)
                        ):
                            events.append(
                                CalendarEvent(
                                    summary=v.get("name") or k, start=start, end=end
                                )
                            )

        return events

    def _is_in_range(
        self, event_start_time: datetime, start_date: datetime, end_date: datetime
    ) -> bool:
        if event_start_time > start_date and event_start_time < end_date:
            return True
        return False
