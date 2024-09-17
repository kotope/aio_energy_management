"""Data coordinator. Owns all the data."""

from datetime import datetime
import logging
import zoneinfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util

from .helpers import convert_datetime, from_str_to_datetime

STORAGE_VERSION = 1
STORAGE_KEY = "aio_energy_management.storage"
_LOGGER = logging.getLogger(__name__)

# TODO: .. version migration
class EnergyManagementCoordinator:
    """Common coordinator for Energy Management component. Owner of the data."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Init persistent store."""
        self._store = Store[dict[str, any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self.listeners = []
        self.data = {}

    async def _async_save_data(self) -> None:
        """Save data to store."""
        _LOGGER.debug("Request to save data: %s", self.data)
        await self._store.async_save(self.data)

    async def async_clear_store(self) -> None:
        """Clear store."""
        _LOGGER.debug("Request to clear all values from the store")
        await self._store.async_save({})

    async def async_load_data(self):
        """Load data from store."""
        stored = await self._store.async_load()
        print(f"ZZZZ: stored = {stored}")
        if stored:
            _LOGGER.debug("Load data from store: %s", stored)
            self.data = self._convert_datetimes(stored)

    async def async_set_data(
        self, entity_id: str, name: str, module: str, dict: dict
    ) -> None:
        """Set entity data."""
        self.data[entity_id] = dict
        self.data[entity_id]["name"] = name
        self.data[entity_id]["type"] = module
        await self._async_save_data()

    def get_data(self, entity_id: str) -> dict | None:
        """Get entity data."""
        _LOGGER.debug("Query data from store for %s", entity_id)
        print(f"data = {self.data.get(entity_id)}")
        return self.data.get(entity_id)

    def _convert_datetimes(self, dictionary: dict) -> dict | None:
        for k, v in dictionary.items():
            dictionary[k] = self._convert_datetimes_of_item(v)
        return dictionary

    def _convert_datetimes_of_item(self, dictionary: dict) -> dict:
        if expires := dictionary.get("expiration"):
            if expires is not datetime:
                dictionary["expiration"] = from_str_to_datetime(
                    dictionary.get("expiration")
                )
            else:
                dictionary["expiration"] = expires

        if fetch_date := dictionary.get("fetch_date"):
            if isinstance(fetch_date, str):
                dictionary["fetch_date"] = dt_util.parse_date(fetch_date)

        if data_list := dictionary.get("list"):
            dictionary["list"] = convert_datetime(data_list)
        if data_list_next := dictionary.get("list_next"):
            dictionary["list_next"] = convert_datetime(data_list_next)

        return dictionary