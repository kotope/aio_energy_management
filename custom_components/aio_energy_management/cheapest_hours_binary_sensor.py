"""Nord pool cheapet hours binary sensor."""

from datetime import date, datetime, timedelta
import logging

from jinja2 import Environment, StrictUndefined

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
import homeassistant.util.dt as dt_util

from .coordinator import EnergyManagementCoordinator
from .enums import HourPriceType
from .exceptions import (
    InvalidEntityState,
    InvalidInput,
    SystemConfigurationError,
    ValueNotFound,
)
from .helpers import (
    convert_datetime,
    from_str_to_datetime,
    from_str_to_time,
    get_first,
    get_last,
    merge_two_dicts,
    time_in_between,
)
from .math import (
    calculate_non_sequential_cheapest_hours,
    calculate_sequential_cheapest_hours,
)
from .models import hour_price

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
        nordpool_official_config_entry=None,
        trigger_time=None,
        trigger_hour=None,
        price_limit=None,
        calendar=True,
        offset=None,
        mtu=60,
        price_modifications=None,
    ) -> None:
        """Init sensor."""
        self._nordpool_entity = nordpool_entity
        self._nordpool_official_config_entry = nordpool_official_config_entry
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
        self._trigger_hour = trigger_hour
        self._price_limit = price_limit
        self._calendar = calendar
        self._price_modifications = price_modifications

        if mtu is None:
            self._mtu = 60
        else:
            self._mtu = mtu

        if offset is None:
            self._offset = {}
        else:
            self._offset = offset

        if trigger_time is not None:
            self._trigger_time = from_str_to_time(trigger_time)

        self.hass = hass
        self._data = self._coordinator.get_data(self._attr_unique_id)

    async def async_update(self) -> None:
        """Update sensor."""
        await self._async_operate()

    @property
    def extra_state_attributes(self) -> dict:
        """Return all the data."""
        return merge_two_dicts(
            self._construct_data_attributes(),
            self._construct_static_attributes(),
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        if self._data is None:
            return False

        items = self._data.get("list")
        if items is None or items == []:
            # No valid data, check failsafe
            _LOGGER.debug("No valid data found. Check failsafe")
            return self._is_failsafe()

        # We got valid data, check the actual list of items
        values = convert_datetime(items)

        if values is None:
            _LOGGER.error(
                "No values found! This is a bug, please report to https://github.com/kotope/aio_energy_management/issues"
            )
            return False

        for value in values:
            start: datetime = dt_util.as_local(value.get("start"))
            end: datetime = dt_util.as_local(value.get("end"))

            if dt_util.now() >= start:
                if dt_util.now() <= end:
                    return True

        return False

    async def _async_operate(self) -> None:
        # Always get new data from coordinator as other components might have modified the data
        self._data = self._coordinator.get_data(self._attr_unique_id)

        await self._swap_list_if_needed()

        # Don't update values if we are already on failsafe as we don't want to interrupt it
        if self._is_failsafe():
            _LOGGER.debug("Failsafe on. Don't interrupt the operation")
            return

        # Check if our data is valid and we do not need to do anything
        if self._is_fetched_today():  # Data valid for today
            _LOGGER.debug(
                "Local entity data is still valid for %s", self._attr_unique_id
            )
            if self._is_expired() is False:
                return

        # No valid data found from store either, try get new
        _LOGGER.debug(
            "No today fetch done for %s or value is expired. Request new data from nord pool integration",
            self._attr_unique_id,
        )

        # Update number of hours.. this actually needs to be stored in the data..
        try:
            self._update_entity_variables()
        except InvalidEntityState:
            _LOGGER.error("Failed to get values from external entities!")
            return

        if self._is_allowed_to_update() is False:
            _LOGGER.debug("Update not allowed by set rules")
            return

        self._data["failsafe"] = self._create_failsafe()

        # Price array from integrations
        today: list = None
        tomorrow: list = None
        if self._nordpool_official_config_entry is not None:
            try:
                (
                    today,
                    tomorrow,
                    active_mtu,
                ) = await self._update_from_nordpool_official(self._mtu)
            except (ServiceValidationError, ValueNotFound) as e:
                _LOGGER.debug(
                    "No values for tomorrow in nord pool official integration %s", e
                )
                if self._is_expired():
                    self._data["list"] = []
                return
            except (SystemConfigurationError, InvalidEntityState) as e:
                _LOGGER.error(
                    "Could not get the latest data from official nord pool integration: %s",
                    e,
                )
                if self._is_expired():
                    self._data["list"] = []
                return

        elif self._nordpool_entity is not None:
            # Update from nordpool
            try:
                (today, tomorrow, active_mtu) = self._update_from_nordpool(
                    requested_mtu=self._mtu
                )
            except ValueNotFound:
                _LOGGER.debug("Could not get the latest data from nordpool integration")
                if self._is_expired():
                    self._data["list"] = []
                return
            except SystemConfigurationError as e:
                _LOGGER.error(
                    "Invalid configuration or mismatch of data: %s",
                    e,
                )
                if self._is_expired():
                    self._data["list"] = []
                return

        elif self._entsoe_entity is not None:
            # Update from entsoe
            try:
                if (
                    self._mtu == 15
                ):  # Don't allow mtu 15 with etsoe as it does not have end time for the time
                    raise SystemConfigurationError(  # noqa: TRY301
                        "MTU 15 not supported with entsoe integration."
                    )

                entsoe = self._update_from_entsoe()
                today = [
                    hour_price.HourPrice.from_dict(item, type=HourPriceType.ENTSOE)
                    for item in entsoe.attributes["prices_today"]
                ]

                tomorrow = [
                    hour_price.HourPrice.from_dict(item, type=HourPriceType.ENTSOE)
                    for item in entsoe.attributes["prices_tomorrow"]
                ]
            except ValueNotFound:
                _LOGGER.debug("Could not get the latest data from entsoe integration")
                if self._is_expired():
                    self._data["list"] = []
                return
            except SystemConfigurationError:
                _LOGGER.error(
                    "Failed to get enough data from Entso-e integration using %s. Ensure your system timezone and Entso-e integration region is correct!",
                    self._entsoe_entity,
                )
                if self._is_expired():
                    self._data["list"] = []
                return

        cheapest = None

        # Apply possible price modifications from template
        if price_modifications := self._price_modifications:
            today = apply_price_modifications(today, price_modifications)
            tomorrow = apply_price_modifications(tomorrow, price_modifications)

        # today and tomorrow are lists of HourPrice objects from now on
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
                    self._data.get("active_price_limit"),
                    self._mtu,
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
                    self._data.get("active_price_limit"),
                    self._mtu,
                )
        except InvalidInput:
            # Logging already made on math.py, just return
            return

        # Construct new data from calculated hours
        if self._is_expired():
            self._set_list(
                cheapest.get("list"),
                self._create_expiration(),
                cheapest.get("extra"),
            )
        elif self._data["list"] != cheapest.get(
            "list"
        ):  # Not expired, but data is not the same. Set to list_next
            self._set_next(
                cheapest.get("list") or [],
                self._create_expiration(),
                cheapest.get("extra") or {},
            )

        self._data["fetch_date"] = self._create_fetch_date()
        await self._store_data()

    async def _store_data(self) -> None:
        await self._coordinator.async_set_data(
            self._attr_unique_id,
            self._attr_name,
            self._calendar,
            self.__class__.__name__,
            self._data,
        )

    async def _swap_list_if_needed(self) -> bool:
        """Swap the list_next to list if needed. Returns true if list was swapped."""
        if self._is_expired():  # Data is expired
            if nxt := self._data.get("next"):
                self._set_list(
                    nxt.get("list") or [],
                    nxt.get("expiration"),
                    nxt.get("extra") or {},
                    is_swap=True,
                )
                # Clear previous next data as it's transferred to parent now
                self._data.pop("next", None)

                # Remove deprecated list_next. List next was used prior version 0.3.3
                if self._data.get("list_next") is not None:
                    self._data.pop("list_next", None)

                await self._store_data()
                return True

            self._data["list"] = []

        return False

    def _set_list(
        self,
        list_data: list,
        expiration: datetime,
        attributes: dict,
        is_swap: bool = False,
    ) -> None:
        """Set list data."""
        if is_swap is False:
            list_data, expiration = self._add_offset(list_data, expiration)
        self._data["list"] = list_data
        self._data["expiration"] = expiration
        self._data["extra"] = attributes
        self._data["updated_at"] = dt_util.now()

    def _set_next(
        self, list_data: list, expiration: datetime, attributes: dict
    ) -> None:
        nxt = {}
        lst, exp = self._add_offset(list_data, expiration)
        nxt["list"] = lst
        nxt["expiration"] = exp
        nxt["extra"] = attributes
        self._data["next"] = nxt

    def _add_offset(self, list: list, expiration: datetime) -> tuple[list, datetime]:
        new_expiration = expiration
        if first := get_first(list):
            if start := first.get("start"):
                if offset := self._offset.get("start"):
                    hours = self._int_from_entity(offset.get("hours"))
                    minutes = self._int_from_entity(offset.get("minutes"))

                    new_start = start + timedelta(
                        hours=hours if hours is not None else 0,
                        minutes=minutes if minutes is not None else 0,
                    )
                    new_first = {"start": new_start, "end": first["end"]}
                    list[0] = new_first
        if last := get_last(list):
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

                    list[-1] = new_last

        return (list, new_expiration)

    def _is_expired(self) -> bool:
        """Check if data is expired."""
        if self._data is not None:
            if self._data.get("list") is None or {}:
                return True

            if self._data.get("expiration") is None:
                return True

            if expires := dt_util.as_local(self._data.get("expiration")):
                _LOGGER.debug(
                    "Checking expiration. Expiration as local = %s, now = %s",
                    expires,
                    dt_util.now(),
                )
                if expires > dt_util.now():
                    return False
        return True

    def _is_allowed_to_update(self) -> bool:
        """Check if update is allowed by local rules."""
        if self._trigger_time is not None:
            if dt_util.now().time() < self._trigger_time:
                return False
        if trigger_hour := self._data.get("active_trigger_hour"):
            if dt_util.now().hour < trigger_hour:
                return False
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

    def _update_from_nordpool(self, requested_mtu: int = 60) -> tuple[list, list, int]:
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

        # Ensure raw_today first value is actually today as we might get old values
        # if Home Assistant event loop has not reached nord pool yet")
        if raw_today := np.attributes.get("raw_today"):
            if first := from_str_to_datetime(get_first(raw_today).get("start")):
                if first.date() != dt_util.start_of_local_day().date():
                    _LOGGER.debug("Nord pool provided old data: Ignore")
                    raise ValueNotFound

        raw_tomorrow = np.attributes.get("raw_tomorrow")
        if raw_tomorrow is None:
            _LOGGER.warning(
                "No values for tomorrow in Norpool entity %s ", self._nordpool_entity
            )
            raise ValueNotFound

        active_mtu = 60
        if self._is_15min_period_in_use(raw_today):
            if requested_mtu == 60:
                raw_today = combine_to_hourly(raw_today)
            else:
                active_mtu = 15
        if self._is_15min_period_in_use(raw_tomorrow):
            if requested_mtu == 60:
                raw_tomorrow = combine_to_hourly(
                    raw_tomorrow,
                )

        today = [
            hour_price.HourPrice.from_dict(item, type=HourPriceType.NORDPOOL)
            for item in raw_today
        ]
        tomorrow = [
            hour_price.HourPrice.from_dict(item, type=HourPriceType.NORDPOOL)
            for item in raw_tomorrow
        ]
        if active_mtu != self._mtu:
            raise SystemConfigurationError(
                f"MTU value {self._mtu} does not match the actual data MTU {active_mtu} used by nord pool official integration. Please correct the configuration"
            )
        return (today, tomorrow, active_mtu)

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

        return entsoe

    async def _update_from_nordpool_official(
        self, requested_mtu: int = 60
    ) -> tuple[list, list, int]:
        today_data = await self.hass.services.async_call(
            domain="nordpool",
            service="get_prices_for_date",
            service_data={
                "config_entry": self._nordpool_official_config_entry,
                "date": dt_util.now().strftime("%Y-%m-%d"),
            },
            return_response=True,
            blocking=True,
        )
        tomorrow_data = await self.hass.services.async_call(
            domain="nordpool",
            service="get_prices_for_date",
            service_data={
                "config_entry": self._nordpool_official_config_entry,
                "date": (dt_util.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            },
            return_response=True,
            blocking=True,
        )
        first_key = next(iter(today_data))
        value_today = today_data[first_key]
        first_key = next(iter(tomorrow_data))
        value_tomorrow = tomorrow_data[first_key]

        active_mtu = 60
        if self._is_15min_period_in_use(value_today):
            if requested_mtu == 60:
                value_today = combine_to_hourly(value_today)
            else:
                active_mtu = 15
        if self._is_15min_period_in_use(value_tomorrow):
            if requested_mtu == 60:
                value_tomorrow = combine_to_hourly(
                    value_tomorrow,
                )

        # Convert to HourPrice list
        today = [
            hour_price.HourPrice.from_dict(item, type=HourPriceType.NORDPOOL_OFFICIAL)
            for item in value_today
        ]
        tomorrow = [
            hour_price.HourPrice.from_dict(item, type=HourPriceType.NORDPOOL_OFFICIAL)
            for item in value_tomorrow
        ]

        if (
            len(tomorrow) < 10
        ):  # Official nordpool no longer raise ServiceValidationError on empty data for tomorrow. Raise valuenotfound when no data is available
            raise ValueNotFound

        if active_mtu != self._mtu:
            raise SystemConfigurationError(
                f"MTU value {self._mtu} does not match the actual data MTU {active_mtu} used by nord pool official integration. Please correct the configuration"
            )
        return (today, tomorrow, active_mtu)

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
            failsafe_on = time_in_between(dt_util.now().time(), start, end)
            _LOGGER.debug("Running on failsafe: %s", failsafe_on)
            return failsafe_on

        return False

    def _construct_data_attributes(self) -> dict:
        # Make some manipulation of the data stucture returned to the user
        d = self._data

        # Move extra data from 'extra' to root
        if extras := self._data.get("extra"):
            d["max_price"] = extras.get("max_price")
            d["min_price"] = extras.get("min_price")
            d["mean_price"] = extras.get("mean_price")
            d.pop("extra", None)
        return d

    def _construct_static_attributes(self) -> dict:
        attrs = {
            "first_hour": self._first_hour,
            "last_hour": self._last_hour,
            "starting_today": self._starting_today,
            "number_of_hours": self._number_of_hours,
            "failsafe_starting_hour": self._failsafe_starting_hour,
            "is_sequential": self._sequential,
            "failsafe_active": self._is_failsafe(),
            "inversed": self._inversed,
        }

        if price_limit := self._price_limit:
            attrs["price_limit"] = price_limit
        if trigger_time := self._trigger_time:
            attrs["trigger_time"] = trigger_time
        if trigger_hour := self._trigger_hour:
            attrs["trigger_hour"] = trigger_hour

        return attrs

    def _update_entity_variables(self) -> None:
        self._data["active_number_of_hours"] = self._int_from_entity(
            self._number_of_hours
        )
        if trigger_hour := self._trigger_hour:
            self._data["active_trigger_hour"] = self._int_from_entity(trigger_hour)
        if price_limit := self._price_limit:
            self._data["active_price_limit"] = self._float_from_entity(price_limit)

    def _float_from_entity(self, entity_id) -> float | None:
        """Get float value from another entity."""
        if entity_id is None:
            return None

        if isinstance(entity_id, float):
            return entity_id

        value = self.hass.states.get(entity_id).state
        if value is not None:
            return float(value)
        _LOGGER.error("Could not get entity state for %s", entity_id)
        raise InvalidEntityState

    def _int_from_entity(self, entity_id) -> int | None:
        """Get int value from another entity."""
        if entity_id is None:
            return None

        if isinstance(entity_id, int):
            return entity_id

        value = self.hass.states.get(entity_id).state
        if value is not None:
            return int(float(value))
        _LOGGER.error("Could not get entity state for %s", entity_id)
        raise InvalidEntityState

    def _is_15min_period_in_use(self, data: list) -> bool:
        """Check if data mtu is 15min."""
        return len(data) > 40


def combine_to_hourly(data):
    """Combine a list of 15-minute price data into hourly averages.

    Args:
        data: A list of dictionaries, where each dictionary has 'start', 'end'
              (ISO 8601 strings), and 'price' (float).

    Returns:
        A list of dictionaries, each representing an hour with 'start', 'end',
        and 'price' (hourly average).

    """
    hourly_data = []
    i = 0
    while i < len(data):
        current_block = []
        # Ensure we have at least 4 items for a full hour
        if i + 3 < len(data):
            # Check if the current item's start minute is :00
            start_dt = datetime.fromisoformat(data[i]["start"])
            if start_dt.minute == 0:
                # Collect the next four 15-minute blocks
                current_block.extend(data[i + j] for j in range(4))

                # Calculate average price
                total_price = sum(item["price"] for item in current_block)
                average_price = total_price / 4

                # Define the hourly start and end times
                hourly_start = current_block[0]["start"]
                hourly_end = current_block[-1]["end"]

                hourly_data.append(
                    {
                        "start": hourly_start,
                        "end": hourly_end,
                        "price": round(average_price, 2),  # Round to 2 decimal places
                    }
                )
                i += 4  # Move to the next hour block
            else:
                i += 1  # Move to next 15-min block if not starting at :00
        else:
            break  # Not enough data for a full hour block

    return hourly_data


def apply_price_modifications(
    hour_prices: list,
    template_str: str,
) -> list:
    """Apply price modifications to each HourPrice using a Jinja2 template.

    Args:
        hour_prices: List of HourPrice objects.
        template_str: Jinja2 template string. Variables: 'price', 'time' (datetime).

    Returns:
        List of HourPrice objects with updated price.
    """
    env = Environment(undefined=StrictUndefined)
    template = env.from_string(template_str)
    updated = []
    for hp in hour_prices:
        # Use start time for 'time' variable
        context = {
            "price": hp.value,
            "time": hp.start if hasattr(hp, "start") else None,
        }
        try:
            new_price = float(template.render(context))
        except Exception as ex:  # noqa: BLE001
            _LOGGER.error("Failed to render price modifications template: %s", ex)
            new_price = hp.value
        # Create a new HourPrice object with updated price
        updated.append(
            hour_price.HourPrice(
                start=hp.start,
                end=hp.end,
                value=new_price,
                type=hp.type,
            )
        )
    return updated
