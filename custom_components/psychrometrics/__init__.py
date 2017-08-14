# -*- coding: utf-8 -*-
"""
Support for the Psychrometrics component.

For more details about this component, please refer to the documentation
https://home-assistant.io/components/psychrometrics/
"""
import asyncio
from collections import deque
from datetime import timedelta
from itertools import cycle
import json
from multiprocessing import Process
import logging
import os
from time import time
from typing import Union, List, Tuple, Optional

import voluptuous as vol

# TODO Remove TEMPORAL remote access
from homeassistant import remote
from homeassistant.components.camera import Camera
from homeassistant.const import (
    CONF_NAME, CONF_SCAN_INTERVAL, STATE_ON, STATE_OFF, ATTR_ICON,
    ATTR_FRIENDLY_NAME, ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS,
    ATTR_DEVICE_CLASS)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.event import (
    async_track_time_interval, async_track_point_in_utc_time)
from homeassistant.util.dt import now

REQUIREMENTS = ['psychrochart==0.1.10']
DEPENDENCIES = ['sensor']

DOMAIN = 'psychrometrics'

_LOGGER = logging.getLogger(__name__)

CONF_ALTITUDE = 'altitude'
CONF_EXTERIOR = 'exterior'
CONF_INTERIOR = 'interior'
CONF_PRESSURE_KPA = 'pressure_kpa'
CONF_EVOLUTION_ARROWS_MIN = 'evolution_arrows_minutes'
CONF_REMOTE_API = 'remote_api'
CONF_WEATHER = 'weather'

DEFAULT_NAME = "Psychrometric chart"
DEFAULT_SCAN_INTERVAL_SEC = 60

DEFAULT_DEAD_BAND = 0.5  # ºC
DEFAULT_DELTA_EVOLUTION = 5400  # 1.5h
DEFAULT_FREQ_SAMPLING_SEC = 300  # 300 (5min)

BINARY_SENSOR_NAME = 'close_house'
SENSOR_NAME = 'house_delta_temperature'

POINT_SCHEMA = vol.Schema(cv.entity_ids)
POINTS_SCHEMA = vol.Schema(
    vol.Any(POINT_SCHEMA, cv.ensure_list(POINT_SCHEMA)))
ROOM_SCHEMA = vol.Schema({cv.string: POINTS_SCHEMA})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_INTERIOR): ROOM_SCHEMA,
        vol.Optional(CONF_EXTERIOR): POINTS_SCHEMA,
        vol.Optional(CONF_WEATHER): POINTS_SCHEMA,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_SEC):
            cv.positive_int,
        vol.Exclusive(CONF_ALTITUDE, 'altitude'): cv.positive_int,
        vol.Exclusive(CONF_PRESSURE_KPA, 'altitude'): cv.positive_int,
        vol.Optional(CONF_EVOLUTION_ARROWS_MIN): cv.positive_int,
        vol.Optional(CONF_REMOTE_API): cv.Dict,
    })
}, required=True, extra=vol.ALLOW_EXTRA)

basedir = os.path.dirname(os.path.abspath(__file__))
CHART_STYLE_JSON = os.path.join(basedir, 'chart_style.json')
OVERLAY_ZONES_JSON = os.path.join(basedir, 'zones_overlay.json')
CONNECTORS_JSON = os.path.join(basedir, 'connectors.json')
POINT_COLORS = cycle([[0.1059, 0.6196, 0.4667, 0.7],
                      [0.851, 0.3725, 0.0078, 0.7],
                      [0.4588, 0.4392, 0.702, 0.7],
                      [0.9059, 0.1608, 0.5412, 0.7],
                      [0.4, 0.651, 0.1176, 0.7],
                      [0.902, 0.6706, 0.0078, 0.7],
                      [0.651, 0.4627, 0.1137, 0.7],
                      [0.4, 0.4, 0.4, 0.7]])
SIGNAL_UPDATE_DATA = DOMAIN + '_update'


