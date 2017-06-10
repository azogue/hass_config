#!/usr/bin/python2
# vim: expandtab ts=4 sw=4
# Inspired by http://www.raspberrypi-spy.co.uk/2015/03/bh1750fvi-i2c-digital-light-intensity-sensor/

import time
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity


REQUIREMENTS = ['smbus-cffi>=0.5.1']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_OPERATION_MODE = 'operation_mode'
CONF_DELAY = 'measurement_delay_ms'

SENSOR_UNIT = 'lx'
DEFAULT_NAME = 'BH1750 Light Sensor'
DEFAULT_I2C_ADDRESS = '0x23'
DEFAULT_I2C_BUS = 1
DEFAULT_MODE = "continuous_high_res_mode_1"
DEFAULT_DELAY_MS = 120

# TODO check Operation modes for BH1750 sensor
# Operation modes for BH1750 sensor (from the datasheet). Time typically 120ms
CONTINUOUS_LOW_RES_MODE = 0x13  # Start measurement at 1lx resolution
CONTINUOUS_HIGH_RES_MODE_1 = 0x10  # Start measurement at 0.5lx resolution.
CONTINUOUS_HIGH_RES_MODE_2 = 0x11  # Start measurement at 1lx resolution.

# In one time measurements, device is set to Power Down after each measurement.
ONE_TIME_HIGH_RES_MODE_1 = 0x20  # Start measurement at 0.5lx resolution.
ONE_TIME_HIGH_RES_MODE_2 = 0x21  # Start measurement at 0.5lx resolution.
ONE_TIME_LOW_RES_MODE = 0x23  # Start measurement at 1lx resolution.

