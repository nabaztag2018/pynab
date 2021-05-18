#!/bin/bash
# -
# Wait for the DB migrations to complete and run a Python service
set -e

SERVICE=$1
if [ "${SERVICE}" == "" ]; then
    echo "Usage: $0 <service-name>"
    echo "e.g.: $0 nabmastodond"
    exit 1
fi

# Wait for migrations to complete
/bin/bash /usr/local/bin/wait-for-file.sh /var/run/postgresql/migrate.completed
RC=$?

if [ ! ${RC} -eq 0 ]; then
    echo "Timeout waiting for migrations to complete, aborting."
    exit 1
fi

# Wait for nabd
/bin/bash /usr/local/bin/wait-for-nabd.sh
RC=$?

if [ ! ${RC} -eq 0 ]; then
    echo "Timeout waiting for nabd to start, aborting."
    exit 1
fi

echo "Running ${SERVICE}"
ln -sf /dev/stdout /var/log/${SERVICE}.log
exec /home/pi/venv/bin/python3 -m ${SERVICE}.${SERVICE}
