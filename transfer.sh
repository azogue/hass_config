#!/bin/bash
HASSIP=192.168.1.13
REMOTE_HASS=/home/homeassistant/.homeassistant
LOCAL_HASS=/Users/uge/Dropbox/PYTHON/PYPROJECTS/hass_config
REMOTE_STATIC_PATH=/srv/homeassistant/homeassistant_venv/lib/python3.4/site-packages/homeassistant/components/frontend/www_static/

echo Transfer HASS config from $LOCAL_HASS to $REMOTE_HASS in $HASSIP
echo Stopping HASS...
ssh pi@$HASSIP sudo systemctl stop home-assistant@homeassistant

echo Set permissions for PI
ssh pi@$HASSIP sudo chmod 777 -R $REMOTE_HASS
ssh pi@$HASSIP sudo chown pi:pi -R $REMOTE_HASS

echo RSYNC:
rsync -avrzp --no-o --no-g -ui  --stats --progress -e ssh --exclude-from $LOCAL_HASS/exclude_patterns.txt $LOCAL_HASS/ pi@$HASSIP:$REMOTE_HASS

echo COPY CUSTOM IMAGES TO STATIC in $REMOTE_STATIC_PATH:
ssh pi@$HASSIP sudo cp $REMOTE_HASS/custom_images/* $REMOTE_STATIC_PATH/images/
ssh pi@$HASSIP ls -la $REMOTE_STATIC_PATH/images/

echo Set permissions for homeassistant
ssh pi@$HASSIP sudo chown homeassistant:homeassistant -R $REMOTE_HASS
ssh pi@$HASSIP sudo chown homeassistant:homeassistant -R $REMOTE_STATIC_PATH/images
ssh pi@$HASSIP sudo chmod 775 -R $REMOTE_HASS

echo Starting HASS
ssh pi@$HASSIP sudo systemctl start home-assistant@homeassistant

echo HASS LOG:
ssh pi@$HASSIP sudo tail -n 100 $REMOTE_HASS/home-assistant.log
