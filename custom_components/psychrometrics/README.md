# Home Assistant **Psychrometrics** component

A component to retrieve the state of multiple ambient sensors (temperature, humidity, ...) and present _curated information_ aggregatting the data, to better explore the ambient status, its evolution, and even get integrated with climate components to help with the best climate decisions for the _smart house_.

<img src="https://rawgit.com/azogue/hass_config/master/screenshots/hass_camera_psychrometric_chart.svg" width="100%" height="100%">

This component should register services to do any needed psychrometric calculation and present sensors with curated states such as the recomendation of the best action to change the air contitions to move to the comfort mode (like: _natural ventilation_, _air conditioning_, _evaporative cooling_, _heat_, _humidification_)
In addition, the aggregated data of the multiple sensors could be shown graphically, with the overlay of information over a (all-customizable) psychrometric chart.

This component is in a early stage, so at this time consists in a **psychrometric chart at constant pressure defined in HA as a dynamic SVG camera with sensors annotated**.

## Configuration

The sensors are defined as follows, with this schema:
```python
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
        vol.Optional(CONF_REMOTE_API): cv.Dict,
    })
}, required=True, extra=vol.ALLOW_EXTRA)
```

So there are three main zones:
 - `Weather` for HA temperature and humidity sensors from weather services
 - `Exterior` for HA temperature and humidity sensors situated in exterior zones at the house
 - `Interior` for HA temperature and humidity sensors situated in the interior of the house. These are sub-grouped with the room names.

This grouping is used to plot a colour-differenciated point for each room, and three bigger points for each of the main zones. Also, some conecctions and zones are added to the plot.

The main idea here is to be able to get/define 'templates' for different `psychrocharts` (for each season, for example), and define the info to be added.


### Yaml configuration example:

As you can see, the ambient points (temperature and relative humidity) are defined by pairs of Home Assistant sensors, and if you have more than one pair in a room or a main zone, you can define a list, and the mean value will be used in the plot.

```yaml
psychrometrics:
  scan_interval: 120  # data update interval
  evolution_arrows_minutes: 240  # draw arrows to show evolution
  altitude: 550  # Altitude in m to calculate the typical pressure
  # pressure_kpa: 97.5  # Pressure in kPa instead of altitude
  interior:  # Interior main zone, with sensors for each room
    Salón:  # Pairs of (T, RH) from each room
      - sensor.salon_temperature, sensor.salon_humidity
    Dormitorio:
      - sensor.dormitorio_temperature_rpi2mpd, sensor.dormitorio_humidity_rpi2mpd
      - sensor.dormitorio_htu21d_temperature_rpi2mpd, sensor.dormitorio_htu21d_humidity_rpi2mpd
    Cocina:
      - sensor.esp1_temperature, sensor.esp1_humidity
    Plancha:
      - sensor.esp3_temperature, sensor.esp3_humidity
    Estudio:
      - sensor.estudio_temperature_rpi2h, sensor.estudio_humidity_rpi2h
  exterior:  # Pairs of (T, RH) from the exterior of the house
      - sensor.galeria_dht22_temperature, sensor.galeria_dht22_humidity
  weather:  # Pairs of (T, RH) from weather services
      - sensor.dark_sky_temperature, sensor.dark_sky_humidity
```

### Screenshots

The psychrometric plot style (curves included, axes, line styles, colors, labels, etc.) is defined in JSON files (could be integrated in the yaml component config, but would be large), and if you know a little of `matplotlib`, the parameters will be self-descriptive.

![Psychrochart camera](https://github.com/azogue/hass_config/blob/master/screenshots/hass_screenshot_psychrometrics_camera.png?raw=true)