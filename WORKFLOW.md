# Efficient Development & Deployment Workflow

## 🚀 Quick Reference

### For UI iterations (fastest)
```bash
# Option 1: Frontend-only production deploy (~30 seconds)
./deploy-frontend-only.sh

# Option 2: Local dev with hot reload (instant changes)
docker compose -f docker-compose.dev.yml up
# Edit files in frontend/src - changes appear instantly in browser
```

### For backend changes
```bash
./deploy-to-droplet.sh
```

---

## 📋 Deployment Strategies

### 1. Local Development with Hot Reload (Recommended for UI work)

**Best for:** Rapid UI iterations, testing, styling

```bash
# Start local dev environment
docker compose -f docker-compose.dev.yml up

# Access app
open http://localhost:5173
```

**Benefits:**
- ⚡ Instant hot module replacement (HMR)
- 🔄 Changes appear in browser without refresh
- 🎨 Perfect for CSS/styling tweaks
- 🐛 Better debugging with source maps
- ⏱️  0 seconds deploy time

**How it works:**
- Frontend runs Vite dev server with HMR
- Source code mounted as volumes
- Edit files → see changes instantly
- Backend also has hot reload enabled

When happy with changes:
```bash
git add -A
git commit -m "Your changes"
git push
./deploy-frontend-only.sh  # ~30 seconds
```

---

### 2. Frontend-Only Production Deploy (Fast)

**Best for:** UI changes ready for production

```bash
./deploy-frontend-only.sh
```

**Benefits:**
- ⏱️  ~30 seconds (vs 5+ minutes)
- 📦 Only rebuilds frontend container
- 🎯 Uses Docker layer caching
- 🔄 Zero downtime restart

**What happens:**
1. Pulls latest code from git
2. Rebuilds only frontend (npm packages cached)
3. Restarts frontend container only
4. Backend/DB keep running

**Use when:**
- ✅ Only changed files in `frontend/src`
- ✅ CSS/styling updates
- ✅ Component changes
- ✅ Page content updates
- ❌ NOT for package.json changes (use full deploy)

---

### 3. Full Stack Deploy (Comprehensive)

**Best for:** Backend changes, new packages, infrastructure updates

```bash
./deploy-to-droplet.sh
```

**What rebuilds:**
- Backend + all Python packages (5+ minutes)
- Frontend + all npm packages
- Database migrations if needed

**Use when:**
- ✅ Backend code changes
- ✅ New Python/npm packages added
- ✅ Environment variable changes
- ✅ Database schema changes
- ✅ Docker configuration changes

---

## 🎯 Workflow Examples

### Scenario 1: Tweaking button colors
```bash
# Start dev environment
docker compose -f docker-compose.dev.yml up -d

# Edit frontend/src/styles/components/Button.scss
# See changes instantly in browser at http://localhost:5173

# When satisfied
git commit -am "Update button colors"
git push
./deploy-frontend-only.sh
```
**Time:** Instant locally, 30s to production

---

### Scenario 2: Adding new page
```bash
# Work locally with hot reload
docker compose -f docker-compose.dev.yml up -d

# Create new component
# Test routing
# Adjust styling

# Deploy
git add frontend/src/pages/NewPage/
git commit -m "Add new analytics page"
git push
./deploy-frontend-only.sh
```
**Time:** 30s to production

---

### Scenario 3: Adding new Python package
```bash
# Add package to backend/requirements.txt
# Must do full deploy for this

git commit -am "Add new ML library"
git push
./deploy-to-droplet.sh
```
**Time:** ~5 minutes (unavoidable for dependency changes)

---

## 💡 Pro Tips

### Speed up npm installs
Already optimized! Dockerfile uses:
- Multi-stage builds
- `npm ci` instead of `npm install`
- Layer caching (package.json copied before source)

### Speed up pip installs
Already optimized! Dockerfile uses:
- `--no-cache-dir` flag
- requirements.txt copied before source
- Layer caching

### For 100s of UI iterations
**Use local dev exclusively:**
```bash
# Once at start of day
docker compose -f docker-compose.dev.yml up -d

# Work all day with instant feedback
# Edit → Save → See change (< 1 second)

# At end of day, deploy polished work
git commit -am "Day's UI improvements"
git push
./deploy-frontend-only.sh
```

### Check what's running
```bash
# Local
docker compose -f docker-compose.dev.yml ps

# Production (on droplet)
ssh root@104.248.170.26 "cd /root/phd-practice && docker compose -f docker-compose.prod.yml ps"
```

### View logs
```bash
# Local frontend
docker compose -f docker-compose.dev.yml logs -f frontend

# Production frontend
ssh root@104.248.170.26 "cd /root/phd-practice && docker compose -f docker-compose.prod.yml logs -f frontend"
```

---

## 🔧 Troubleshooting

### "Changes not appearing locally"
- Check volume mounts: `docker compose -f docker-compose.dev.yml ps`
- Restart dev server: `docker compose -f docker-compose.dev.yml restart frontend`
- Hard refresh browser: Cmd+Shift+R

### "Frontend deploy seems slow"
- First deploy after package.json change is slow (rebuilds npm packages)
- Subsequent deploys are fast (~30s) thanks to layer caching

### "Want to skip git push"
You can work directly on droplet (not recommended):
```bash
ssh root@104.248.170.26
cd /root/phd-practice
# Make changes
docker compose -f docker-compose.prod.yml up -d --build frontend
```

---

## 📊 Deployment Time Comparison

| Method | Time | Use Case |
|--------|------|----------|
| Local dev (HMR) | < 1 sec | Active development |
| Frontend-only deploy | ~30 sec | UI changes to production |
| Full deploy | ~5 min | Backend/package changes |

---

## 🎨 Recommended Daily Workflow

**Morning:**
```bash
git pull
docker compose -f docker-compose.dev.yml up -d
open http://localhost:5173
```

**During day:**
- Edit files in `frontend/src`
- Changes appear instantly
- Test in browser
- Commit frequently: `git commit -am "Feature X"`

**Before leaving:**
```bash
git push
./deploy-frontend-only.sh
```

**Result:** Hundreds of iterations, instant feedback, 30 second deploys! 🚀
