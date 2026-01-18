# Deployment Checklist - January 2026

## ✅ Pre-Deployment Verification

### Frontend Build
- [x] Frontend builds successfully without errors
- [x] SCSS syntax error fixed (Dashboard.scss line 95)
- [x] All new components added:
  - [x] Enhanced StatsCards with progress bars and tags
  - [x] Premium styling with IBM enterprise design
  - [x] Status badges on all pages
  - [x] Gradient animations and micro-interactions
- [x] Build size: ~500KB (acceptable, consider code-splitting in future)

### Backend Architecture
- [x] PID-gated architecture implemented
- [x] GraphQL sync service created (`backend/app/services/graphql_sync.py`)
- [x] S3 sync with PID validation (`backend/app/services/s3_sync.py`)
- [x] Authority service for validation (`backend/app/services/authority_service.py`)
- [x] Provenance service for XAI (`backend/app/services/provenance_service.py`)
- [x] API routes:
  - [x] `/api/graphql_sync/*` - GraphQL sync endpoints
  - [x] `/api/provenance/*` - Provenance tracking
  - [x] `/api/documents/*` - Document upload with PID requirement
- [x] Dependencies in `requirements.txt`:
  - [x] fastapi==0.115.0
  - [x] sqlalchemy==2.0.36
  - [x] pgvector==0.3.5
  - [x] boto3==1.35.60
  - [x] transformers, sentence-transformers, docling

### Database
- [x] Migration script ready: `backend/migrations/001_add_pid_to_documents.sql`
  - [x] Adds PID columns (pid, authority_id, authority_data)
  - [x] Creates provenance tables (training_runs, inference_logs, corpus_snapshots)
  - [x] Adds pgvector Vector(384) type for embeddings
  - [x] Creates indexes and constraints
- [ ] **ACTION REQUIRED**: Run migration after deployment
  ```bash
  psql -h localhost -U postgres -d epistemic_drift -f backend/migrations/001_add_pid_to_documents.sql
  ```

### Documentation
- [x] PID_ARCHITECTURE.md - Complete architecture guide
- [x] PROVENANCE_GUIDE.md - XAI and citation system
- [x] TESTING_GUIDE.md - Testing procedures
- [x] YEAR1_SUPERVISOR_BRIEF.md - PhD Year 1 status report

### Docker Configuration
- [x] `docker-compose.yml` - Development environment
- [x] `docker-compose.prod.yml` - Production environment
- [x] Backend Dockerfile exists
- [x] Frontend Dockerfile exists
- [x] nginx configuration for production

### Environment Variables Needed
Create `.env` file on production server with:
```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<SECURE_PASSWORD>
POSTGRES_DB=epistemic_drift

# S3/DO Spaces
S3_BUCKET=<your-bucket>
S3_ENDPOINT=<spaces-endpoint>
S3_ACCESS_KEY=<access-key>
S3_SECRET_KEY=<secret-key>

# Auth0
VITE_AUTH0_DOMAIN=dev-i4m880asz7y6j5sk.us.auth0.com
VITE_AUTH0_AUDIENCE=https://api.ddrarchive.org
VITE_AUTH0_CLIENT_ID=<client-id>

# Granite Model (optional - defaults to CPU)
GRANITE_MODEL_PATH=ibm-granite/granite-4.0-h-small-instruct
GRANITE_DEVICE=cpu
```

## 📋 Deployment Steps

### 1. Commit and Push Changes
```bash
git add .
git commit -m "feat: PID-gated architecture + provenance system + premium UI

- Implement PID allowlist filter for training corpus quality control
- Add GraphQL and S3 sync services with authority validation
- Create comprehensive provenance system for academic rigor
- Add training_runs, inference_logs, corpus_snapshots tables
- Enhance frontend with IBM enterprise styling and animations
- Add progress bars, status badges, and gradient effects
- Update all pages with premium visual design
- Add supervisor documentation (YEAR1_SUPERVISOR_BRIEF.md)"

git push origin main
```

### 2. Deploy to Digital Ocean Droplet
```bash
# SSH into droplet
ssh root@104.248.170.26

# Navigate to project
cd /path/to/ai-methods

# Run deployment script
./deploy.sh
```

### 3. Run Database Migration
```bash
# Connect to database container
docker exec -it epistemic-drift-db psql -U postgres -d epistemic_drift

# Or from host
psql -h localhost -U postgres -d epistemic_drift -f backend/migrations/001_add_pid_to_documents.sql
```

### 4. Verify Deployment
- [ ] Visit http://innovationdesign.io
- [ ] Check Dashboard loads with new premium styling
- [ ] Verify stats cards show PID metrics
- [ ] Check Evidence Tracer, Experimental Log, Session Recorder pages
- [ ] Test GraphQL endpoint: http://innovationdesign.io/graphql
- [ ] Verify backend health: http://innovationdesign.io/api/health

### 5. Test Core Functionality
- [ ] GraphQL sync: `POST /api/graphql_sync/sync-item` with PID
- [ ] S3 sync: Check PID filtering works
- [ ] Upload document: Verify PID requirement enforced
- [ ] Check database has new tables:
  ```sql
  \dt  -- Should show training_runs, inference_logs, corpus_snapshots
  \d documents  -- Should show pid, authority_id columns
  ```

## 🚨 Known Issues & TODOs

### Post-Deployment Tasks
1. **Complete Docling Implementation**
   - Replace TODOs in `backend/app/services/docling_processor.py`
   - Test PDF and TIFF extraction with OCR

2. **Expand Corpus**
   - Currently: 3 PIDs
   - Target: 50-100 PIDs for Year 1
   - Add TIFF metadata to GraphQL for PID 001808484369

3. **GraphQL Schema Updates**
   - Add `pidCount` to systemMetrics query
   - Add `trainingRuns`, `corpusSnapshots` table counts
   - Add `tiffs` count to s3Storage

4. **Performance Optimization**
   - Consider code-splitting for frontend (500KB bundle)
   - Test pgvector performance with 50K+ chunks
   - Benchmark IVFFlat indexes

### Optional Enhancements
- Add automated backups for corpus snapshots
- Implement drift analysis algorithms
- Build semantic search interface
- Add temporal visualization dashboard
- Export training datasets in HuggingFace format

## 📊 Success Metrics

### Immediate (Week 1)
- [x] Frontend builds without errors
- [x] Backend has all new services
- [ ] Database migration runs successfully
- [ ] Application deploys to production
- [ ] All pages load with new styling

### Short-term (Month 1)
- [ ] Docling processing 10+ PIDs
- [ ] First corpus snapshot created
- [ ] GraphQL sync tested with real data
- [ ] Provenance system logs first inference

### Medium-term (Quarter 1)
- [ ] 20-50 PIDs in corpus
- [ ] First training run with Granite
- [ ] Temporal drift analysis implemented
- [ ] Supervisor review completed

## 🔒 Security Checklist
- [ ] Environment variables not committed to git
- [ ] Strong database password set
- [ ] S3 credentials secured
- [ ] Auth0 properly configured
- [ ] HTTPS/SSL enabled (via nginx)
- [ ] CORS policies configured
- [ ] Rate limiting on API endpoints

## 🎯 Rollback Plan
If deployment fails:
```bash
# Stop new containers
docker-compose -f docker-compose.prod.yml down

# Restore previous version
git reset --hard HEAD~1
docker-compose -f docker-compose.prod.yml up -d

# Rollback database if needed
# (Use backup from scripts/backup-database.sh)
```

---

**Deployment Date**: January 18, 2026  
**Version**: v1.0.0-year1-baseline  
**Status**: ✅ Ready for deployment
