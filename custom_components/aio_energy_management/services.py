"""AIO Energy Management Service utility."""

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import config_validation as cv

from .const import COORDINATOR, DOMAIN

LOGGER = logging.getLogger(__name__)

ATTR_UNIQUE_ID = "unique_id"

SERVICE_CLEAR_DATA_SCHEMA = {
    vol.Required(ATTR_UNIQUE_ID): cv.string,
}

SERVICE_CLEAR_DATA = "clear_data"
SERVICES = [SERVICE_CLEAR_DATA]

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the AIO Energy Management services."""
    coordinator = hass.data[DOMAIN][COORDINATOR]
    _LOGGER.debug("Register services")

    async def clear_data(service_call: ServiceCall) -> None:
        if unique_id := service_call.data.get(ATTR_UNIQUE_ID):
            await coordinator.async_clear_data(unique_id)
        else:
            _LOGGER.error("Failed to clear data: no unique_id provided")

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_DATA,
        clear_data,
        schema=vol.Schema(SERVICE_CLEAR_DATA_SCHEMA),
        supports_response=SupportsResponse.NONE,
    )
