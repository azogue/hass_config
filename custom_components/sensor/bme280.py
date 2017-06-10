# -*- coding: utf-8 -*-
"""
Support for BME280 temperature, humidity and pressure sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bme280/

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
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    TEMP_FAHRENHEIT, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

REQUIREMENTS = ['smbus-cffi>=0.5.1']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_OVERSAMPLING_TEMP = 'oversampling_temperature'
CONF_OVERSAMPLING_PRES = 'oversampling_pressure'
CONF_OVERSAMPLING_HUM = 'oversampling_humidity'
CONF_OPERATION_MODE = 'operation_mode'
CONF_T_STANDBY = 'time_standby'
CONF_FILTER_MODE = 'filter_mode'
CONF_DELTA_TEMP = 'delta_temperature'

DEFAULT_NAME = 'BME280 Sensor'
DEFAULT_I2C_ADDRESS = '0x76'
DEFAULT_I2C_BUS = 1
DEFAULT_OVERSAMPLING_TEMP = 1       # Temperature oversampling x 1
DEFAULT_OVERSAMPLING_PRES = 1       # Pressure oversampling x 1
DEFAULT_OVERSAMPLING_HUM = 1        # Humidity oversampling x 1
DEFAULT_OPERATION_MODE = 3          # Normal mode (forced mode: 2)
DEFAULT_T_STANDBY = 5               # Tstandby 1000ms
DEFAULT_FILTER_MODE = 0             # Filter off
DEFAULT_DELTA_TEMP = 0.

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)

SENSOR_TEMPERATURE = 'temperature'
SENSOR_HUMIDITY = 'humidity'
SENSOR_PRESSURE = 'pressure'
SENSOR_TYPES = {
    SENSOR_TEMPERATURE: ['Temperature', None],
    SENSOR_HUMIDITY: ['Humidity', '%'],
    SENSOR_PRESSURE: ['Pressure', 'mb']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=[SENSOR_TEMPERATURE, SENSOR_HUMIDITY, SENSOR_PRESSURE]
                 ): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_TEMP,
                 default=DEFAULT_OVERSAMPLING_TEMP): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_PRES,
                 default=DEFAULT_OVERSAMPLING_PRES): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_HUM,
                 default=DEFAULT_OVERSAMPLING_HUM): vol.Coerce(int),
    vol.Optional(CONF_OPERATION_MODE,
                 default=DEFAULT_OPERATION_MODE): vol.Coerce(int),
    vol.Optional(CONF_T_STANDBY,
                 default=DEFAULT_T_STANDBY): vol.Coerce(int),
    vol.Optional(CONF_FILTER_MODE,
                 default=DEFAULT_FILTER_MODE): vol.Coerce(int),
    vol.Optional(CONF_DELTA_TEMP,
                 default=DEFAULT_DELTA_TEMP): vol.Coerce(float),
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the BME280 sensor."""
    SENSOR_TYPES[SENSOR_TEMPERATURE][1] = hass.config.units.temperature_unit
    name = config.get(CONF_NAME)
    i2c_address = config.get(CONF_I2C_ADDRESS)

    try:
        # noinspection PyUnresolvedReferences
        import smbus
        bus = smbus.SMBus(config.get(CONF_I2C_BUS))
    except ImportError as exc:
        _LOGGER.error("ImportError: %s", exc)
        return False

    sensor = BME280(
        bus, i2c_address,
        osrs_t=config.get(CONF_OVERSAMPLING_TEMP),
        osrs_p=config.get(CONF_OVERSAMPLING_PRES),
        osrs_h=config.get(CONF_OVERSAMPLING_HUM),
        mode=config.get(CONF_OPERATION_MODE),
        t_sb=config.get(CONF_T_STANDBY),
        filter_mode=config.get(CONF_FILTER_MODE),
        delta_temp=config.get(CONF_DELTA_TEMP)
    )
    if not sensor.detected:
        _LOGGER.error("BME280 sensor not detected at %s", i2c_address)
        return False

    dev = []
    try:
        for variable in config[CONF_MONITORED_CONDITIONS]:
            dev.append(BME280Sensor(
                sensor, variable, SENSOR_TYPES[variable][1], name))
    except KeyError:
        pass

    async_add_devices(dev)


