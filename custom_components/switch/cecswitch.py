# -*- coding: utf-8 -*-
"""
CEC Kodi Switch

Simple switch for turn on / off the TV attached to one Raspberry PI running KODI with `script.json-cec` add-on.

* For turning ON (CECActivateSource()), The KODI JSONRPC API does it OK
* For turning OFF (Standby order), The KODI JSONRPC API fails (with my current config: RPI3_OSMC_last + Toshiba TV),
  so, with the proper CEC config in OSMC-KODI (turn all off in exit, but no action in init), I'm calling the
  `media_player.kodi` service to turn off (HASS Kodi platform config with `turn_off_action: quit`).

  Not anymore:
    so I'm doing it the very wrong way: I'm sshing in the remote Kodi_RPI to run `cec-client` and go standby.
    Problem is, at that moment, Kodi CEC goes lost, so, before I turn ON the TV again,  I have to some way restart KODI.
    I'm killing it without any pity, sorry.
  But you can use this 'brute-force' method if you can ssh to the kodi machine with public key auth (and no password).
  For that, append `ssh: ssh_user` to the switch config in Home Assistant:

Example yaml config:
```
    - platform: cecswitch
      name: "TV Salón"
      host: "192.168.1.56"
      port: 8080  # (optional)
      username: "osmc"  # (optional)
      password: "osmc"  # (optional)
```

"""
import asyncio
import logging
import subprocess
import voluptuous as vol
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from homeassistant.util import utcnow, as_local
import requests
import json


_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:kodi'
DEFAULT_NAME = 'Kodi CEC Switch'
DEFAULT_PORT = 8080
DEFAULT_USER = ''
DEFAULT_PASS = ''
CONF_SSH = 'ssh'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USER): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASS): cv.string,
    vol.Optional(CONF_SSH, default=None): cv.string,
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the CEC Kodi switch."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    kodi_user = config.get(CONF_USERNAME)
    kodi_passwd = config.get(CONF_PASSWORD)
    auth = None
    if kodi_user and kodi_passwd:
        auth = (kodi_user, kodi_passwd)
    ssh_user = config.get(CONF_SSH)

    # Create switches:
    switches = [CECSwitch(hass, name, host, port, auth, ssh_user)]
    _LOGGER.info('CEC switch platform "{}" loaded:\n * {}'
                 .format(name, '\n * '.join([str(s) for s in switches])))
    if not switches:
        _LOGGER.error("No switches added")
        return False
    async_add_devices(switches)
    return True


class CECSwitch(SwitchDevice):
    """Representation of a KODI CEC switch."""

    def __init__(self, hass, name, host, port, auth, ssh_user):
        """Initialize the CECSwitch."""
        self.hass = hass
        self._name = name
        self._host = host
        self._port = port
        self._url_base = 'http://{}:{}/'.format(self._host, self._port)
        self._auth = auth
        self._ssh_user = ssh_user
        self._use_ssh_to_turnoff = self._ssh_user is not None
        self._state = False
        self.update()

    def _run_kodi_cec(self, command="toggle"):
        """Run Kodi CEC add-on with parameters via JSONRPC API."""
        _LOGGER.debug('RUN_KODI_CEC')
        payload_cec_addon = {"jsonrpc": "2.0", "method": "Addons.ExecuteAddon", "id": 1,
                             "params": {"addonid": "script.json-cec", "params": {"command": command}}}
        data = {"request": json.dumps(payload_cec_addon)}
        r = requests.get(self._url_base + 'jsonrpc', params=data, auth=self._auth,
                         headers={'Content-Type': 'application/json'}, timeout=5)
        if r.ok:
            return True
        _LOGGER.error('KODI NOT PRESENT? -> {}'.format(r.content))
        return False

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
        _LOGGER.debug('{}: STATE IS ON? {}'.format(as_local(utcnow()), self._state))
        return self._state

    @property
    def name(self):
        """The name of the switch."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def toggle(self):
        """Toggle the switch."""
        if self._state:
            _LOGGER.info('TOGGLE FROM ON TO OFF')
            self.turn_off()
        else:
            _LOGGER.info('TOGGLE FROM OFF TO ON')
            self.turn_on()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        _LOGGER.debug('CMD ON: run_kodi_cec("activate")')
        self._run_kodi_cec("activate")
        self._state = True
        self.update_ha_state()
        _LOGGER.info('SWITCH TURN ON')

    def turn_off(self):
        """Turn the switch off."""
        if self._use_ssh_to_turnoff:
            # SSH commands (cec-client & sudo kill commands):
            ssh_mask = 'ssh {}@{} "{}"'
            off_command = '/bin/echo "standby 0" | /usr/osmc/bin/cec-client -d 1 -s'
            subprocess.call(ssh_mask.format(self._ssh_user, self._host, off_command), shell=True)
            _LOGGER.debug('CMD OFF: ' + ssh_mask.format(self._ssh_user, self._host, off_command))
            # Killing KODI!
            get_kodi_pid_cmd = "/bin/ps aux|grep '^osmc'|grep kodi.bin"
            get_kodi_pid_local = " |grep kodi/ |awk '{print $2}' "
            cmd = ssh_mask.format(self._ssh_user, self._host, get_kodi_pid_cmd) + get_kodi_pid_local
            out = subprocess.check_output(cmd, shell=True)
            _LOGGER.debug('CMD KODI PID: {}'.format(cmd))
            if out:
                pid_kodi = int(out.decode().split()[0])
                kill_kodi_cmd = "sudo kill -9 {}".format(pid_kodi)
                subprocess.call(ssh_mask.format(self._ssh_user, self._host, kill_kodi_cmd), shell=True)
                _LOGGER.debug('CMD KILL KODI: {}'.format(ssh_mask.format(self._ssh_user, self._host, kill_kodi_cmd)))
        else:
            data = {"entity_id": "media_player.kodi"}
            self.hass.services.call("homeassistant", "turn_off", service_data=data)
            _LOGGER.debug('CMD OFF: self.hass.services.call("homeassistant", "turn_off", '
                          'service_data={"entity_id": "media_player.kodi"})')
            # _LOGGER.debug('CMD OFF: _run_kodi_cec("standby")')
            # self._run_kodi_cec("standby")
        self._state = False
        self.update_ha_state()
        _LOGGER.info('SWITCH TURN OFF')

    def update(self):
        """Check if device is on and update the state."""
        _LOGGER.debug('{}: SWITCH IN UPDATE, state is {}'.format(as_local(utcnow()), self._state))
        return self._state
