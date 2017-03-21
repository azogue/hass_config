# -*- coding: utf-8 -*-
"""
Support for Dummy Sensors, for update its states from outside HASS but be present in HA start
(to be present in Appdaemon init, or Homebridge-homeassistant)

"""
import logging
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_SENSORS, CONF_FRIENDLY_NAME, CONF_UNIT_OF_MEASUREMENT, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'Dummy Sensor'


SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_FRIENDLY_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=None): cv.string
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): vol.Schema({cv.slug: SENSOR_SCHEMA}),
})


# noinspection PyUnusedLocal
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Dummy Sensor."""
    sensors = []
    for device, device_config in config[CONF_SENSORS].items():
        fn = device_config.get(CONF_FRIENDLY_NAME)
        unit = device_config.get(CONF_UNIT_OF_MEASUREMENT)
        sensors.append(DummySensor(device, fn, unit))
    add_devices(sensors)


class DummySensor(Entity):
    """Represent a Dummy sensor."""

    def __init__(self, name, friendly_name, unit):
        self._name = name
        self._unit = unit
        self._friendly_name = friendly_name
        self._state = STATE_UNKNOWN
        _LOGGER.info('Created Dummy Sensor "{}"'.format(name))

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Entity pushes its state to HA!"""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @property
    def state_attributes(self):
        """Return the state attributes."""
        if self._unit is not None:
            return dict(friendly_name=self._friendly_name, unit_of_measurement=self._unit)
        return dict(friendly_name=self._friendly_name)

    # @property
    # def device_class(self):
    #     """Return the class of the binary sensor."""
    #     return self._device_class

    # @property
    # def icon(self):
    #     """Return the icon of the binary sensor."""
    #     return self._icon
