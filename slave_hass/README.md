# Another HomeAssistant configuration (slave HASS)

HA config on another RPI with some sensors attached, which is posting state changes on the 'master' instance.

This RPI has:
  * 1x PIR sensor.
  ~~* 1x DS18b20 temperature sensor --> integrated with a custom mod from the `onewire` sensor platform ([`myonewire.py`](https://github.com/azogue/hass_config/blob/master/custom_components/sensor/myonewire.py))~~
  ~~* 1x DHT22 temperature & humidity sensor~~
  ~~* 1x DHT11 temperature & humidity sensor (**removed** because its shitty precission)~~
  ~~* [Raspberry PI Sense Hat](https://www.raspberrypi.org/products/sense-hat/) integrated with a simple `custom_component` sensor (`mysensehat.py`) sensing pressure, temperature and humidity.~~
  * 1x BME280 pressure, temperature and humidity i2c digital sensor.
  * 1x BH1750 light level i2c digital sensor.
  * 1x output relay to control an AC light circuit.


## MotionEye Cameras

This RPI (RPi 2 rev.B) is also running **[MotionEye](https://github.com/ccrisan/motioneye)**, serving video streams and video motion detection of 2 video sources: a local PI Camera and a remote rtsp stream of other cheap wifi camera.

**With a customized `motion` config**, I'm updating 2 binary_sensor's in the master HA instance with the motion detection events, and, in addition, I have 2 `command_line` switches for turning on and off the motion detection in each video stream. **How I did it?** Well, let's see:

### MotionEye install

First things first. You need MotionEye running. If you don't, I did it as advised in the [Install On Raspbian](https://github.com/ccrisan/motioneye/wiki/Install-On-Raspbian) Wiki. In a ssh session with sudo powers:

```bash
sudo apt-get install python-pip python-dev curl libssl-dev libcurl4-openssl-dev libjpeg-dev libx264-142 libavcodec56 libavformat56 libmysqlclient18 libswscale3 libpq5

wget https://github.com/ccrisan/motioneye/wiki/precompiled/ffmpeg_3.1.1-1_armhf.deb
sudo dpkg -i ffmpeg_3.1.1-1_armhf.deb

wget https://github.com/Motion-Project/motion/releases/download/release-4.0.1/pi_jessie_motion_4.0.1-1_armhf.deb
sudo dpkg -i pi_jessie_motion_4.0.1-1_armhf.deb

sudo pip install pytz
sudo pip install motioneye
sudo mkdir -p /etc/motioneye
sudo mkdir -p /var/lib/motioneye
```

Now, if you already have the MotionEye config files, transfer them:

```bash
sudo cp /path/to/your/motion.conf /etc/motioneye/motion.conf
sudo cp /path/to/your/motioneye.conf /etc/motioneye/motioneye.conf
sudo cp /path/to/your/thread-1.conf /etc/motioneye/thread-1.conf
sudo cp /path/to/your/thread-2.conf /etc/motioneye/thread-2.conf
```

### **Home Assistant integration**

For now, there isn't a specific Home Assistant component (a `camera` platform) to handle the MotionEye cameras, but they work well as JPG cameras, using the [`generic` IP camera](https://home-assistant.io/components/camera.generic/).

The yaml config needed for each camera is something like this:

```yaml
camera:
  - platform: generic
    name: Your camera custom name
    still_image_url: http://MEYE_IP/picture/MEYE_ID_CAM/current/?_username=MEYE_USERNAME&_signature=MEYE_HEXDATA_DERIVED_FROM_YOUR_MEYEPWD
```
And you can grab the `still_image_url` directly from the MotionEye Web UI, in the **'Video Streaming' section, go to 'Useful URLs'->'Snapshot URL'** and copy/paste it.
With that, now you have your cameras in Home Assistant. What about the motion detection?

#### Motion detection as Home Assistant binary sensors

**If you have `motion` doing motion detection in MotionEye**, you can use the events generated to write the state of a `binary_sensor` in Home Assistant, simply using the Home Assistant [RESTful API](https://home-assistant.io/developers/rest_api/).
As explained in the [HA docs](https://home-assistant.io/developers/rest_api/#post-apistatesltentity_id), you can use `curl` to make POST requests and make changes in the states of the entities, or even create new ones:

```bash
curl -X POST -H "x-ha-access: YOUR_PASSWORD" \
       -H "Content-Type: application/json" \
       -d '{"state": "on", "attributes": {"friendly_name": "Motion Detection", "device_class": "motion"}}' \
       http://localhost:8123/api/states/binary_sensor.meye_camera_motion
```

Before going on the next step, try the `curl` command with your custom config from the shell of the MotionEye machine, to check all things are working ok in the HA side. You can create a new binary sensor and change it's state setting "state" to "on" or "off".

##### Motion custom configuration

The `motion` detector generates events that are used to make things like take a snapshot, or start video recording. The intention here is to call Home Assistant with `curl` commands when these events happen.
For now, not all of the interesting events are implemented in the MotionEye Web UI, so a manual edition of the camera configuration files (`/etc/motioneye/thread-ID.conf` files) is needed to define the curl commands. The problem is, when you change something in the UI, MotionEye writes a new `thread-ID.conf`, removing the extra commands defined previously. So I made **[a little script](https://github.com/azogue/hass_config/blob/master/slave_hass/check_motion_config.py)** to make these config changes automatically.

The events I use are: `on_event_start`, `on_event_end`, `on_camera_lost` and `on_camera_found`, so, when a 'on_event_start' or a 'on_camera_lost' happens, a binary sensor gets activated ("on" state), and when 'on_event_stop' or 'on_camera_found' event happens, it changes to "off".

The python script is intended to run at startup with sudo powers, because it needs permission to write in the MotionEye cameras config files, which there are in `/etc/motioneye`.
To do that, edit your CRON file (`crontab -e`) and add:
```
@reboot sudo /srv/homeassistant/bin/python /home/homeassistant/.homeassistant/check_motion_config.py
```
Replace `/srv/homeassistant/bin/python` for your python interpreter if the path is not the same as mine. I use the HA python bin to ensure the `yaml` library is installed, because I use it to read the Home Assistant API password from my `secrets.yaml` file. But you can remove it and set your password explicitly in that script, when customizing it for your use case, and then run it from any python binary:

```python
# Define here your custom HA config for each MotionEye camera:
MEYE_CAMERAS_BIN_SENSORS = {
    1: {"entity_id": "binary_sensor.motioncam_salon",
        "friendly_name": "Vídeo-Mov. en Salón",
        "homebridge_hidden": "true",
        "device_class": "motion"},
    2: {"entity_id": "binary_sensor.motioncam_estudio",
        "friendly_name": "Vídeo-Mov. en Estudio",
        "homebridge_hidden": "true",
        "device_class": "motion"}
}

# Define here how to find your Home Assistant instance
HA_HOST = "127.0.0.1"  # If HA runs in the same host than MotionEye
HA_PORT = 8123
HA_PROTOCOL = "http"

# Define your Home Assistant API password
# (Here I'm reading my `secrets.yaml` file and getting the 'hass_pw' value)
basedir = os.path.dirname(os.path.abspath(__file__))
PATH_SECRETS = os.path.join(basedir, 'secrets.yaml')
with open(PATH_SECRETS) as _file:
    SECRETS = yaml.load(_file.read())
HA_API_PASSWORD = SECRETS['hass_pw']
```

#### Motion detection control with Home Assistant switches

In this case, we want to turn on / off the video motion detection for the MotionEye cameras, and do it from Home Assistant. A `command_line` switch running a shell script which talks to the `motion` API is the way to go:
The yaml config for these switches is:

```yaml
switch:
  - platform: command_line
    scan_interval: 120
    switches:
      motioncam_escam:
        command_on: '/path/to/shell_script/switch_camera_motion_detection.sh MEYE_IP CAM_ID start'
        command_off: '/path/to/shell_script/switch_camera_motion_detection.sh MEYE_IP CAM_ID pause'
        command_state: '/path/to/shell_script/switch_camera_motion_detection.sh MEYE_IP CAM_ID status'
        friendly_name: Use video motion detection in MEYE cam 1
        value_template: '{{ value_json == 1 }}'


```

And the shell script which `curl`s the `motion` API ([`switch_camera_motion_detection.sh`](https://github.com/azogue/hass_config/blob/master/shell/switch_camera_motion_detection.sh)):

```bash
#!/bin/bash
MOTION_IP="$1"
CAMERA="$2"
COMMAND="$3"
if [ $COMMAND = "status" ]
then
    curl -s http://$MOTION_IP:7999/$CAMERA/detection/$COMMAND|grep 'status ACTIVE'|wc -l
else
    curl -s http://$MOTION_IP:7999/$CAMERA/detection/$COMMAND|grep 'Done'|wc -l
fi
exit 0
```

For this script to work, you need to customize your `motion.conf` with these:
```
webcontrol_html_output off
webcontrol_port 7999
webcontrol_localhost off
```

And then, you can try it manually running these commands from the CLI:
```bash
curl -s http://MEYE_IP:7999/CAM_ID/detection/status
curl -s http://MEYE_IP:7999/CAM_ID/detection/start
curl -s http://MEYE_IP:7999/CAM_ID/detection/pause
```

Now you have, for each camera, **a switch controlling the motion detection**, and a **binary sensor reflecting the motion state**.
