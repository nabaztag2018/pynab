#!/bin/bash
exec /home/pi/venv/bin/gunicorn --timeout 60 -b 0.0.0.0 nabweb.wsgi
