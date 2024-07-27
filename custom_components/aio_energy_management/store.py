"""Storage."""

from datetime import datetime
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .helpers import convert_datetime, from_str_to_datetime

STORAGE_VERSION = 1
STORAGE_KEY = "aio_energy_management.storage"
_LOGGER = logging.getLogger(__name__)


# TODO: Should se store contain the type of entity as well? .. e.g. cheapest_hours, solar_energy?
class EnergyManagementStore:
    """Persistent storage for Energy Management component."""

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
        if stored:
            _LOGGER.debug("Load data from store: %s", stored)
            self.data = stored

    async def async_set_data(self, entity_id: str, dict: dict) -> None:
        """Set entity data."""
        self.data[entity_id] = dict
        await self._async_save_data()

    # TODO: Change to get_cheapest_hours_data
    def get_data(self, entity_id: str) -> dict | None:
        """Get entity data."""
        _LOGGER.debug("Query data from store for %s", entity_id)
        data = self.data.get(entity_id)
        if data is None:
            return None

        expires = data.get("expiration")
        if expires is not datetime:
            data["expiration"] = from_str_to_datetime(data.get("expiration"))
        else:
            data["expiration"] = expires
        data["list"] = convert_datetime(data.get("list"))
        _LOGGER.debug("Get data for %s from store: %s", entity_id, data)
        return data
