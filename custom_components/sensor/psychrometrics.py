"""
Support for the Psychrometrics component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/sensor.psychrometrics/
"""
import asyncio

from homeassistant.const import (
    CONF_NAME, ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, ATTR_ICON)
from ..psychrometrics import DOMAIN, PsychrometricsSensor


DEPENDENCIES = ['psychrometrics']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the vacuum switch from discovery info."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    unit = discovery_info[ATTR_UNIT_OF_MEASUREMENT]
    fn_name = discovery_info[ATTR_FRIENDLY_NAME]
    icon = discovery_info[ATTR_ICON]

    chart_handler = hass.data[DOMAIN]

    async_add_devices(
        [PsychrometricsSensor(chart_handler, name, fn_name, unit, icon)])
