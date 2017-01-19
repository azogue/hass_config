# -*- coding: utf-8 -*-
"""
# Home Assistant Custom Component supporting [enerPI sensors](https://github.com/azogue/enerpi)
running *enerpi* + *enerpiweb* in some local host.

Derived from the general REST sensor (https://home-assistant.io/components/sensor.rest/), it connects via GET requests
to the local working enerpi web server and populates new hass sensors, which are updated through a single conexion to
the enerPI real-time stream.
In addition, it generates local PNG files from the remote SVG tiles with the last 24 hours evolution of each sensor,
which can be used as `local_file` hass cameras to show color plots in Home Assistant frontend. (in a too-twisted way
that depends on the cairosvg library).
These special `local_file` cameras refresh are updated every `pngtiles_refresh` seconds.
It's a very simple, and very bad (imho), way to integrate enerpi in Hass, until I learn to create an html component
that can integrate the svg background mosaics...

The setup does a few things:
- First, it gets the enerpi sensor configuration at `http://ENERPI_IP/enerpi/api/filedownload/sensors`.
- With the existent enerpi sensor config, it extracts the last produced sensor data at
  `http://ENERPI_IP/enerpi/api/last` and populates new sensors with the defined `monitored_variables` or
  with all sensors in the enerpiweb server.
- Also, it creates 2 input_slider's and one input_boolean for automating an alert when main power goes over a
  custom limit and when it downs to a safe level again.
- Then, it generates the first local PNG files, requesting the remote SVG tiles, with urls like:
    `http://ENERPI_IP/enerpi/static/img/generated/tile_enerpi_data_{sensor_name}_last_24h.svg`
  Sets absolute size and color background (no css here) in the svg content, and renders it in PNG with cairosvg.
- Finally, it extracts the last produced sensor data at `http://ENERPI_IP/enerpi/api/last` and populates new sensors
  with the defined `monitored_variables` or with all sensors in the enerpiweb server.

### Requirements

Since converting SVG to PNG requires the **`cairosvg`** library, you will probably need to install the following:
```
apt-get install python3-dev python3-lxml python3-cffi libffi-dev libxml2-dev libxslt-dev libcairo2-dev
pip3 install cairosvg
```

### YAML HASS configuration:

* On configuration.yaml:
```
enerpi:
  enerpi_rpi3:
    host: 192.168.1.44
    name: enerPI
    scan_interval: 10
    monitored_variables:
      - power
      - ldr
    pngtiles_refresh: 300
    dpi: 200
```
Only the `host` variable is required. To establish the frequency for updating the enerpi state, use the variable
`scan_interval`, and for the enerPI tiles, user `pngtiles_refresh`, both variables in seconds.

* For customize friendly names and icons, in `customize.yaml or where applicable:
```
sensor.enerpi_power:
  icon: mdi:flash
  friendly_name: Main power
camera.enerpi_power:
  friendly_name: Main power (24h)
sensor.enerpi_ldr:
  icon: mdi:lightbulb
  friendly_name: Hall illuminance
camera.enerpi_ldr:
  friendly_name: Hall illuminance (24h)
```

* For automating an alert when main power goes over a custom limit and when it downs to a safe level again.
This is done with 2 `input_slider`'s (for dynamic customization of the upper & lower limit for the main power variable
to control) and 2 `input_booleans`, one for toggle on/off this control, and the other for saving the
`enerpi alarm state`.
You can define your desired *hysteresis* setting the minimum delay for activating or deactivating the alarm state.
```
automation:
- alias: Maxpower
  trigger:
    platform: template
    value_template: >
    {%if (states('sensor.enerpi_power')|float / 1000 > states.input_slider.enerpi_max_power.state|float)%}
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
      message: "Potencia actual demasiado alta: {{ states.sensor.enerpi_power.state }} W."
      data:
        push:
          badge: '{{ states.sensor.enerpi_power.state }}'
          sound: "US-EN-Morgan-Freeman-Vacate-The-Premises.wav"
          category: "ALARM"

- alias: MaxpowerOff
  trigger:
    platform: template
    value_template: >
        {{states('sensor.enerpi_power')|float/1000<states.input_slider.enerpi_max_power_reset.state|float}}

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
      message: "Potencia eléctrica actual: {{ states.sensor.enerpi_power.state }} W."
```

* For grouping it all in a tab view (`groups.yaml`):
```
enerPI:
  - sensor.enerpi
  - sensor.enerpi_power
  - sensor.enerpi_ldr
  - camera.enerpi_tile_power
  - camera.enerpi_tile_ldr

enerPI Max Power Control:
  - input_boolean.switch_control_enerpi_max_power
  - input_slider.enerpi_max_power
  - input_slider.enerpi_max_power_reset

enerpi_view:
  name: enerPI
  icon: mdi:flash
  view: yes
  entities:
    - sensor.enerpi
    - group.enerpi
    - group.enerpi_max_power_control
```

* For customize the logging level (debug | info | error | ...):
```
logger:
  logs:
    custom_components.enerpi: debug
```
"""
import asyncio
from collections import deque, OrderedDict
import datetime as dt
from dateutil.parser import parse
from json import loads
import logging
import os
import re
import requests
from time import time
import voluptuous as vol
from homeassistant.const import (STATE_UNKNOWN, STATE_ON, CONF_HOST, CONF_PORT, CONF_PREFIX, CONF_NAME,
                                 CONF_SCAN_INTERVAL, CONF_MONITORED_VARIABLES, CONF_DEVICES)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.camera.local_file import LocalFile
