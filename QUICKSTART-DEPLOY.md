# Quick Start - Deploy to innovationdesign.io

## What's Been Set Up

✅ Auth0 credentials configured in `.env` file
✅ Logout button added to Carbon UI Shell header with proper icon
✅ Production Docker configuration created
✅ Nginx configuration optimized for production
✅ Deployment scripts ready

## Deploy Now

### Option 1: Automated Deployment (Recommended)

Simply run:
```bash
./deploy-to-droplet.sh
```

This will:
- Sync your local source to the droplet
- Preserve the production `.env` and Auth0 credentials already on the droplet
- Rebuild only the app services that need to change
- Display deployment status

### Option 2: Manual Deployment

1. SSH into the droplet:
```bash
ssh root@104.248.170.26
```

2. Follow the steps in `DEPLOYMENT.md`

## Post-Deployment: Configure Auth0

⚠️ **CRITICAL**: After deployment, add these URLs to your Auth0 Application:

1. Go to: https://manage.auth0.com/dashboard/us/dev-i4m880asz7y6j5sk/applications
2. Select your application (Client ID: 1tKb110HavDT3KsqC5P894JEOZ3fQXMm)
3. Add to **Allowed Callback URLs**:
   ```
   https://innovationdesign.io,
   http://innovationdesign.io,
   http://104.248.170.26
   ```
4. Add to **Allowed Logout URLs**:
   ```
   https://innovationdesign.io,
   http://innovationdesign.io,
   http://104.248.170.26
   ```
5. Add to **Allowed Web Origins**:
   ```
   https://innovationdesign.io,
   http://innovationdesign.io,
   http://104.248.170.26
   ```
6. Click **Save Changes**

## DNS Configuration

Point your domain to the droplet:
- Type: A Record
- Name: @ (or innovationdesign.io)
- Value: 104.248.170.26
- TTL: 3600

## Files Changed

- `.env` - Auth0 environment variables
- `ddr-public/src/main.jsx` - Updated to use environment variables
- `ddr-public/src/components/Header/Header.jsx` - Added Logout icon
- `docker-compose.prod.yml` - Production Docker setup
- `ddr-public/nginx.prod.conf` - Production nginx config
- `ddr-public/Dockerfile` - Updated to accept build args
- `deploy.sh` - Deployment script
- `deploy-to-droplet.sh` - Automated SSH deployment
- `DEPLOYMENT.md` - Full deployment documentation

## Verify Deployment

After running the deployment:

1. Check the site: http://104.248.170.26 or http://innovationdesign.io
2. Test login/logout functionality
3. Verify Auth0 authentication works

## Need SSL?

See `DEPLOYMENT.md` section 8 for Let's Encrypt SSL setup instructions.
