#!/bin/bash

HA_PWD=${1}
HA_URL=${2}
if [ "$3" = "" ]
then
    TIMEOUT=2
else
    TIMEOUT=${3}
fi
HA_ROUTE="states"
OUTPUT_TEXT_CHECK="</body>"

RESULT=$(curl -Ss -f --max-time ${TIMEOUT} -X GET \
    -H "x-ha-access: ${HA_PWD}" \
    -H "Content-Type: application/json" \
    ${HA_URL}${HA_ROUTE} | /bin/grep -c "${OUTPUT_TEXT_CHECK}")

[ "$RESULT" -eq "1" ]  && echo "success"||echo "fail"
exit 0