#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Support for HTU21D temperature and humidity sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.htu21d/

http://www.te.com/commerce/DocumentDelivery/DDEController?Action=showdoc
&DocId=Data+Sheet%7FHPC199_6%7FA%7Fpdf%7FEnglish%7FENG_DS_HPC199_6_A.pdf
%7FCAT-HSC0004

http://www.datasheetspdf.com/datasheet/download.php?id=779951,
http://www.datasheetspdf.com/PDF/HTU21D/779951/1

DATASHEET: htu21d sensor
- Enable I2C
...
- Add user homeassistant to group i2c
...

- Install [smbus-cffi](https://pypi.python.org/pypi/smbus-cffi/)
```
sudo apt-get install build-essential libi2c-dev i2c-tools python-dev libffi-dev
pip3 install smbus-cffi
```
"""
import asyncio
from datetime import timedelta
import logging
import time

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['smbus-cffi>=0.5.1']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_BUS = 'i2c_bus'
I2C_ADDRESS = 0x40
DEFAULT_I2C_BUS = 1

# I2C_SLAVE = 0x0703
CMD_READ_TEMP_HOLD = 0xE3
CMD_READ_HUM_HOLD = 0xE5
CMD_READ_TEMP_NOHOLD = 0xF3
CMD_READ_HUM_NOHOLD = 0xF5
CMD_WRITE_USER_REG = 0xE6
CMD_READ_USER_REG = 0xE7
CMD_SOFT_RESET = 0xFE
MEASUREMENT_WAIT_TIME = 0.055

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

DEFAULT_NAME = 'HTU21D Sensor'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the HTU21D sensor."""
    name = config.get(CONF_NAME)
    bus_number = config.get(CONF_I2C_BUS)
    try:
        # noinspection PyUnresolvedReferences
        import smbus
        bus = smbus.SMBus(bus_number)
    except ImportError as exc:
        _LOGGER.error("ImportError: %s", exc)
        return False

    sensor = yield from hass.async_add_job(HTU21D, bus)
    if not sensor.detected:
        _LOGGER.error("HTU21D sensor not detected in bus %s", bus_number)
        return False

    dev = [HTU21DSensor(sensor, name, 'temperature', TEMP_CELSIUS),
           HTU21DSensor(sensor, name, 'humidity', '%')]
    async_add_devices(dev)


class HTU21D:
    """Implement HTU21D communication."""

    def __init__(self, bus):
        # TODO quitar debug
        self.counter_updates = 0
        self.counter_ok = 0

        self._bus = bus
        self.ok = self._soft_reset()
        self.temperature = -255
        self.humidity = -255
        self.update()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # TODO check cierre del bus I2c
        _LOGGER.info('Exit: dir(bus): %s', str(dir(self._bus)))
        self._bus.close()
        # self._power_down()

    def _soft_reset(self):
        try:
            self._bus.write_byte(I2C_ADDRESS, CMD_SOFT_RESET)
            time.sleep(MEASUREMENT_WAIT_TIME)
            return True
        except OSError as exc:
            _LOGGER.error("Bad writing in bus: %s", exc)
            return False

    @property
    def detected(self) -> bool:
        """Sensor is working ok."""
        return self.ok

    @staticmethod
    def _calc_temp(sensor_temp):
        t_sensor_temp = sensor_temp / 65536.0
        return -46.85 + (175.72 * t_sensor_temp)

    @staticmethod
    def _calc_humid(sensor_humid):
        t_sensor_humid = sensor_humid / 65536.0
        return -6.0 + (125.0 * t_sensor_humid)

    @staticmethod
    def _temp_coefficient(rh_actual, temp_actual):
        return rh_actual - 0.15 * (25 - temp_actual)

    @staticmethod
    def _crc8check(value):
        # Ported from Sparkfun Arduino HTU21D Library:
        # https://github.com/sparkfun/HTU21D_Breakout
        remainder = ((value[0] << 8) + value[1]) << 8
        remainder |= value[2]

        # POLYNOMIAL = 0x0131 = x^8 + x^5 + x^4 + 1
        # divisor = 0x988000 is the 0x0131 polynomial shifted to farthest
        # left of three bytes
        divisor = 0x988000

        for i in range(0, 16):
            if remainder & 1 << (23 - i):
                remainder ^= divisor
            divisor >>= 1

        if remainder == 0:
            return True
        else:
            _LOGGER.error('Bad CRC: remainder=%s', remainder)
            return False

    @property
    def valid_measurement(self):
        """Return True for a valid measurement data."""
        return self.ok and self.temperature > -100 and self.humidity > -1

    @property
    def dew_point_temperature(self):
        """Get the dew point temperature for the last measurement."""
        if self.valid_measurement:
            coef_a, coef_b, coef_c = 8.1332, 1762.39, 235.66
            part_press = 10 ** (coef_a - coef_b / (self.temperature + coef_c))
            from math import log10
            dp = - coef_c
            dp -= coef_b / (log10(self.humidity * part_press / 100.) - coef_a)
            return dp
        return -255

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Read raw data and calculate temperature and humidity."""
        try:
            self._bus.write_byte(I2C_ADDRESS, CMD_READ_TEMP_NOHOLD)
            time.sleep(MEASUREMENT_WAIT_TIME)
            buf_t = self._bus.read_i2c_block_data(
                I2C_ADDRESS, CMD_READ_TEMP_HOLD, 3)

            self._bus.write_byte(I2C_ADDRESS, CMD_READ_HUM_NOHOLD)
            time.sleep(MEASUREMENT_WAIT_TIME)
            buf_h = self._bus.read_i2c_block_data(
                I2C_ADDRESS, CMD_READ_HUM_HOLD, 3)
        except OSError as exc:
            self.ok = False
            _LOGGER.error("Bad reading: %s", exc)
            return

        if self._crc8check(buf_t):
            temp = (buf_t[0] << 8 | buf_t[1]) & 0xFFFC
            self.temperature = self._calc_temp(temp)

            if self._crc8check(buf_h):
                humid = (buf_h[0] << 8 | buf_h[1]) & 0xFFFC
                rh_actual = self._calc_humid(humid)
                # For temperature coefficient compensation
                rh_final = self._temp_coefficient(rh_actual, self.temperature)
                rh_final = 100.0 if rh_final > 100 else rh_final  # Clamp > 100
                rh_final = 0.0 if rh_final < 0 else rh_final  # Clamp < 0
                self.humidity = rh_final
            else:
                self.humidity = -255
        else:
            self.temperature = -255
        self.counter_updates += 1
        if self.valid_measurement:
            self.counter_ok += 1
        _LOGGER.debug('UPDATED: {:.2f} ºC, {:.2f} %. #{} / ok:{} - Tª rocío: {:.2f}'
                      .format(self.temperature, self.humidity,
                              self.counter_updates, self.counter_ok, self.dew_point_temperature))


class HTU21DSensor(Entity):
    """Implementation of the HTU21D sensor."""

    def __init__(self, htu21d_client, name, variable, unit):
        """Initialize the sensor."""
        self._name = '{}_{}'.format(name, variable)
        self._variable = variable
        self._unit_of_measurement = unit
        self._client = htu21d_client
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

    # def update(self):
    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from the HTU21D and update the states."""
        tic = time.time()
        yield from self.hass.async_add_job(self._client.update)
        value = getattr(self._client, self._variable)
        if self._client.valid_measurement:
            self._state = round(value, 1)
        else:
            _LOGGER.warning("Bad Update of sensor.%s: %s", self.name, value)
        toc = time.time()
        _LOGGER.debug('sensor %s update #%s finished in %.3f: %s %s',
                      self.name, self._client.counter_updates, toc - tic,
                      self._state, self.unit_of_measurement)


if __name__ == "__main__":
    # noinspection PyUnresolvedReferences
    import smbus

    b = smbus.SMBus(1)
    s = HTU21D(b)
    s.update()
    print("Temp: %s C" % s.temperature)
    print("Humid: %s %% rH" % s.humidity)
