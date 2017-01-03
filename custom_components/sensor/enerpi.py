# -*- coding: utf-8 -*-
"""
    # Home Assistant Custom Component supportting enerPI sensors running enerpi + enerpiweb in some local host.

    Derived from the general REST sensor (https://home-assistant.io/components/sensor.rest/), it connects via GET
    requests to the local working enerpi web server and populates new hass sensors, which are updated through
    a single request.

    In addition, it generates local PNG files from the remote SVG tiles with the last 24 hours evolution of each sensor,
    which can be used as 'local_file' hass cameras to show color plots in Home Assistant frontend.
    (in a too-twisted way that depends on the cairosvg library)

    It's a very simple, and very bad (imho), way to integrate enerpi in Hass, until I learn to create an html component
    that can integrate the streaming values (with sse) and the svg background mosaics...

    The setup does a few things:
    - First, it gets the enerpi sensor configuration at 'http://ENERPI_IP/enerpi/api/filedownload/sensors'.
    - Then, it generates the first local PNG files, requesting the remote SVG tiles, with urls like:
        'http://ENERPI_IP/enerpi/static/img/generated/tile_enerpi_data_{sensor_name}_last_24h.svg'
        Sets absolute size and color background (no css here) in the svg content, and renders it in PNG with cairosvg.
    - Finally, it extracts the last produced sensor data at 'http://ENERPI_IP/enerpi/api/last' and populates new
    sensors with the defined 'monitored_variables' or with all sensors in the enerpiweb server.

    ## YAML HASS configuration:

    * On configuration.yaml (or where it is needed):

        sensor:
          - platform: enerpi
            name: enerPI rpi2
            host: 192.168.1.44
            port: 80
            prefix: enerpi
            scan_interval: 5
            data_refresh: 5
            pngtiles_refresh: 600
            monitored_variables:
              - power_1
              - power_2
              - ldr
              - ref

    Only the 'host' variable is required. To establish the scanning frequency for getting enerpi state, use the
    variables 'data_refresh' & 'pngtiles_refresh', in seconds. 'data_refresh' has to be higher or equal than
    HA 'scan_interval' to function properly, because the trigger for request data is inside the HA update function.

    * For the tiles representation as local_file cameras:

        camera:
          - platform: local_file
            name: enerpi_rpi3_power_1
            file_path: /path/to/homeassistant/config/custom_components/sensor/enerpi_rpi3_power_1_tile_24h.png

          - platform: local_file
            name: enerpi_rpi3_power_2
            file_path: /path/to/homeassistant/config/custom_components/sensor/enerpi_rpi3_power_2_tile_24h.png

          - platform: local_file
            name: enerpi_rpi3_ldr
            file_path: /path/to/homeassistant/config/custom_components/sensor/enerpi_rpi3_ldr_tile_24h.png

    (you can access this info in the HASS log, when enerpi loads)

    * For customize friendly names and icons, in customize.yaml or where applicable:

        sensor.enerpi_rpi3_power_1:
          icon: mdi:flash
          friendly_name: Main power
        camera.enerpi_rpi3_power_1:
          friendly_name: Main power evolution
        sensor.enerpi_rpi3_power_2:
          icon: mdi:power-plug
          friendly_name: Kitchen appliances
        sensor.enerpi_rpi3_ldr:
          icon: mdi:lightbulb-on
          friendly_name: Hall illuminance
        camera.enerpi_rpi3_ldr:
          friendly_name: Hall illuminance evolution

    * For automating an alert when main power goes over a custom limit and when it downs to a save level again:
    This is done with 2 input_slider's (for customizing the upper & lower limit of main power) and 2 input_booleans,
    one for toggle on/off this control, and the other for saving the 'enerpi alarm state'.
    You can define your desired 'hysteresis' setting the minimum delay for activate or deactivate the alarm state.

        input_boolean:
          - switch_control_enerpi_max_power:
            initial: on
          - state_enerpi_alarm_max_power:
            initial: off

        input_slider:
          - enerpi_max_power:
            initial: 3.5
            min: 1.0
            max: 6.0
            step: 0.25
          - enerpi_max_power_reset:
            initial: 2.5
            min: 1.0
            max: 6.0
            step: 0.25

        automation:
        - alias: Maxpower
          trigger:
            platform: template
            value_template: >
            {%if (states('sensor.enerpi_rpi3_power')|float / 1000 > states.input_slider.enerpi_max_power.state|float)%}
            true{% else %}false{% endif %}

          condition:
            condition: and
            conditions:
              - condition: state
                entity_id: input_boolean.switch_control_enerpi_max_power
                state: 'on'
              - condition: state
                entity_id: input_boolean.state_enerpi_alarm_max_power
                state: 'off'
                for:
                  seconds: 30
          action:
          - service: homeassistant.turn_on
            entity_id: input_boolean.state_enerpi_alarm_max_power
          - service: notify.ios
            data_template:
              title: "Alto consumo eléctrico!"
              message: "Potencia actual demasiado alta: {{ states.sensor.enerpi_rpi3_power.state }} W."
              data:
                push:
                  badge: '{{ states.sensor.enerpi_rpi3_power.state }}'
                  sound: "US-EN-Morgan-Freeman-Vacate-The-Premises.wav"
                  category: "ALARM"

        - alias: MaxpowerOff
          trigger:
            platform: template
            value_template: >
                {{states('sensor.enerpi_rpi3_power')|float/1000<states.input_slider.enerpi_max_power_reset.state|float}}

          condition:
            condition: and
            conditions:
              - condition: state
                entity_id: input_boolean.switch_control_enerpi_max_power
                state: 'on'
              - condition: state
                entity_id: input_boolean.state_enerpi_alarm_max_power
                state: 'on'
                for:
                  minutes: 1
          action:
          - service: homeassistant.turn_off
            entity_id: input_boolean.state_enerpi_alarm_max_power
          - service: notify.ios
            data_template:
              title: "Consumo eléctrico: Normal"
              message: "Potencia eléctrica actual: {{ states.sensor.enerpi_rpi3_power.state }} W."

    * For grouping it all in a tab view:

        group:
          - enerpi_rpi3:
              - sensor.enerpi_rpi3_power
              - camera.enerpi_rpi3_power
              - sensor.enerpi_rpi3_ldr
              - camera.enerpi_rpi3_ldr
              - sensor.enerpi_rpi3_noise
              - camera.enerpi_rpi3_noise
              - sensor.enerpi_rpi3_ref
              - camera.enerpi_rpi3_ref

          - enerpi_rpi2:
              - sensor.enerpi_rpi2_power_1
              - camera.enerpi_rpi2_power_1
              - sensor.enerpi_rpi2_power_2
              - camera.enerpi_rpi2_power_2
              - sensor.enerpi_rpi2_ldr
              - camera.enerpi_rpi2_ldr

          - enerPI Max Power Control:
              - input_boolean.switch_control_enerpi_max_power
              - input_slider.enerpi_max_power
              - input_slider.enerpi_max_power_reset
              - input_boolean.state_enerpi_alarm_max_power

          - enerpi_view:
              name: enerPI
              icon: mdi:flash
              view: yes
              entities:
                - group.enerpi_rpi3
                - group.enerpi_max_power_control
                - group.enerpi_rpi2

    * For seeing the logs (debug | info | error | ...):

        logger:
          logs:
            custom_components.enerpi: debug

    ------

    Enerpiweb streamed data example:
    {
      "host": "rpi3",
      "ldr": 0.1637,
      "msg": "{\"host\": \"rpi3\", \"power\": 439, \"ref\": 647, \"ldr\": 0.1637, \"ref_n\": 21,
                \"ts\": \"2016-12-09 13:41:23.954988\", \"noise\": 0.0022}",
      "noise": 0.0022,
      "power": 439,
      "ref": 647,
      "ref_n": 21,
      "ts": "2016-12-09 13:41:23.95"
    }

"""
import asyncio
import cairosvg
import datetime as dt
import logging
from lxml.etree import XMLSyntaxError
import os
import re
import requests
from time import time
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (STATE_UNKNOWN, CONF_HOST, CONF_PORT, CONF_PREFIX, CONF_NAME,
                                 CONF_MONITORED_VARIABLES, CONF_METHOD, CONF_PAYLOAD, CONF_HEADERS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify


REQUIREMENTS = ['cairosvg>=1.0.22']


URL_SENSORS_MASK = 'http://{}:{}/{}/api/filedownload/sensors'
URL_DATA_MASK = 'http://{}:{}/{}/api/last'
URL_TILE_MASK = 'http://{}:{}/{}/static/img/generated/tile_enerpi_data_{}_last_24h.svg'
CONF_DPI = 'dpi'
CONF_DATA_REFRESH = 'data_refresh'
CONF_PNGTILES_REFRESH = 'pngtiles_refresh'


ICON = 'mdi:flash'
DEFAULT_PORT = 80
DEFAULT_PREFIX = 'enerpi'
DEFAULT_NAME = 'enerPI REST Sensor'
DEFAULT_METHOD = 'GET'
DEFAULT_DPI = 300
DEFAULT_DATA_REFRESH = 5
DEFAULT_PNGTILES_REFRESH = 300

KEY_TIMESTAMP = 'ts'
KEY_HOST = 'host'
KEY_RAW_MSG = 'msg'
KEYS_REQUIRED_MSG = [KEY_TIMESTAMP, KEY_HOST, KEY_RAW_MSG]

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=['all']): cv.ensure_list,
    vol.Optional(CONF_DPI, default=DEFAULT_DPI): cv.positive_int,
    vol.Optional(CONF_DATA_REFRESH, default=DEFAULT_DATA_REFRESH): cv.positive_int,
    vol.Optional(CONF_PNGTILES_REFRESH, default=DEFAULT_PNGTILES_REFRESH): cv.positive_int,

    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,

    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HEADERS): {cv.string: cv.string},
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD): vol.In(['POST', 'GET']),
    vol.Optional(CONF_PAYLOAD): cv.string
})


