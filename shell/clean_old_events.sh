#!/bin/bash
# Para crontab de PI:
#
# 0 1 */2 * * sudo /home/homeassistant/.homeassistant/clean_old_events.sh 3

DAYS_OLD="$1"
# PATH_EVENTOS=/media/usb32/
PATH_EVENTOS=/mnt/usbdrive/

# echo para sysmail en debug: (comentar)
find $PATH_EVENTOS -mtime +$DAYS_OLD -type f -print

# Borrado
find $PATH_EVENTOS -mtime +$DAYS_OLD -type f -delete
find $PATH_EVENTOS -type d -empty -delete
exit 0
