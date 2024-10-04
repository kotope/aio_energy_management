"""Nord pool cheapet hours binary sensor."""

from datetime import date, datetime, timedelta
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
import homeassistant.util.dt as dt_util

from .coordinator import EnergyManagementCoordinator
from .exceptions import (
    InvalidEntityState,
    InvalidInput,
    SystemConfigurationError,
    ValueNotFound,
)
from .helpers import (
    convert_datetime,
    from_str_to_time,
    merge_two_dicts,
    time_in_between,
)
from .math import (
    calculate_non_sequential_cheapest_hours,
    calculate_sequential_cheapest_hours,
)

_LOGGER = logging.getLogger(__name__)


class CheapestHoursBinarySensor(BinarySensorEntity):
    """Cheapest hours sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id,
        name,
        first_hour,
        last_hour,
        starting_today,
        number_of_hours,
        sequential,
        coordinator: EnergyManagementCoordinator,
        failsafe_starting_hour=None,
        inversed=False,
        entsoe_entity=None,
        nordpool_entity=None,
        trigger_time=None,
    ) -> None:
        """Init sensor."""
        self._nordpool_entity = nordpool_entity
        self._entsoe_entity = entsoe_entity
        self._attr_unique_id = unique_id.replace(" ", "_")
        self._attr_name = name
        self._attr_icon = "mdi:clock"
        self._attr_is_on = STATE_UNKNOWN
        self._coordinator = coordinator
        self._first_hour = first_hour
        self._last_hour = last_hour
        self._starting_today = starting_today
        self._sequential = sequential
        self._failsafe_starting_hour = failsafe_starting_hour
        self._number_of_hours = number_of_hours
        self._inversed = inversed
        self._trigger_time = None

        if trigger_time is not None:
            self._trigger_time = from_str_to_time(trigger_time)

        self.hass = hass
        # Data
        self._data = self._coordinator.get_data(self._attr_unique_id)
        if self._data is None:
            self._data = {}

    async def async_update(self) -> None:
        """Update sensor."""
        await self._async_operate()

    @property
    def extra_state_attributes(self) -> dict:
        """Return all the data."""
        return merge_two_dicts(self._data, self._construct_attributes())

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self._data is None:
            return False

        items = self._data.get("list")
        if items is None or len(items) == 0:
            # No valid data, check failsafe
            _LOGGER.debug("No valid data found. Check failsafe")
            return self._is_failsafe()

        # We got valid data, check the actual list of items
        values = convert_datetime(items)

        if values is None:
            return False

        for value in values:
            start: datetime = dt_util.as_local(value.get("start"))
            end: datetime = dt_util.as_local(value.get("end"))

            if dt_util.now() >= start:
                if dt_util.now() <= end:
                    return True

        return False

    async def _async_operate(self) -> None:
        if self._data is None:
            self._data = self._coordinator.get_data(self._attr_unique_id)

        # Don't update values if we are already on failsafe as we don't want to interrupt it
        if self._is_failsafe():
            return None

        # Check if our data is valid and we do not need to do anything
        if self._is_fetched_today():  # Data valid for today
            _LOGGER.debug(
                "Local entity data is still valid for %s", self._attr_unique_id
            )
            if self._is_expired() is False:
                return None

        if self._is_allowed_to_update() is False:
            _LOGGER.debug("Update not allowed by rules: trigger_time")
            return None

        # No valid data found from store either, try get new
        _LOGGER.debug(
            "No today fetch done for %s or value is expired. Request new data from nord pool integration",
            self._attr_unique_id,
        )

        # Update number of hours.. this actually needs to be stored in the data..
        try:
            self._update_number_of_hours()
        except InvalidEntityState:
            return None

        await self._swap_list_if_needed()
        self._data["failsafe"] = self._create_failsafe()

        # Price array from integrations
        today: list = None
        tomorrow: list = None

        if self._nordpool_entity is not None:
            # Update from nordpool
            try:
                nordpool = self._update_from_nordpool()
                today = nordpool.attributes["today"]
                tomorrow = nordpool.attributes["tomorrow"]
            except ValueNotFound:
                _LOGGER.debug("Could not get the latest data from nordpool integration")
                if self._is_expired():
                    self._data.pop("list", None)
                return None
        elif self._entsoe_entity is not None:
            # Update from entsoe
            try:
                entsoe = self._update_from_entsoe()
                today = [item["price"] for item in entsoe.attributes["prices_today"]]
                tomorrow = [
                    item["price"] for item in entsoe.attributes["prices_tomorrow"]
                ]
            except ValueNotFound:
                _LOGGER.debug("Could not get the latest data from entsoe integration")
                if self._is_expired():
                    self._data.pop("list", None)
                return None
            except SystemConfigurationError:
                _LOGGER.error(
                    "Failed to get enough data from Entso-e integration using %s. Ensure your system timezone and Entso-e integration region is correct!",
                    self._entsoe_entity,
                )
                if self._is_expired():
                    self._data.pop("list", None)
                return None

        cheapest = None

        # Use proper method if sequential or non-sequential
        try:
            if self._sequential:
                cheapest = calculate_sequential_cheapest_hours(
                    today,
                    tomorrow,
                    self._data["active_number_of_hours"],
                    self._starting_today,
                    self._first_hour,
                    self._last_hour,
                    self._inversed,
                )
            else:
                cheapest = calculate_non_sequential_cheapest_hours(
                    today,
                    tomorrow,
                    self._data["active_number_of_hours"],
                    self._starting_today,
                    self._first_hour,
                    self._last_hour,
                    self._inversed,
                )
        except InvalidInput:
            return None

        # Construct new data from calculated hours
        if self._is_expired():
            self._set_list(cheapest, self._create_expiration())
        elif (
            self._data["list"] != cheapest
        ):  # Not expired, but data is not the same. Set to list_next
            # Data is not the same, set the next
            self._data["list_next"] = cheapest
            self._data["list_next_expiration"] = self._create_expiration()

        self._data["fetch_date"] = self._create_fetch_date()
        await self._store_data()

    async def _store_data(self) -> None:
        await self._coordinator.async_set_data(
            self._attr_unique_id,
            self._attr_name,
            self.__class__.__name__,
            self._data,
        )

    async def _swap_list_if_needed(self) -> bool:
        """Swap the list_next to list if needed. Returns true if list was swapped."""
        if self._is_expired():  # Data is expired
            if list_next := self._data.get("list_next"):
                self._set_list(list_next, self._data.get("list_next_expiration"))
                self._data.pop("list_next", None)
                self._data.pop("list_next_expiration", None)
                await self._store_data()
                return True
            self._data.pop("list", None)

        return False

    def _set_list(self, list: dict, expiration: datetime) -> None:
        """Set list data."""
        self._data["list"] = list
        self._data["expiration"] = expiration
        self._data["updated_at"] = dt_util.now()

    def _is_expired(self) -> bool:
        """Check if data is expired."""
        if self._data is not None:
            if self._data.get("list") is None or {}:
                return True

            if self._data.get("expiration") is None:
                return True

            expires = dt_util.as_local(self._data.get("expiration"))
            if expires is not None:
                if expires > dt_util.now():
                    return False
        return True

    def _is_allowed_to_update(self) -> bool:
        """Check if update is allowed by local rules."""
        if self._trigger_time is not None:
            return dt_util.now().time() >= self._trigger_time

        return True

    def _is_fetched_today(self) -> bool:
        if self._data is None:
            return False

        fetch_date = self._data.get("fetch_date")
        if fetch_date is not None and fetch_date == dt_util.start_of_local_day().date():
            return True
        return False

    def _create_failsafe(self) -> dict | None:
        """Construct failsafe dictionary."""
        if self._failsafe_starting_hour is None:
            return None

        start = dt_util.now().replace(
            hour=self._failsafe_starting_hour, minute=0, second=0, microsecond=0
        )
        end = start + timedelta(hours=self._data["active_number_of_hours"])
        return {"start": start.time(), "end": end.time()}

    def _create_expiration(self) -> datetime:
        """Calculate value expiration."""
        return dt_util.start_of_local_day() + timedelta(hours=24 + 1 + self._last_hour)

    def _create_fetch_date(self) -> date:
        """Return fetch date."""
        return dt_util.start_of_local_day().date()

    def _update_from_nordpool(self) -> State:
        np = self.hass.states.get(self._nordpool_entity)

        if np is None:
            _LOGGER.debug(
                "Got empty data from Norpool entity %s ", self._nordpool_entity
            )
            raise ValueNotFound
        if np.attributes.get("today") is None:
            _LOGGER.debug(
                "No values for today in Norpool entity %s ", self._nordpool_entity
            )
            raise ValueNotFound
        if np.attributes.get("tomorrow_valid") is False or None:
            _LOGGER.debug(
                "No values for tomorrow_valid in Norpool entity %s ",
                self._nordpool_entity,
            )
            raise ValueNotFound
        if np.attributes.get("tomorrow") is None:
            _LOGGER.warning(
                "No values for tomorrow in Norpool entity %s ", self._nordpool_entity
            )
            raise ValueNotFound

        return np

    def _update_from_entsoe(self) -> State:
        """Update from entsoe integration."""
        entsoe = self.hass.states.get(self._entsoe_entity)
        if entsoe is None:
            _LOGGER.debug("Got empty data from Entso-e entity %s ", self._entsoe_entity)
            raise ValueNotFound

        if entsoe.attributes.get("prices") is None:
            _LOGGER.debug(
                "No values for today in Entso-e entity %s ", self._entsoe_entity
            )

        if tomorrow := entsoe.attributes.get("prices_tomorrow"):
            if len(tomorrow) < 10:
                _LOGGER.debug(
                    "Not enough values for tomorrow in Entso-e entity %s (probably prices not yet published) ",
                    self._entsoe_entity,
                )
                raise ValueNotFound
        else:
            _LOGGER.warning(
                "No values for tomorrow in Entso-e entity %s", self._entsoe_entity
            )
            raise ValueNotFound

        if len(tomorrow) < 24:
            # TODO: Summer time saving support for this check aswell
            raise SystemConfigurationError

        return entsoe

    def _is_failsafe(self) -> bool:
        if (
            self._data is None
        ):  # TODO: If data is none, we most probably need to check the failsafe value instead of just returning false!
            return False

        if self._is_expired() is False:
            return False  # Data not expired yet.

        if failsafe := self._data.get("failsafe"):
            start = from_str_to_time(failsafe.get("start"))
            end = from_str_to_time(failsafe.get("end"))

            return time_in_between(dt_util.now().time(), start, end)

        return False

    def _construct_attributes(self) -> dict:
        return {
            "first_hour": self._first_hour,
            "last_hour": self._last_hour,
            "starting_today": self._starting_today,
            "number_of_hours": self._number_of_hours,
            "failsafe_starting_hour": self._failsafe_starting_hour,
            "is_sequential": self._sequential,
            "failsafe_active": self._is_failsafe(),
            "inversed": self._inversed,
        }

    def _update_number_of_hours(self) -> None:
        if isinstance(self._number_of_hours, int):
            self._data["active_number_of_hours"] = self._number_of_hours
            return None

        value = self.hass.states.get(self._number_of_hours).state
        if value is not None:
            self._data["active_number_of_hours"] = int(float(value))
        else:
            _LOGGER.error(
                "Could not get entity state for cheapest hours number of hours!"
            )
            raise InvalidEntityState