def make_psychrochart(svg_image,
                      altitude, pressure_kpa, points, connectors, arrows):
    """Create the PsychroChart SVG file and save it to disk."""
    from psychrochart.agg import PsychroChart
    from psychrochart.util import load_config

    # Load chart style:
    chart_style = load_config(CHART_STYLE_JSON)
    if altitude is not None:
        chart_style['limits']['altitude_m'] = altitude
    elif pressure_kpa is None:
        chart_style['limits']['pressure_kpa'] = pressure_kpa

    # Make chart
    chart = PsychroChart(chart_style, OVERLAY_ZONES_JSON, logger=_LOGGER)

    # Append lines
    t_min, t_opt, t_max = 16, 23, 30
    chart.plot_vertical_dry_bulb_temp_line(
        t_min, {"color": [0.0, 0.125, 0.376], "lw": 2, "ls": ':'},
        ' TOO COLD, {:g}°C'.format(t_min), ha='left',
        loc=0., fontsize=14)
    chart.plot_vertical_dry_bulb_temp_line(
        t_opt, {"color": [0.475, 0.612, 0.075], "lw": 2, "ls": ':'})
    chart.plot_vertical_dry_bulb_temp_line(
        t_max, {"color": [1.0, 0.0, 0.247], "lw": 2, "ls": ':'},
        'TOO HOT, {:g}°C '.format(t_max), ha='right', loc=1,
        reverse=True, fontsize=14)

    chart.plot_points_dbt_rh(points, connectors)
    if arrows:
        chart.plot_arrows_dbt_rh(arrows)
    chart.plot_legend(
        frameon=False, fontsize=8, labelspacing=.8, markerscale=.7)

    chart.save(svg_image, format='svg')
    return True


@asyncio.coroutine
def async_setup(hass, config_hosts):
    """Setup the Psychrochart Platform."""
    config = config_hosts[DOMAIN]

    name = config.get(CONF_NAME)
    interior_rooms = config.get(CONF_INTERIOR)
    exterior = config.get(CONF_EXTERIOR)
    weather = config.get(CONF_WEATHER)
    altitude = config.get(CONF_ALTITUDE)
    pressure_kpa = config.get(CONF_PRESSURE_KPA)
    scan_interval = config.get(CONF_SCAN_INTERVAL)
    evolution_arrows_minutes = config.get(CONF_EVOLUTION_ARROWS_MIN)

    remote_api_conf = config.get(CONF_REMOTE_API)

    zones = {CONF_INTERIOR: interior_rooms,
             CONF_EXTERIOR: exterior,
             CONF_WEATHER: weather}

    connectors = yield from hass.async_add_job(
        json.load, open(CONNECTORS_JSON))

    chart_handler = PsychroChartHandler(
        hass, altitude, pressure_kpa, zones, connectors,
        scan_interval, evolution_arrows_minutes, remote_api_conf)

    hass.data[DOMAIN] = chart_handler

    # Todo don't use domain=camera --> make new card (without caption)
    yield from async_load_platform(hass, 'camera', DOMAIN, {"name": name})

    conf_sensor = {
        CONF_NAME: SENSOR_NAME,
        ATTR_FRIENDLY_NAME: "Recalentamiento de casa",
        ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
        ATTR_ICON: "mdi:thermometer"}

    conf_bin = {
        CONF_NAME: BINARY_SENSOR_NAME,
        ATTR_FRIENDLY_NAME: "Apertura de ventanas",
        ATTR_DEVICE_CLASS: "opening"}

    yield from async_load_platform(hass, 'sensor', DOMAIN, conf_sensor)
    yield from async_load_platform(hass, 'binary_sensor', DOMAIN, conf_bin)

    return True