class BME280:
    """BME280 sensor working in i2C bus."""

    # Calibration data
    _calibration_t = None
    _calibration_h = None
    _calibration_p = None
    _temp_fine = None

    def __init__(self, bus,
                 i2c_address=DEFAULT_I2C_ADDRESS,
                 osrs_t=DEFAULT_OVERSAMPLING_TEMP,
                 osrs_p=DEFAULT_OVERSAMPLING_PRES,
                 osrs_h=DEFAULT_OVERSAMPLING_HUM,
                 mode=DEFAULT_OPERATION_MODE,
                 t_sb=DEFAULT_T_STANDBY,
                 filter_mode=DEFAULT_FILTER_MODE,
                 delta_temp=DEFAULT_DELTA_TEMP,
                 spi3w_en=0):  # 3-wire SPI Disable):
        # Sensor location
        self._bus = bus
        self._i2c_add = int(i2c_address, 0)

        # BME280 parameters
        self.mode = mode
        self.ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | self.mode
        self.config_reg = (t_sb << 5) | (filter_mode << 2) | spi3w_en
        self.ctrl_hum_reg = osrs_h

        self._delta_temp = delta_temp
        self._with_pressure = osrs_p > 0
        self._with_humidity = osrs_h > 0

        # Sensor data
        self._temperature = None
        self._humidity = None
        self._pressure = None

        try:
            self.update(True)
            self.detected = True
            _LOGGER.info(
                'Created BME280 sensor at i2c:0x{:0x}, OS: {}xT, '
                '{}xP {}xH, mode {}, standby {}, filter {}'
                .format(self._i2c_add, osrs_t, osrs_p, osrs_h,
                        mode, t_sb, filter_mode))
        except OSError as exc:
            _LOGGER.warning("OSError trying to write data in i2c bus: %s", exc)

    def _compensate_temperature(self, adc_t):
        """Formula from datasheet Bosch BME280 Environmental sensor.

        8.1 Compensation formulas in double precision floating point
        Edition BST-BME280-DS001-10 | Revision 1.1 | May 2015
        """
        v1 = ((adc_t / 16384.0 - self.calibration_t[0] / 1024.0)
              * self.calibration_t[1])
        v2 = ((adc_t / 131072.0 - self.calibration_t[0] / 8192.0)
              * (adc_t / 131072.0 - self.calibration_t[0] / 8192.0)
              * self.calibration_t[2])
        self._temp_fine = v1 + v2
        if self._delta_temp != 0.:  # temperature correction for self heating
            temp = self._temp_fine / 5120.0 + self._delta_temp
            self._temp_fine = temp * 5120.0
        else:
            temp = self._temp_fine / 5120.0
        return temp

    def _compensate_pressure(self, adc_p):
        """Formula from datasheet Bosch BME280 Environmental sensor.

        8.1 Compensation formulas in double precision floating point
        Edition BST-BME280-DS001-10 | Revision 1.1 | May 2015.
        """
        v1 = (self._temp_fine / 2.0) - 64000.0
        v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * self.calibration_p[5]
        v2 += ((v1 * self.calibration_p[4]) * 2.0)
        v2 = (v2 / 4.0) + (self.calibration_p[3] * 65536.0)
        v1 = (((self.calibration_p[2]
                * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8)
              + ((self.calibration_p[1] * v1) / 2.0)
              ) / 262144
        v1 = ((32768 + v1) * self.calibration_p[0]) / 32768

        if v1 == 0:
            return 0

        pressure = ((1048576 - adc_p) - (v2 / 4096)) * 3125
        if pressure < 0x80000000:
            pressure = (pressure * 2.0) / v1
        else:
            pressure = (pressure / v1) * 2

        v1 = (self.calibration_p[8]
              * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
        v2 = ((pressure / 4.0) * self.calibration_p[7]) / 8192.0
        pressure += ((v1 + v2 + self.calibration_p[6]) / 16.0)

        return pressure / 100

    def _compensate_humidity(self, adc_h):
        """Formula from datasheet Bosch BME280 Environmental sensor.

        8.1 Compensation formulas in double precision floating point
        Edition BST-BME280-DS001-10 | Revision 1.1 | May 2015.
        """
        var_h = self._temp_fine - 76800.0
        if var_h == 0:
            return 0

        var_h = ((adc_h - (self.calibration_h[3] * 64.0 +
                           self.calibration_h[4] / 16384.0 * var_h))
                 * (self.calibration_h[1] / 65536.0
                    * (1.0 + self.calibration_h[5] / 67108864.0 * var_h
                       * (1.0 + self.calibration_h[2] / 67108864.0 * var_h))))
        var_h *= 1.0 - self.calibration_h[0] * var_h / 524288.0

        if var_h > 100.0:
            var_h = 100.0
        elif var_h < 0.0:
            var_h = 0.0

        return var_h

    def _populate_calibration_data(self):
        """From datasheet Bosch BME280 Environmental sensor."""
        calibration_t = []
        calibration_p = []
        calibration_h = []
        raw_data = []

        try:
            for i in range(0x88, 0x88 + 24):
                raw_data.append(self._bus.read_byte_data(self._i2c_add, i))
            raw_data.append(self._bus.read_byte_data(self._i2c_add, 0xA1))
            for i in range(0xE1, 0xE1 + 7):
                raw_data.append(self._bus.read_byte_data(self._i2c_add, i))
        except OSError as exc:
            _LOGGER.error("Can't populate calibration data: %s", exc)
            return

        calibration_t.append((raw_data[1] << 8) | raw_data[0])
        calibration_t.append((raw_data[3] << 8) | raw_data[2])
        calibration_t.append((raw_data[5] << 8) | raw_data[4])

        if self._with_pressure:
            calibration_p.append((raw_data[7] << 8) | raw_data[6])
            calibration_p.append((raw_data[9] << 8) | raw_data[8])
            calibration_p.append((raw_data[11] << 8) | raw_data[10])
            calibration_p.append((raw_data[13] << 8) | raw_data[12])
            calibration_p.append((raw_data[15] << 8) | raw_data[14])
            calibration_p.append((raw_data[17] << 8) | raw_data[16])
            calibration_p.append((raw_data[19] << 8) | raw_data[18])
            calibration_p.append((raw_data[21] << 8) | raw_data[20])
            calibration_p.append((raw_data[23] << 8) | raw_data[22])

        if self._with_humidity:
            calibration_h.append(raw_data[24])
            calibration_h.append((raw_data[26] << 8) | raw_data[25])
            calibration_h.append(raw_data[27])
            calibration_h.append((raw_data[28] << 4) | (0x0F & raw_data[29]))
            calibration_h.append(
                (raw_data[30] << 4) | ((raw_data[29] >> 4) & 0x0F))
            calibration_h.append(raw_data[31])

        for i in range(1, 2):
            if calibration_t[i] & 0x8000:
                calibration_t[i] = (-calibration_t[i] ^ 0xFFFF) + 1

        if self._with_pressure:
            for i in range(1, 8):
                if calibration_p[i] & 0x8000:
                    calibration_p[i] = (-calibration_p[i] ^ 0xFFFF) + 1

        if self._with_humidity:
            for i in range(0, 6):
                if calibration_h[i] & 0x8000:
                    calibration_h[i] = (-calibration_h[i] ^ 0xFFFF) + 1

        self.calibration_t = calibration_t
        self.calibration_h = calibration_h
        self.calibration_p = calibration_p

    def _take_forced_measurement(self):
        """
        In forced mode, the BME sensor goes back to sleep after each
        measurement and we need to set it to forced mode once at this point,
        so it will take the next measurement and then return to sleep again.
        In normal mode simply does new measurements periodically.
        """
        # set to forced mode, i.e. "take next measurement"
        self._bus.write_byte_data(self._i2c_add, 0xF4, self.ctrl_meas_reg)
        while self._bus.read_byte_data(self._i2c_add, 0xF3) & 0x08:
            asyncio.sleep(0.005)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, first_reading=False):
        """Read raw data and update compensated variables."""
        try:
            if first_reading:
                self._bus.write_byte_data(self._i2c_add, 0xF2, self.ctrl_hum_reg)
                self._bus.write_byte_data(self._i2c_add, 0xF5, self.config_reg)
                self._bus.write_byte_data(self._i2c_add, 0xF4, self.ctrl_meas_reg)
                self._populate_calibration_data()

            if self.mode == 2:  # MODE_FORCED
                self._take_forced_measurement()

            data = []
            for i in range(0xF7, 0xF7 + 8):
                data.append(self._bus.read_byte_data(self._i2c_add, i))
        except OSError as exc:
            _LOGGER.warning("Bad update: %s", exc)
            return

        pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        hum_raw = (data[6] << 8) | data[7]

        self._temperature = self._compensate_temperature(temp_raw)
        if self._with_humidity:
            self._humidity = self._compensate_humidity(hum_raw)
        if self._with_pressure:
            self._pressure = self._compensate_pressure(pres_raw)

    @property
    def temperature(self):
        """Return temperature in celsius."""
        return self._temperature

    @property
    def humidity(self):
        """Return relative humidity in percentage."""
        return self._humidity

    @property
    def pressure(self):
        """Return pressure in hPa."""
        return self._pressure


class BME280Sensor(Entity):
    """Implementation of the BME280 sensor."""

    def __init__(self, bme280_client, sensor_type, temp_unit, name):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.bme280_client = bme280_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from the BME280 and update the states."""
        self.bme280_client.update()
        if self.type == SENSOR_TEMPERATURE and self.bme280_client.temperature:
            temperature = round(self.bme280_client.temperature, 2)
            if (temperature >= -20) and (temperature < 80):
                self._state = temperature
                if self.temp_unit == TEMP_FAHRENHEIT:
                    self._state = round(celsius_to_fahrenheit(temperature), 1)
        elif self.type == SENSOR_HUMIDITY and self.bme280_client.humidity:
            humidity = round(self.bme280_client.humidity, 2)
            if (humidity >= 0) and (humidity <= 100):
                self._state = humidity
        elif self.type == SENSOR_PRESSURE and self.bme280_client.pressure:
            pressure = round(self.bme280_client.pressure, 2)
            self._state = pressure
        else:
            _LOGGER.warning("Bad Update of sensor.%s_%s", self.name, self.type)