OPERATION_MODES = {
    "continuous_low_res_mode": CONTINUOUS_LOW_RES_MODE,
    "continuous_high_res_mode_1": CONTINUOUS_HIGH_RES_MODE_1,
    "continuous_high_res_mode_2": CONTINUOUS_HIGH_RES_MODE_2,
    "one_time_high_res_mode_1": ONE_TIME_HIGH_RES_MODE_1,
    "one_time_high_res_mode_2": ONE_TIME_HIGH_RES_MODE_2,
    "one_time_low_res_mode": ONE_TIME_LOW_RES_MODE
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
    vol.Optional(CONF_OPERATION_MODE, default=DEFAULT_MODE): cv.string,
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
    if not sensor.detected:
        _LOGGER.error("BH1750 sensor not detected at %s", i2c_address)
        return False

    dev = [BH1750Sensor(sensor, name, SENSOR_UNIT)]
    _LOGGER.info("Setup of BH1750 light sensor at %s in mode %s is complete",
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
        self.ok = False
        self._bus = bus
        self._i2c_add = addr
        self._mode = None
        self._delay = measurement_delay / 1000.
        self.operation_mode = OPERATION_MODES[operation_mode]
        self.continuous_sampling = operation_mode.startswith('continuous')
        self._power_down()
        self._mtreg = None
        self.set_sensitivity()
        self.light_level = -1
        _LOGGER.debug('Sensor created: %s', str(self))

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._power_down()

    def __repr__(self) -> str:
        msg = "<BH1750 Sensor - sensitivity: {}, mode: {}, " \
              "continuous sampling: {}>"
        key_mode = list(filter(
            lambda x: OPERATION_MODES[x] == self.operation_mode,
            OPERATION_MODES))[0]
        return msg.format(self.sensitivity, key_mode, self.continuous_sampling)

    def _set_mode(self, mode):
        self._mode = mode
        try:
            self._bus.write_byte(self._i2c_add, self._mode)
            self.ok = True
        except OSError as exc:
            _LOGGER.error("Bad writing in bus: %s", exc)
            self.ok = False

    def _power_down(self):
        self._set_mode(self.POWER_DOWN)

    def _power_on(self):
        self._set_mode(self.POWER_ON)

    def _reset(self):
        # It has to be powered on before resetting
        self._power_on()
        self._set_mode(self.RESET)

    @property
    def detected(self) -> bool:
        """Sensor is working ok."""
        return self.ok

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
        """ Return current measurement result in lx. """
        try:
            data = self._bus.read_word_data(self._i2c_add, self._mode)
            self.ok = True
        except OSError as exc:
            _LOGGER.error("Bad reading in bus: %s", exc)
            self.ok = False
            return -1

        count = data >> 8 | (data & 0xff) << 8
        mode2coeff = 2 if (self._mode & 0x03) == 0x01 else 1
        ratio = 1 / (1.2 * (self._mtreg / 69.0) * mode2coeff)
        return ratio * count

    def _wait_for_result(self, additional=0):
        """Wait for the sensor to be ready for measurement."""
        basetime = 0.018 if (self._mode & 0x03) == 0x03 else 0.128
        time.sleep(basetime * (self._mtreg / 69.0) + additional)

    def do_measurement(self, mode, additional_delay=0) -> float:
        """
        Perform complete measurement using command
        specified by parameter mode with additional
        delay specified in parameter additional_delay.
        Return output value in Lx.
        """
        _LOGGER.debug('Measurement mode: %s, ∆s: %s, last: %.1f',
                      mode, additional_delay, self.light_level)
        if not self.continuous_sampling \
                or self.light_level < 0 \
                or mode != self._mode:
            self._reset()
            self._set_mode(mode)
            self._wait_for_result(additional=additional_delay)
        return self._get_result()

    def update(self):
        """Update the measured light level."""
        self.light_level = self.do_measurement(
            self.operation_mode, self._delay)


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
        tic = time.time()
        # self.bh1750_client.update()
        yield from self.hass.async_add_job(self.bh1750_client.update)
        if self.bh1750_client.light_level >= 0:
            self._state = int(round(self.bh1750_client.light_level))
        else:
            _LOGGER.warning("Bad Update of sensor.%s: %s",
                            self.name, self.bh1750_client.light_level)
        toc = time.time()
        _LOGGER.debug('sensor update finished in %.3f s. Light level: %s',
                      toc - tic, self._state)


# if __name__ == "__main__":
#     import smbus
#     import sys
#
#     # bus = smbus.SMBus(0) # Rev 1 Pi uses 0
#     b = smbus.SMBus(1)  # Rev 2 Pi uses 1
#
#     # sensitivity = 39
#     # while True:
#     #     print("Sensitivity: {:d}".format(sensitivity))
#     #     for operation_m, mode_v in OPERATION_MODES.items():
#     #         if operation_m.startswith('one_time_'):
#     #             s = BH1750(b, operation_mode=operation_m)
#     #             s.set_sensitivity(sensitivity)
#     #             time.sleep(.2)
#     #             s.update()
#     #             time.sleep(.3)
#     #             s.update()
#     #             print("Mode {} - Light Level : {:3.2f} lx"
#     #                   .format(operation_m, s.light_level))
#     #             time.sleep(.6)
#     #     print("--------")
#     #
#     #     sensitivity = (sensitivity + 10) % 255
#     #     time.sleep(2)
#
#     op_mode = "one_time_high_res_mode_1"
#     delay = 0
#     delta = 1
#     if len(sys.argv) > 1:
#         op_mode = sys.argv[1]
#         print("Operation mode: {}".format(op_mode))
#     if len(sys.argv) > 2:
#         delay = float(sys.argv[2])
#         print("additional_delay: {}".format(delay))
#     if len(sys.argv) > 3:
#         delta = float(sys.argv[3])
#         print("∆T: {} s".format(delta))
#     s = BH1750(b, operation_mode=op_mode)
#     print(s)
#
#     while True:
#         try:
#             light_level = s.do_measurement(
#                 s.operation_mode, additional_delay=delay)
#             print("Light Level : {:3.2f} lx".format(light_level))
#             time.sleep(delta)
#         except KeyboardInterrupt:
#             print('Exiting...')
#             break
