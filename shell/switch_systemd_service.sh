#!/bin/bash
# "$1" : systemd service name (sudo powers needed)
# "$2" : command: start|stop|status
if [ "$2" = "start" ]
then
    sudo /bin/systemctl start $1
elif [ "$2" = "stop" ]
then
    sudo /bin/systemctl stop $1
elif [ "$2" = "status" ]
then
    /bin/systemctl status $1 |grep running|wc -l
else
    exit -1
fi
exit 0

