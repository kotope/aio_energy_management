"""Fixtures for testing."""

import pytest

import homeassistant.util.dt as dt_util


@pytest.fixture(autouse=True)
async def setup_fixture(hass, hass_time_zone):
    """Set up things to be run when tests are started."""
    await hass.config.async_set_time_zone(hass_time_zone)


@pytest.fixture
def hass_tz_info(hass):
    """Return timezone info for the hass timezone."""
    return dt_util.get_time_zone(hass.config.time_zone)


@pytest.fixture
def hass_time_zone():
    """Return default hass timezone."""
    return "Europe/Helsinki"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return