from homeassistant.helpers.entity import Entity
from homeassistant.util import slugify, utcnow
from homeassistant.components.discovery import load_platform


REQUIREMENTS = ['cairosvg>=1.0.22']
DEPENDENCIES = ['sensor', 'camera']

ICON = 'mdi:flash'
DOMAIN = 'enerpi'

# enerpi web api routes:
URL_SENSORS_MASK = 'http://{}:{}/{}/api/filedownload/sensors'
URL_CONSUMPTION_LASTWEEK = 'http://{}:{}/{}/api/consumption/from/{:%Y-%m-%d}?daily=true&round=1'
URL_STREAM_MASK = 'http://{}:{}/{}/api/stream/realtime'
URL_DATA_MASK = 'http://{}:{}/{}/api/last'
URL_TILE_MASK = 'http://{}:{}/{}/static/img/generated/tile_enerpi_data_{}_last_24h.svg'

CONF_DPI = 'dpi'
CONF_PNGTILES_REFRESH = 'pngtiles_refresh'

CONF_TILE_CAMERAS = "tile_cameras"
CONF_TILES_DPI = "tiles_dpi"
CONF_TILES_PNGS_REFRESH = "tiles_pngs_refresh"
CONF_MAIN_POWER = "main_power"
CONF_TILE_EXTENSION = "png"
CONF_DELTA_REFRESH = "delta_refresh"
CONF_LASTWEEK = "consumption_last_week"

DEFAULT_PORT = 80
DEFAULT_PREFIX = 'enerpi'
DEFAULT_NAME = 'enerPI'
DEFAULT_DPI = 300
DEFAULT_DATA_REFRESH = 10
DEFAULT_PNGTILES_REFRESH = 600
DEFAULT_MIN_DELTA_W_CHANGE = 50

KEY_TIMESTAMP = "ts"
KEYS_REQUIRED_MSG = [KEY_TIMESTAMP, "host", "msg"]

LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        cv.slug: vol.All({
            vol.Required(CONF_HOST): cv.string,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
            vol.Optional(CONF_PREFIX, default=DEFAULT_PREFIX): cv.string,
            vol.Optional(CONF_MONITORED_VARIABLES, default=['all']): cv.ensure_list,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_DATA_REFRESH): cv.positive_int,
            vol.Optional(CONF_DELTA_REFRESH, default=DEFAULT_MIN_DELTA_W_CHANGE): cv.positive_int,
            vol.Optional(CONF_PNGTILES_REFRESH, default=DEFAULT_PNGTILES_REFRESH): cv.positive_int,
            vol.Optional(CONF_DPI, default=DEFAULT_DPI): cv.positive_int
        })
    })
}, required=True, extra=vol.ALLOW_EXTRA)

# Entity ids for max power control:
MPC_BOOL_SWITCH = 'input_boolean.switch_control_enerpi_max_power'
MPC_SLIDER_MAX = 'input_slider.enerpi_max_power'
MPC_SLIDER_MIN = 'input_slider.enerpi_max_power_reset'
MPC_GROUP = 'group.enerpi_max_power_control'


##########################################
# ENERPI JSON DATA: LAST DATA & CONFIG:
##########################################
def get_last_data_request(host, port=DEFAULT_PORT, prefix=DEFAULT_PREFIX, retries=5):
    """Get the latest data from enerPI Platform."""
    url = URL_DATA_MASK.format(host, port, prefix)
    data, retry = None, 0
    while retry < retries:
        try:
            r = requests.get(url, timeout=30)
            if r.ok:
                return r.json()
        except requests.exceptions.RequestException:
            LOGGER.error("Error fetching data in: {}".format(url))
        retry += 1
        asyncio.sleep(5)
    return None


##########################################
# ENERPI TILES: REMOTE SVG TO LOCAL PNG:
##########################################
def _make_tile_abs_size_and_background(svg_content, col1='#8C27D3', col2='#BFA0F5', opacity=0.8):
    """Transform SVG from relative to absolute size, and append radial gradient color in background."""
    rg_dimensions = re.compile('viewBox="0 0 (\d{2,4}) (\d{2,4})" ')
    rg_w = re.compile('width="(\d{1,3}%)" preserveAspectRatio="none"')
    rg_h = re.compile('svg height="(\d{1,3}%)" ')
    id_g = 'custom_grad_bg'
    tile_gradient = '''<radialGradient id="{}" gradientUnits="userSpaceOnUse" cx="70%" cy="70%" r="100%">
    <stop stop-color="{}" offset="0"/><stop stop-color="{}" offset="1"/></radialGradient>'''.format(id_g, col1, col2)
    try:
        width, height = rg_dimensions.findall(svg_content)[0]
    except IndexError:
        LOGGER.error("Can't get dimensions of SVG. is correct? {}".format(svg_content))
        return svg_content
    svg_content_abs = rg_h.sub('svg height="{}pt" '.format(height),
                               rg_w.sub('width="{}pt"'.format(width), svg_content, count=1),
                               count=1)
    idx_insert_g = svg_content_abs.find('<defs>\n')
    return re.sub('style="fill:none;opacity:0;"',
                  'style="fill:url(#{});opacity:{};"'.format(id_g, opacity),
                  svg_content_abs[:idx_insert_g + 8] + tile_gradient + svg_content_abs[idx_insert_g + 8:], count=1)


def _get_remote_tile_svg_and_transform(host, port, prefix, name, c1, c2):
    """Get remote SVG file and transform it before exporting to PNG."""
    r_svg = requests.get(URL_TILE_MASK.format(host, port, prefix, name))
    if r_svg.ok:
        svg_content_s = r_svg.content.decode()
        return _make_tile_abs_size_and_background(svg_content_s, c1, c2)
    LOGGER.error('TILE REQUEST ERROR: {}'.format(r_svg))
    return None