##########################################
# ENERPI TILES: REMOTE SVG TO LOCAL PNG:
##########################################
def _make_tile_abs_size_and_background(svg_content, color_1='#8C27D3', color_2='#BFA0F5', opacity=0.8):
    rg_dimensions = re.compile('viewBox="0 0 (\d{2,4}) (\d{2,4})" ')
    rg_w = re.compile('width="(\d{1,3}%)" preserveAspectRatio="none"')
    rg_h = re.compile('svg height="(\d{1,3}%)" ')
    id_g = 'custom_grad_bg'
    tile_gradient = '''<radialGradient id="{}" gradientUnits="userSpaceOnUse" cx="70%" cy="70%" r="100%">
    <stop stop-color="{}" offset="0"/><stop stop-color="{}" offset="1"/></radialGradient>'''.format(id_g, color_1,
                                                                                                    color_2)
    width, height = rg_dimensions.findall(svg_content)[0]
    svg_content_abs = rg_h.sub('svg height="{}pt" '.format(height),
                               rg_w.sub('width="{}pt"'.format(width), svg_content, count=1),
                               count=1)
    idx_insert_g = svg_content_abs.find('<defs>\n')
    return re.sub('style="fill:none;opacity:0;"',
                  'style="fill:url(#{});opacity:{};"'.format(id_g, opacity),
                  svg_content_abs[:idx_insert_g + 8] + tile_gradient + svg_content_abs[idx_insert_g + 8:],
                  count=1)


