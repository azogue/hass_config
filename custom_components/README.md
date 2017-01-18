# Home Assistant Custom Components

These are my custom components for HomeAssistant:
  * A **custom CEC Switch** for turning ON&OFF my TV, which uses the `script.json-cec` add-on in KODI, instead of the normal CEC shell client, which breaks the KODI CEC (in my case) and makes unusable tv remote.
  * A little mod of the `onewire` sensor platform with minimum and maximum value validation.
  * A little mod of the `sensehat` sensor platform with value rounding.
  * A very specific solution for one custom datalogger running in a RPI which monitors temperatures of my gas heater system, taking indirect measures to estimate the heating state. It gets the data querying a remote MySQL DB in the remote RPI.
  * A custom platform with sensors, evolution graphics and inputs for supporting my custom current meter, [enerPI](https://github.com/azogue/enerpi).

## Home Assistant Custom Component supporting [enerPI sensors](https://github.com/azogue/enerpi) running *enerpi* + *enerpiweb* in some local host.

Derived from the general REST sensor (https://home-assistant.io/components/sensor.rest/), it connects via GET requests to the local working enerpi web server and populates new hass sensors, which are updated through a single conexion to the enerPI real-time stream.
In addition, it generates local PNG files from the remote SVG tiles with the last 24 hours evolution of each sensor, which can be used as `local_file` hass cameras to show color plots in Home Assistant frontend. (in a too-twisted way that depends on the cairosvg library). These special `local_file` cameras refresh are updated every `pngtiles_refresh` seconds.
It's a very simple, and very bad (imho), way to integrate enerpi in Hass, until I learn to create an html component that can integrate the svg background mosaics...

The setup does a few things:
- First, it gets the enerpi sensor configuration at `http://ENERPI_IP/enerpi/api/filedownload/sensors`.
- With the existent enerpi sensor config, it extracts the last produced sensor data at `http://ENERPI_IP/enerpi/api/last` and populates new sensors with the defined `monitored_variables` or with all sensors in the enerpiweb server.
- Also, it creates 2 input_slider's and one input_boolean for automating an alert when main power goes over a custom limit and when it downs to a safe level again.
- Then, it generates the first local PNG files, requesting the remote SVG tiles, with urls like:
    `http://ENERPI_IP/enerpi/static/img/generated/tile_enerpi_data_{sensor_name}_last_24h.svg`
  Sets absolute size and color background (no css here) in the svg content, and renders it in PNG with cairosvg.
- Finally, it extracts the last produced sensor data at `http://ENERPI_IP/enerpi/api/last` and populates new sensors with the defined `monitored_variables` or with all sensors in the enerpiweb server.

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
