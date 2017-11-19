#!/bin/bash
echo "RESTART HA"
sudo systemctl restart home-assistant@homeassistant
echo "RESTART APPDAEMON"
sudo systemctl stop appdaemon
rm -f /home/homeassistant/appdaemon.log
rm -f /home/homeassistant/appdaemon_err.log
sudo systemctl start appdaemon
echo "STOP HOMEBRIDGE"
sudo systemctl stop homebridge
