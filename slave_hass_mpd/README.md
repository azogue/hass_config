# Another HomeAssistant configuration

### slave HASS MPD

HA config on another RPI 2 in another room, with some sensors attached, running a MPD server, which is posting state changes on the 'master' instance with a custom Appdaemon app.

This RPI has:
  * 1x PIR sensor
  * 1x DS18b20 temperature sensor --> integrated with a custom mod from the `onewire` sensor platform ([`myonewire.py`](https://github.com/azogue/hass_config/blob/master/custom_components/sensor/myonewire.py))
  * 1x DHT22 temperature & humidity sensor
  
Also, an audio hat **[pimoroni pHAT DAC](https://shop.pimoroni.com/products/phat-dac)** connected with a speaker which I turn on/off with an Etekcity outlet controlled by the master HASS. 
