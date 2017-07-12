"""
# Turn off Kodi script

This is a minimal change of the standard yaml script for the turn_off_action
of the Kodi media player, to **allow a conditional action in the sequence**.

```yaml
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

Using this python_script, the Kodi config becomes:

```yaml
turn_off_action:
  service: python_script.turn_off_kodi
```

"""
KODI_MEDIA_PLAYER = 'media_player.kodi'

kodi_state = hass.states.get(KODI_MEDIA_PLAYER).state

# Call STOP only when doing something!
if (kodi_state != 'idle') and (kodi_state != 'off'):
    hass.services.call('media_player', 'kodi_call_method',
                       {"entity_id": KODI_MEDIA_PLAYER,
                        "method": 'Player.Stop',
                        "playerid": 1})

hass.services.call('media_player', 'kodi_call_method',
                   {"entity_id": KODI_MEDIA_PLAYER,
                    "method": 'Addons.ExecuteAddon',
                    "addonid": 'script.json-cec',
                    "params": {"command": "standby"}})
