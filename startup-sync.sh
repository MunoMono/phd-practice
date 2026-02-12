#!/bin/bash
# Auto-sync script for parent PIDs - runs on backend container startup
# This ensures the database always has the correct password and PIDs are synced

echo "🔧 Ensuring database password is correct..."
docker exec phd-practice-db psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'postgres';" 2>&1 | grep -q "ALTER ROLE" && echo "✅ Password verified"

echo "🔄 Running PID sync..."
docker exec phd-practice-backend python /app/quick_sync.py

echo "✅ Startup sync complete"
