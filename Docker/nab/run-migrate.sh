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

echo "Updating localization messages"
all_locales="-l fr_FR -l de_DE -l en_US -l en_GB -l it_IT -l es_ES -l ja_jp -l pt_BR -l de -l en -l es -l fr -l it -l ja -l pt"
/home/pi/venv/bin/python3 /home/pi/pynab/manage.py compilemessages ${all_locales}

echo "Add migration completion marker file"
touch /var/run/postgresql/migrate.completed