def _png_tile_export(svg_content_bytes, png_file, dpi=300):
    """Cairo PNG export from SVG."""
    import cairosvg
    from lxml.etree import XMLSyntaxError

    # *** Not working in RPI  as `cairosvg.svg2png(svg_content_bytes, write_to=png_file, dpi=dpi)` !?? ***
    local_svg = png_file[:-3] + 'svg'
    with open(local_svg, 'wb') as f:
        f.write(svg_content_bytes)
    try:
        # noinspection PyUnresolvedReferences
        cairosvg.svg2png(url=local_svg, write_to=png_file, dpi=dpi)
        return True
    except XMLSyntaxError as e:
        LOGGER.error('PNG_TILE ({}) -> Export error: {}'.format(png_file, e))
        return False


def _creation_local_png_tile(host, port, prefix, name, c1, c2, png_file, dpi=DEFAULT_DPI):
    """Creates local PNG version of remote SVG enerpi tile."""
    svg_content = _get_remote_tile_svg_and_transform(host, port, prefix, name, c1, c2)
    if svg_content is not None:
        return _png_tile_export(svg_content.encode(), png_file, dpi)
    return False


def _extract_sensor_params(sensor):
    """Extract enerpi sensors info, including background colors from rgb to hex."""
    c1 = '#' + ''.join(map('{:02x}'.format, sensor['tile_gradient_st'][:3]))
    c2 = '#' + ''.join(map('{:02x}'.format, sensor['tile_gradient_end'][:3]))
    if 'mdi:icon' in sensor:
        icon = sensor['mdi:icon']
        LOGGER.info('MDI Icon detected: {} -> {}'.format(sensor['name'], icon))
    else:
        icon = sensor['icon']
        LOGGER.warn('MDI Icon not detected, using font-awesome icon (may be incompatible): {} -> {}'
                    .format(sensor['name'], icon))
    return sensor['name'], sensor['description'], sensor['unit'], sensor['is_rms'], icon, c1, c2


