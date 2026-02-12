# Auth0 Configuration Guide

## Step 1: Configure Auth0 Application Settings

Go to your Auth0 dashboard: https://manage.auth0.com/

Navigate to: **Applications** → **Applications** → **Epistemic Drift Research** (or your app name)

### Application URIs

Add the following URLs to your application settings:

**Allowed Callback URLs:**
```
http://localhost:5173, https://innovationdesign.io
```

**Allowed Logout URLs:**
```
http://localhost:5173, https://innovationdesign.io
```

**Allowed Web Origins:**
```
http://localhost:5173, https://innovationdesign.io
```

**Allowed Origins (CORS):**
```
http://localhost:5173, https://innovationdesign.io
```

Click **Save Changes** at the bottom of the page.

## Step 2: Create an API in Auth0 (Optional but Recommended)

For backend JWT validation, create an Auth0 API:

1. Go to **Applications** → **APIs** → **Create API**
2. Name: `Epistemic Drift Research API`
3. Identifier: `https://innovationdesign.io/api` (or any unique identifier)
4. Signing Algorithm: `RS256`
5. Click **Create**

Then update the backend `.env` file:
```bash
AUTH0_AUDIENCE=https://innovationdesign.io/api
```

## Step 3: Deploy to Production

### Backend Deployment

SSH into your server and update the `.env` file:

```bash
ssh root@innovationdesign.io

cd /root/phd-practice/backend
nano .env
```

Add these lines (if not already present):
```
AUTH0_DOMAIN=dev-i4m880asz7y6j5sk.us.auth0.com
AUTH0_AUDIENCE=https://innovationdesign.io/api
ALLOWED_ORIGINS=["http://localhost:5173", "https://innovationdesign.io"]
```

Save and exit (Ctrl+X, Y, Enter)

### Deploy Both Frontend and Backend

```bash
cd /root/phd-practice
git pull
docker compose -f docker-compose.prod.yml build --no-cache
docker compose -f docker-compose.prod.yml up -d
```

## Step 4: Test Authentication

1. Navigate to https://innovationdesign.io
2. You should see the login page
3. Click "Sign in to continue"
4. You'll be redirected to Auth0 login
5. After login, you'll be redirected back to the dashboard

## Credentials Used

- **Domain:** dev-i4m880asz7y6j5sk.us.auth0.com
- **Client ID:** 1s7mH4zeZ1iDyLFcbi6elTNL7fttJwGg
- **Client Secret:** FIxgtZPUfGXEdNKPE87XN6nCG2EdvecfXox9LZmMl0Nqr3FkSqrKVA6n9wlVuin6

## Security Notes

- Client Secret is only needed for server-to-server authentication (not used in SPA flow)
- JWT tokens are verified using Auth0's public keys (JWKS)
- All API endpoints can be protected by adding `user = Depends(get_current_user)` to route functions
- User session is stored in browser localStorage with automatic token refresh

## Protecting Backend Endpoints (Example)

To protect an endpoint, import and use the auth dependency:

```python
from app.core.auth import get_current_user
from fastapi import Depends

@router.get("/protected-endpoint")
async def protected_route(user: dict = Depends(get_current_user)):
    return {"message": f"Hello {user['email']}!"}
```

For optional authentication:

```python
from app.core.auth import get_optional_user

@router.get("/optional-auth")
async def optional_route(user: dict = Depends(get_optional_user)):
    if user:
        return {"message": f"Welcome back {user['email']}!"}
    return {"message": "Hello anonymous user!"}
```
