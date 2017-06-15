"""
Support for BH1750 light sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bh1750/
"""
import time
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['smbus-cffi==0.5.1']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_OPERATION_MODE = 'operation_mode'
CONF_DELAY = 'measurement_delay_ms'

# Operation modes for BH1750 sensor (from the datasheet). Time typically 120ms
# In one time measurements, device is set to Power Down after each sample.
CONTINUOUS_LOW_RES_MODE = "continuous_low_res_mode"
CONTINUOUS_HIGH_RES_MODE_1 = "continuous_high_res_mode_1"
CONTINUOUS_HIGH_RES_MODE_2 = "continuous_high_res_mode_2"
ONE_TIME_HIGH_RES_MODE_1 = "one_time_high_res_mode_1"
ONE_TIME_HIGH_RES_MODE_2 = "one_time_high_res_mode_2"
ONE_TIME_LOW_RES_MODE = "one_time_low_res_mode"
OPERATION_MODES = {
    CONTINUOUS_LOW_RES_MODE: (0x13, True),  # 4lx resolution
    CONTINUOUS_HIGH_RES_MODE_1: (0x10, True),  # 0.5lx resolution.
    CONTINUOUS_HIGH_RES_MODE_2: (0X11, True),  # 1lx resolution.
    ONE_TIME_HIGH_RES_MODE_1: (0x20, False),  # 0.5lx resolution.
    ONE_TIME_HIGH_RES_MODE_2: (0x21, False),  # 0.5lx resolution.
    ONE_TIME_LOW_RES_MODE: (0x23, False),  # 4lx resolution.
}

SENSOR_UNIT = 'lx'
DEFAULT_NAME = 'BH1750 Light Sensor'
DEFAULT_I2C_ADDRESS = '0x23'
DEFAULT_I2C_BUS = 1
DEFAULT_MODE = CONTINUOUS_HIGH_RES_MODE_1
DEFAULT_DELAY_MS = 120

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
    vol.Optional(CONF_OPERATION_MODE, default=DEFAULT_MODE):
        vol.In(OPERATION_MODES),
    vol.Optional(CONF_DELAY, default=DEFAULT_DELAY_MS): cv.positive_int,
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the BH1750 sensor."""
    name = config.get(CONF_NAME)
    bus_number = config.get(CONF_I2C_BUS)
    i2c_address = int(config.get(CONF_I2C_ADDRESS), 0)
    operation_mode = config.get(CONF_OPERATION_MODE)
    measurement_delay = config.get(CONF_DELAY)

    try:
        # noinspection PyUnresolvedReferences
        import smbus
        bus = smbus.SMBus(bus_number)
    except ImportError as exc:
        _LOGGER.error("ImportError: %s", exc)
        return False

    sensor = BH1750(bus, i2c_address, operation_mode, measurement_delay)
    if not sensor.sample_ok:
        _LOGGER.error("BH1750 sensor not detected at %s", i2c_address)
        return False

    dev = [BH1750Sensor(sensor, name, SENSOR_UNIT)]
    _LOGGER.info("Setup of BH1750 light sensor at %s in mode %s is complete.",
                 bus_number, i2c_address, operation_mode)
    async_add_devices(dev)


class BH1750:
    """Implement BH1750 communication."""

    # Define some constants from the datasheet
    POWER_DOWN = 0x00  # No active state
    POWER_ON = 0x01  # Power on
    RESET = 0x07  # Reset data register value

    def __init__(self, bus, addr=int(DEFAULT_I2C_ADDRESS, 0),
                 operation_mode=DEFAULT_MODE,
                 measurement_delay=DEFAULT_DELAY_MS):
        """Initialize the sensor."""
        self._ok = False
        self._bus = bus
        self._i2c_add = addr
        self._mode = None
        self._delay = measurement_delay / 1000.
        self._operation_mode = OPERATION_MODES[operation_mode][0]
        self._continuous_sampling = OPERATION_MODES[operation_mode][1]
        self._power_down()
        self._mtreg = None
        self.set_sensitivity()
        self.light_level = -1
        self.update()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Shut down the sensor at exit."""
        self._power_down()

    def _set_mode(self, mode):
        self._mode = mode
        try:
            self._bus.write_byte(self._i2c_add, self._mode)
            self._ok = True
        except OSError as exc:
            _LOGGER.error("Bad writing in bus: %s", exc)
            self._ok = False

    def _power_down(self):
        self._set_mode(self.POWER_DOWN)

    def _power_on(self):
        self._set_mode(self.POWER_ON)

    def _reset(self):
        # It has to be powered on before resetting
        self._power_on()
        self._set_mode(self.RESET)

    @property
    def sample_ok(self) -> bool:
        """Return sensor ok state."""
        return self._ok

    @property
    def sensitivity(self) -> int:
        """Return the sensitivity value, an integer between 31 and 254."""
        return self._mtreg

    def set_sensitivity(self, sensitivity=69):
        """Set the sensitivity value.

        Valid values are 31 (lowest) to 254 (highest), default is 69.
        """
        if sensitivity < 31:
            self._mtreg = 31
        elif sensitivity > 254:
            self._mtreg = 254
        else:
            self._mtreg = sensitivity
        self._power_on()
        self._set_mode(0x40 | (self._mtreg >> 5))
        self._set_mode(0x60 | (self._mtreg & 0x1f))
        self._power_down()

    def _get_result(self) -> float:
        """Return current measurement result in lx."""
        try:
            data = self._bus.read_word_data(self._i2c_add, self._mode)
            self._ok = True
        except OSError as exc:
            _LOGGER.error("Bad reading in bus: %s", exc)
            self._ok = False
            return -1

        count = data >> 8 | (data & 0xff) << 8
        mode2coeff = 2 if (self._mode & 0x03) == 0x01 else 1
        ratio = 1 / (1.2 * (self._mtreg / 69.0) * mode2coeff)
        return ratio * count

    def _wait_for_result(self):
        """Wait for the sensor to be ready for measurement."""
        basetime = 0.018 if (self._mode & 0x03) == 0x03 else 0.128
        time.sleep(basetime * (self._mtreg / 69.0) + self._delay)

    def update(self):
        """Update the measured light level in lux."""
        if not self._continuous_sampling \
                or self.light_level < 0 \
                or self._operation_mode != self._mode:
            self._reset()
            self._set_mode(self._operation_mode)
            self._wait_for_result()
        self.light_level = self._get_result()
        _LOGGER.debug('Measurement mode: %s, ∆s: %s, last: %.1f',
                      self._operation_mode, self._delay, self.light_level)


class BH1750Sensor(Entity):
    """Implementation of the BH1750 sensor."""

    def __init__(self, bh1750_client, name, unit):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = unit
        self.bh1750_client = bh1750_client
        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'light'

    # def update(self):
    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from the BH1750 and update the states."""
        yield from self.hass.async_add_job(self.bh1750_client.update)
        if self.bh1750_client.light_level >= 0:
            self._state = int(round(self.bh1750_client.light_level))
        else:
            _LOGGER.warning("Bad Update of sensor.%s: %s",
                            self.name, self.bh1750_client.light_level)
