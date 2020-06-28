#!/bin/bash
# -
# Wait for the DB to be accessible and run the DB migrations
set -e

/bin/bash /usr/local/bin/wait-for-db.sh
RC=$?

if [ ! ${RC} -eq 0 ]; then
    echo "Unable to access database, aborting."
    exit 1
fi

echo "Running DB migrations"
/home/pi/venv/bin/python3 /home/pi/pynab/manage.py migrate

echo "Add migration completion marker file"
touch /var/run/postgresql/migrate.completed