def _extract_sensor_params(sensor):
    c1 = '#' + ''.join(map('{:02x}'.format, sensor['tile_gradient_st'][:3]))
    c2 = '#' + ''.join(map('{:02x}'.format, sensor['tile_gradient_end'][:3]))
    return sensor['name'], sensor['description'], sensor['unit'], sensor['is_rms'], c1, c2


def _get_remote_tile_svg_and_transform(enerpi_name, host, port, prefix, sensor):
    name, desc, unit, is_rms, c1, c2 = _extract_sensor_params(sensor)
    url_tile_s = URL_TILE_MASK.format(host, port, prefix, name)
    svg_content_s = requests.get(url_tile_s).content.decode()
    new_svg_content_s = _make_tile_abs_size_and_background(svg_content_s, c1, c2)
    filename = '{}_{}_tile_24h.png'.format(enerpi_name, name)
    return new_svg_content_s, name, filename


def _png_tile_export(svg_content_bytes, filename, filepathbase, dpi=300):
    png_file = os.path.join(filepathbase, filename)
    # *** Not working in RPI !?? ***
    # cairosvg.svg2png(svg_content_bytes, write_to=png_file, dpi=dpi)
    local_svg = png_file[:-3] + 'svg'
    with open(local_svg, 'wb') as f:
        f.write(svg_content_bytes)
    try:
        # noinspection PyUnresolvedReferences
        cairosvg.svg2png(url=local_svg, write_to=png_file, dpi=dpi)
        return True, png_file
    except XMLSyntaxError as e:
        _LOGGER.error('PNG_TILE ({}) -> Export error: {}'.format(filename, e))
        return False, e


