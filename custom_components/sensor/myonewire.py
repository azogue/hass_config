# -*- coding: utf-8 -*-
"""
Support for 1-Wire temperature sensors. -> Mod for retry readings & drop bad readings (with min/max value by definition)

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.onewire/
"""
import os
import time
import logging
from glob import glob
import voluptuous as vol
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import STATE_UNKNOWN, TEMP_CELSIUS, CONF_MINIMUM, CONF_MAXIMUM
from homeassistant.components.sensor import PLATFORM_SCHEMA


CONF_MOUNT_DIR = 'mount_dir'
CONF_NAMES = 'names'
DEFAULT_MOUNT_DIR = '/sys/bus/w1/devices/'
DEVICE_FAMILIES = ('10', '22', '28', '3B', '42')

DEFAULT_MAXIMUM = 125
DEFAULT_MINIMUM = -25

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAMES): {cv.string: cv.string},
    vol.Optional(CONF_MOUNT_DIR, default=DEFAULT_MOUNT_DIR): cv.string,
    vol.Optional(CONF_MAXIMUM, default=DEFAULT_MAXIMUM): cv.positive_int,
    vol.Optional(CONF_MINIMUM, default=DEFAULT_MINIMUM): int,
})

_LOGGER = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the one wire Sensors."""
    base_dir = config.get(CONF_MOUNT_DIR)
    maximum = config.get(CONF_MAXIMUM)
    minimum = config.get(CONF_MINIMUM)
    sensor_ids = []
    device_files = []
    for device_family in DEVICE_FAMILIES:
        for device_folder in glob(os.path.join(base_dir, device_family +
                                               '[.-]*')):
            sensor_ids.append(os.path.split(device_folder)[1])
            if base_dir == DEFAULT_MOUNT_DIR:
                device_files.append(os.path.join(device_folder, 'w1_slave'))
            else:
                device_files.append(os.path.join(device_folder, 'temperature'))

    if not device_files:
        _LOGGER.error('No onewire sensor found. Check if '
                      'dtoverlay=w1-gpio is in your /boot/config.txt. '
                      'Check the mount_dir parameter if it\'s defined.')
        return

    devs = []
    names = sensor_ids

    for key in config.keys():
        if key == "names":
            # only one name given
            if isinstance(config['names'], str):
                names = [config['names']]
            # map names and sensors in given order
            elif isinstance(config['names'], list):
                names = config['names']
            # map names to ids.
            elif isinstance(config['names'], dict):
                names = []
                for sensor_id in sensor_ids:
                    names.append(config['names'].get(sensor_id, sensor_id))
    for device_file, name in zip(device_files, names):
        devs.append(MyOneWire(name, device_file, minimum, maximum))
    add_devices(devs)


class MyOneWire(Entity):
    """Implementation of an One wire Sensor."""

    def __init__(self, name, device_file, minimum=DEFAULT_MINIMUM, maximum=DEFAULT_MAXIMUM):
        """Initialize the sensor."""
        self._name = name
        self._device_file = device_file
        self._minimum = minimum
        self._maximum = maximum
        self._state = STATE_UNKNOWN
        self.update()

    def _read_temp_raw(self):
        """Read the temperature as it is returned by the sensor."""
        try:
            with open(self._device_file, 'r') as ds_device_file:
                lines = ds_device_file.readlines()
            return lines
        except FileNotFoundError:
            # _LOGGER.error('Cannot read from sensor: ' + self._device_file)
            return ['NO']

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return TEMP_CELSIUS

    def update(self):
        """Get the latest data from the device."""
        temp = - self._minimum ** 2
        if self._device_file.startswith(DEFAULT_MOUNT_DIR):
            n_retries = 0
            lines = self._read_temp_raw()
            while (lines[0].strip()[-3:] != 'YES') and (n_retries < 2):
                time.sleep(0.2)
                lines = self._read_temp_raw()
                n_retries += 1
            if len(lines) > 1:
                equals_pos = lines[1].find('t=')
                if equals_pos != -1:
                    temp_string = lines[1][equals_pos+2:]
                    temp = round(float(temp_string) / 1000.0, 1)
            else:
                _LOGGER.error('Cannot read sensor!: ' + self._device_file)
                return
        else:
            try:
                ds_device_file = open(self._device_file, 'r')
                temp_read = ds_device_file.readlines()
                ds_device_file.close()
                if len(temp_read) == 1:
                    temp = round(float(temp_read[0]), 1)
            except ValueError:
                _LOGGER.warning('Invalid temperature value read from ' +
                                self._device_file)
            except FileNotFoundError:
                _LOGGER.warning('Cannot read from sensor: ' +
                                self._device_file)

        if temp < self._minimum or temp > self._maximum:
            return
        self._state = round(temp, 2)
