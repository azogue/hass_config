#!/bin/bash
REL_PATH_IMAGE="$1"
IMG_URL="$2"
HASS_PW="$3"

PATH_FILE=/home/homeassistant/.homeassistant/www/${REL_PATH_IMAGE}
PATH_TS_FILE=${PATH_FILE}_t
DIRNAME=$(dirname ${PATH_FILE})
BASENAME=$(basename ${PATH_FILE})

touch -d '-60 seconds' ${PATH_TS_FILE}
c=1
/usr/bin/curl -s -o ${PATH_FILE} -H "x-ha-access: ${HASS_PW}" ${IMG_URL}
while [ $c -le 7 ] && [ $(find ${DIRNAME} -name ${BASENAME} -newer ${PATH_TS_FILE} |wc -l) = 0 ]
do
    /usr/bin/curl -s -o ${PATH_FILE} -H "x-ha-access: ${HASS_PW}" ${IMG_URL}
#	echo $(find $DIRNAME -name $BASENAME -newer $PATH_TS_FILE |wc -l)
#	echo "Welcone $c times"
	(( c++ ))
done
#echo "* hecho en $c intentos"
exit 0