def _generate_local_png_tile(enerpi_name, host, port, prefix, sensor, filepathbase, dpi=300):
    svg_content, sensor_name, filename = _get_remote_tile_svg_and_transform(enerpi_name, host, port, prefix, sensor)
    _LOGGER.debug('LOCAL_PNG for {} --> {} => {}'.format(sensor_name, filename, svg_content[:300]))
    ok_export, png_file = _png_tile_export(svg_content.encode(), filename, filepathbase, dpi)
    if ok_export:
        mask_lf_cam = '  - platform: local_file\n    name: {}\n    file_path: {}'
        return png_file, mask_lf_cam.format('{}_{}'.format(enerpi_name, sensor_name).lower(), png_file)


##########################################
# ENERPI PLATFORM:
##########################################
# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the ENERPI sensor."""

    name = slugify(config.get(CONF_NAME))
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    prefix = config.get(CONF_PREFIX)
    dpi = config.get(CONF_DPI)
    data_refresh = config.get(CONF_DATA_REFRESH)
    pngs_refresh = config.get(CONF_PNGTILES_REFRESH)

    payload = config.get(CONF_PAYLOAD)
    method = config.get(CONF_METHOD)
    headers = config.get(CONF_HEADERS)
    auth = None

    # Get ENERPI Data
    rest = EnerpiRestJSONData(hass, name, host, port, prefix, dpi, data_refresh, pngs_refresh,
                              headers, payload, method=method, auth=auth, verify_ssl=False)
    rest.update()
    if rest.data is None:
        _LOGGER.error('Unable to fetch enerPI REST data')
        return False
    elif not all([k in rest.data for k in KEYS_REQUIRED_MSG]):
        _LOGGER.error('enerPI BAD DATA fetched --> {}'.format(rest.data))
        return False

    # Get timestamp & host name from last update:
    all_sensors_data = rest.data.copy()
    enerpi_remote_host = all_sensors_data.pop(KEY_HOST)
    _ = all_sensors_data.pop(KEY_TIMESTAMP)
    _ = all_sensors_data.pop(KEY_RAW_MSG)

    # Create devices:
    devices = []
    d_sensors = {s['name']: s for s in rest.sensors_conf}
    monitored_sensors = config.get(CONF_MONITORED_VARIABLES)

    if (len(monitored_sensors) == 1) and (monitored_sensors[0] == 'all'):
        sensors_append = list(d_sensors.keys())
    else:
        # present_sensors = list(filter(lambda x: not x.startswith('ref'), all_sensors_data.keys()))
        sensors_append = monitored_sensors
    for sensor_key in sensors_append:
        if sensor_key not in d_sensors.keys():
            if sensor_key in all_sensors_data.keys():  # ref sensor
                devices.append(EnerpiRestSensor(rest, enerpi_remote_host, name, sensor_key, '', True))
            else:
                _LOGGER.error("Sensor type: {} does not exist in {}".format(sensor_key, d_sensors.keys()))
        else:
            unit = d_sensors[sensor_key]['unit']
            is_rms = d_sensors[sensor_key]['is_rms']
            devices.append(EnerpiRestSensor(rest, enerpi_remote_host, name, sensor_key, unit, is_rms))

    _LOGGER.info('enerPI platform "{}" loaded:\n * {}'
                 .format(name, '\n * '.join([str(d) for d in devices])))
    yield from async_add_devices(devices)


class EnerpiRestSensor(Entity):
    """Implementation of a REST sensor."""

    def __init__(self, rest, host, name_base, sensor_key, unit_of_measurement, is_rms):
        """Initialize the REST sensor."""
        self.rest = rest
        self._state = STATE_UNKNOWN
        self._name = '{}_{}'.format(name_base, sensor_key)
        self._key = sensor_key
        self._unit = unit_of_measurement
        self._is_rms = is_rms
        self._host = host
        self.async_update()

    def __repr__(self):
        """Enerpi sensor representation."""
        return '<ENERPI SENSOR {} in {}. Last value: {} [{}]>'.format(self._name, self._host, self._state, self._unit)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit

    @property
    def state(self):
        """Return the main state of the device."""
        # _LOGGER.debug('({:%d-%b %H:%M:%S}) DEBUG ENERPI STATE: {} {}; ({})'
        #               .format(dt.datetime.now(), self._state, self._unit, self._name))
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes of the sensor (--> of the platform)."""
        data = self.rest.state_attributes.copy()
        extra = {}
        try:
            extra['ts'] = data['ts']
            if self._is_rms:
                extra['ref'] = data['ref']
            else:
                extra['ref'] = data['ref_n']
        except KeyError:
            pass
        return extra

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from REST API and update the state."""
        self.rest.update()
        value = self.rest.data
        if value is None:
            self._state = STATE_UNKNOWN
        else:
            self._state = value[self._key]
            if not self._is_rms:
                self._state = round(self._state * 100, 2)


