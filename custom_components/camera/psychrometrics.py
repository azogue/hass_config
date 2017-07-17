# -*- coding: utf-8 -*-
"""

"""
import asyncio

from ..psychrometrics import PsychroCam, make_psychrochart


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info):
    """Set up the Psychrometric chart as Camera."""
    if discovery_info:
        # Create chart:
        chart = yield from hass.async_add_job(
            make_psychrochart,
            discovery_info['altitude'], discovery_info['pressure_kpa'])

        cam = PsychroCam(
            hass, chart,
            discovery_info['zones_sensors'],
            discovery_info['connectors'],
            discovery_info['entity_name'],
            discovery_info['refresh_interval'],
            discovery_info['remote_api'])
        async_add_devices([cam])
    else:
        return False
