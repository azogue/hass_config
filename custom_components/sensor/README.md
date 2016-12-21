# Home Assistant Custom Component supporting [enerPI sensors](https://github.com/azogue/enerpi) running *enerpi* + *enerpiweb* in some local host.

Derived from the general REST sensor (https://home-assistant.io/components/sensor.rest/), it connects via GET requests to the local working enerpi web server and populates new hass sensors, which are updated through a single request.

In addition, it generates local PNG files from the remote SVG tiles with the last 24 hours evolution of each sensor, which can be used as `local_file` hass cameras to show color plots in Home Assistant frontend. (in a too-twisted way that depends on the cairosvg library)

It's a very simple, and very bad (imho), way to integrate enerpi in Hass, until I learn to create an html component that can integrate the streaming values (with sse) and the svg background mosaics...

The setup does a few things:
- First, it gets the enerpi sensor configuration at `http://ENERPI_IP/enerpi/api/filedownload/sensors`.
- Then, it generates the first local PNG files, requesting the remote SVG tiles, with urls like:
    `http://ENERPI_IP/enerpi/static/img/generated/tile_enerpi_data_{sensor_name}_last_24h.svg`
  Sets absolute size and color background (no css here) in the svg content, and renders it in PNG with cairosvg.
- Finally, it extracts the last produced sensor data at `http://ENERPI_IP/enerpi/api/last` and populates new sensors with the defined `monitored_variables` or with all sensors in the enerpiweb server.

## YAML HASS configuration:

* On configuration.yaml (or where it is needed):
```
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
```
Only the `host` variable is required. To establish the scanning frequency for getting the enerpi state, use the variables `data_refresh` & `pngtiles_refresh`, in seconds. `data_refresh` has to be higher or equal than HA `scan_interval` to function properly, because the trigger for requesting data is inside the HA update function.

* For the tiles representation as `local_file cameras:
```
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
```
  (you can access this info in the HASS log, when the enerpi component loads)

* For customize friendly names and icons, in `customize.yaml or where applicable:
```
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
```

* For automating an alert when main power goes over a custom limit and when it downs to a safe level again. This is done with 2 `input_slider`'s (for dynamic customization of the upper & lower limit for the main power variable to control) and 2 `input_booleans`, one for toggle on/off this control, and the other for saving the `enerpi alarm state`. You can define your desired *hysteresis* setting the minimum delay for activating or deactivating the alarm state.
```
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
```

* For grouping it all in a tab view:
```
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
```

* For seeing the logs (debug | info | error | ...):
```
        logger:
          logs:
            custom_components.enerpi: debug
```
