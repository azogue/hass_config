# Home Assistant
My personal [Home Assistant](https://home-assistant.io) configuration. Used for automate my home devices:
 - 9 Hue lights in two rooms
 - 5 Etekcity RF outlets
 - 2 custom electrical current probes ([enerPI](https://github.com/azogue/enerpi) pet project), which are working in HA as `custom_components` ([code](https://github.com/azogue/hass_config/tree/master/custom_components/sensor))
 - Multiple RPI's (1x RPI rev B, 2x RPI_2, 3x RPI_3) running KODI, multiple sensors and more nerd stuff
 - ...

The `hass` instance runs in one dedicated, ethernet-connected, **Raspberry PI 3**, with some sensors attached:
 - 1x DS18b20 temperature sensor
 - 1x DHT22 temperature & humidity sensor
 - 1x PIR motion sensor
 - 1x NOIR PI Camera
 - 1x RF Emitter (for control the previously identified outlets with a RF receiver)

This RPI has the last version of raspbian jessie, and it's running these marvellous open-source projects:
 - **[Home Assistant](https://github.com/home-assistant/home-assistant)** (obviously!)
 - **[HomeBridge](https://github.com/nfarina/homebridge)**
 - **[Home Assistant for Homebridge](https://github.com/home-assistant/homebridge-homeassistant)**

In addition, recently I have been creating [some automations](https://github.com/azogue/hass_appdaemon_apps) under the new **[AppDaemon](https://home-assistant.io/ecosystem/appdaemon/) system** of apps, and I find it a bewitching method that doing anything in HA.

Some info about what's here:
 * **Notifications** by: email, pushbullet account, KODI notifications and iOS Home Assistant app (in private beta for now)
 * **Device tracking** by: `nmap_tracker` and `bluetooth_tracker` (with internal BT module of RPI 3)
 * **Cameras**: Currently, only the attached NO-IR PI Camera
 * **Lights**: Phillips HUE System, excluded from homebridge (I have a 2º gen Hue bridge)
 * **Switches**: A 5x/2remote RF outlet pack from Etekcity which was extremely cheap and works like a charm sending commands with the RF emitter installed in the RPI.
 * **KODI**: Control the KODI instance which is running 24/7 in another dedicated RPI 3,
 connected to the TV+HomeCinema kit, and making as AirPlay receiver

