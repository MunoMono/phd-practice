# Release v1.0.1 - Data Quality Baseline

**Release Date:** 30 January 2026  
**Tag:** `v1.0.1`  
**Status:** ✅ Production Deployed

---

## Summary

Data quality baseline with corrected PDF/TIFF counts and ML provenance tracking. This release fixes media count inaccuracies from v1.0.0 and establishes accurate human-in-the-loop training corpus metrics.

---

## Critical Fixes

### Media Count Corrections
- **PDF Counts Fixed:** Accurate counts extracted from DDR Archive GraphQL API
  - Previously counted `attached_media` array items (4)
  - Now correctly sums `pdf_files` arrays within media items (59 total)
- **ML Provenance Filter:** Tracks `use_for_ml=true` flag for training corpus
  - 7 PDFs approved for ML training out of 59 total
  - Human-in-the-loop curation tracked via digital_assets metadata

### Schema Updates
- Renamed `jpg_count` → `tiff_count` (accurate terminology for ingested media)
- Added `ml_pdf_count` field for ML-approved PDFs
- Added `ml_tiff_count` field for ML-approved TIFFs (currently 0)
- GraphQL schema returns both total and ML-approved counts

### Database State
```sql
-- Accurate PID Authority Media Counts (as of v1.0.1)
-- Bruce Archer (873981573030): 16 PDFs (2 ML), 0 TIFFs
-- Kenneth Agnew (451248821104): 7 PDFs (3 ML), 0 TIFFs  
-- RCA Prospectuses (880612075513): 20 PDFs (1 ML), 0 TIFFs
-- RCA Rector's reports (124881079617): 16 PDFs (1 ML), 0 TIFFs
-- TOTALS: 59 PDFs (7 ML-approved), 0 TIFFs per-PID
```

**Note:** 5 TIFFs exist in Digital Ocean Spaces but not tracked per-PID yet. All have `use_for_ml=FALSE`.

---

## UI/UX Improvements

- **IBM Carbon Design Compliance:** Changed list bullets from round (•) to dashed (–)
- **Provenance Display:** Dashboard shows ML-approved vs total media counts
- **Typography:** PID lists use monospace font for better readability

---

## Infrastructure

### Database
- **Engine:** PostgreSQL 15 + pgvector
- **Password:** `postgres/postgres` (stabilized after authentication issues)
- **Backup:** `epistemic_drift_v1.0.1_20260130_140402.sql` (29KB)

### Code
- **Backup:** `phd-practice_v1.0.1_code_20260130_140418.tar.gz` (7.6MB)
- **Location:** `/root/` on production server

### Deployment
- **Production URL:** https://innovationdesign.io
- **Backend:** Docker container with Python 3.11, FastAPI, Strawberry GraphQL
- **Frontend:** React + Vite + IBM Carbon Design System
- **Auth:** Auth0 SPA flow (working, "Hello Graham" displayed)

---

## Training Corpus Metrics

### ML-Approved Media (use_for_ml=true)
| PID Authority | Total PDFs | ML PDFs | Total JPGs | ML JPGs |
|---------------|------------|---------|------------|---------|
| Bruce Archer (873981573030) | 16 | 2 | 16 | 0 |
| Kenneth Agnew (451248821104) | 7 | 3 | 17 | 0 |
| RCA Prospectuses (880612075513) | 20 | 1 | 20 | 0 |
| RCA Rector's reports (124881079617) | 16 | 1 | 16 | 0 |
| **TOTALS** | **59** | **7** | **69** | **0** |

**Training Corpus:** 7 PDFs curated for ML training via human-in-the-loop provenance

---

## Known Issues

1. **Database Password:** Still using default `postgres/postgres` - needs hardening for production
2. **Connection Pool:** Backend requires full restart after database password changes
3. **TIFF Tracking:** Only 5 TIFFs in Spaces, not tracked per-PID in database yet
4. **S3 Env Vars:** Missing environment variables cause warnings (non-critical)

---

## Technical Debt

- [ ] Update `fetch_and_sync_pids.py` to use correct PDF counting logic
- [ ] Implement TIFF-per-PID tracking if needed for provenance
- [ ] Secure database credentials (rotate from default password)
- [ ] Add database connection retry logic to backend

---

## Deployment Commands

```bash
# Pull latest code
ssh root@innovationdesign.io "cd /root/phd-practice && git pull"

# Rebuild and restart backend
ssh root@innovationdesign.io "cd /root/phd-practice && docker compose -f docker-compose.prod.yml build --no-cache backend && docker compose -f docker-compose.prod.yml up -d backend"

# Rebuild and restart frontend
ssh root@innovationdesign.io "cd /root/phd-practice && docker compose -f docker-compose.prod.yml build --no-cache frontend && docker compose -f docker-compose.prod.yml up -d frontend"

# Reset database password if needed
ssh root@innovationdesign.io "docker exec phd-practice-db psql -U postgres -d epistemic_drift -c \"ALTER USER postgres WITH PASSWORD 'postgres';\""
```

---

## Verification

```bash
# Test GraphQL API
curl -s 'https://innovationdesign.io/api/graphql' -H 'Content-Type: application/json' \
  -d '{"query":"{ systemMetrics { pidAuthorities { pid title pdfCount mlPdfCount tiffCount mlTiffCount } } }"}' | jq

# Expected response:
# - 4 PID authorities returned
# - Total PDFs: 59 (7 ML-approved)
# - TIFFs per-PID: 0
```

---

## Git History

```
4d735cc Use IBM Carbon dashed bullets (–) instead of round bullets (•)
df8fd74 Fix TIFF counts: rename jpg->tiff fields, set to 0 (only 5 TIFFs total, all ML=FALSE)
fe4e52c Add ML-approved TIFF counts (57 total): 4+17+20+16 across 4 PIDs
8778dde Add v1.0.0 release documentation and backups
```

---

## Attribution

**Research Context:** PhD research on epistemic drift in design methods, supervised at Royal College of Art. Uses DDR Archive (Design & Designers in Residence) as source repository via persistent identifiers (PIDs).

**Lead Developer:** Graham (AI-assisted development)  
**Institution:** Royal College of Art  
**Data Source:** DDR Archive GraphQL API (https://api.ddrarchive.org/graphql)

---

## Next Steps

1. ✅ **v1.0.1 Tagged and Deployed** - Data quality baseline established
2. 🔄 **Docling Integration** - Process 7 ML-approved PDFs with IBM Docling
3. 🔄 **Embedding Generation** - Create 384-dim BERT embeddings for chunks
4. 🔄 **Granite Fine-tuning** - Train on curated corpus with provenance tracking

---

**End of Release Notes v1.0.1**
