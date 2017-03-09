# -*- coding: utf-8 -*-
"""
enerPI Adaptation of the local_file camera, for represent locally as cameras the enerPI SVG tiles with the sensors evo.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.local_file/
"""
import asyncio
import os
from ..enerpi import (EnerpiTileCam, LOGGER, CONF_HOST, CONF_PORT, CONF_PREFIX,
                      CONF_TILE_CAMERAS, CONF_TILES_PNGS_REFRESH, CONF_TILE_EXTENSION)


BASEDIR = os.path.dirname(os.path.abspath(__file__))


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info):
    """Setup the enerPI Cameras: create local_file cameras mirroring the enerpi SVG tiles."""

    cameras = []
    if discovery_info:
        for name, config_enerpi_host in discovery_info.items():
            host = config_enerpi_host.get(CONF_HOST)
            port = config_enerpi_host.get(CONF_PORT)
            prefix = config_enerpi_host.get(CONF_PREFIX)
            tile_cameras = config_enerpi_host.get(CONF_TILE_CAMERAS)
            pngs_refresh = config_enerpi_host.get(CONF_TILES_PNGS_REFRESH)
            for cam_name, cam_path, mag, desc in tile_cameras:
                # check path:
                if os.path.exists(cam_path) and cam_path.startswith(BASEDIR) and cam_path.endswith(CONF_TILE_EXTENSION):
                    cam = EnerpiTileCam(hass, cam_name, cam_path, host, port, prefix, name, mag, desc, pngs_refresh)
                    LOGGER.debug('Append enerPI camera as LocalFile cam: {} -> {}'.format(cam, cam_path))
                    cameras.append(cam)
                else:
                    LOGGER.error('BAD PATH for enerPI camera "{}": {} --> Not appended'.format(cam_name, cam_path))
            LOGGER.info('enerPI platform cameras "{}". Cameras added: **{}**'.format(name, cameras))
    else:
        LOGGER.warn('No enerPI cameras present in configuration.')
        return False
    if cameras:
        yield from async_add_devices(cameras)
    else:
        return False
