# Another HomeAssistant configuration (slave HASS)

HA config on another RPI with some sensors attached, which is posting state changes on the 'master' instance.

This RPI has:
    * 1x PIR sensor
    * 1x DS18b20 temperature sensor --> integrated with a custom mod from onewire sensor platform (`myonewire.py`)
    * 1x DHT22 temperature & humidity sensor
    ~~* 1x DHT11 temperature & humidity sensor (**removed** because its shitty precission)~~
    * Raspberry PI Sense Hat (->AstroPI) integrated with a custom_component sensor (`mysensehat.py`) sensing:
        - Pressure
        - Temperature
        - Humidity


# MotionEye Cameras

This RPI (RPi 2 rev.B) is also running **[motioneye](https://github.com/ccrisan/motioneye)**, serving video streams and video motion detection of 2 video sources: a local PI Camera and a remote rtsp stream of other cheap wifi camera.

With a customized `motion` config, I'm updating 2 binary_sensor's in the master HA instance with the motion detection, and, in addition, I have 2 `command_line` switches for turning on and off the motion detection in each video stream.