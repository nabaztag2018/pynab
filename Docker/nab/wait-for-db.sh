#!/bin/bash
# -
# Wait for the database to be accessible
set -e

RETRIES=5

until psql -U pynab -d pynab -c "select 1" > /dev/null 2>&1 || [ ${RETRIES} -eq 0 ]; do
    echo "Waiting for pynab DB to be ready, $((RETRIES--)) remaining attempts..."
    sleep 1
done

psql -U pynab -d pynab -c "select 1" > /dev/null 2>&1
exit $?
