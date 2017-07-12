# -*- coding: utf-8 -*-
"""
CEC Kodi Switch

Simple switch for turn on / off the TV attached to one Raspberry PI
running OSMC-KODI with the `script.json-cec` add-on.

* For turning ON (CECActivateSource()), a service call for the
  `media_player.kodi_execute_addon` service to call the `script.json-cec`
  addon with `{"command": "activate"}` params.
* For turning OFF, with the proper CEC config in OSMC-KODI
  (turn all off in exit, but no action in init),
  a service call for the `media_player.kodi` service to turn off
  (HASS Kodi platform config with `turn_off_action: quit`).

Example yaml config:
```yaml
switch:
- platform: cecswitch
  name: "TV Salón"
  kodi_player: media_player.kodi
  on_cec_command: activate
```

** **UPDATE**:

With the new options to define HA scripts to turn ON/OFF Kodi, this extra
switch is not required anymore. It can be replaced with scripts like this:

```yaml
media_player:
  - platform: kodi
    turn_on_action:
    - service: media_player.kodi_call_method
      data:
        entity_id: media_player.kodi
        method: Addons.ExecuteAddon
        addonid: script.json-cec
        params:
          command: activate
    turn_off_action:
    - service: media_player.kodi_call_method
      data:
        entity_id: media_player.kodi
        method: Player.Stop
        playerid: 1
    - service: media_player.kodi_call_method
      data:
        entity_id: media_player.kodi
        method: Addons.ExecuteAddon
        addonid: script.json-cec
        params:
          command: standby
```
"""
import asyncio
import logging
import voluptuous as vol
from homeassistant.components.switch import SwitchDevice, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_NAME)
from homeassistant.util import utcnow, as_local


_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['media_player']

ICON = 'mdi:kodi'
CONF_KODI_PLAYER = "kodi_player"
CONF_COMMAND_ON = "on_cec_command"
DEFAULT_COMMAND_ON = "activate"
DEFAULT_NAME = 'Kodi CEC Switch'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_KODI_PLAYER): cv.entity_id,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_COMMAND_ON, default=DEFAULT_COMMAND_ON): cv.string
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup the CEC Kodi switch."""
    player = config.get(CONF_KODI_PLAYER)
    switch_name = config.get(CONF_NAME)
    command_on = config.get(CONF_COMMAND_ON)
    # Create switch:
    switch = CECSwitch(hass, player, switch_name, command_on)
    _LOGGER.info('CEC switch for Kodi device: "{}" loaded'.format(player))
    async_add_devices([switch])
    return True


class CECSwitch(SwitchDevice):
    """Representation of a KODI CEC switch."""

    def __init__(self, hass, player, switch_name, command_on):
        """Initialize the CECSwitch."""
        self.hass = hass
        self._kodi_player = player
        self._name = switch_name
        self._command_on = command_on
        self._state = False

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return False

    @property
    def is_on(self):
        """Return true if switch is on."""
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
            self.turn_off()
        else:
            self.turn_on()

    def turn_on(self):
        """Turn the switch on."""
        data = {"entity_id": self._kodi_player,
                "method": "Addons.ExecuteAddon",
                "addonid": "script.json-cec",
                "params": {"command": self._command_on}}
        self.hass.services.call("media_player", "kodi_call_method",
                                service_data=data)
        self._state = True
        self.schedule_update_ha_state()
        _LOGGER.info('SWITCH TURN ON')

    def turn_off(self):
        """Turn the switch off."""
        data = {"entity_id": self._kodi_player}
        self.hass.services.call("media_player", "turn_off", service_data=data)
        self._state = False
        self.schedule_update_ha_state()
        _LOGGER.info('SWITCH TURN OFF')
