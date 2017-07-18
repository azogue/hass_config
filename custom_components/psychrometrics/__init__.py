# -*- coding: utf-8 -*-
"""

"""
# TODO DESCRIPTION
import asyncio
from collections import deque
from datetime import timedelta
from io import BytesIO
from itertools import cycle
import json
import logging
import os
from time import time
from typing import Union, List, Tuple, Optional

import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.const import (
    CONF_NAME, CONF_SCAN_INTERVAL, STATE_ON, STATE_OFF)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.event import (
    async_track_time_interval, async_track_point_in_utc_time)
from homeassistant.util.dt import now
# TODO Remove TEMPORAL remote access
from homeassistant import remote

REQUIREMENTS = ['psychrochart==0.1.5']
DEPENDENCIES = ['sensor']

DOMAIN = 'psychrometrics'

CONF_ALTITUDE = 'altitude'
CONF_EXTERIOR = 'exterior'
CONF_INTERIOR = 'interior'
CONF_PRESSURE_KPA = 'pressure_kpa'
CONF_EVOLUTION_ARROWS_MIN = 'evolution_arrows_minutes'
CONF_REMOTE_API = 'remote_api'
CONF_WEATHER = 'weather'

DEFAULT_NAME = "Psychrometric chart"
DEFAULT_SCAN_INTERVAL_SEC = 60

_LOGGER = logging.getLogger(__name__)

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


def make_psychrochart(altitude, pressure_kpa):
    """Create the PsychroChart object where to overlay the sensors info."""
    from psychrochart.agg import PsychroChart
    from psychrochart.util import load_config
    from psychrochart import __version__ as version, __file__ as psy_file

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

    return chart


def update_chart_overlay(chart, svg_image,
                         points, connectors, arrows,
                         first_generation=False):
    """Update the PsychroChart with the sensors info and return the SVG."""
    # svg_image = BytesIO()
    chart.plot_points_dbt_rh(points, connectors)
    if arrows:
        # Make pairs:
        chart.plot_arrows_dbt_rh(arrows)
    if first_generation:
        # Append legend
        chart.plot_legend(
            frameon=False, fontsize=8, labelspacing=.8, markerscale=.7)
    chart.save(svg_image, format='svg')
    chart.remove_annotations()


@asyncio.coroutine
def async_setup(hass, config_hosts):
    """Setup the Psychrochart Platform."""
    config = config_hosts[DOMAIN]

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

    chart_config = {
        "altitude": altitude,
        "pressure_kpa": pressure_kpa,
        "zones_sensors": zones,
        "connectors": connectors,
        "entity_name": config.get(CONF_NAME),
        "refresh_interval": scan_interval,
        "evolution_arrows_minutes": evolution_arrows_minutes,
        "remote_api_conf": remote_api_conf}

    yield from async_load_platform(hass, 'camera', DOMAIN, chart_config)

    # Todo don't use domain=camera --> make new card (without caption)
    # component = EntityComponent(_LOGGER, DOMAIN, hass, scan_interval)
    # component = EntityComponent(_LOGGER, 'camera', hass, scan_interval)

    # hass.http.register_view(CameraImageView(component.entities))
    # hass.http.register_view(CameraMjpegStream(component.entities))

    # entities = [PsychroCam(
    #     hass, chart, zones, connectors, config.get(CONF_NAME), scan_interval, api)]
    # yield from component.async_add_entities(entities)

    return True


class PsychroCam(Camera):
    """Custom Camera for the psychrometric chart."""

    def __init__(self, hass, chart_object, zones_sensors, connectors,
                 entity_name, refresh_interval, evolution_arrows_minutes,
                 remote_api_conf):
        """Initialize Local File Camera component."""
        super().__init__()
        self.hass = hass
        self.content_type = 'image/svg+xml'
        self._name = entity_name
        self._last_tile_generation = None
        self._delta_refresh = timedelta(seconds=refresh_interval)
        self.chart = chart_object
        self.zones_sensors = zones_sensors
        self.colors_interior_zones = {
            k: next(POINT_COLORS)
            for k in sorted(self.zones_sensors[CONF_INTERIOR])}
        self.connectors = connectors

        if evolution_arrows_minutes:
            len_deque = int(timedelta(minutes=evolution_arrows_minutes)
                            / self._delta_refresh)
            self._points = deque([], maxlen=len_deque)
        self._image_bytes = None
        # self._file_path = os.path.join(basedir, 'chart.svg')

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
        # self._counter_frames = 0

        # Chart regeneration
        if self.remote_api is not None:  # No need to wait
            async_track_point_in_utc_time(
                self.hass, self.update_chart, now() + timedelta(seconds=1))
        async_track_time_interval(
            self.hass, self.update_chart, self._delta_refresh)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return image response."""
        if self._image_bytes is not None:
            return self._image_bytes

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    # Todo state OK vs COLD/HOT/DRY/WET
    # @property
    # def state(self):
    #     """Return the camera state."""
    #     if self._image_bytes is None:
    #         return STATE_OFF
    #     return STATE_ON

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
        # Extract T-RH points

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

        self._points.append(points.copy())
        _LOGGER.debug('NEW POINTS: %s', points)

        arrows = {}
        if len(self._points) > 1:
            arrows = {k: [p, self._points[0][k]]
                      for k, p in points.items() if k in self._points[0]
                      and p != self._points[0][k]}
            _LOGGER.debug('MAKE ARROWS: %s', arrows)
            arrows = _apply_style(arrows, self.colors_interior_zones)

        points = _apply_style(points, self.colors_interior_zones)

        svg_image = BytesIO()
        yield from self.hass.async_add_job(
            update_chart_overlay, self.chart, svg_image,
            points, self.connectors, arrows, self._image_bytes is None)
        svg_image.seek(0)
        self._image_bytes = svg_image.read()

        self._last_tile_generation = now()
        _LOGGER.debug('CHART generated in {:.2f} sec'.format(time() - tic))

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
