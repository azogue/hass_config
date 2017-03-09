#!/srv/homeassistant/bin/python
# -*- coding: utf-8 -*-
"""
Script for getting the internal and external IP address of the localhost and notify it via email and/or Pushbullet.
- It gets the config info from the secrets.yaml file of the Home Assistant configuration.
- Uses libraries used by HASS in `deps/`
- Perfect for using it within a CRON job on boot:

```
sudo -u homeassistant /srv/homeassistant/bin/python3.6 /home/homeassistant/.homeassistant/cronip.py -s -nw -extra -e

CRONJOB:
@reboot sudo -u homeassistant /srv/homeassistant/bin/python3.6 /home/homeassistant/.homeassistant/cronip.py -s
```

"""
import datetime as dt
import logging
import os
import re
import subprocess
import time
import sys


BASEDIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASEDIR, 'deps'))


import psutil
from pushbullet import Pushbullet
import smtplib
import socket
import yaml


VERBOSE = True
WAIT_INIT = 20
TIME_PAUSE = 5

LOG_LEVEL = 'INFO'  # 'DEBUG'
PATH_SECRETS = os.path.join(BASEDIR, 'secrets.yaml')
LOG_FILE = os.path.join(BASEDIR, 'cronip.log')
EXT_IP_FILE = os.path.join(BASEDIR, 'external_ip.txt')

# Configuration
with open(PATH_SECRETS) as _file:
    SECRETS = yaml.load(_file.read())
PB_TOKEN = SECRETS['pushbullet_api_key']
PB_TARGET = SECRETS['pb_target'].split('/')[1]
EMAIL_TARGET = SECRETS['email_target']
EMAIL_SERVER_USER = SECRETS['hass_email']
EMAIL_SERVER_PWD = SECRETS['hass_email_pw']
PUSH_INITS = SECRETS.get('push_inits', False)
EMAIL_INITS = SECRETS.get('email_inits', False)
EMAIL_DEBUG = None
if 'debug_mode' in SECRETS:
    EMAIL_DEBUG = SECRETS['debug_mode']


def _get_cmd_output(cmd, default=None, verbose=True, **kwargs):
    list_cmd = cmd.split()
    # kwargs.update({'stdout': subprocess.PIPE})
    try:
        out = subprocess.check_output(list_cmd, **kwargs).decode()
        if out.endswith('\n'):
            return True, out[:-1]
        return True, out
    except subprocess.TimeoutExpired as e:
        time.sleep(TIME_PAUSE / 2)
        if verbose:
            print('\nERROR subprocess.CalledProcessError: {} invocando el comando: {}'.format(e, cmd))
    except subprocess.CalledProcessError as e:
        if verbose:
            print('\nERROR subprocess.CalledProcessError: {} invocando el comando: {}'.format(e, cmd))
    except FileNotFoundError as e:
        if verbose:
            print('\nERROR FileNotFoundError: {} invocando el comando: {}'.format(e, cmd))
    if default:
        return False, default
    return False, 0


def send_push_notification(title, content, target):
    """Sends a PB text notification."""
    pb = Pushbullet(PB_TOKEN)
    pb.push_note(title, content, email=target)
    return True


def send_email(email_subject, email_content, target):
    """Sends a text email."""
    try:
        smtpserver = smtplib.SMTP("smtp.gmail.com", 587)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.login(EMAIL_SERVER_USER, EMAIL_SERVER_PWD)
        email = 'To: {}\nFrom: {}\nSubject: {}\n\n{}\n'.format(target, EMAIL_SERVER_USER, email_subject, email_content)
        smtpserver.sendmail(EMAIL_SERVER_USER, target, email.encode())
        smtpserver.close()
        logging.info('EMAIL SENDED={}'.format(email_subject))
        return True
    except smtplib.SMTPException as e:
        logging.error('EMAIL NOT SENDED={}; SMTPException: {}'.format(email_subject, e))
    except socket.gaierror as e:
        logging.error('EMAIL NOT SENDED={}; socket.gaierror: {}; ¿Hay conexión a internet??'.format(email_subject, e))
    except Exception as e:
        logging.error('EMAIL NOT SENDED={}; Exception: {}'.format(email_subject, e))
    return False