##########################################
# ENERPI PLATFORM:
##########################################
@asyncio.coroutine
def async_setup(hass, config_hosts):
    """Setup the enerPI Platform."""
    enerpi_config = {}
    for enerpi_name, config in config_hosts[DOMAIN].items():
        name = config.get(CONF_NAME, enerpi_name)
        clean_name = slugify(name)
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)
        prefix = config.get(CONF_PREFIX)
        monitored_sensors = config.get(CONF_MONITORED_VARIABLES)
        dpi = config.get(CONF_DPI)
        data_refresh = config.get(CONF_SCAN_INTERVAL)
        delta_refresh = config.get(CONF_DELTA_REFRESH)
        pngs_refresh = config.get(CONF_PNGTILES_REFRESH)

        # Get ENERPI Config & last data
        all_sensors_data = get_last_data_request(host, port, prefix, retries=10)
        if all_sensors_data is None:
            LOGGER.error('Unable to fetch enerPI REST data')
            # return False
        elif not all([k in all_sensors_data for k in KEYS_REQUIRED_MSG]):
            LOGGER.error('enerPI BAD DATA fetched --> {}'.format(all_sensors_data))
            # return False
        else:  # Drop aux vars from all_sensors_data:
            [all_sensors_data.pop(k) for k in KEYS_REQUIRED_MSG]

            # Filter enerpi sensors to add
            d_sensors = {}
            req_conf = requests.get(URL_SENSORS_MASK.format(host, port, prefix), timeout=30)
            if req_conf.ok:
                sensors_conf = req_conf.json()
                d_sensors = {s['name']: s for s in sensors_conf}
            if (len(monitored_sensors) == 1) and (monitored_sensors[0] == 'all'):
                sensors_append = list(d_sensors.keys())
            else:
                # present_sensors = list(filter(lambda x: not x.startswith('ref'), all_sensors_data.keys()))
                sensors_append = monitored_sensors

            # Get consumption of last week (to init that counter):
            start, consumption_kwh_week = dt.datetime.today().date() - dt.timedelta(days=7), None
            req_week = requests.get(URL_CONSUMPTION_LASTWEEK.format(host, port, prefix, start), timeout=30)
            if req_week.ok:
                data = req_week.json()
                consumption_kwh_week = [round(data[k], 1) for k in sorted(data.keys())]

            mask_png_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         'camera', '{}_{}_tile_24h.' + CONF_TILE_EXTENSION)
            main_power, devices_ids, tile_cameras = None, [], []
            for sensor_key in sensors_append:
                png_file = mask_png_file.format(clean_name, sensor_key)
                if (sensor_key in d_sensors.keys()) or (sensor_key in all_sensors_data.keys()):
                    if sensor_key not in d_sensors.keys():  # ref sensor
                        friendly_name, unit, is_rms, icon = sensor_key, '', True, 'numeric'
                        c1, c2 = '#FF2211', '#DDDDDD'
                    else:
                        sensor = d_sensors[sensor_key]
                        sensor_key, friendly_name, unit, is_rms, icon, c1, c2 = _extract_sensor_params(sensor)
                        if is_rms and main_power is None:
                            main_power = sensor_key
                    devices_ids.append(('{}.{}_{}'.format('sensor', clean_name, sensor_key),
                                        sensor_key, unit, is_rms, friendly_name, icon))
                    # Create empty local files
                    open(png_file, 'w').close()
                    tile_cameras.append(('{}_{}_{}'.format(clean_name, 'tile', sensor_key), png_file,
                                         sensor_key, friendly_name, unit, is_rms, c1, c2))
                else:
                    LOGGER.error("Sensor type: {} does not exist in {}".format(sensor_key, d_sensors.keys()))

            enerpi_config[clean_name] = {CONF_NAME: name, CONF_HOST: host, CONF_PORT: port, CONF_PREFIX: prefix,
                                         CONF_DEVICES: devices_ids,
                                         CONF_SCAN_INTERVAL: data_refresh, CONF_DELTA_REFRESH: delta_refresh,
                                         CONF_TILE_CAMERAS: tile_cameras, CONF_TILES_DPI: dpi,
                                         CONF_TILES_PNGS_REFRESH: pngs_refresh, CONF_MAIN_POWER: main_power,
                                         CONF_LASTWEEK: consumption_kwh_week}

    # Load platforms sensor & camera with the enerpi_config:
    if enerpi_config:
        load_platform(hass, 'sensor', DOMAIN, enerpi_config)
        load_platform(hass, 'camera', DOMAIN, enerpi_config)
        return True
    else:
        LOGGER.error('ENERPI PLATFORM NOT LOADED')
        return False


class EnerpiTileCam(LocalFile):
    """Custom LocalFile Camera for enerPI tiles as local PNG's"""

    def __init__(self, entity_name, file_path, host, enerpi_name, desc):
        """Initialize Local File Camera component."""
        super().__init__(entity_name, file_path)
        self._host = host
        self._enerpi = enerpi_name
        self._desc = desc

    @property
    def brand(self):
        """Camera brand."""
        return 'Enerpi TILE from {}'.format(self._host)

    @property
    def model(self):
        """Camera model."""
        return 'enerPI TILE camera {} ({})'.format(self._desc, self._host)

    @property
    def state_attributes(self):
        """Camera state attributes."""
        st_attrs = super().state_attributes
        st_attrs.update({"friendly_name": '{} ({})'.format(self._desc, self._enerpi)})
        return st_attrs


class EnerpiSensor(Entity):
    """Implementation of a EnerPI sensor."""

    def __init__(self, streamer, name=DEFAULT_NAME):
        """Initialize the EnerPI sensor."""
        self._streamer = streamer
        self._state = STATE_UNKNOWN
        self._name = name

    def __repr__(self):
        """Enerpi sensor representation."""
        return '<ENERPI SENSOR {}. Last state: {}>'.format(self._name, self._state)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Return False because the entity pushes its state to HA."""
        return False

    @property
    def state(self):
        """Return the main state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON


