#!/bin/bash

if [ "$1" = "pushbullet" ]
then
    RESNUM=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "Error setting up platform pushbullet")
    [ "$RESNUM" -lt "1" ]  && echo "success"||echo "fail"
elif [ "$1" = "richsmtp" ]
then
    RESNUM=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "Error setting up platform richsmtp")
    [ "$RESNUM" -lt "1" ]  && echo "success"||echo "fail"
elif [ "$1" = "telegram" ]
then
    RESNUM=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "Error setting up platform telegram")
    [ "$RESNUM" -lt "1" ]  && echo "success"||echo "fail"
elif [ "$1" = "ios" ]
then
    RESNUM=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "Error setting up platform ios")
    [ "$RESNUM" -lt "1" ]  && echo "success"||echo "fail"
elif [ "$1" = "kodi" ]
then
    RESNUM=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "Error setting up platform kodi")
    [ "$RESNUM" -lt "1" ]  && echo "success"||echo "fail"
elif [ "$1" = "recorder" ]
then
    RESNUM=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "ERROR (Recorder)")
    [ "$RESNUM" -lt "1" ]  && echo "success"||echo "fail"
elif [ "$1" = "core_error" ]
then
    /bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c homeassistant.core
elif [ "$1" = "core_warning" ]
then
    /bin/grep WARNING /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c homeassistant.core
elif [ "$1" = "unable_find" ]
then
    /bin/grep WARNING /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c "Unable to find service notify"
else
#    RESCORE=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c homeassistant.core)
#    RESNOT=$(/bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c homeassistant.components.notify)
#    echo $((RESCORE + RESNOT))
    /bin/grep ERROR /home/homeassistant/.homeassistant/home-assistant.log | /bin/grep -c homeassistant.components.notify
fi
exit 0