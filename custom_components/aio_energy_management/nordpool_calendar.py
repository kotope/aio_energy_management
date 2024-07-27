"""Calendar entity for nord pool cheapest hours."""

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

DAY_OF_WEEK = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


class NordPoolCheapestHoursCalendar(CalendarEntity):
    """Calendar entity."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init."""
        self.hass = hass
        self._attr_name = "cheapest_hours_calendar_test"

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

        newEvent = CalendarEvent(
            summary="Summary",
            start=dt_util.now() + timedelta(hours=1),
            end=dt_util.now() + timedelta(hours=4),
        )

        events.append(newEvent)
        return events
