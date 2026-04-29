#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "PostgreSQL is ready!"

echo "Applying migrations..."
alembic upgrade head
echo "Migrations complete!"

echo "Importing historical seed data (idempotent)..."
PYTHONPATH=/app python /app/scripts/import_seed.py

echo "Starting FastAPI..."
exec "$@"
