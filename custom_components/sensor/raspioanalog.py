# -*- coding: utf-8 -*-
"""
A simple analog sensor for Raspberry PI with a MCP3008 A/D conversor (like in the Raspio Analog Zero Hat),
using the `gpiozero` library.

* YAML configuration example:

```
sensor:
  - platform: raspioanalog
    channels:
      7:
        name: Illumination 1
        unit_of_measurement: '%'
        device_class: light
      3:
        name: Illumination 2
        unit_of_measurement: '%'
        device_class: light
        negate: yes  # use 'negate' for invert the percentage value (x_% = 100 - x_%)
    scan_interval: 10
```
"""
import asyncio
import logging
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_UNIT_OF_MEASUREMENT, CONF_DEVICE_CLASS
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv


_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['gpiozero==1.3.1']

CONF_CHANNEL = 'channels'
CONF_TYPE = 'analog'
CONF_NEGATE = 'negate'


SENSOR_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, None): cv.string,
    vol.Optional(CONF_DEVICE_CLASS, None): cv.string,
    vol.Optional(CONF_NEGATE, False): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CHANNEL):
        vol.Schema({cv.positive_int: SENSOR_SCHEMA}),
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the raspio analog platform."""
    channels = config.get(CONF_CHANNEL)
    sensors = []
    for channel_num, conf_analog_s in channels.items():
        sensors.append(AnalogSensor(conf_analog_s.get(CONF_NAME),
                                    channel_num,
                                    conf_analog_s.get(CONF_UNIT_OF_MEASUREMENT),
                                    conf_analog_s.get(CONF_DEVICE_CLASS),
                                    conf_analog_s.get(CONF_NEGATE)))
    async_add_devices(sensors)


class AnalogSensor(Entity):
    """Representation of an Analog Sensor in a MCP3008 A/D conversor."""

    def __init__(self, name, analog_channel, unit=None, device_class=None, negate=False):
        """Initialize the analog sensor."""
        from gpiozero import MCP3008

        self._analog_sensor = MCP3008(channel=analog_channel)
        self._channel = analog_channel
        self._name = name
        self._device_class = device_class
        self._unit = unit
        self._negate_value = negate
        self._value = self._get_analog_value_as_percentage()

    def _get_analog_value_as_percentage(self):
        if self._negate_value:
            value = round(100. - self._analog_sensor.value * 100., 1)
        else:
            value = round(self._analog_sensor.value * 100., 1)
        return value

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._value

    @property
    def name(self):
        """Get the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit

    @asyncio.coroutine
    def async_update(self):
        """Get the latest value from the pin."""
        self._value = self._get_analog_value_as_percentage()