class PsychroChartHandler:
    """Handler for the psychrometric chart."""

    def __init__(self, hass, altitude, pressure_kpa,
                 zones_sensors, connectors,
                 refresh_interval, evolution_arrows_minutes, remote_api_conf):
        """Initialize Local File Camera component."""
        self.hass = hass
        self._last_tile_generation = None
        self._delta_refresh = timedelta(seconds=refresh_interval)
        self._altitude = altitude
        self._pressure_kpa = pressure_kpa
        self.zones_sensors = zones_sensors
        self.colors_interior_zones = {
            k: next(POINT_COLORS)
            for k in sorted(self.zones_sensors[CONF_INTERIOR])}
        self.connectors = connectors

        if evolution_arrows_minutes:
            len_deque = int(timedelta(minutes=evolution_arrows_minutes)
                            / self._delta_refresh)
        else:
            len_deque = 1
        self.points = deque([], maxlen=len_deque)
        self.svg_image_bytes = None

        self.delta_house = None
        self.open_house = None
        self._deadband = 0.5  # ºC
        self.sensor_attributes = {}

        # Remote access to sensors in other HA instance
        self.remote_api = None
        if remote_api_conf:
            from homeassistant import remote
            api = remote.API(
                remote_api_conf['base_url'],
                api_password=remote_api_conf.get('api_password'),
                port=remote_api_conf.get('port', 8123),
                use_ssl=remote_api_conf.get('use_ssl', False))
            assert api.validate_api()
            self.remote_api = api

        # Chart regeneration
        if self.remote_api is not None:  # No need to wait
            async_track_point_in_utc_time(
                self.hass, self.update_chart, now() + timedelta(seconds=10))
        async_track_time_interval(
            self.hass, self.update_chart, self._delta_refresh)

    def update_chart_overlay(self, svg_image, points, connectors, arrows):
        """Update the PsychroChart with the sensors info and return the SVG."""
        p = Process(target=make_psychrochart,
                    args=(svg_image, self._altitude, self._pressure_kpa,
                          points, connectors, arrows))
        p.start()
        p.join()
        with open(svg_image, 'rb') as f:
            self.svg_image_bytes = f.read()

    def _get_sensor_state(self, entity_id, remote_states=None):

        def _opt_float(x: str) -> Optional[float]:
            try:
                return float(x)
            except ValueError:
                return None

        value = None
        if remote_states is not None:
            value = [_opt_float(s.state) for s in
                     filter(lambda x: x.entity_id == entity_id,
                            remote_states)]
            if value:
                value = value[0]
        else:
            sensor = self.hass.states.get(entity_id)
            if sensor is not None:
                value = _opt_float(sensor.state)
        return value

    @asyncio.coroutine
    def collect_states(self):
        """Get states from sensors for each zone/subzone."""

        def _get_sensor_list(sensor_list):
            sensors_subzone = []
            for pair in sensor_list:
                s_temp = self._get_sensor_state(pair[0], remote_states)
                s_humid = self._get_sensor_state(pair[1], remote_states)
                if s_temp is not None and s_humid is not None:
                    sensors_subzone.append((s_temp, s_humid))
                else:
                    _LOGGER.warning('ERROR PAIR: %s -> (%s, %s)',
                                    pair, s_temp, s_humid)
            return sensors_subzone

        remote_states = None
        if self.remote_api is not None:
            remote_states = yield from self.hass.async_add_job(
                remote.get_states, self.remote_api)
        results = {}
        for main_zone, values in self.zones_sensors.items():
            if isinstance(values, list):
                results[main_zone] = _get_sensor_list(values)
            else:
                assert isinstance(values, dict)
                results[main_zone] = {}
                for s_zone, sensors_sz in values.items():
                    results[main_zone][s_zone] = _get_sensor_list(sensors_sz)
        return results

    @asyncio.coroutine
    def get_dbt_rh_points(self):
        """Extract temperature - humidity points from sensors."""
        def _mean(values: Union[List[float],
                                Tuple[float]]) -> Optional[float]:
            if values:
                try:
                    return sum(values) / len(values)
                except TypeError:
                    _LOGGER.error('Bad values in mean: %s', values)
            return None

        results = yield from self.collect_states()
        points = {}
        for key, value in results.items():
            if isinstance(value, dict):
                temp_zone = humid_zone = counter = 0
                for k_room, s_values in value.items():
                    temp = _mean([v[0] for v in s_values])
                    humid = _mean([v[1] for v in s_values])
                    if temp is not None and humid is not None:
                        points[k_room] = (int(100 * temp) / 100.,
                                          int(100 * humid) / 100.)
                        temp_zone += temp
                        humid_zone += humid
                        counter += 1
                if counter:
                    points[key] = (int(100 * temp_zone / counter) / 100.,
                                   int(100 * humid_zone / counter) / 100.)
            else:
                temp = _mean([v[0] for v in value])
                humid = _mean([v[1] for v in value])
                if temp is not None and humid is not None:
                    points[key] = (int(100 * temp) / 100.,
                                   int(100 * humid) / 100.)
        return points

    @asyncio.coroutine
    def update_sensors(self):
        """Update temp and humid sensors to make a new SVG chart."""
        if not self.points:
            return

        points = self.points[-1]
        _LOGGER.debug('POINTS FOR UPD SENSORS: %s', points)
        main_zones = [CONF_INTERIOR, CONF_EXTERIOR, CONF_WEATHER]
        deltas_zones = delta_est = delta_house = None
        temp_int, temp_ext, temp_est = [points[k][0] if k in points else None
                                        for k in main_zones]
        _LOGGER.debug('TEMPS: Int: %s, Ext: %s, Est: %s',
                      temp_int, temp_ext, temp_est)

        if temp_est is not None and temp_ext is not None:
            delta_est = round(temp_ext - temp_est, 1)
            assert (abs(delta_est) < 25)
        if temp_int is not None and temp_ext is not None:
            delta_house = round(temp_int - temp_ext, 1)
            assert (abs(delta_house) < 15)
            deltas_zones = {z: round(p[0] - temp_ext, 1) for z, p in
                            points.items() if z not in main_zones}

        attrs = {
            "Interior": temp_int,
            "Exterior": temp_ext,
            "Exterior Est.": temp_est,
            "∆T with estimated exterior": delta_est,
            ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS,
            ATTR_FRIENDLY_NAME: "Recalentamiento de casa",
            ATTR_ICON: "mdi:thermometer",
        }
        # Append deltas_zones
        if deltas_zones is not None:
            [attrs.update({z: delta}) for z, delta in deltas_zones.items()]

        self.sensor_attributes = attrs
        # Decision logic (deadband)
        if delta_house is None:
            return

        self.delta_house = delta_house
        if self.open_house is None:
            # First value
            self.open_house = delta_house > 0
            _LOGGER.info("Monitoring natural ventilation "
                         "(∆House: {} ºC, Open:{})"
                         .format(delta_house, self.open_house))
        elif self.open_house and delta_house < -self._deadband:
            _LOGGER.info("Natural ventilation --> OFF (∆House: {} ºC)"
                         .format(delta_house))
            self.open_house = False
        elif not self.open_house and delta_house > self._deadband:
            self.open_house = True
            _LOGGER.info("Natural ventilation --> ON (∆House: {} ºC)"
                         .format(delta_house))

        async_dispatcher_send(self.hass, SIGNAL_UPDATE_DATA)

    # noinspection PyUnusedLocal
    @asyncio.coroutine
    def update_chart(self, *args):
        """Re-generates Chart SVG."""

        def _apply_style(labeled_points, colors_interior_zones):
            point_styles = {
                CONF_EXTERIOR: {'marker': 'X', 'markersize': 15,
                                'color': [0.855, 0.004, 0.278, 0.8],
                                'label': 'Exterior'},
                CONF_WEATHER: {'marker': "d", 'markersize': 10,
                               'color': [0.573, 0.106, 0.318, .5],
                               'label': 'Weather service'},
                CONF_INTERIOR: {'marker': '*', 'markersize': 25,
                                'color': [0.0, 0.502, 0.337, 0.8],
                                'label': 'Interior'}}
            for k in point_styles:
                if k in labeled_points:
                    label = point_styles[k].pop('label')
                    labeled_points[k] = {
                        "xy": labeled_points[k],
                        "style": point_styles[k],
                        "label": label}
            for k, p_value in labeled_points.items():
                if not isinstance(p_value, dict):
                    labeled_points[k] = {
                        "xy": labeled_points[k],
                        "style": {'marker': 'o', 'markersize': 10,
                                  'color': colors_interior_zones[k]},
                        "label": k}
            return labeled_points

        tic = time()
        points = yield from self.get_dbt_rh_points()
        _LOGGER.debug('NEW POINTS: %s', points)

        self.points.append(points.copy())
        yield from self.update_sensors()

        arrows = {}
        if len(self.points) > 1:
            arrows = {k: [p, self.points[0][k]]
                      for k, p in points.items() if k in self.points[0]
                      and p != self.points[0][k]}
            _LOGGER.debug('MAKE ARROWS: %s', arrows)
            arrows = _apply_style(arrows, self.colors_interior_zones)

        points_plot = _apply_style(points, self.colors_interior_zones)

        svg_image = os.path.join(basedir, 'psychrochart.svg')
        yield from self.hass.async_add_job(
            self.update_chart_overlay, svg_image,
            points_plot, self.connectors, arrows)
        self._last_tile_generation = now()
        _LOGGER.debug('CHART generated in {:.2f} sec'.format(time() - tic))


