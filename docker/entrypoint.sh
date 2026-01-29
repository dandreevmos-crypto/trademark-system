#!/bin/bash
set -e

echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 1
done
echo "Database is ready!"

echo "Running database initialization..."
python /app/scripts/init_db.py

echo "Starting application..."
exec "$@"
