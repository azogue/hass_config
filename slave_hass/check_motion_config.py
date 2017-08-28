# -*- coding: utf-8 -*-
"""
# Check or modify the MotionEye cameras config to use Home Assistant sensors.

This script reads the ME camera config files (`/etc/motioneye/thread-ID.conf`)
and then checks the commands asigned to some motion detection events:
 * 'on_event_start', 'on_event_end', 'on_camera_lost' and 'on_camera_found'

The intention is controlling Home Assistant binary sensors with these events,
so, when a 'on_event_start' or a 'on_camera_lost' happens, a binary sensor gets
activated ("on" state), and when 'on_event_stop' or 'on_camera_found' event
happens, it changes to "off".

The existence of this script is because not all events are implemented in the
MotionEye Web UI to `motion`, and when you change something in the UI, ME writes
a new `thread-ID.conf`, removing the extra commands used to `curl` the state of
one binary motion sensor for each ME camera. This script fixes the config for
the events of interest, leaving the rest of the camera config untouched.

This python script is intended to run at startup with sudo powers, because it
needs permission to write in the MotionEye cameras config files, which there
are in `/etc/motioneye`.

To do that, edit your CRON file (`crontab -e`) and add:
```
@reboot sudo /srv/homeassistant/bin/python /home/homeassistant/.homeassistant/check_motion_config.py
```

Replace `/srv/homeassistant/bin/python` for your python interpreter if the path
is not the same as mine. I use the HA python bin to ensure the `yaml` library
is installed, because I use it to read the Home Assistant API password from
my `secrets.yaml` file. But you can remove it and set your password explicitly
in this script, as the rest of the HA config is, and then run it from any python binary.

## You need to customize this script and change these acordingly:

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
"""
import json
import os
import sys
import yaml

# --------------- Start of custom configuration --------------

# MotionEye cameras to HA binary sensors:
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

# Home Assistant configuration
HA_HOST = "127.0.0.1"  # If HA runs in the same host than MotionEye
HA_PORT = 8123
HA_PROTOCOL = "http"

# Read Home Assistant configuration to get the API password
basedir = os.path.dirname(os.path.abspath(__file__))
PATH_SECRETS = os.path.join(basedir, 'secrets.yaml')
with open(PATH_SECRETS) as _file:
    SECRETS = yaml.load(_file.read())
HA_API_PASSWORD = SECRETS['hass_pw']

# --------------- End of custom configuration --------------

MEYE_RESTART_COMMAND = "sudo systemctl restart motioneye"
MEYE_CONFIG_PATH = "/etc/motioneye/motioneye.conf"
MASK_MEYE_CONF_THREAD = '/etc/motioneye/thread-{}.conf'
MEYE_EVENTS_FIELDS_STATES = {
    'on_event_end': ('off', 'stop'),
    'on_event_start': ('on', 'start'),
    'on_camera_lost': ('on', 'start'),
    'on_camera_found': ('off', 'stop')
}

TEMPLATE_CMD = ('/usr/local/lib/python2.7/dist-packages/motioneye/scripts/'
                'relayevent.sh "/etc/motioneye/motioneye.conf" {} %t; '
                'curl -X POST -H "x-ha-access: {}" '
                '-H "Content-Type: application/json" ')


def _make_curl_cmd(meye_event: str, ha_sensor_attrs: dict) -> str:
    """Make the config line for each MotionEye event."""
    ha_state, meye_action = MEYE_EVENTS_FIELDS_STATES[meye_event]
    entity_id = ha_sensor_attrs.pop("entity_id")
    ha_sensor_state = {
        "state": ha_state,
        "attributes": ha_sensor_attrs
    }

    cmd = '/usr/local/lib/python2.7/dist-packages/motioneye/scripts/'
    cmd += 'relayevent.sh '
    cmd += '"/etc/motioneye/motioneye.conf" {} %t; '.format(meye_action)
    cmd += 'curl -X POST -H "x-ha-access: {}" '.format(HA_API_PASSWORD)
    cmd += '-H "Content-Type: application/json" '
    cmd += '-d \'{}\' '.format(json.dumps(ha_sensor_state, ensure_ascii=False))
    cmd += '{}://{}:{}/api/states/{};\n'.format(
        HA_PROTOCOL, HA_HOST, HA_PORT, entity_id)
    return cmd


def check_meye_cameras_motion_config() -> bool:
    """Check (and fix) the MotionEye config to integrate cameras in HA.

    Read the `thread-X.conf` camera config files and, if needed, fix it
    to use Home Assistant motion binary sensors when motion events happen.

    As this script needs to read and write protected files in the MotionEye
    configuration, `sudo` powers are needed.
    """
    config_changes = False  # General flag

    for meye_id_cam, ha_bin_sensor_conf in MEYE_CAMERAS_BIN_SENSORS.items():
        cam_config_changes = False  # Cam flag
        meyecam_conf_path = MASK_MEYE_CONF_THREAD.format(meye_id_cam)
        with open(meyecam_conf_path) as f:
            lines_conf_i = f.readlines()
        lines_conf_i_out = lines_conf_i.copy()
        events_to_check = list(MEYE_EVENTS_FIELDS_STATES.keys())
        for i, l in enumerate(lines_conf_i):
            for meye_event in MEYE_EVENTS_FIELDS_STATES:
                if l.startswith(meye_event):
                    cmd = _make_curl_cmd(meye_event, ha_bin_sensor_conf.copy())
                    if cmd not in l:
                        new_l = '{} {}'.format(meye_event, cmd)
                        lines_conf_i_out[i] = new_l
                        print('** BAD LINE FOR EVENT "{}" IN [{}]. '
                              'Change line[{}] for line[{}]'
                              .format(meye_event, meyecam_conf_path,
                                      len(l), len(new_l)))
                        cam_config_changes = True
                    events_to_check.remove(meye_event)
        # Now add the non included events:
        if events_to_check:
            cam_config_changes = True
            lines_conf_i_out += [_make_curl_cmd(ev, ha_bin_sensor_conf.copy())
                                 for ev in events_to_check]

        if cam_config_changes:
            config_changes = True
            print('**** REWRITING "{}"'.format(meyecam_conf_path))
            print('\n\t-> {}\n'.format('\t-> '.join(lines_conf_i_out)))
            with open(meyecam_conf_path, 'w') as f:
                f.writelines(lines_conf_i_out)
    return config_changes


if __name__ == '__main__':
    if check_meye_cameras_motion_config():
        print('****** RESTARTING MOTIONEYE ({}) '
              'to get the changes in config...'.format(MEYE_RESTART_COMMAND))
        os.system(MEYE_RESTART_COMMAND)
    sys.exit(0)
