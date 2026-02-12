#!/bin/bash
set -e  # Exit on any error

echo "🚀 Deploying to production droplet..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Pull latest code
echo -e "${BLUE}📥 Pulling latest code...${NC}"
cd /root/phd-practice
git pull

# Build and deploy with Docker Compose v2
echo -e "${BLUE}🔨 Building containers...${NC}"
docker compose -f docker-compose.prod.yml build

# Stop old containers and remove any conflicting ones
echo -e "${BLUE}🛑 Stopping old containers...${NC}"
docker compose -f docker-compose.prod.yml down --remove-orphans

# Clean up any stale containers with our names
echo -e "${BLUE}🧹 Cleaning up stale containers...${NC}"
docker ps -a --format '{{.Names}}' | grep -E 'phd-practice|phd-practice' | xargs -r docker rm -f 2>/dev/null || true

# Start new containers
echo -e "${BLUE}▶️  Starting new containers...${NC}"
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# Wait for health checks
echo -e "${BLUE}⏳ Waiting for services to be healthy...${NC}"
sleep 10

# Show status
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
docker compose -f docker-compose.prod.yml ps

echo ""
echo -e "${GREEN}🌐 Site: https://innovationdesign.io${NC}"
echo -e "${GREEN}🔌 API: https://innovationdesign.io/api/granite/health${NC}"
