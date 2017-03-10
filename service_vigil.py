# -*- coding: utf-8 -*-

"""
Script para observar el status de los servicios en uso y anotar los cambios en un fichero CSV

```
    sudo /srv/homeassistant/bin/python /home/homeassistant/vigilconf/hass_conf/service_vigil.py old_pwd new_pwd

#  /10 * * * * sudo /srv/homeassistant/bin/python3.6 /home/homeassistant/.homeassistant/service_vigil.py
```
"""
from dateutil.parser import parse
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
SERVICES_CHECK = {
    'localhost': {'mask': MASK_STATUS_SERV,
                  'services': ['nginx', 'noip', 'appdaemon', 'home-assistant@homeassistant', 'homebridge']},
    # 'rpi33': {'mask': 'ssh pi@192.168.1.13 ' + MASK_STATUS_SERV,
    #           'services': ['nginx', 'noip', 'appdaemon', 'home-assistant@homeassistant', 'homebridge']},
    'rpi2h': {'mask': 'ssh pi@192.168.1.46 ' + MASK_STATUS_SERV,
              'services': ['appdaemon', 'home-assistant@homeassistant', 'motioneye']},
    'rpi2': {'mask': 'ssh pi@192.168.1.52 ' + MASK_STATUS_SERV,
             'services': ['mpd', 'mopidy', 'shairport-sync', 'upmpdcli', 'appdaemon', 'home-assistant@homeassistant']}
}
LOG_CSVFILE = os.path.join(basedir, 'log_service_status.csv')
# os.chdir(basedir)

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
    key = '{}_{}'.format(machine, service)
    # print(out)
    active_status = list(filter(lambda x: 'Active:' in x, out.splitlines()))
    if active_status:
        act = active_status[0]
        # print(act)
        try:
            date = parse(rg_date.findall(act)[0])
        except IndexError:
            date = None
        # print(date)
        data_services[key] = ('active (running)' in act, date, act)
        if verbose:
            print('  * {:30} Active={} FROM: {}'.format(service + ':', data_services[key][0], data_services[key][1]))
        return data_services[key][0]
    data_services[key] = (False, None, out)
    print('ERROR in {}->{}:\n{}'.format(machine, service, out))
    return False


def _update_csv_log(data_services):
    """
    Check changes in services status, and, if so, updates a csv file. Returns True if any changes.
    :param data_services: dict with service status data
    :return: changed
    :rtype: bool
    """
    write_col_index = write_new_row = False

    col_index = ';'.join(['{0}_{1}_ok;{0}_{1}_start'.format(m, s)
                          for m, d in sorted(SERVICES_CHECK.items()) for s in d['services']])
    col_index += ';\n'
    # print(col_index)
    row_status = ';'.join(['{};{}'.format(*data_services['{}_{}'.format(m, s)])
                           for m, d in sorted(SERVICES_CHECK.items()) for s in d['services']])
    row_status += ';\n'
    # print(row_status)

    if not os.path.exists(LOG_CSVFILE):
        write_col_index = True
        write_new_row = True
    else:
        with open(LOG_CSVFILE) as f:
            last_row = f.readlines()[-1]
        if last_row != row_status:
            write_new_row = True
    if write_col_index or write_new_row:
        if write_col_index:
            rows = [col_index, row_status]
        else:
            rows = [row_status]
        with open(LOG_CSVFILE, 'a') as f:
            f.writelines(rows)
        print('** SERVICE STATUS UPDATED:\n{}'.format(open(LOG_CSVFILE).read()))
        data_services['new_logdata'] = rows
        return True
    return False


if __name__ == '__main__':
    force_send = verbose_mode = False
    if len(sys.argv) > 1:
        verbose_mode = True
        if sys.argv[1] == 'send':
            force_send = True

    d_serv = {}
    for machine_id, data in SERVICES_CHECK.items():
        mask = data['mask']
        if verbose_mode:
            print('\n---> SERVICE STATUS IN {}:'.format(machine_id.upper()))
        for service_i in data['services']:
            check_service_status(machine_id, mask, service_i, d_serv, verbose_mode)

    if _update_csv_log(d_serv) or force_send:

        subject = '*** {} [{}] - SERVICES STATUS'.format(BASE_URL, EXT_IP)
        msg = ''
        for machine_id, data in sorted(SERVICES_CHECK.items()):
            mask = data['mask']
            msg += '\n---> SERVICE STATUS OF {}:\n'.format(machine_id.upper())
            for service_i in data['services']:
                key = '{}_{}'.format(machine_id, service_i)
                msg += '  * {:30} Active={} FROM: {}\n\t Raw: "{}"\n'.format(service_i + ':', *d_serv[key])
        if 'new_logdata' in d_serv:
            subject += ' CHANGED!'
            msg += '\n\nNEW_LOGDATA:\n{}'.format(d_serv['new_logdata'])

        # Notificación:
        if verbose_mode:
            print(msg)
        _send_push_notification(PB_TOKEN, subject, msg, EMAIL_TARGET)
        _send_email(subject, msg, EMAIL_TARGET)
        if EMAIL_DEBUG is not None:
            _send_email(subject, msg, EMAIL_DEBUG)
    sys.exit(0)
