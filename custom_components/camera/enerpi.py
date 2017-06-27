# -*- coding: utf-8 -*-
"""
enerPI Adaptation of the local_file camera, to show SVG TILES as cameras.

"""
import asyncio
import os
from ..enerpi import (
    EnerpiTileCam, LOGGER, CONF_HOST, CONF_PORT, CONF_PREFIX,
    CONF_TILE_CAMERAS, CONF_TILES_SVGS_REFRESH,
    CONF_TILE_EXTENSION, CONF_WIDTH_TILES)


BASEDIR = os.path.dirname(os.path.abspath(__file__))


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info):
    """Set up the enerPI Cameras: local_file cameras mirroring SVG tiles."""
    cameras = []
    if discovery_info:
        for name, config_enerpi_host in discovery_info.items():
            host = config_enerpi_host.get(CONF_HOST)
            port = config_enerpi_host.get(CONF_PORT)
            prefix = config_enerpi_host.get(CONF_PREFIX)
            tile_cameras = config_enerpi_host.get(CONF_TILE_CAMERAS)
            pngs_refresh = config_enerpi_host.get(CONF_TILES_SVGS_REFRESH)
            width_tiles = config_enerpi_host.get(CONF_WIDTH_TILES)
            for cam_name, cam_path, mag, desc, c1, c2 in tile_cameras:
                # check path:
                if os.path.exists(cam_path) and cam_path.startswith(BASEDIR) \
                        and cam_path.endswith(CONF_TILE_EXTENSION):
                    cam = EnerpiTileCam(
                        hass, cam_name, cam_path, host, port, prefix, name,
                        mag, desc, pngs_refresh, width_tiles, c1, c2)
                    LOGGER.debug(
                        'Append enerPI camera as LocalFile cam: {} -> {}'
                        .format(cam, cam_path))
                    cameras.append(cam)
                else:
                    LOGGER.error(
                        'BAD PATH for enerPI camera "{}": {} --> Not appended'
                        .format(cam_name, cam_path))
            LOGGER.info('enerPI platform cameras "{}". Cameras added: **{}**'
                        .format(name, cameras))
    else:
        LOGGER.warn('No enerPI cameras present in configuration.')
        return False
    if cameras:
        async_add_devices(cameras)
    else:
        return False
