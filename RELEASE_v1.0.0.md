# EPISTEMIC DRIFT RESEARCH - Release v1.0.0

**Release Date:** January 30, 2026  
**Deployed:** https://innovationdesign.io  
**Git Tag:** v1.0.0

---

## 🎯 Release Highlights

First production release with Auth0 authentication, PID-validated authority tracking, and GraphQL API ready for Docling document ingestion.

---

## 🔐 Authentication

- **Auth0 Domain:** dev-i4m880asz7y6j5sk.us.auth0.com
- **Client ID:** 1s7mH4zeZ1iDyLFcbi6elTNL7fttJwGg
- **Flow:** SPA with direct redirect (email/password only, no Google OAuth)
- **Callback URLs:**
  - http://localhost:5173 (development)
  - https://innovationdesign.io (production)

---

## 📊 Database State

- **4 PID-validated authority records**
- **10 tables** (documents, document_chunks, training_runs, corpus_snapshots, etc.)
- **PostgreSQL 15** with pgvector extension
- **Ready for:** Docling document ingestion

---

## 📚 PID Authorities (Training Corpus)

| PID | Title | PDF Count (ML=TRUE) |
|-----|-------|---------------------|
| 873981573030 | Bruce Archer collection | 2 PDFs |
| 451248821104 | Kenneth Agnew collection | 2 PDFs |
| 880612075513 | RCA Prospectuses \| 1967-85 | 1 PDF |
| 124881079617 | RCA Rector's reports \| 1967-85 | 1 PDF |

**Total:** 6 PDFs flagged for ML training with full DDR Archive provenance

---

## 💾 Backups Created

All backups stored on production server at `/root/backups/` and `/root/ai-methods/backups/`

### Database Backup
```
epistemic_drift_v1.0_20260130_132839.sql (29KB)
Location: /root/ai-methods/backups/
```

### Code Backup
```
ai-methods_v1.0_code_20260130_132909.tar.gz (3.8MB)
Location: /root/backups/
Excludes: node_modules, __pycache__, .git
```

### Git Tag
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## 🏗️ Architecture

### Frontend
- **Framework:** React 18 + Vite
- **UI Library:** IBM Carbon Design System
- **Auth:** @auth0/auth0-react
- **Deployment:** Nginx (port 80/443)
- **Container:** epistemic-drift-frontend

### Backend
- **Framework:** FastAPI + Uvicorn
- **Auth:** python-jose (JWT validation ready, not enforced yet)
- **API:** REST + GraphQL (Strawberry)
- **Deployment:** Docker (port 8000)
- **Container:** epistemic-drift-backend

### Database
- **Engine:** PostgreSQL 15
- **Extensions:** pgvector (for BERT embeddings)
- **Container:** epistemic-drift-db (ankane/pgvector:latest)
- **Deployment:** Docker (port 5432)

### Docker Volumes
- `ai-methods_postgres_data` - Database persistence
- `ai-methods_backend_logs` - Application logs
- `ai-methods_model_cache` - Hugging Face models
- `ai-methods_minio_data` - S3-compatible storage (not yet configured)

---

## 🚀 Deployment Commands

### Full Stack Restart
```bash
cd /root/ai-methods
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Backend Only
```bash
cd /root/ai-methods
git pull
docker compose -f docker-compose.prod.yml build backend
docker compose -f docker-compose.prod.yml up -d backend
```

### Frontend Only
```bash
cd /root/ai-methods
git pull
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Database Backup
```bash
docker exec epistemic-drift-db pg_dump -U postgres epistemic_drift > backup_$(date +%Y%m%d).sql
```

### Database Restore
```bash
docker exec -i epistemic-drift-db psql -U postgres epistemic_drift < backup_20260130.sql
```

---

## 📋 Database Schema (v1.0)

### Core Tables
- `documents` - PID-linked authority records with metadata
- `document_chunks` - Text chunks for vector search
- `document_embeddings` - BERT 384-dim embeddings
- `training_runs` - IBM Granite fine-tuning provenance
- `corpus_snapshots` - SHA-256 versioned training corpus states
- `inference_logs` - Session tracking for XAI
- `drift_analyses` - Temporal drift detection results

### Support Tables
- `research_sessions` - User inference sessions
- `experiments` - ML experiment tracking
- `digital_assets` - S3 file references (not yet used)

---

## 🔍 API Endpoints

### GraphQL (Primary)
```
POST https://innovationdesign.io/api/graphql

Query Example:
{
  systemMetrics {
    pidCount
    pidAuthorities {
      pid
      title
      pdfCount
      tiffCount
    }
  }
}
```

### REST (Legacy, deprecated)
```
GET https://innovationdesign.io/api/metrics/stats
GET https://innovationdesign.io/api/v1/sync/pids
```

---

## 📦 Environment Variables (.env)

### Frontend (VITE_*)
```bash
VITE_AUTH0_DOMAIN=dev-i4m880asz7y6j5sk.us.auth0.com
VITE_AUTH0_CLIENT_ID=1tKb110HavDT3KsqC5P894JEOZ3fQXMm
VITE_AUTH0_AUDIENCE=https://api.ddrarchive.org
VITE_AUTH0_REDIRECT_URI=https://innovationdesign.io
VITE_DDR_ENV=production
VITE_GRAPHQL_ENDPOINT=https://ddrarchive.org/graphql
```

### Backend
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=epistemic_drift
POSTGRES_HOST=db
POSTGRES_PORT=5432
AUTH0_DOMAIN=dev-i4m880asz7y6j5sk.us.auth0.com
AUTH0_AUDIENCE=https://api.ddrarchive.org
```

---

## 🎯 Next Steps (v1.1 Roadmap)

### Immediate (Week 1)
1. ✅ Baseline v1.0.0 release
2. 🔄 Docling ingestion of 6 ML-flagged PDFs
3. 🔄 Generate BERT embeddings (sentence-transformers)
4. 🔄 Test evidence tracer with chunk → PID provenance

### Short-term (Month 1)
5. IBM Granite 3.1 8B model loading
6. Fine-tuning pipeline with PID provenance
7. Session recorder with full XAI attribution
8. Temporal drift analysis (1965-1985)

### Medium-term (Quarter 1)
9. Expand to 50 PID authorities (Year 1 target)
10. S3/Spaces integration for PDF storage
11. Advanced drift visualization
12. Supervisor validation interface

---

## 🐛 Known Issues

- ✅ ~~Database password authentication errors~~ (FIXED: v1.0.0)
- ✅ ~~PID authorities showing generic titles~~ (FIXED: v1.0.0)
- ⚠️ S3 storage not configured (variables blank, no impact on core functionality)
- ⚠️ Backend JWT validation implemented but not enforced on endpoints yet

---

## 📝 Notes

- **Database credentials:** Default `postgres/postgres` - change for production security
- **Auth0 free tier:** Email/password only, no social logins
- **GraphQL preferred:** REST endpoints deprecated, use GraphQL for all new features
- **Backup strategy:** Manual backups before major changes, automated backups TBD

---

## 🙏 Attribution

- **IBM Granite:** Enterprise AI models (not yet loaded)
- **DDR Archive:** Design research provenance (https://ddrarchive.org)
- **IBM Carbon:** Design system components
- **Auth0:** Authentication platform
- **Docling:** PDF document processing (ready to integrate)

---

**End of Release Notes v1.0.0**