def _notify_email(d_result, extra_info=False, with_email=False):
    email_subject = 'RPI {} started! [IP: {}, {}]'.format(d_result['name'], d_result['ip_ext'], d_result['IP'])
    confs = ['name', 'user', 'path_home', 'IP']
    info_host = '\n'.join(['  -> {:10} : {}'.format(k.upper(), d_result[k]) for k in confs])
    if extra_info:
        template = 'Configuración:\n{}\n\n**IP EXTERNA**: {}\n(Obtención en {:.3f} segs)\n\nIFCONFIG:\n{}'
        email_content = template.format(info_host, d_result['ip_ext'], d_result['time_ip_ext'], d_result['ifconfig'])
    else:
        template = 'Configuración:\n{}\n\n**IP EXTERNA**: {}\n(Obtención en {:.3f} segs)'
        email_content = template.format(info_host, d_result['ip_ext'], d_result['time_ip_ext'])
    if (PB_TARGET is not None) and PUSH_INITS:
        send_push_notification(email_subject, email_content, PB_TARGET)
    ok_email = True
    if with_email and (EMAIL_TARGET is not None) and EMAIL_INITS:
        ok_email = send_email(email_subject, email_content, EMAIL_TARGET)
        if ok_email:
            logging.debug('SALIDA OK de name:{}, file:{}'.format(__name__, __file__))
        else:
            logging.debug('SALIDA SIN NOTIFICAR POR EMAIL de name:{}, file:{}'.format(__name__, __file__))
    if ok_email and (EMAIL_DEBUG is not None):
        send_email(email_subject, email_content, EMAIL_DEBUG)


def get_usb_devices():
    """
    Bus 001 Device 004: ID 0781:5567 SanDisk Corp. Cruzer Blade
    Bus 001 Device 006: ID 0930:6545 Toshiba Corp. Kingston DataTr...
    Bus 001 Device 005: ID 0bda:2838 Realtek Semiconductor Corp. RTL2838 DVB-T
    Bus 001 Device 004: ID 7392:7811 Edimax Technology Co., Ltd EW-7811Un 802.11n Wireless Adapter [Realtek RTL8188CUS]
    Bus 001 Device 003: ID 0424:ec00 Standard Microsystems Corp. SMSC9512/9514 Fast Ethernet Adapter
    Bus 001 Device 002: ID 0424:9514 Standard Microsystems Corp.
    Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
    """
    regexpr_usb = re.compile(r'Bus (?P<Bus>\d{1,3}) Device (?P<Device>\d{1,3}): ID (?P<ID>.+?) (?P<Name>.+?)$')
    if sys.platform == 'darwin':
        return []
    else:
        ok_lsusb, lsusb = _get_cmd_output('/usr/bin/lsusb')
        assert ok_lsusb
        return [regexpr_usb.search(l).groupdict() for l in lsusb.splitlines()]


