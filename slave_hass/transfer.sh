#!/bin/bash
HASSIP=192.168.1.46
REMOTE_HASS=/home/homeassistant/.homeassistant
LOCAL_HASS=/Users/uge/Dropbox/PYTHON/PYPROJECTS/hass_config/slave_hass
EXCLUDE_FILE=/Users/uge/Dropbox/PYTHON/PYPROJECTS/hass_config/exclude_patterns.txt

echo Set permissions for PI
ssh pi@$HASSIP sudo chmod 777 -R $REMOTE_HASS
ssh pi@$HASSIP sudo chown pi:pi -R $REMOTE_HASS

echo RSYNC:
rsync -avrzp -L --no-o --no-g -ui  --stats --progress -e ssh --exclude-from $EXCLUDE_FILE $LOCAL_HASS/ pi@$HASSIP:$REMOTE_HASS

echo Set permissions for homeassistant
ssh pi@$HASSIP sudo chown homeassistant:nogroup -R $REMOTE_HASS
ssh pi@$HASSIP sudo chmod 775 -R $REMOTE_HASS

echo HASS LOG:
ssh pi@$HASSIP sudo tail -n 100 $REMOTE_HASS/home-assistant.log
