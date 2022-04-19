#!/bin/bash
# -
# run a Python service

SERVICE=${1:-}
if [ "${SERVICE}" == "" ]; then
    echo "Usage: $0 <service-name>"
    echo " e.g.: $0 nabmastodond"
    exit 1
fi

ln -sf /dev/stdout /var/log/${SERVICE}.log
while :
do
    /opt/venv/bin/python3 -m ${SERVICE}.${SERVICE} &
    wait $!
done
