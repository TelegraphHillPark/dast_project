#!/bin/sh
set -e

mkdir -p /app/uploads/avatars /app/wordlists
chown -R appuser:appuser /app/uploads /app/wordlists

echo "Running Alembic migrations..."
gosu appuser alembic upgrade head

echo "Starting application..."
exec gosu appuser "${@:-uvicorn app.main:app --host 0.0.0.0 --port 8000}"