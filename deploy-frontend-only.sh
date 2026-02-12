#!/bin/bash
set -e

echo "🎨 Fast Frontend-Only Deployment"
echo "=================================="

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

DROPLET_IP="104.248.170.26"
DROPLET_USER="root"

echo -e "${BLUE}📡 Connecting to droplet...${NC}"

ssh ${DROPLET_USER}@${DROPLET_IP} << 'ENDSSH'
set -e

cd /root/phd-practice

echo "📥 Pulling latest frontend changes..."
git pull

echo "🔨 Rebuilding frontend only (uses cached layers)..."
docker compose -f docker-compose.prod.yml build frontend

echo "🔄 Restarting frontend container..."
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate frontend

echo "✅ Frontend deployed!"
docker compose -f docker-compose.prod.yml ps frontend

ENDSSH

echo ""
echo -e "${GREEN}✨ Frontend deployment complete!${NC}"
echo "🌐 View at: http://innovationdesign.io"
echo ""
echo "⏱️  Total time: ~15-30 seconds (vs 5+ minutes for full rebuild)"
