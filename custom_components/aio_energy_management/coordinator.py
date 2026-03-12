"""Data coordinator. Owns all the data."""

from datetime import datetime, timedelta
import logging

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
        self.requires_calendar_update = False

    async def _async_save_data(self) -> None:
        """Save data to store."""
        _LOGGER.debug("Request to save data: %s", self.data)
        await self._store.async_save(self.data)

    async def async_clear_store(self) -> None:
        """Clear store."""
        _LOGGER.debug("Request to clear all values from the store")
        await self._store.async_save({})

    async def async_clear_data(self, unique_id: str) -> None:
        """Clear entity data by unique_id."""
        _LOGGER.debug("Request to clear data for %s", unique_id)
        if self.data.get(unique_id) is not None:
            self.data.pop(unique_id, None)
            await self._async_save_data()

    async def async_load_data(self):
        """Load data from store."""
        stored = await self._store.async_load()
        if stored:
            _LOGGER.debug("Load data from store: %s", stored)
            self.data = self.convert_datetimes(stored)
            self.requires_calendar_update = True

    async def async_set_data(
        self,
        entity_id: str,
        name: str,
        calendar: bool,
        module: str,
        dict: dict,  # Data that is currently active or upcoming
        archived: list | None,  # Data that is to be moved on the archive
    ) -> None:
        """Set entity data."""
        prev_archived = {}

        # Check if previous
        if entity := self.data.get(entity_id):
            prev_archived = entity.get("archived")

        self.data[entity_id] = dict
        self.data[entity_id]["name"] = name
        self.data[entity_id]["type"] = module
        self.data[entity_id]["calendar"] = calendar

        self.data[entity_id]["archived"] = self._update_archived(
            entity_id, prev_archived, archived
        )

        _LOGGER.debug(
            "Set new data for %s. Archive is = %s",
            entity_id,
            [self.data[entity_id]["archived"]],
        )

        self.requires_calendar_update = True
        await self._async_save_data()

    def _update_archived(
        self, entity_id: str, existing_archive: list | None, new_data: list | None
    ) -> list:
        """Merge archived lists by 'start' key, preferring self.data[entity_id] values on conflict."""

        current_archived = existing_archive
        if current_archived is None:
            current_archived = []

        # Build dicts keyed by 'start' for fast lookup
        current_by_start = {
            item["start"]: item for item in current_archived if "start" in item
        }

        new_by_start = []
        if new_data is not None:
            new_by_start = {item["start"]: item for item in new_data if "start" in item}

        # Merge keys: use current if exists, else new
        merged = []
        all_starts = set(current_by_start) | set(new_by_start)
        for start in sorted(all_starts):
            if start in current_by_start:
                merged.append(current_by_start[start])
            else:
                merged.append(new_by_start[start])

        return merged

    def clear_archived(self, entity_id: str, retention_days: int) -> None:
        """Clear archived data older than retention days."""
        now = dt_util.now()
        if entity_data := self.data.get(entity_id):
            archived = entity_data.get("archived", [])
            filtered_archived = [
                item
                for item in archived
                if "end" in item
                and (
                    from_str_to_datetime(item["end"])
                    >= now - timedelta(days=retention_days)
                )
            ]
            self.data[entity_id]["archived"] = filtered_archived
            _LOGGER.debug(
                "After clearing, archived for %s is %s",
                entity_id,
                filtered_archived,
            )

    def get_data(self, entity_id: str) -> dict | None:
        """Get entity data."""
        _LOGGER.debug("Query data from store for %s", entity_id)
        data = self.data.get(entity_id)
        if data is None:
            data = {}

        if data.get("list") is None:
            data["list"] = []  # Always contain list
        return data

    def convert_datetimes(self, dictionary: dict) -> dict | None:
        """Convert stored datetime items back to data."""
        for k, v in dictionary.items():
            dictionary[k] = self._convert_datetimes_of_item(v)
        return dictionary

    def _convert_datetimes_of_item(self, dictionary: dict) -> dict:
        """Convert stored datetime strings back to datetime objects."""
        datetime_fields = {"expiration", "updated_at"}
        date_fields = {"fetch_date"}
        list_fields = {"list", "archived"}

        for field in datetime_fields:
            if value := dictionary.get(field):
                if isinstance(value, str):
                    dictionary[field] = from_str_to_datetime(value)

        for field in date_fields:
            if value := dictionary.get(field):
                if isinstance(value, str):
                    dictionary[field] = dt_util.parse_date(value)

        for field in list_fields:
            if value := dictionary.get(field):
                dictionary[field] = convert_datetime(value)

        if data_next := dictionary.get("next"):
            if list_next := data_next.get("list"):
                dictionary["next"]["list"] = convert_datetime(list_next)
            if expiration_next := data_next.get("expiration"):
                if isinstance(expiration_next, str):
                    dictionary["next"]["expiration"] = from_str_to_datetime(
                        expiration_next
                    )

        return dictionary
