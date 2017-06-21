#!/bin/bash
# shell/remote_hass_switch.sh http://REMOTE_HASS_IP:8123 password switch.relay toggle

HASS_URL="$1"
HASS_PW="$2"
SWITCH_NAME="$3"
OPERATION="$4"

if [ "${OPERATION}" = "status" ]
then
    /usr/bin/curl -s ${HASS_URL}/api/states/${SWITCH_NAME}?api_password=${HASS_PW} | grep '"state": "on"' | wc -l
else
    ENTITY_1='{"entity_id": "'
    ENTITY_2='"}'
    /usr/bin/curl -s -H "x-ha-access: ${HASS_PW}" -d "${ENTITY_1}${SWITCH_NAME}${ENTITY_2}" ${HASS_URL}/api/services/switch/${OPERATION} | grep '"state": "on"' | wc -l
fi
exit 0
