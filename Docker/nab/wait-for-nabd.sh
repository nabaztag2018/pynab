#!/bin/bash
# -
# Wait for nabd to be accessible
set -e

RETRIES=5

until nc -z $NABD_HOST $NABD_PORT_NUMBER || [ ${RETRIES} -eq 0 ]; do
    echo "Waiting for nabd to be listing on $NABD_HOST:$NABD_PORT_NUMBER, $((RETRIES--)) remaining attempts..."
    sleep 1
done

nc -z $NABD_HOST $NABD_PORT_NUMBER
exit $?
