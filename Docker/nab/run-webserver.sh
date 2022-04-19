#!/bin/bash
exec /opt/venv/bin/gunicorn --timeout 60 -b 0.0.0.0 nabweb.wsgi
