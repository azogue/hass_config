#!/bin/bash
MOTION_IP="$1"
CAMERA="$2"
COMMAND="$3"
if [ $COMMAND = "status" ]
then
    curl -s http://$MOTION_IP:7999/$CAMERA/detection/$COMMAND|grep 'status ACTIVE'|wc -l
else
    curl -s http://$MOTION_IP:7999/$CAMERA/detection/$COMMAND|grep 'Done'|wc -l
fi
