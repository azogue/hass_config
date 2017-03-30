# -*- coding: utf-8 -*-
#  sudo /srv/homeassistant/bin/python /home/homeassistant/.homeassistant/check_motion_config.py
"""
# Este script está preparado para ejecutarse en el boot, de forma que corrija la configuración de cámaras en MotionEye
hasta que se implemente la edición de comando en final de evento ('on_event_end').
* Ahora sobreescribe la configuración, de ahí la necesidad de este script.

Edit conf file para rellenar:
on_event_end /usr/local/lib/python2.7/dist-packages/motioneye/scripts/relayevent.sh
    "/etc/motioneye/motioneye.conf" stop %t;
    curl -X POST -H "x-ha-access: HASSPWD" -H "Content-Type: application/json"
    -d \'{"state": "off", "attributes": {"friendly_name": "Movimiento en Vídeo de Zona 2"}}\'
    http://127.0.0.1:8123/api/states/binary_sensor.entity_cammov;\n'
"""
import json
import os
import sys
import yaml


MASK_ENTITY_ZONA = 'binary_sensor.cam_mov_zona_{}'
MASK_FNAME_ZONA = 'Movimiento en Vídeo de Zona {}'
CAMERAS_ZONAS = {1: 2, 2: 1}  # motion_thread: num_zona

basedir = os.path.dirname(os.path.abspath(__file__))
PATH_SECRETS = os.path.join(basedir, 'secrets.yaml')

# Configuration
with open(PATH_SECRETS) as _file:
    SECRETS = yaml.load(_file.read())
HASS_PWD = SECRETS['hass_pw']

MASK_MOTION_CONF_THREAD = '/etc/motioneye/thread-{}.conf'
FIELDS_STATES = {'on_event_end': ('off', 'stop'), 'on_event_start': ('on', 'start')}
TEMPLATE_CMD = '''/usr/local/lib/python2.7/dist-packages/motioneye/scripts/relayevent.sh '''
TEMPLATE_CMD += '''"/etc/motioneye/motioneye.conf" {} %t; curl -X POST -H "x-ha-access: {}" '''
TEMPLATE_CMD += '''-H "Content-Type: application/json" '''


def _make_curl_cmd(field, zona):
    ha_state, motion_ev = FIELDS_STATES[field]
    ha_json = dict(state=ha_state, attributes=dict(friendly_name=MASK_FNAME_ZONA.format(zona),
                                                   device_class='motion', homebridge_hidden=True))
    ha_json = json.dumps(ha_json, ensure_ascii=False)

    cmd = TEMPLATE_CMD.format(motion_ev, HASS_PWD)
    cmd += '''-d \'{}\' http://127.0.0.1:8123/api/states/{};'''.format(ha_json, MASK_ENTITY_ZONA.format(zona))
    return cmd


def check_motion_config_meye_cameras():
    """Lee la configuración de las cámaras de MotionEye en Motion y comprueba que los comandos sean correctos.
    De no ser así, los corrige."""
    hay_cambios = False

    for th, zona in CAMERAS_ZONAS.items():
        hay_cambios_t = False
        p_thread = MASK_MOTION_CONF_THREAD.format(th)
        with open(p_thread) as f:
            lines_conf_i = f.readlines()
        lines_conf_i_out = lines_conf_i.copy()
        for i, l in enumerate(lines_conf_i):
            for field in FIELDS_STATES.keys():
                if l.startswith(field):
                    cmd = _make_curl_cmd(field, zona)
                    if cmd not in l:
                        new_l = '{} {}'.format(field, cmd)
                        lines_conf_i_out[i] = new_l
                        print('** BAD LINE IN "{}" [{}]. Change:\n-> {}---> {}'.format(field, p_thread, l, new_l))
                        hay_cambios_t = True
        if hay_cambios_t:
            hay_cambios = True
            print('**** REWRITING "{}"'.format(p_thread))
            with open(p_thread, 'w') as f:
                f.writelines(lines_conf_i_out)
    return hay_cambios


if __name__ == '__main__':
    restart_meye = check_motion_config_meye_cameras()
    if restart_meye:
        print('****** RESTARTING MOTIONEYE (sudo systemctl restart motioneye) to get the changes in config...')
        os.system('sudo systemctl restart motioneye')
    sys.exit(0)
