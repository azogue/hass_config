"""
Support for the Psychrometrics component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/binary_sensor.psychrometrics/
"""
import asyncio

from ..psychrometrics import (
    DOMAIN, PsychrometricsBinarySensor, CONF_NAME,
    ATTR_FRIENDLY_NAME, ATTR_DEVICE_CLASS)


DEPENDENCIES = ['psychrometrics']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the vacuum switch from discovery info."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    fn_name = discovery_info[ATTR_FRIENDLY_NAME]
    device_class = discovery_info[ATTR_DEVICE_CLASS]

    chart_handler = hass.data[DOMAIN]

    async_add_devices([PsychrometricsBinarySensor(
        chart_handler, name, fn_name, device_class)])
