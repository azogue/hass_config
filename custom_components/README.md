# Home Assistant Custom Components

These are my custom components for HomeAssistant:
  * A **[custom CEC Switch](https://github.com/azogue/hass_config/tree/master/custom_components/switch)** for turning ON&OFF my TV, which uses the `script.json-cec` add-on in KODI, instead of the normal CEC shell client, which breaks the KODI CEC (in my case) and makes unusable tv remote.
  * A simple **[analog sensor for Raspberry PI with a MCP3008 A/D conversor](https://github.com/azogue/hass_config/blob/master/custom_components/sensor/raspioanalog.py)** (like in the **Raspio Analog Zero Hat**), using the `gpiozero` library.
  * A [little mod](https://github.com/azogue/hass_config/blob/master/custom_components/sensor/myonewire.py) of the `onewire` sensor platform with minimum and maximum value validation.
  * A [little mod](https://github.com/azogue/hass_config/blob/master/custom_components/sensor/mysensehat.py) of the `sensehat` sensor platform with value rounding.
  * A [very specific solution for one custom datalogger](https://github.com/azogue/hass_config/blob/master/custom_components/sensor/enerweb.py) running in a RPI which monitors temperatures of my gas heater system, taking indirect measures to estimate the heating state. It gets the data querying a remote MySQL DB in the remote RPI.
  * A **[*dummy* binary sensor](https://github.com/azogue/hass_config/blob/master/custom_components/binary_sensor/dummy.py)**. My simple solution to binary sensors which are updated from outside HASS (like the ones from video-motion detection that `motion` creates), for using them without problems in AppDaemon apps.
  * A **[custom SMPT notifier](https://github.com/azogue/hass_config/blob/master/custom_components/notify/richsmtp.py)** which can accept html with attached images (jinja2 renders) to send rich emails.
  * A custom platform with sensors, evolution graphics and inputs supporting my custom current meter, **[enerPI](https://github.com/azogue/enerpi)**.

## Home Assistant Custom Component supporting [enerPI sensors](https://github.com/azogue/enerpi) running *enerpi* + *enerpiweb* in some local host.

Derived from the general REST sensor (https://home-assistant.io/components/sensor.rest/), it connects via GET requests to the local working enerpi web server and populates new hass sensors, which are updated through a single conexion to the enerPI real-time stream.

In addition, it generates local PNG files with the last 24 hours evolution of each sensor, used as `local_file` HA cameras to show color plots in Home Assistant frontend. 
These special `local_file` cameras refresh are updated every `pngtiles_refresh` seconds.

The platform setup does a few things:
- First, it gets the enerpi sensor configuration at `http://ENERPI_IP/enerpi/api/filedownload/sensors`.
- With the existent enerpi sensor config, it extracts the last produced sensor data at `http://ENERPI_IP/enerpi/api/last` and the last week total consumption at `http://ENERPI_IP/enerpi/api/consumption/from/{:%Y-%m-%d}?daily=true&round=1`; and populates new sensors with the defined `monitored_variables` or with all sensors in the enerpiweb server.
- Also, it creates 2 input_slider's and one input_boolean for automating an alert when main power goes over a custom limit and when it downs to a safe level again.
- Then, it generates local file cameras with the mirrors of the enerPI tiles in PNG format, with urls like: `http://ENERPI_IP/enerpi/static/img/generated/tile_enerpi_data_{sensor_name}_last_24h.png`
- Finally, it connects to the real-time stream and updates HA states when it is convenient.

### YAML HASS configuration:

* On configuration.yaml:
```
enerpi:
  enerpi_rpi3:
    host: 192.168.1.44
    name: enerPI
    scan_interval: 10
    delta_refresh: 1000  # Watt.
    monitored_variables:
      - power
      - ldr
    pngtiles_refresh: 300
```
Only the `host` variable is required. To establish the frequency for updating the enerpi state, use the variable `scan_interval`, and for the enerPI tiles, user `pngtiles_refresh`, both variables in seconds.

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

* For automating an alert when main power goes over a custom limit and when it downs to a safe level again. This is done with 2 `input_slider`'s (for dynamic customization of the upper & lower limit for the main power variable to control) and 2 `input_booleans`, one for toggle on/off this control, and the other for saving the `enerpi alarm state`. You can define your desired *hysteresis* setting the minimum delay for activating or deactivating the alarm state.
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
