#!/bin/bash
# -
# Do needed inits, then run nabd, all nab.*d services and nabweb.
set -e

# Do inits
echo "Doing Pynab inits..."
/usr/local/bin/run-inits.sh

# Start services
for daemon in nabd ${DAEMONS:-} ; do
    echo "Starting ${daemon}..."
    /usr/local/bin/run-service.sh ${daemon} &
done

# Start nabweb
echo "Starting nabweb..."
while :
do
    /usr/local/bin/run-webserver.sh &
    wait $!
done
