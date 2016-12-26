# Home Assistant Custom **CEC Kodi Switch**.

Simple switch for turn on / off the TV attached to one Raspberry PI running KODI with `script.json-cec` add-on.

* For **turning ON** (**CECActivateSource()**), The KODI JSONRPC API does it OK
* For **turning OFF** (Standby order), The KODI JSONRPC API fails (with my current config: RPI3_OSMC_last + Toshiba TV), so, with the **proper CEC config in OSMC-KODI** (turn all off in exit, but no action in init), I'm calling the `media_player.kodi` service to turn off (HASS Kodi platform config with `turn_off_action: quit`).

  Not anymore:
  ~~so I'm doing it the very wrong way: I'm sshing in the remote Kodi_RPI to run `cec-client` and go standby. Problem is, at that moment, Kodi CEC goes lost, so, before I turn ON the TV again,  I have to some way restart KODI. I'm killing it without any pity, sorry.~~
  But you can use this 'brute-force' method if you can ssh to the kodi machine with public key auth (and no password). For that, append `ssh: ssh_user` to the switch config in Home Assistant.

## YAML HASS example configuration:

```
    - platform: cecswitch
      name: "TV Salón"
      host: "192.168.1.56"
      port: 8080  # (optional)
      username: "osmc"  # (optional)
      password: "osmc"  # (optional)
```
