#!/bin/bash
set -e

# Start Gunicorn (Python API) in the background
gunicorn server:app \
    --bind 127.0.0.1:8000 \
    --workers 1 \
    --timeout 120 \
    --log-level info \
    --access-logfile - \
    --error-logfile - &

GUNICORN_PID=$!

# If Nginx exits for any reason, kill Gunicorn too (and vice versa)
# This ensures Docker sees a non-zero exit and restarts the container
trap "kill $GUNICORN_PID 2>/dev/null; exit" INT TERM

# Start Nginx in foreground — keeps container alive
nginx -g "daemon off;" &
NGINX_PID=$!

# Wait for either process to exit; kill the other one
wait -n 2>/dev/null || true
kill $GUNICORN_PID $NGINX_PID 2>/dev/null
exit 1
