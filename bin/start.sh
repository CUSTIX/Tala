#!/bin/sh
# Production start (Render runs this via the Dockerfile's prod target).
set -e

python manage.py migrate --noinput
python manage.py createcachetable
# Demo accounts are temporary: delete the expired ones (with all their fake classes).
python manage.py purge_demo

# Threads, not processes: the free instance has 512 MB. Access log without query strings.
exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 --worker-class gthread --threads 4 \
  --worker-tmp-dir /dev/shm \
  --max-requests 1000 --max-requests-jitter 100 \
  --timeout 60 --graceful-timeout 30 \
  --access-logfile - --access-logformat '%(h)s "%(m)s %(U)s" %(s)s %(b)s %(L)s'
