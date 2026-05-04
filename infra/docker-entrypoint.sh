#!/bin/bash
set -e

DB_HOST="postgres"
DB_PORT="5432"

# ── 1. Wait for PostgreSQL port ───────────────────────────────────────────────
echo "Waiting for PostgreSQL..."
while ! nc -z "$DB_HOST" "$DB_PORT"; do
  sleep 1
done

# ── 2. Verify credentials (port-open ≠ auth-ready) ───────────────────────────
# Retry up to 30 s.  Failure usually means the postgres_data volume was created
# with a different password than what is now in DATABASE_URL (happens when
# setup.sh is re-run and a new POSTGRES_PASSWORD is generated).
echo "Verifying database credentials..."
AUTH_OK=false
for i in $(seq 1 15); do
  if python3 -c "
import psycopg2, os, sys
try:
    psycopg2.connect(os.environ.get('DATABASE_URL', ''))
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
    AUTH_OK=true
    break
  fi
  sleep 2
done

if [ "$AUTH_OK" = "false" ]; then
  echo ""
  echo "ERROR: Cannot authenticate to PostgreSQL after 30 s."
  echo ""
  echo "  Most likely cause: the postgres_data Docker volume was created with a"
  echo "  different password than the one now in DATABASE_URL."
  echo "  This happens when setup.sh is re-run and generates a new password."
  echo ""
  echo "  Fix — delete the old volume and re-run setup:"
  echo "    docker compose -f infra/docker-compose.yml down -v"
  echo "    bash setup.sh"
  echo ""
  exit 1
fi
echo "PostgreSQL is ready!"

# ── 3. Apply Alembic migrations ───────────────────────────────────────────────
echo "Applying migrations..."
alembic upgrade head
echo "Migrations complete!"

# ── 4. Import seed data (non-fatal — already-imported is ok) ─────────────────
echo "Importing seed data (idempotent)..."
PYTHONPATH=/app python /app/scripts/import_seed.py || \
  echo "Seed import skipped (non-fatal)"

echo "Starting FastAPI..."
exec "$@"
