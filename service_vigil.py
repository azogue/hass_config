# -*- coding: utf-8 -*-

"""
Script para observar el status de los servicios en uso y anotar los cambios en un fichero JSON, para notificar
al admin via email y/o Pushbullet de los cambios acontecidos.

Diseñado para ejecutarse como tarea CRON cada X minutos.
Uso:
```
    sudo /srv/homeassistant/bin/python /home/homeassistant/vigilconf/hass_conf/service_vigil.py

    # CRON TASK
    /10 * * * * sudo /srv/homeassistant/bin/python3.6 /home/homeassistant/.homeassistant/service_vigil.py
```

El fichero JSON tiene la siguiente estructura:
```
LOG_JSONFILE = { machine: { serv_1: { state: True, ts_ini: dt.datetime,
                                      last_state: True, last_ts_ini: dt.datetime, changed: False},
                            serv_2: { state: True, ts_ini: dt.datetime,
                                      last_state: True, last_ts_ini: dt.datetime, changed: False}}
```
"""
from dateutil.parser import parse
import json
import os
import re
import socket
from subprocess import check_output, CalledProcessError, STDOUT
import sys


basedir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(basedir, 'deps'))


from pushbullet import Pushbullet
import smtplib
import yaml


MASK_STATUS_SERV = '/bin/systemctl status {}'
MASK_TS = '{:%Y-%m-%d %H:%M:%S}'
SERVICES_CHECK = {
    'localhost': {'mask': MASK_STATUS_SERV,
                  'services': ['nginx', 'noip2', 'appdaemon', 'home-assistant@homeassistant', 'homebridge']},
    # 'rpi33': {'mask': 'ssh pi@192.168.1.13 ' + MASK_STATUS_SERV,
    #           'services': ['nginx', 'noip', 'appdaemon', 'home-assistant@homeassistant', 'homebridge']},
    'rpi2h': {'mask': 'ssh pi@192.168.1.46 ' + MASK_STATUS_SERV,
              'services': ['appdaemon', 'home-assistant@homeassistant', 'motioneye']},
    'rpi2': {'mask': 'ssh pi@192.168.1.52 ' + MASK_STATUS_SERV,
             'services': ['mpd', 'mopidy', 'shairport-sync', 'appdaemon', 'home-assistant@homeassistant']}
}
LOG_JSONFILE = os.path.join(basedir, 'log_service_status.json')
PATH_SECRETS = os.path.join(basedir, 'secrets.yaml')
EXT_IP_FILE = os.path.join(basedir, 'external_ip.txt')
try:
    with open(EXT_IP_FILE) as _file:
        EXT_IP = _file.read()
except FileNotFoundError:
    EXT_IP = '???.???.???.???'

# Configuration
with open(PATH_SECRETS) as _file:
    SECRETS = yaml.load(_file.read())
PB_TOKEN = SECRETS['pushbullet_api_key']
EMAIL_SERVER_USER = SECRETS['hass_email']
EMAIL_SERVER_PWD = SECRETS['hass_email_pw']
EMAIL_TARGET = SECRETS['email_target']
EMAIL_DEBUG = None
if 'debug_mode' in SECRETS:
    EMAIL_DEBUG = SECRETS['debug_mode']
BASE_URL = SECRETS['base_url']


def _send_push_notification(pb_token, title, content, target):
    pb = Pushbullet(pb_token)
    pb.push_note(title, content, email=target)
    return True


def _send_email(email_subject, email_content, target):
    try:
        smtpserver = smtplib.SMTP("smtp.gmail.com", 587)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.login(EMAIL_SERVER_USER, EMAIL_SERVER_PWD)
        email = 'To: {}\nFrom: {}\nSubject: {}\n\n{}\n'.format(target, EMAIL_SERVER_USER, email_subject, email_content)
        smtpserver.sendmail(EMAIL_SERVER_USER, target, email.encode())
        smtpserver.close()
        print('EMAIL SENDED={} TO {}'.format(email_subject, target))
        return True
    except smtplib.SMTPException as e:
        print('EMAIL NOT SENDED={}; SMTPException: {}'.format(email_subject, e))
    except socket.gaierror as e:
        print('EMAIL NOT SENDED={}; socket.gaierror: {}; ¿Hay conexión a internet??'.format(email_subject, e))
    except Exception as e:
        print('EMAIL NOT SENDED={}; Exception: {}'.format(email_subject, e))
    return False


