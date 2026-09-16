# Deployment Guide for innovationdesign.io

## Overview
This guide covers deploying the phd-practice repository to Digital Ocean droplet at 104.248.170.26 for innovationdesign.io.

**Source of truth & deploy model**: The GitHub repo (`git@github.com:MunoMono/phd-practice.git`) is the source of truth. No GitHub Actions are used. Deployments run directly from your local machine to the droplet using the provided scripts.

**Current deployment safety rule**: deploy from your local workspace by syncing source to the droplet. Do not rely on `git pull` inside `/root/phd-practice`, and do not overwrite the droplet `.env`; production Auth0 and runtime credentials are already stored there.

## Prerequisites
- Digital Ocean droplet: 104.248.170.26
- Domain: innovationdesign.io (add to Auth0 allowed callbacks)
- Auth0 tenant: dev-i4m880asz7y6j5sk.us.auth0.com

## Auth0 Configuration

### Required Settings in Auth0 Dashboard

1. **Application Settings** (Application: 1tKb110HavDT3KsqC5P894JEOZ3fQXMm)
   - Allowed Callback URLs:
     ```
     https://innovationdesign.io,
     http://innovationdesign.io,
     http://104.248.170.26
     ```
   - Allowed Logout URLs:
     ```
     https://innovationdesign.io,
     http://innovationdesign.io,
     http://104.248.170.26
     ```
   - Allowed Web Origins:
     ```
     https://innovationdesign.io,
     http://innovationdesign.io,
     http://104.248.170.26
     ```

2. **API Settings**
   - Identifier: `https://api.ddrarchive.org`

## Deployment Steps

### 1. SSH into Digital Ocean Droplet
```bash
ssh root@104.248.170.26
```

### 2. Install Prerequisites (if not already installed)
```bash
# Update system
apt-get update && apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
apt-get install docker-compose-plugin -y

# Install Git
apt-get install git -y
```

### 3. Prepare the Droplet Once
```bash
ssh root@104.248.170.26
cd /root/phd-practice
test -f .env && echo ".env present"
docker compose -f docker-compose.prod.yml ps
```

### 4. Deploy From Local
```bash
# Full app deploy: sync local source, preserve droplet .env, rebuild backend/frontend only
./deploy-to-droplet.sh

# Frontend-only deploy: sync only frontend source and recreate only the frontend service
./deploy-frontend-only.sh
```

These scripts:
- sync source from your local workspace to `/root/phd-practice`
- preserve `/root/phd-practice/.env`
- avoid `git reset --hard` and avoid regenerating production Auth0 credentials
- avoid touching unrelated containers on the droplet

### 5. Verify Deployment
```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Test health endpoint
curl http://localhost/health
```

### 6. Configure DNS
Point `innovationdesign.io` A record to `104.248.170.26`

### 7. (Optional) Set up SSL with Let's Encrypt
```bash
# Install certbot
apt-get install certbot python3-certbot-nginx -y

# Get SSL certificate
certbot certonly --standalone -d innovationdesign.io -d www.innovationdesign.io

# Create SSL directory
mkdir -p /root/phd-practice/ssl

# Copy certificates
cp /etc/letsencrypt/live/innovationdesign.io/fullchain.pem /root/phd-practice/ssl/
cp /etc/letsencrypt/live/innovationdesign.io/privkey.pem /root/phd-practice/ssl/

# Rebuild container
cd /root/phd-practice
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# Enable SSL in nginx config (edit nginx.prod.conf and uncomment HTTPS block)
```

## Maintenance

### Update Deployment
```bash
./deploy-to-droplet.sh
```

### View Logs
```bash
docker-compose -f docker-compose.prod.yml logs -f ddr-public
```

### Restart Container
```bash
docker-compose -f docker-compose.prod.yml restart
```

## Troubleshooting

### Check if container is running
```bash
docker ps
```

### Check nginx logs
```bash
docker exec innovationdesign-frontend cat /var/log/nginx/error.log
```

### Test Auth0 connection
Open browser console at innovationdesign.io and check for any CORS or Auth0 errors.

### Common Issues
1. **CORS errors**: Verify Auth0 allowed origins include your domain
2. **Login redirect fails**: Check Auth0 callback URLs
3. **Container won't start**: Check `docker-compose -f docker-compose.prod.yml logs`
