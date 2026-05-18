#!/bin/sh
set -e
mkdir -p /app/uploads/avatars /app/wordlists
chown -R appuser:appuser /app/uploads /app/wordlists
exec gosu appuser "$@"
