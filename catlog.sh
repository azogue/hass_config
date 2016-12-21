#!/bin/bash
HASSIP=192.168.1.13
REMOTE_HASS=/home/homeassistant/.homeassistant

echo HASS LOG:
echo ssh pi@$HASSIP sudo cat $REMOTE_HASS/home-assistant.log
ssh pi@$HASSIP sudo cat $REMOTE_HASS/home-assistant.log
ssh pi@$HASSIP sudo ls -la $REMOTE_HASS/home-assistant*
