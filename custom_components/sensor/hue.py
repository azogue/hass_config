"""
Sensor for checking the status of Hue sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hue_sensors/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle


REQUIREMENTS = ['hue-sensors==1.1']

DOMAIN = 'hue'
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)

# Device icon / attrs
MODELS = ['SML', 'RWL', 'ZGP', 'GEO']
MODELS_ATTRS = {
    'SML': {'icon': 'mdi:run-fast',
            'attrs': ['light_level', 'battery', 'last_updated',
                      'lux', 'dark', 'daylight', 'temperature']},
    'RWL': {'icon': 'mdi:remote', 'attrs': ['battery', 'last_updated']},
    'ZGP': {'icon': 'mdi:remote', 'attrs': ['battery', 'last_updated']},
    'GEO': {'icon': 'mdi:cellphone', 'attrs': []}}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES): cv.ensure_list(MODELS),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Hue sensors."""
    import hue_sensors as hs
    url = hass.data[DOMAIN] + '/sensors'
    data = HueSensorData(url, hs.parse_hue_api_response)
    data.update()
    sensors = []
    models = config.get(CONF_DEVICES)
    for key in data.data.keys():
        if not models or data.data[key]['model'] in models:
            sensors.append(HueSensor(key, data))
    add_devices(sensors, True)


class HueSensorData(object):
    """Get the latest sensor data."""

    def __init__(self, url, parse_hue_api_response):
        """Initialize the data object."""
        self.url = url
        self.data = None
        self.parse_hue_api_response = parse_hue_api_response

    # Update only once in scan interval.
    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data."""
        response = requests.get(self.url)
        if response.status_code != 200:
            _LOGGER.warning("Invalid response from API")
        else:
            self.data = self.parse_hue_api_response(response.json())


class HueSensor(Entity):
    """Class to hold Hue Sensor basic info."""

    ICON = 'mdi:run-fast'

    def __init__(self, hue_id, data):
        """Initialize the sensor object."""
        self._hue_id = hue_id
        self._data = data    # data is in .data
        self._name = self._data.data[self._hue_id]['name']
        self._model = self._data.data[self._hue_id]['model']
        self._state = self._data.data[self._hue_id]['state']
        self._icon = MODELS_ATTRS[self._model]['icon']
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Attributes."""
        return self._attributes

    def update(self):
        """Update the sensor."""
        self._data.update()
        self._state = self._data.data[self._hue_id]['state']
        for attr in MODELS_ATTRS[self._model]['attrs']:
            self._attributes[attr] = self._data.data[self._hue_id][attr]
