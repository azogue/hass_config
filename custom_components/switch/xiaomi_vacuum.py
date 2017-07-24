"""
Support for Xiaomi Vacuum cleaner robot.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/switch.xiaomi_vacuum/
"""
import asyncio

from homeassistant.components.xiaomi_vacuum import (
    DOMAIN, ICON, CONF_NAME, MiroboVacuumSwitch)


DEPENDENCIES = ['xiaomi_vacuum']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the vacuum switch from discovery info."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    mirobo_vacuum = hass.data[DOMAIN]

    yield from async_add_devices(
        [MiroboVacuumSwitch(name, mirobo_vacuum, ICON)], True)
