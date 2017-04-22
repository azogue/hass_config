#!/bin/bash
HASSIP=[REDACTED_HASSIP]
REMOTE_HASS=/home/homeassistant/.homeassistant
LOCAL_HASS=[REDACTED_LOCALPATH]
REMOTE_STATIC_PATH=/home/homeassistant/.homeassistant/www/images/

echo Set permissions for PI
ssh pi@$HASSIP sudo chmod 777 -R $REMOTE_HASS
ssh pi@$HASSIP sudo chown pi:pi -R $REMOTE_HASS

echo RSYNC:
rsync -avrzp -L --no-o --no-g -ui  --stats --progress -e ssh --exclude-from $LOCAL_HASS/exclude_patterns.txt $LOCAL_HASS/ pi@$HASSIP:$REMOTE_HASS

echo COPY CUSTOM IMAGES TO STATIC in $REMOTE_STATIC_PATH:
ssh pi@$HASSIP sudo cp $REMOTE_HASS/custom_images/* $REMOTE_STATIC_PATH
ssh pi@$HASSIP ls -la $REMOTE_STATIC_PATH/images/

echo Set permissions for homeassistant
ssh pi@$HASSIP sudo chown homeassistant:homeassistant -R $REMOTE_HASS
ssh pi@$HASSIP sudo chmod 775 -R $REMOTE_HASS

echo HASS LOG:
ssh pi@$HASSIP sudo tail -n 100 $REMOTE_HASS/home-assistant.log
