#!/bin/bash
HYPERION_IP=192.168.1.56
HYPERION_USER=osmc
# Uses ssh with public-key in authorized_keys for secure-nopasswd login in remote kodi machine
if [ "$1" = "" ]
then
    # echo "ssh $HYPERION_USER@$HYPERION_IP sudo /usr/sbin/service hyperion status|grep running|wc -l"
    ssh $HYPERION_USER@$HYPERION_IP sudo /usr/sbin/service hyperion status|grep running|wc -l
else
    if [ "$1" = "1" ]
    then
        ssh $HYPERION_USER@$HYPERION_IP sudo /usr/sbin/service hyperion start
    else
        ssh $HYPERION_USER@$HYPERION_IP sudo /usr/sbin/service hyperion stop
    fi
    ssh $HYPERION_USER@$HYPERION_IP sudo /usr/sbin/service hyperion status|grep running|wc -l
fi
exit 0

# Before, with Kodi Ambilight add-on:
# KODI_URL="http://192.168.1.56:8080/jsonrpc"
# ADDON="script.xbmc.hue.ambilight"
# if [ "$1" = "" ]
# then
#     curl -s --user osmc:osmc --header "Content-Type: application/json" --data-binary '{"id": 1, "params": {"properties": ["enabled"], "addonid": "script.xbmc.hue.ambilight"}, "jsonrpc": "2.0", "method": "Addons.GetAddonDetails"}' $KODI_URL|grep '"enabled":true'|wc -l
# else
#     if [ "$1" = "1" ]
#     then
#         curl -s --user osmc:osmc --header "Content-Type: application/json" --data-binary '{"id": 1, "params": {"enabled": true, "addonid": "script.xbmc.hue.ambilight"}, "jsonrpc": "2.0", "method": "Addons.SetAddonEnabled"}'  $KODI_URL|grep '"result":"OK"'|wc -l
#     else
#         curl -s --user osmc:osmc --header "Content-Type: application/json" --data-binary '{"id": 1, "params": {"enabled": false, "addonid": "script.xbmc.hue.ambilight"}, "jsonrpc": "2.0", "method": "Addons.SetAddonEnabled"}'  $KODI_URL|grep '"result":"OK"'|wc -l
#     fi
# fi