class PsychroCam(Camera):
    """Custom Camera for the psychrometric chart."""

    def __init__(self, hass, chart_handler, entity_name):
        """Initialize Local File Camera component."""
        super().__init__()
        self.hass = hass
        self.content_type = 'image/svg+xml'
        self._name = entity_name
        self._chart = chart_handler

    @asyncio.coroutine
    def async_camera_image(self):
        """Return image response."""
        if self._chart.svg_image_bytes is not None:
            return self._chart.svg_image_bytes

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def brand(self):
        """Camera brand."""
        return 'AzogueLabs'

    @property
    def model(self):
        """Camera model."""
        return 'Psychrometric chart'

    # @property
    # def state_attributes(self):
    #     """Camera state attributes."""
    #     st_attrs = super().state_attributes
    #     # st_attrs.update({"friendly_name": self.name,
    #     #                  "attribution": "Powered by AzogueLabs",
    #     #                  "last_changed": self._last_tile_generation})
    #     st_attrs.update({"friendly_name": self.name,
    #                      "attribution": "Powered by AzogueLabs"})
    #     return st_attrs


class PsychrometricsSensor(Entity):
    """Representation of a sensor for the psychrometrics component."""

    def __init__(self, chart_handler, name, friendly_name, unit, icon):
        """Initialize the psychrometric sensor object."""
        self._chart = chart_handler
        self._name = name
        self._friendly_name = friendly_name
        self._icon = icon
        self._unit = unit

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
        """Return the state of the sensor."""
        return self._chart.delta_house

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self):
        """Return true when state is known."""
        return self._chart.delta_house is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = self._chart.sensor_attributes.copy()
        attrs.update({"friendly_name": self._friendly_name})
        return attrs

    @property
    def icon(self):
        """Return the icon for the sensor."""
        return self._icon

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update dispatcher."""
        @callback
        def async_sensor_update():
            """Update callback."""
            self.hass.async_add_job(self.async_update_ha_state(True))

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_DATA, async_sensor_update)


class PsychrometricsBinarySensor(BinarySensorDevice):
    """Representation of a binary sensor for the psychrometrics component."""

    def __init__(self, chart_handler, name, friendly_name, device_class):
        """Initialize the sensor object."""
        self._chart = chart_handler
        self._name = name
        self._friendly_name = friendly_name
        self._device_class = device_class

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self._chart.open_house

    @property
    def state(self):
        """Return the state of the binary sensor."""
        return STATE_ON if self.is_on else STATE_OFF

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        return self._device_class

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def available(self):
        """Return true when state is known."""
        return False if self._chart.open_house is None else True

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {"friendly_name": self._friendly_name}
        return attrs

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register update dispatcher."""
        @callback
        def async_sensor_update():
            """Update callback."""
            self.hass.async_add_job(self.async_update_ha_state(True))

        async_dispatcher_connect(
            self.hass, SIGNAL_UPDATE_DATA, async_sensor_update)
