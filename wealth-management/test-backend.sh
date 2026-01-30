#!/bin/bash

# Wealth Management Backend Test Script

echo "🧪 Testing Wealth Management Backend"
echo "===================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop and try again."
    exit 1
fi

echo "✓ Docker is running"

# Build and start services
echo ""
echo "📦 Building and starting services..."
docker-compose -f docker-compose.backend.yml up -d --build

# Wait for PostgreSQL to be ready
echo ""
echo "⏳ Waiting for PostgreSQL to be ready..."
sleep 5

# Check if database is accessible
docker-compose -f docker-compose.backend.yml exec -T db psql -U postgres -d wealthmanagement -c "SELECT 1;" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ PostgreSQL is ready"
else
    echo "❌ PostgreSQL is not ready"
    exit 1
fi

# Run database migrations (create tables)
echo ""
echo "📋 Creating database tables..."
docker-compose -f docker-compose.backend.yml exec -T backend python -c "from database import engine; import models; models.Base.metadata.create_all(bind=engine); print('✓ Tables created')"

# Seed database
echo ""
echo "🌱 Seeding database with default portfolio..."
docker-compose -f docker-compose.backend.yml exec -T backend python seed.py

# Test API endpoint
echo ""
echo "🔌 Testing API endpoints..."
sleep 2

# Test health check
curl -s http://localhost:8000/ > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ Backend API is responding"
else
    echo "❌ Backend API is not responding"
fi

# Test get portfolios
RESPONSE=$(curl -s http://localhost:8000/api/portfolios/)
if echo "$RESPONSE" | grep -q "Model Portfolio"; then
    echo "✓ Portfolio data retrieved successfully"
else
    echo "⚠️  Portfolio data not found (might need to seed)"
fi

echo ""
echo "===================================="
echo "✅ Backend test complete!"
echo ""
echo "Available services:"
echo "  - PostgreSQL: localhost:5432"
echo "  - Backend API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo ""
echo "View logs: docker-compose -f docker-compose.backend.yml logs -f"
echo "Stop: docker-compose -f docker-compose.backend.yml down"