def get_machine_info(verbose, exclude_wlan=False):
    """Gets some info about the localhost."""
    # Machine
    # NAME, IP, USER, IS_MAC, NUM_CPU, BOOT_TIME
    regexpr_ifconfig = re.compile(r'inet (addr:)?(?P<IP>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) ')
    # regexpr_IP = re.compile(r'(?P<IP1>\d{1,3})\.(?P<IP2>\d{1,3})\.(?P<IP3>\d{1,3})\.(?P<IP4>\d{1,3})')

    def _extract_ifconfig(res_ifconfig):
        # IP(s) de la máquina local:
        # regexpr_ip = re.compile(r'(?P<IP1>\d{1,3})\.(?P<IP2>\d{1,3})\.(?P<IP3>\d{1,3})\.(?P<IP4>\d{1,3})')
        busqueda = regexpr_ifconfig.findall(res_ifconfig)
        ips_locales = [b[1] for b in busqueda if b[1] != '127.0.0.1']
        # ips_locales_n = [[int(n) for n in regexpr_ip.findall(ip)[0]] for ip in ips_locales]
        return ips_locales  # , ips_locales_n

    # def _extract_iwconfig(data):
    #     tokens = [l.split() for l in data.splitlines()]
    #     c = 0
    #     wificon = {}
    #     while c < len(tokens):
    #         if len(tokens[c]) > 3 and tokens[c][0] == 'wlan0':
    #             try:
    #                 wificon['ESSID'] = re.findall('ESSID:"(.*)"', tokens[c][3])[0]
    #                 wificon['type_conection'] = tokens[c][2]
    #                 c += 2
    #                 wificon['bitrate'] = re.findall('Rate=?:?(.*)', tokens[c][1])[0] + ' {}'.format(tokens[c][2])
    #                 try:
    #                     wificon['power'] = re.findall('Tx-Power=(.*)', tokens[c][3])[0] + ' {}'.format(tokens[c][4])
    #                 except IndexError:
    #                     pass
    #                 c += 2
    #                 wificon['power_mng'] = re.findall('Management:(.*)', tokens[c][1])[0]
    #                 c += 1
    #                 wificon['link_quality'] = re.findall('Quality=(.*)', tokens[c][1])[0]
    #                 wificon['signal_level'] = re.findall('level=(.*)', tokens[c][3])[0] + ' {}'.format(tokens[c][4])
    #             except Exception as e:
    #              print('Error extracting iwconfig output:\nEXCEPTION: {}\nTOKENS:\n{}\nFILA: {}'.format(e, tokens, c))
    #         c += 1
    #     return wificon

    # Nombre, tipo, user de la máquina local:
    is_mac = True if sys.platform == 'darwin' else False
    ok_name, name = _get_cmd_output('/bin/hostname', default='rpi')
    ok_current_user, current_user = _get_cmd_output('/usr/bin/id -u -n', default='pi')
    # IP(s) de la máquina local:
    ok_ifconfig_output, ifconfig_output = _get_cmd_output('/sbin/ifconfig', default='IFCONFIG No disponible')
    if exclude_wlan:
        ok_iwconfig_output = iwconfig_output = False
    else:
        ok_iwconfig_output, iwconfig_output = _get_cmd_output('/sbin/iwconfig wlan0',
                                                              default='IWCONFIG No disponible', verbose=False)
    ip, hay_conexion, ips_lan = '127.0.0.1', False, []
    if ok_ifconfig_output:
        ips_lan = _extract_ifconfig(ifconfig_output)
        if len(ips_lan) > 0:
            ip = ips_lan[0]
            hay_conexion = True
    dict_machine = {'is_mac': is_mac, 'name': name, 'user': current_user, 'hay_conexion': hay_conexion, 'IP': ip,
                    'IPs': ips_lan, 'n_IPs': len(ips_lan),
                    'nCPU': (psutil.cpu_count(), psutil.cpu_count(logical=False)),
                    'boot_time': dt.datetime.fromtimestamp(psutil.boot_time())}
    if ok_iwconfig_output:
        dict_machine['iwconfig'] = iwconfig_output
    dict_machine['ifconfig'] = ifconfig_output
    dict_machine['usb_devices'] = get_usb_devices()
    if verbose:
        [print('{0}:\t{1}'.format(k, v)) for k, v in dict_machine.items()]
    return dict_machine


