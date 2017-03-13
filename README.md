# Home Assistant
My personal [Home Assistant](https://home-assistant.io) configuration. Used for automate my home devices:
 - 9 Hue lights in three rooms
 - 8 Etekcity RF outlets
 - 1 custom electrical current probe ([enerPI](https://github.com/azogue/enerpi) pet project), which is working in HA as as `custom_component` ([code](https://github.com/azogue/hass_config/tree/master/custom_components))
 - KODI RPI3 (OSMC) with a TV turner, access to the local Media Collection, and Hyperion controlling some Hue lights.
 - Multiple RPI's (1x RPI rev B, 2x RPI_2, 3x RPI_3) running KODI, other instances of HA, multiple sensors and more nerd stuff
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

There are other 2 RPI2's running HA ('slave' ones) in my *little* system, with PIR sensors, DHT22 sensors and a SenseHat. One RPI also runs [MotionEye](https://github.com/ccrisan/motioneye), handling a local video stream (PI camera) and other video stream from a cheap chinesse IP camera (ESCAM QF001); and the other RPI2 has a pHAT DAC with a speaker attached, and runs MPD and shairport-sync.

In addition, recently I have been creating [some automations](https://github.com/azogue/hass_appdaemon_apps) under the new **[AppDaemon](https://home-assistant.io/ecosystem/appdaemon/) system** of apps, and I find it a bewitching method that doing anything in HA.

Some info about what's here:
 * **Notifications** by: email, pushbullet account, KODI notifications and iOS Home Assistant app (in private beta for now)
 * **Device tracking** by: `nmap_tracker` and `bluetooth_tracker` (with internal BT module of RPI 3)
 * **Cameras**: One local NO-IR PI Camera and two more MotionEye streams from other RPI on LAN.
 * **Lights**: Phillips HUE System, excluded from homebridge (I have a 2º gen Hue bridge which is HomeKit compatible).
 * **Switches**: 5x/2remote + 3x/2remote RF outlet packs from Etekcity which were extremely cheap and work like a charm sending commands with the RF emitter installed in the RPI. Also, more 'software' switches to do automations and manipulate correctly HA input_booleans with HomeKit (the `input_boolean`s don't update the initial state in the homebrige plugin, bug?), including:
    - A custom_component/switch for turning ON and OFF my main TV, which is connected to the RPI3 with KODI (with [OSMC](https://osmc.tv) running the [`script.json-cec`](https://github.com/joshjowen/script.json-cec) add-on) --> [`cecswitch` platform](https://github.com/azogue/hass_config/tree/master/custom_components/switch).
    - A WOL switch for my Synology NAS.
    - `command_line` switches for turning ON|OFF and getting status for [Hyperion](https://github.com/hyperion-project/hyperion) in KODI RPI and [Motion](https://motion-project.github.io) detection on video streams.
 * **KODI**: Control the KODI instance which is running 24/7 in another dedicated RPI 3, connected to the TV+HomeCinema kit, and making as AirPlay receiver, DVBT tuner & recorder, and main media player for movies and tv shows.
 * Now I'm playing along with some ESP8266 dev kits to place some sensors in small spaces and talk with HASS directly or with a mosquitto server...
 * Multiple scripts and automations for make my life easier...

The *data center* of all of these little smart machines is a Synology DS213j NAS with 4TB+3TB storage running 24/7 and serving media to all devices. The MySQL KODI database is in there, so any consumer device views the same. 
These days I'm testing to move the Home Assistant DB to the NAS, with a recorder `db_url` like: `mysql://USER:PASS@NAS_IP/HASSDB`. And it's working very well... recorder errors had disappeared and all seems working *more fluent*.

## Screenshots

Some screenshots of the frontend:

![Home view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_home_view.png?raw=true)

![Control view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_control_view.png?raw=true)

![Alarm clock view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_alarmclock_view.png?raw=true)

![enerPI view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_enerpi_view.png?raw=true)

![LAN view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_network_view.png?raw=true)

![Admin view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_admin_settings_view.png?raw=true)

![Alarm view](https://github.com/azogue/hass_config/blob/master/screenshots/hass_alarm_view.png?raw=true)

---
* [enerPI](https://github.com/azogue/enerpi) and [MotionEye](https://github.com/ccrisan/motioneye) running in iframes:

![enerPI iframe](https://github.com/azogue/hass_config/blob/master/screenshots/hass_enerpi_iframe.png?raw=true)

![MotionEye iframe](https://github.com/azogue/hass_config/blob/master/screenshots/hass_motioneye_iframe.png?raw=true)
