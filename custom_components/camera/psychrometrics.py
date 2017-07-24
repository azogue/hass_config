# -*- coding: utf-8 -*-
"""
Support for the Psychrometrics component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/camera.psychrometrics/

"""
import asyncio

from ..psychrometrics import DOMAIN, PsychroCam


DEPENDENCIES = ['psychrometrics']


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info):
    """Set up the Psychrometric chart as Camera."""
    if discovery_info is None:
        return

    chart_handler = hass.data[DOMAIN]

    async_add_devices(
        [PsychroCam(hass, chart_handler, discovery_info['name'])])
