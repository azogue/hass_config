# -*- coding: utf-8 -*-
import asyncio
from ..enerpi import (EnerpiStreamer, LOGGER, EnerpiSensor, CONF_HOST, CONF_PORT, CONF_PREFIX,
                      CONF_SCAN_INTERVAL, CONF_DELTA_REFRESH, CONF_DEVICES, CONF_MAIN_POWER, CONF_LASTWEEK)


##########################################
# ENERPI PLATFORM:
##########################################
# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info):
    """Setup the enerPI Platform sensors getting the platform config from discovery_info."""
    devices_enerpi_hosts = []
    if discovery_info:
        is_master = True
        master_enerpi_added = False
        for clean_name, config_enerpi_host in discovery_info.items():
            LOGGER.debug('enerpi sensors config: {}'.format(config_enerpi_host))
            host = config_enerpi_host.get(CONF_HOST)
            port = config_enerpi_host.get(CONF_PORT)
            prefix = config_enerpi_host.get(CONF_PREFIX)
            devices = config_enerpi_host.get(CONF_DEVICES)
            main_power = config_enerpi_host.get(CONF_MAIN_POWER)
            data_refresh = config_enerpi_host.get(CONF_SCAN_INTERVAL)
            delta_refresh = config_enerpi_host.get(CONF_DELTA_REFRESH)
            lastweek_consumption = config_enerpi_host.get(CONF_LASTWEEK)

            streamer = EnerpiStreamer(hass, clean_name, host, port, prefix,
                                      devices, main_power, lastweek_consumption,
                                      data_refresh, delta_refresh, is_master)
            is_master = False
            devices_enerpi_hosts.append(EnerpiSensor(streamer, clean_name))
            LOGGER.info('enerPI platform sensors "{}". Sensors added: **{}**'.format(clean_name, devices))
    else:
        LOGGER.warn('No enerPI sensors present in configuration.')
        return False
    if devices_enerpi_hosts:
        async_add_devices(devices_enerpi_hosts)
    else:
        return False
