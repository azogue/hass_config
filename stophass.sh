#!/bin/bash
HASSIP=192.168.1.13
REMOTE_HASS=/home/homeassistant/.homeassistant

echo Stopping HASS...
ssh pi@$HASSIP sudo systemctl stop home-assistant@homeassistant

echo HASS LOG:
ssh pi@$HASSIP sudo tail -n 100 $REMOTE_HASS/home-assistant.log
