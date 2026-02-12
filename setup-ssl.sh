#!/bin/bash

# Setup SSL with Let's Encrypt for innovationdesign.io
# This script must be run on the droplet as root

set -e

echo "=========================================="
echo "Setting up SSL with Let's Encrypt"
echo "=========================================="

# Install certbot
echo "Installing certbot..."
apt-get update
apt-get install -y certbot

# Stop the frontend container temporarily
echo "Stopping frontend container..."
cd /root/phd-practice
docker compose -f docker-compose.prod.yml stop frontend

# Get SSL certificate
echo "Obtaining SSL certificate for innovationdesign.io..."
certbot certonly --standalone -d innovationdesign.io -d www.innovationdesign.io \
    --non-interactive \
    --agree-tos \
    --email graham@innovationdesign.io \
    --preferred-challenges http

# Switch nginx config to production (SSL) version
echo "Switching to SSL nginx configuration..."
docker compose -f docker-compose.prod.yml exec frontend sh -c \
    "ln -sf /etc/nginx/conf.d/nginx.prod.conf /etc/nginx/conf.d/default.conf"

# Rebuild and restart with SSL
echo "Restarting frontend with SSL configuration..."
docker compose -f docker-compose.prod.yml up -d frontend

# Test nginx config
echo "Testing nginx configuration..."
docker compose -f docker-compose.prod.yml exec frontend nginx -t

# Reload nginx
echo "Reloading nginx..."
docker compose -f docker-compose.prod.yml exec frontend nginx -s reload

# Setup auto-renewal
echo "Setting up SSL certificate auto-renewal..."
(crontab -l 2>/dev/null; echo "0 0 * * * certbot renew --quiet && docker compose -f /root/phd-practice/docker-compose.prod.yml exec frontend nginx -s reload") | crontab -

echo "=========================================="
echo "SSL Setup Complete!"
echo "=========================================="
echo ""
echo "Your site is now accessible at:"
echo "  https://innovationdesign.io"
echo "  https://www.innovationdesign.io"
echo ""
echo "HTTP requests will automatically redirect to HTTPS"
echo ""
echo "Certificate auto-renewal is configured to run daily"
echo "=========================================="
