#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib/git_deploy_guard.sh"

echo "🎨 Fast Frontend-Only Deployment"
echo "=================================="

GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

DROPLET_IP="104.248.170.26"
DROPLET_USER="root"
REMOTE_APP_DIR="/root/phd-practice"
ALLOW_DIRTY=false

while [[ $# -gt 0 ]]; do
	case "$1" in
		--allow-dirty)
			ALLOW_DIRTY=true
			shift
			;;
		*)
			echo "ERROR: Unknown option '$1'" >&2
			echo "Usage: ./deploy-frontend-only.sh [--allow-dirty]" >&2
			exit 1
			;;
	esac
done

git_require_clean_worktree "${ALLOW_DIRTY}"

echo -e "${BLUE}📡 Connecting to droplet...${NC}"

if [[ "${GIT_DEPLOY_TREE_DIRTY}" == "true" ]]; then
	echo "⚠️  Deploying a dirty tree because --allow-dirty was used."
fi

echo "📤 Syncing local frontend source..."
rsync -avz --delete \
	--exclude 'node_modules' \
	--exclude 'dist' \
	--exclude '.git' \
	--exclude '.env*' \
	--exclude 'test-results' \
	./frontend/ ${DROPLET_USER}@${DROPLET_IP}:${REMOTE_APP_DIR}/frontend/

ssh ${DROPLET_USER}@${DROPLET_IP} << 'ENDSSH'
set -e

cd /root/phd-practice

echo "🧹 Stopping legacy frontend container on 8080 if present..."
docker stop testamentary-traces-frontend >/dev/null 2>&1 || true
docker rm testamentary-traces-frontend >/dev/null 2>&1 || true

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

deployment_marker_contents "deploy-frontend-only.sh" | ssh ${DROPLET_USER}@${DROPLET_IP} "cat > ${REMOTE_APP_DIR}/current-deployment.txt"

echo "🧾 Current deployment marker:"
ssh ${DROPLET_USER}@${DROPLET_IP} "cat ${REMOTE_APP_DIR}/current-deployment.txt"