class EnerpiStreamer(object):
    """Class for handling the ENERPI data retrieval."""

    def __init__(self, hass, name, host, port, prefix, devices_ids, main_sensor, lastweek_consumption,
                 tile_cameras, dpi, data_refresh, delta_refresh, pngs_refresh, is_master_enerpi=True):
        """Initialize the data object."""
        self.hass = hass
        self._name = name
        self._entity_id = '{}.{}'.format('sensor', self._name)
        self._host = host
        self._port = port
        self._prefix = prefix
        self._url_stream = URL_STREAM_MASK.format(self._host, self._port, self._prefix)

        # Refresh config:
        self._refresh_interval = data_refresh
        self._refresh_delta = delta_refresh
        self._refresh_interval_pngtiles = pngs_refresh

        # Enerpi streaming data & stats:
        self.last_data = {}
        self._last_update = None
        self._last_state_ch = None
        self._period_mean = -1
        self._state = STATE_UNKNOWN
        self._main_key = main_sensor

        self._roll_mean_power_300 = deque([], 300)
        self._consumption_day = 0.

        if lastweek_consumption is None:
            lastweek_consumption = [0.] * 3
        LOGGER.info('lastweek_consumption: {}'.format(lastweek_consumption))
        self._consumption_week = deque(lastweek_consumption, 7)

        self._last_instant_power = 0
        self._peak = [0, utcnow()]

        # Set 'sub-states':
        self._attrs_devices = {}
        for entity_id, name, unit, is_rms, friendly_name, icon in devices_ids:
            attrs = {'icon': 'mdi:{}'.format(icon),
                     'friendly_name': friendly_name,
                     'unit_of_measurement': unit}
            self._attrs_devices[entity_id] = (name, attrs, is_rms)
            self.hass.states.async_set(entity_id, STATE_UNKNOWN, attributes=attrs, force_update=False)

        if is_master_enerpi:
            # enerPI inputs for Max Power control:
            switch_attrs = {"friendly_name": "enerPI - control de potencia",
                            "icon": "mdi:toggle-switch",
                            "homebridge_hidden": "true"}
            s1_attrs = switch_attrs.copy()
            s1_attrs["friendly_name"] = "Max Power(kW)"
            s1_attrs["icon"] = "mdi:flash-red-eye"
            s1_attrs["max"] = 6.0
            s1_attrs["min"] = 1.0
            s1_attrs["step"] = 0.25
            s2_attrs = s1_attrs.copy()
            s2_attrs["friendly_name"] = "Reset level(kW)"
            s2_attrs["icon"] = "mdi:flash-off"
            LOGGER.debug('{}: {}'.format(MPC_BOOL_SWITCH, switch_attrs))
            self.hass.states.async_set(MPC_BOOL_SWITCH, STATE_ON, attributes=switch_attrs, force_update=False)
            LOGGER.debug('{}: {}'.format(MPC_SLIDER_MAX, s1_attrs))
            self.hass.states.async_set(MPC_SLIDER_MAX, 4.0, attributes=s1_attrs, force_update=False)
            LOGGER.debug('{}: {}'.format(MPC_SLIDER_MIN, s2_attrs))
            self.hass.states.async_set(MPC_SLIDER_MIN, 2.0, attributes=s2_attrs, force_update=False)

        # TODO enerPI grouping:
        # entities = "sensor.{},".format(name)
        # entities += ",".join(self._attrs_devices.keys()) + ","
        # entities += ",".join(['camera.{}'.format(c[0]) for c in tile_cameras])
        # group_attrs = {"entity_id": entities, "friendly_name": name, "icon": ICON}
        # LOGGER.debug('group_attrs: {}'.format(group_attrs))
        # self.hass.states.async_set('group.{}'.format(name), STATE_ON, attributes=group_attrs, force_update=False)
        # LOGGER.info('ENERPI Sensors added. If you want to group or customize, the entities are: ** {} **'
        #             .format(', '.join([self._entity_id] + list(self._attrs_devices.keys()))))

        # LOGGER.debug('{}: {}'.format(MPC_GROUP, group_ctl_attrs))
        # group_ctl_attrs = {"entity_id": ",".join([MPC_BOOL_SWITCH, MPC_SLIDER_MAX, MPC_SLIDER_MIN]),
        #                    "friendly_name": '{} Max Power Control'.format(name)}
        # LOGGER.debug('{}: {}'.format(MPC_GROUP, group_ctl_attrs))
        # self.hass.states.async_set(MPC_GROUP, STATE_ON, attributes=group_ctl_attrs, force_update=False)

        # Local PNG conf
        self._sensors_tiles_conf = tile_cameras
        self._png_dpi = dpi
        self._last_tile_generation = None

        # Generate local png's from remote SVG Tiles (1ºst time)
        self.hass.async_add_job(self.async_update_local_png_tiles())

        # Start receiving stream:
        try:
            asyncio.ensure_future(self._generator_stream(), loop=self.hass.loop)
        except AttributeError:  # for python 3.4.2
            asyncio.async(self._generator_stream(), loop=self.hass.loop)

    @property
    def enerpi_state_attributes(self):
        """Return the state attributes of the platform."""
        data = self.last_data.copy()
        extra = OrderedDict()
        extra['icon'] = ICON
        extra['friendly_name'] = 'Power State'
        try:
            extra['Last Main Power (W)'] = data[self._main_key]
            list_values = list(self._roll_mean_power_300)
            extra['Power 1min (W)'] = round(sum(list_values[-60:]) / len(list_values[-60:]), 0)
            extra['Power 5min (W)'] = round(sum(list_values) / len(list_values), 0)
            extra['Consumption Day (Wh)'] = round(self._consumption_day, 3)
            # extra['Consumption_week_kWh'] = np.round(np.sum(self._consumption_week) / 1000., 3)
            extra['Consumption Week (kWh)'] = ','.join([str(round(c / 1000, 1)) for c in self._consumption_week])
            for entity_id, (name, attrs, is_rms) in self._attrs_devices.items():
                name_use = '# raw samples' if (name == "ref") else name.upper()
                if is_rms and name != self._main_key:
                    extra[name_use] = round(data[name], 1)
                elif not is_rms:
                    extra[name_use] = round(100 * data[name], 1)
            extra['Power Peak (today)'] = self._peak[0]
            extra['last_update'] = data[KEY_TIMESTAMP]
        except KeyError as e:
            LOGGER.error('KeyError in state_attrs de {} --> {}'.format(self._name, e))
            return None
        return extra

    @asyncio.coroutine
    def _generator_stream(self):
        counter_samples = 0
        while True:
            LOGGER.debug('Starting enerPI stream receiver')
            try:
                for l in requests.get(self._url_stream, stream=True, timeout=60).iter_lines():
                    if l:
                        l = l.decode('UTF-8')
                        if not l.startswith('data: '):
                            break
                        try:
                            data = loads(l.lstrip('data: '))
                            main_instant_power = data[self._main_key]
                            self._roll_mean_power_300.append(main_instant_power)
                            new_ts = parse(data[KEY_TIMESTAMP])
                            if self._last_update is not None:
                                consumption = main_instant_power * (new_ts - self._last_update).total_seconds() / 3600
                                if new_ts.day != self._last_update.day:
                                    self._consumption_day = consumption
                                    self._consumption_week.append(consumption)
                                else:
                                    self._consumption_day += consumption
                                    self._consumption_week[-1] += consumption
                            self.last_data.update(data)

                            # Today Peak:
                            if main_instant_power > self._peak[0]:
                                self._peak = (main_instant_power, new_ts)
                            elif self._peak[1].day != new_ts.day:
                                self._peak = (main_instant_power, new_ts)

                            if counter_samples < 10:
                                self._period_mean = int(round(main_instant_power) / 5) * 5
                            else:
                                self._period_mean = int(round(sum(list(self._roll_mean_power_300)[-10:]) / 50)) * 5

                            # Aplica state = f(escala):
                            if self._period_mean < 25:
                                str_state = 'OFF'
                            elif self._period_mean < 250:
                                str_state = 'standby'
                            elif self._period_mean < 500:
                                str_state = 'active'
                            elif self._period_mean < 1000:
                                str_state = 'intensive'
                            elif self._period_mean < 3500:
                                str_state = 'high'
                            elif self._period_mean < 4500:
                                str_state = 'very high'
                            else:
                                str_state = 'danger'

                            # PNG tiles regeneration:
                            if ((self._last_tile_generation is not None) and
                                    (time() - self._last_tile_generation > self._refresh_interval_pngtiles - .5)):
                                self.hass.async_add_job(self.async_update_local_png_tiles())

                            # State change
                            if ((self._last_state_ch is None) or (self._state != str_state) or
                                    (abs(self._last_instant_power - main_instant_power) > self._refresh_delta) or
                                    ((new_ts - self._last_state_ch).total_seconds() > self._refresh_interval - .25)):
                                self._last_state_ch = new_ts
                                if self._state != str_state:
                                    LOGGER.debug('CHANGE STATE FROM "{}" TO "{}" -> last_data: {}'
                                                 .format(self._state, str_state, self.last_data))
                                self._state = str_state
                                self.hass.states.async_set(self._entity_id, self._state,
                                                           attributes=self.enerpi_state_attributes)
                                for entity_id, (name, attrs, is_rms) in self._attrs_devices.items():
                                    value = self.last_data[name]
                                    if not is_rms:
                                        value = round(value * 100, 2)
                                    self.hass.states.async_set(entity_id, value, attributes=attrs)
                            self._last_update = new_ts
                            self._last_instant_power = main_instant_power
                            yield from asyncio.sleep(.5)
                            counter_samples += 1
                        except (ValueError, TypeError) as e:
                            if l != 'data: "CLOSE"':
                                LOGGER.error('{} reading stream [{}]: line="{}"'.format(e.__class__, e, l))
            except (requests.ReadTimeout, requests.ConnectionError) as e:
                LOGGER.error('Error reading enerPI stream [{}]; (Samples OK={})'.format(e, counter_samples))
                asyncio.sleep(10)

    @asyncio.coroutine
    def async_update_local_png_tiles(self):
        """Re-generates LOCAL PNG Files from enerpi remote SVG tiles."""
        if self._last_tile_generation is None:  # 1st tile generation
            LOGGER.info('ENERPI png tiles 1st generation for --> {}'.format(self._sensors_tiles_conf))
        self._last_tile_generation = tic = time()
        png_filepaths = []
        for cam_name, cam_path, mag, desc, unit, is_rms, c1, c2 in self._sensors_tiles_conf:
            ok = _creation_local_png_tile(self._host, self._port, self._prefix, mag, c1, c2, cam_path, self._png_dpi)
            if ok:
                png_filepaths.append(cam_path)
            else:
                LOGGER.error('Error generating TILE: {} -> {}'.format(cam_name, cam_path))
        toc = time()
        if png_filepaths:
            basep = os.path.dirname(png_filepaths[0])
            names = [p.replace(basep, '') for p in png_filepaths]
            LOGGER.debug('({:%d-%b %H:%M:%S}) ENERPI: {} PNGs generated. TOOK {:.2f} sec'
                         .format(dt.datetime.now(), len(names), toc - tic))
            if (toc - tic) > .1 * self._refresh_interval_pngtiles:  # if gen time > 10 % ∆T --> re-schedule next gen
                self._last_tile_generation = time()
        elif self._sensors_tiles_conf:
            LOGGER.error('NO PNG local tiles generation ?! Sensor conf is: {}, tiles_conf is: {}'
                         .format(self._attrs_devices, self._sensors_tiles_conf))
