#!/bin/bash

# Quick deployment script for innovationdesign.io
# This script SSHs into the DO droplet and deploys the application

set -e

DROPLET_IP="104.248.170.26"
DROPLET_USER="root"
REPO_URL="https://github.com/MunoMono/ai-methods.git"

echo "🚀 Deploying to innovationdesign.io (${DROPLET_IP})..."

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

# Install Git if not present
if ! command -v git &> /dev/null; then
    echo "Installing Git..."
    apt-get install -y git
fi

echo "📂 Setting up repository..."

# Navigate to deployment directory
cd /root

# Clone or update repository
if [ -d "ai-methods" ]; then
    echo "Updating existing repository..."
    cd ai-methods
    git fetch origin
    git reset --hard origin/main
    git pull origin main
else
    echo "Cloning repository..."
    git clone https://github.com/MunoMono/ai-methods.git
    cd ai-methods
fi

# Create .env file with Auth0 credentials and database configuration
echo "🔐 Creating environment configuration..."
cat > .env << 'EOF'
# Auth0 Configuration for innovationdesign.io
VITE_AUTH0_DOMAIN=dev-i4m880asz7y6j5sk.us.auth0.com
VITE_AUTH0_CLIENT_ID=1tKb110HavDT3KsqC5P894JEOZ3fQXMm
VITE_AUTH0_AUDIENCE=https://api.ddrarchive.org
VITE_AUTH0_REDIRECT_URI=https://innovationdesign.io

# Environment
VITE_DDR_ENV=production

# GraphQL API Endpoint
VITE_GRAPHQL_ENDPOINT=https://ddrarchive.org/graphql

# PostgreSQL Configuration
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=epistemic_drift

# Backend Configuration
GRANITE_MODEL_PATH=ibm-granite/granite-4.0-h-small-instruct
GRANITE_DEVICE=cpu

# S3/Storage Configuration (optional)
S3_BUCKET=
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
EOF

echo "🛑 Stopping existing containers..."
docker compose -f docker-compose.prod.yml down || true

echo "🏗️  Building application..."
docker compose -f docker-compose.prod.yml build --no-cache

echo "▶️  Starting application..."
docker compose -f docker-compose.prod.yml up -d

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
echo "⚠️  IMPORTANT: Add these URLs to Auth0 Application Settings:"
echo "   Allowed Callback URLs: https://innovationdesign.io, http://innovationdesign.io, http://104.248.170.26"
echo "   Allowed Logout URLs: https://innovationdesign.io, http://innovationdesign.io, http://104.248.170.26"
echo "   Allowed Web Origins: https://innovationdesign.io, http://innovationdesign.io, http://104.248.170.26"
