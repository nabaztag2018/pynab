#!/bin/bash
# -
# Wait for a file to appear
set -e

RETRIES=5

FILE=$1
if [ "${FILE}" == "" ]; then
    echo "Usage: $0 </path/to/file>"
    exit 1
fi

until [ -f ${FILE} ] || [ ${RETRIES} -eq 0 ]; do
    echo "Waiting for ${FILE} to appear, $((RETRIES--)) remaining attempts..."
    sleep 1
done

test -f ${FILE}
exit $?