def get_ext_ip(timeout=10):
    """Get the external IP of the localhost."""
    tic = time.time()
    n_retry = 0
    ok, ip, time_obtain = False, '', 1e6
    while n_retry < 2:
        # ok, ip_ext = _get_cmd_output('/usr/bin/curl ifconfig.me', default=None, timeout=timeout)
        ok, ip_ext = _get_cmd_output('wget http://ipinfo.io/ip -qO -', default=None, timeout=timeout)
        # print('Intento de ip_ext: {}'.format(ip_ext))
        toc = time.time()
        if ok:
            # ip = ip_ext[:-1]
            ip = ip_ext
        time_obtain = toc - tic

        try:
            with open(EXT_IP_FILE) as file_ip:
                old_ip = file_ip.read()
        except FileNotFoundError:
            old_ip = ''

        if ok and (not old_ip or old_ip != ip_ext):
            with open(EXT_IP_FILE, 'w') as file_ip:
                file_ip.write(ip_ext)
                mascara = 'WRITING NEW EXT_IP in {}: {}. T_OBTENCIÓN: {:.2f} seg'
        elif not ok:
            mascara = 'ERROR EXT_IP ({}) TIMEOUT?: {}. T_OBTENCIÓN: {:.2f} seg'
            n_retry += 1
        else:
            mascara = 'OK EXT_IP ({}) NOT CHANGING: {}. T_OBTENCIÓN: {:.2f} seg'
            n_retry = 1000
        logging.debug(mascara.format(EXT_IP_FILE, ip, time_obtain))
    return ok, ip, time_obtain


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description='RPI START NOTIFY SERVICE')
    p.add_argument('-s', '--silent', action='store_true', help='HIDES OUTPUT')
    p.add_argument('-e', '--email', action='store_true', help='SENDS EMAIL')
    p.add_argument('-p', '--print', action='store_true', help='PRINT LOG FILE')
    p.add_argument('-nw', '--no-wifi', action='store_true', help="DON'T CHECK WLAN0")
    p.add_argument('--extra', action='store_true', help='REPORT EXTRA INFO')
    p.add_argument('--delete', action='store_true', help='DELETE LOG FILE')
    p.add_argument('--nowait', action='store_true', help="DON'T WAIT FOR NETWORK {} SECS".format(WAIT_INIT))
    args = p.parse_args()
    print(args)
    _verbose = not args.silent

    logging.basicConfig(filename=LOG_FILE, level=LOG_LEVEL, datefmt='%d/%m/%Y %H:%M:%S',
                        format='%(levelname)s [%(filename)s_%(funcName)s] - %(asctime)s: %(message)s')

    if not args.nowait:
        time.sleep(WAIT_INIT)
    path_home = '/home/homeassistant'

    os.chdir(path_home)
    logging.debug('INIT CRONIP con path_home: {}'.format(path_home))

    if args.print:
        with open(LOG_FILE) as f:
            log_lines = f.readlines()
        print('LAST {} LOG ENTRIES:'.format(50))
        [print(l[:-1]) for l in log_lines[-50:]]
    elif args.delete:
        logging.info('LOG DELETED (SIZE=0) --> {}'.format(LOG_FILE))
        print('LOG DELETED (SIZE=0) --> {}'.format(LOG_FILE))
        with open(LOG_FILE, 'w') as f:
            f.write('')
    else:
        results = get_machine_info(_verbose, args.no_wifi)
        results.update({'path_home': path_home})

        ok_ip_ext, ext_ip, time_ip_ext = get_ext_ip()
        msg = 'RESULTADOS:\n{}\n--> IP_EXT: {} (OK: {}, TIME: {} seg)'.format(results, ok_ip_ext, ext_ip, time_ip_ext)
        if _verbose:
            print(msg)
        logging.debug(msg)
        results.update({'hay_ip_ext': ok_ip_ext, 'ip_ext': ext_ip, 'time_ip_ext': time_ip_ext})
        if ok_ip_ext:
            _notify_email(results, args.extra, args.email)
        else:
            second_retry = 0
            while second_retry < 2 and not ok_ip_ext:
                logging.error('NO SE ENCUENTRA IP EXTERNA. IP: {}'.format(results['IP']))
                second_retry += 1
                time.sleep(TIME_PAUSE)
                ok_ip_ext, ext_ip, time_ip_ext = get_ext_ip(timeout=15)
                results.update({'hay_ip_ext': ok_ip_ext, 'ip_ext': ext_ip, 'time_ip_ext': time_ip_ext})
            _notify_email(results, args.extra, args.email)
            logging.info('ENCONTRADA IP EXTERNA. IP: {}'.format(results['ip_ext']))
