"""The errors of Energy Management integration."""

from homeassistant import exceptions


class ValueNotFound(exceptions.HomeAssistantError):
    """Error to indicate values not found error."""


class InvalidInput(exceptions.HomeAssistantError):
    """Error to indicate invalid input."""


class InvalidEntityState(exceptions.HomeAssistantError):
    """Error to indicate invalid external entity state."""
