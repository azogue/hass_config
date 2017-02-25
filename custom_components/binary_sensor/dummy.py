# -*- coding: utf-8 -*-
"""
Support for Dummy Binary Sensors. (for update its states from outside HASS)

"""
import logging
import voluptuous as vol
from homeassistant.components.binary_sensor import BinarySensorDevice, SENSOR_CLASSES_SCHEMA, PLATFORM_SCHEMA
from homeassistant.const import CONF_FRIENDLY_NAME, CONF_SENSOR_CLASS, CONF_SENSORS
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'Binary Dummy Sensor'


SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_SENSOR_CLASS, default=None): SENSOR_CLASSES_SCHEMA
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Command line Binary Sensor."""
    # _LOGGER.info('Dummy Sensor setup_platform: {}'.format(config))
    sensors = []
    for device, device_config in config[CONF_SENSORS].items():
        fn = device_config.get(CONF_FRIENDLY_NAME)
        sensor_class = device_config.get(CONF_SENSOR_CLASS)
        sensors.append(DummyBinarySensor(device, sensor_class, fn))
    add_devices(sensors)


class DummyBinarySensor(BinarySensorDevice):
    """Represent a Dummy binary sensor."""

    def __init__(self, name, sensor_class, friendly_name):
        """Initialize the Command line binary sensor."""
        # self._hass = hass
        self._name = name
        self._sensor_class = sensor_class
        self._friendly_name = friendly_name
        # self._icon = icon
        self._state = False
        _LOGGER.info('Created Dummy Sensor "{}"'.format(name))
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Entity pushes its state to HA!"""
        return False

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._state

    @property
    def sensor_class(self):
        """Return the class of the binary sensor."""
        return self._sensor_class
    #
    @property
    def state_attributes(self):
        """Return the state attributes."""
        return dict(friendly_name=self._friendly_name, sensor_class=self._sensor_class)

    # @property
    # def icon(self):
    #     """Return the icon of the binary sensor."""
    #     return self._icon

    def update(self):
        """Get the latest data and updates the state."""
        # _LOGGER.info('DEBUG update dummy "{}" --> {}'.format(self._name, self._state))
        pass
