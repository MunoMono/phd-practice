#!/bin/bash
set -e

echo "🔄 Ensuring database password is synced..."

# Wait for database to be ready
until PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -U ${POSTGRES_USER} -d postgres -c '\q' 2>/dev/null; do
  echo "⏳ Waiting for database to be ready..."
  sleep 2
done

# Sync the password
echo "🔒 Syncing database password..."
PGPASSWORD=${POSTGRES_PASSWORD} psql -h ${POSTGRES_HOST} -U ${POSTGRES_USER} -d postgres -c "ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';" 2>/dev/null || true

echo "✅ Database password synced"
echo "🚀 Starting backend server..."

# Start the FastAPI server
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
