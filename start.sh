#!/bin/sh
set -e

# Start Gunicorn (Python API) in the background
gunicorn server:app \
    --bind 127.0.0.1:8000 \
    --workers 2 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - &

# Start Nginx in the foreground (keeps the container alive)
nginx -g "daemon off;"
