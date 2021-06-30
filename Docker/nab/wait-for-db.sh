#!/bin/bash
# -
# Wait for the database to be accessible
set -e

RETRIES=10

CALLER=${1:-}

until psql -U pynab -d pynab -c "select 1" > /dev/null 2>&1 || [ ${RETRIES} -eq 0 ]; do
    echo "${CALLER}: waiting for pynab DB to be ready, $((RETRIES--)) remaining attempts..."
    sleep 1
done

psql -U pynab -d pynab -c "select 1" > /dev/null 2>&1
exit $?