class EnerpiRestJSONData(object):
    """Class for handling the ENERPI data retrieval."""

    def __init__(self, hass, name, host, port, prefix, dpi, data_refresh, pngs_refresh,
                 headers, data, auth=None, verify_ssl=False, method='GET'):
        """Initialize the data object."""
        self.hass = hass
        self._name = name
        self._host = host
        self._port = port
        self._prefix = '' if not prefix else '/{}'.format(prefix)
        self._url = URL_DATA_MASK.format(self._host, self._port, self._prefix)
        self._request = requests.Request(method, self._url, headers=headers, auth=auth, data=data).prepare()
        self._verify_ssl = verify_ssl

        # Sensors data & config
        self.data = None
        self.sensors_conf = []

        # Local PNG conf
        self._png_dpi = dpi
        self._filepathbase = os.path.dirname(os.path.abspath(__file__))
        self._png_filepaths = []
        self.config_info_local_file_cameras = ''

        # Refresh config:
        self._refresh_interval = data_refresh
        self._refresh_interval_pngtiles = pngs_refresh
        self._tic = time()
        self._tic_pngtiles = self._tic

        # Get sensors config:
        req_conf = requests.get(URL_SENSORS_MASK.format(host, port, prefix))
        if req_conf.ok:
            self.sensors_conf = req_conf.json()

        # All remote tiles to local png's
        self.hass.async_add_job(self.async_update_local_png_tiles(True))

    @asyncio.coroutine
    def async_update_local_png_tiles(self, is_first_gen=False):
        """Re-generates LOCAL PNG Files from enerpi remote SVG tiles."""
        tic = time()
        png_gen_out = [_generate_local_png_tile(self._name, self._host, self._port, self._prefix, s,
                                                self._filepathbase, dpi=self._png_dpi) for s in self.sensors_conf]
        self._png_filepaths = list(zip(*png_gen_out))[0]
        self.config_info_local_file_cameras = 'camera:\n' + '\n'.join(list(zip(*png_gen_out))[1])
        toc = time()
        if self._png_filepaths:
            basep = os.path.dirname(self._png_filepaths[0])
            names = [p.replace(basep, '') for p in self._png_filepaths]
            _LOGGER.debug('({:%d-%b %H:%M:%S}) ENERPI: {} PNGs generated. TOOK {:.2f} sec'
                          .format(dt.datetime.now(), len(names), toc - tic))
        else:
            _LOGGER.error('NO PNG local tiles generation ?! Sensor conf is: {}'.format(self.sensors_conf))
        if toc - tic < self._refresh_interval_pngtiles / 10:
            self._tic_pngtiles = tic
        else:
            self._tic_pngtiles = toc
        if is_first_gen:
            _LOGGER.info('ENERPI png tiles with local_file cameras: --> cameras.yaml config:\n{}'
                         .format(self.config_info_local_file_cameras))

    def update(self):
        """Get the latest data from REST service with provided method."""
        tic = time()
        if (self.data is None) or (tic - self._tic + .1 > self._refresh_interval):
            try:
                with requests.Session() as session:
                    response = session.send(self._request, timeout=10, verify=self._verify_ssl)
                self.data = response.json()
                toc = time()
                if toc - tic < self._refresh_interval / 4:
                    self._tic = tic
                else:
                    self._tic = toc
                _LOGGER.debug('({:%d-%b %H:%M:%S}) ENERPI REQ. DATA. TS={}'.format(dt.datetime.now(), self.data['ts']))
                if toc - self._tic_pngtiles + .1 > self._refresh_interval_pngtiles:
                    self.hass.async_add_job(self.async_update_local_png_tiles())
            except requests.exceptions.RequestException:
                _LOGGER.error("Error fetching data: %s", self._request)
                self.data = None

    @property
    def state_attributes(self):
        """Return the state attributes of the platform."""
        if self.data is None:
            return {}
        data = self.data.copy()
        try:
            data.pop(KEY_RAW_MSG)
        except KeyError:
            _LOGGER.error('Not "{}" key in enerpi_data! --> {}'.format(KEY_RAW_MSG, self.data))
        return data
