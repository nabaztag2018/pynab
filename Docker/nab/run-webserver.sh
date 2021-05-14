#!/bin/bash
for daemon in ${PID_DAEMONS:-} ; do
    bash /usr/local/bin/pid_daemon_proxy.sh $daemon &
done
exec /home/pi/venv/bin/gunicorn --timeout 60 -b 0.0.0.0 nabweb.wsgi