def check_service_status(machine, mask_cmd, service, data_services, verbose=False):
    """
    Checks service status
    :param machine: machine identifier ('localhost' or a friendly name for a remote machine)
    :param mask_cmd: string mask to make the status command (in localhost or ssh'ing a remote machine)
    :param service: service name
    :param data_services: dict for recolecting service status data
    :param verbose: print info in stdout
    :return: is_alive
    :rtype: bool

    """
    rg_date = re.compile('since \w+ (.+) \w+;')
    cmd = mask_cmd.format(service)
    try:
        out = check_output(cmd.split(), stderr=STDOUT).decode()
    except CalledProcessError as e:
        out = e.output.decode()
    active_status = list(filter(lambda x: 'Active:' in x, out.splitlines()))
    if active_status:
        act = active_status[0]
        state = 'active (running)' in act
        try:
            date = MASK_TS.format(parse(rg_date.findall(act)[0]))
        except IndexError:
            date = None
        # print(date)
        if ('ts_ini' not in data_services[machine][service]) or data_services[machine][service]['ts_ini'] != date:
            data_services[machine][service]['changed'] = True
            if 'ts_ini' in data_services[machine][service]:  # not first sample
                data_services[machine][service]['last_state'] = data_services[machine][service]['state']
                data_services[machine][service]['last_ts_ini'] = data_services[machine][service]['ts_ini']
            else:
                data_services[machine][service]['last_state'] = state
                data_services[machine][service]['last_ts_ini'] = date
            data_services[machine][service]['state'] = state
            data_services[machine][service]['ts_ini'] = date
        else:
            data_services[machine][service]['changed'] = False
        if verbose:
            print('  * {0:30} Changed? {changed} --> ACT:{state}; SINCE {ts_ini}. Last st:{last_state} [{last_ts_ini}]'
                  .format(service + ':', **data_services[machine][service]))
        return data_services[machine][service]['state']
    else:
        data_services[machine][service] = {'state': False,
                                           'ts_ini': None,
                                           'last_state': data_services[machine][service].get('state', False),
                                           'last_ts_ini': data_services[machine][service].get('ts_ini', None),
                                           'changed': data_services[machine][service].get('state', False) is True}
    print('ERROR in {}->{}:\n{}'.format(machine, service, out))
    return False


def _update_json_log(data_services):
    """
    Check changes in services status, and, if so, updates a json file. Returns changes.
    :param data_services: dict with service status data
    :return: changed_services
    :rtype: dict
    """
    write = False
    if not os.path.exists(LOG_JSONFILE):
        write = True
        serv_changes = data_services
    else:
        serv_changes = {}
        with open(LOG_JSONFILE) as _f:
            last_data_services = json.loads(_f.read())
        for m in data_services.keys():
            if m not in last_data_services:
                serv_changes[m] = data_services[m]
                write = True
            else:
                for s in data_services[m].keys():
                    if ((s not in last_data_services[m]) or
                            (data_services[m][s]['state'] != last_data_services[m][s]['state']) or
                            (data_services[m][s]['ts_ini'] != last_data_services[m][s]['ts_ini'])):
                        if m in serv_changes.keys():
                            serv_changes[m][s] = data_services[m][s]
                        else:
                            serv_changes[m] = {s: data_services[m][s]}
                        write = True
    if write:
        with open(LOG_JSONFILE, 'w') as _f:
            _f.write(json.dumps(data_services))
        print('\n\n** SERVICE STATUS UPDATED:\n\n{}'.format(json.loads(open(LOG_JSONFILE).read())))
    return serv_changes


if __name__ == '__main__':
    force_send = verbose_mode = False
    if len(sys.argv) > 1:
        verbose_mode = True
        if sys.argv[1] == 'send':
            force_send = True

    # Prev state in disk
    if os.path.exists(LOG_JSONFILE):
        with open(LOG_JSONFILE) as f:
            d_serv = json.loads(f.read())
    else:
        d_serv = {machine_id: {service_i: {'changed': True} for service_i in data['services']}
                  for machine_id, data in SERVICES_CHECK.items()}

    # Check services
    for machine_id, data in SERVICES_CHECK.items():
        if verbose_mode:
            print('\n---> SERVICE STATUS IN {}:'.format(machine_id.upper()))
        for service_i in data['services']:
            check_service_status(machine_id, data['mask'], service_i, d_serv, verbose_mode)

    # Notify changes & update JSON in disk
    changes = _update_json_log(d_serv)
    if changes or force_send:
        if not changes:
            changes = d_serv
        # Msg generation:
        subject = 'Systemd Status changed in {}'.format(', '.join(sorted(changes.keys())))
        msg = 'Service vigil in {} [{}]\n'.format(EXT_IP, BASE_URL)
        msg_extra, with_extra = '\n\n* Services with no change in status:\n', False
        for machine_id, data_mi in sorted(changes.items()):
            machine_title = '\n-> Status of {}:\n'.format(machine_id.upper())
            if any([changes[machine_id][service_i]['changed'] for service_i in data_mi.keys()]):
                msg += machine_title
            if any([not changes[machine_id][service_i]['changed'] for service_i in data_mi.keys()]):
                msg_extra += machine_title
                with_extra = True
            for service_i in data_mi.keys():
                if changes[machine_id][service_i]['changed']:
                    mask = '  * {0:30}  ----> ACT:{state}; SINCE {ts_ini}. Last st:{last_state} [{last_ts_ini}]\n'
                    msg += mask.format(service_i + ':', **changes[machine_id][service_i])
                else:
                    mask = '  * {0:30}   ==   ACT:{state}; SINCE {ts_ini}. Last st:{last_state} [{last_ts_ini}]\n'
                    msg_extra += mask.format(service_i + ':', **changes[machine_id][service_i])

        # Notificación:
        if verbose_mode:
            print(msg + msg_extra)
        _send_push_notification(PB_TOKEN, subject, msg, EMAIL_TARGET)
        _send_email(subject, msg + msg_extra if with_extra else msg, EMAIL_TARGET)
        # if EMAIL_DEBUG is not None:
        #     _send_email(subject, msg, EMAIL_DEBUG)
    sys.exit(0)
