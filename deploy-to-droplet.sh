#!/bin/bash

# Quick deployment script for innovationdesign.io
# This script SSHs into the DO droplet and deploys the application

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/scripts/lib/git_deploy_guard.sh"

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
            echo "Usage: ./deploy-to-droplet.sh [--allow-dirty]" >&2
            exit 1
            ;;
    esac
done

git_require_clean_worktree "${ALLOW_DIRTY}"

echo "🚀 Deploying to innovationdesign.io (${DROPLET_IP})..."

if [[ "${GIT_DEPLOY_TREE_DIRTY}" == "true" ]]; then
    echo "⚠️  Deploying a dirty tree because --allow-dirty was used."
fi

echo "📤 Syncing local application source to droplet..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude '.venv' \
    --exclude 'venv' \
    --exclude 'node_modules' \
    --exclude 'dist' \
    --exclude '__pycache__' \
    --exclude '.pytest_cache' \
    --exclude '.mypy_cache' \
    --exclude '.DS_Store' \
    --exclude '.prod-sync' \
    --exclude 'backups' \
    --exclude 'logs' \
    --exclude 'frontend/test-results' \
    ./ ${DROPLET_USER}@${DROPLET_IP}:${REMOTE_APP_DIR}/

# SSH into droplet and execute deployment commands
ssh ${DROPLET_USER}@${DROPLET_IP} << 'ENDSSH'
set -e

echo "📦 Installing prerequisites..."

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Install Docker Compose plugin if not present
if ! docker compose version &> /dev/null; then
    echo "Installing Docker Compose..."
    apt-get update
    apt-get install -y docker-compose-plugin
fi

# Navigate to deployment directory
cd /root/phd-practice

if [ ! -f ".env" ]; then
    echo "❌ Missing /root/phd-practice/.env on droplet. Aborting to avoid overwriting production config."
    exit 1
fi

echo "🏗️  Building application..."
docker compose -f docker-compose.prod.yml build frontend backend

echo "▶️  Starting application..."
docker compose -f docker-compose.prod.yml up -d --no-deps --force-recreate backend frontend

echo "🔥 Configuring firewall..."
if ! ufw status | grep -q "Status: active"; then
    echo "y" | ufw enable
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow 22/tcp
    ufw allow 80/tcp
    ufw allow 443/tcp
    ufw deny 5432/tcp
    ufw deny 8000/tcp
    ufw deny 9000/tcp
    ufw reload
    echo "✅ Firewall enabled and configured"
else
    echo "✅ Firewall already active"
fi

echo "✅ Deployment complete!"
echo ""
echo "📊 Container status:"
docker compose -f docker-compose.prod.yml ps

echo ""
echo "🌐 Application should be available at:"
echo "   http://innovationdesign.io"
echo "   http://104.248.170.26"
echo ""
echo "📝 View logs with: docker compose -f docker-compose.prod.yml logs -f"
ENDSSH

echo ""
echo "✨ Deployment finished successfully!"
echo ""
echo "ℹ️  Production .env/Auth0 settings were preserved on the droplet."

deployment_marker_contents "deploy-to-droplet.sh" | ssh ${DROPLET_USER}@${DROPLET_IP} "cat > ${REMOTE_APP_DIR}/current-deployment.txt"

echo ""
echo "🧾 Current deployment marker:"
ssh ${DROPLET_USER}@${DROPLET_IP} "cat ${REMOTE_APP_DIR}/current-deployment.txt"
