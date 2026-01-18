# PID-Gated Training Corpus Architecture

## Overview

This system implements a **PID-based allowlist filter** to ensure only curated, authority-linked digital assets enter the Grantie model training corpus.

## Architecture Principles

### 1. **Postgres Authorities = Source of Truth**
- CSV authorities loaded into Postgres
- Each authority record has a unique **PID (Persistent Identifier)**
- PIDs are the canonical reference for all digital assets

### 2. **DigitalOcean Spaces Storage**
- Digital media assets (PDFs, TIFFs) uploaded to DO Spaces
- Assets **must** have PID linkage (via filename, metadata, or explicit tagging)
- Non-PID assets are ignored during sync (not training-eligible)

### 3. **GraphQL Metadata Layer**
- DDR Archive GraphQL API exposes authority metadata
- Includes human-curated captions for each digital asset
- Provides rich contextual data harmonized with the assets themselves

### 4. **Training Corpus Filter**
- **ONLY** documents with valid PIDs are processed
- S3 sync validates PID against Postgres authorities
- Upload endpoint requires PID as mandatory field
- GraphQL queries can filter for `only_with_pid: true`

## Critical Files

### Database Schema
- [`backend/app/models/document.py`](backend/app/models/document.py)
  - `pid` column (REQUIRED, UNIQUE, INDEXED)
  - `authority_id` column (DDR Archive ID)
  - `authority_data` JSONB (cached GraphQL metadata)

### Services
- [`backend/app/services/authority_service.py`](backend/app/services/authority_service.py)
  - PID validation against DDR Archive GraphQL
  - Authority metadata fetching
  - Enrichment of document records with captions/metadata

- [`backend/app/services/s3_sync.py`](backend/app/services/s3_sync.py)
  - `list_training_assets_in_bucket()` - Only returns PID-linked assets
  - `extract_pid_from_s3_key()` - Parses PID from filename/metadata
  - `get_valid_pids_from_postgres()` - Builds allowlist from database

### API Endpoints
- [`backend/app/api/routes/documents.py`](backend/app/api/routes/documents.py)
  - Upload endpoint requires `pid` parameter
  - Validates file types (PDF/TIFF only)
  - Rejects uploads without valid PID

### GraphQL Schema
- [`backend/app/api/graphql/schema.py`](backend/app/api/graphql/schema.py)
  - `temporal_documents(only_with_pid: true)` - Query training corpus
  - `training_corpus_stats` - PID coverage metrics

## Workflow

### 1. Authority Creation (Postgres)
```
CSV → Postgres authorities table
  ↓
Assign PID to each record
  ↓
PID becomes canonical reference
```

### 2. Digital Asset Upload (DO Spaces)
```
Curator uploads PDF/TIFF to DO Spaces
  ↓
Filename includes PID (e.g., pid_12345_document.pdf)
OR S3 metadata tagged with PID
  ↓
Asset is now discoverable by PID
```

### 3. Ingestion via Upload Endpoint
```python
POST /api/v1/documents/upload
{
  "file": <pdf_or_tiff>,
  "pid": "12345",  # REQUIRED
  "publication_year": 1970,
  "title": "Document Title"
}
```

**Validation:**
- ✅ PID must be provided
- ✅ PID validated against authorities (optional, can be async)
- ✅ Only PDF/TIFF accepted
- ❌ Rejects if no PID
- ❌ Rejects if invalid file type

### 4. S3 Sync (Batch Processing)
```python
from app.services.s3_sync import S3SyncService

sync = S3SyncService()

# Get only PID-linked assets (training corpus)
assets = sync.list_training_assets_in_bucket(enforce_pid_filter=True)

for asset in assets:
    if asset['pid']:
        # Download and process
        sync.process_pdf(asset, temp_path)
```

**Filter Logic:**
1. List all PDFs/TIFFs in bucket
2. Extract PID from S3 key/metadata
3. Check if PID exists in Postgres authorities
4. **Reject if no PID or invalid PID**
5. Process only allowlisted assets

### 5. GraphQL Queries (Training Corpus)
```graphql
query GetTrainingCorpus {
  # Only PID-linked documents
  temporalDocuments(
    startYear: 1965,
    endYear: 1985,
    onlyWithPid: true  # CRITICAL FILTER
  ) {
    documentId
    pid
    authorityId
    title
    publicationYear
  }
  
  # Coverage statistics
  trainingCorpusStats {
    totalDocuments
    totalWithPid
    totalWithoutPid  # Orphaned assets
    pidCoveragePercent
  }
}
```

## PID Extraction Strategies

### Filename Patterns
```
pid_12345_document.pdf        → PID: 12345
PID-67890-report.pdf          → PID: 67890
00123_analysis.tiff           → PID: 00123
```

### S3 Metadata (Recommended)
```python
# When uploading to S3, tag with PID
s3_client.put_object(
    Bucket='my-bucket',
    Key='document.pdf',
    Body=file_content,
    Metadata={
        'pid': '12345',  # Most reliable method
        'authority_id': 'auth_67890'
    }
)
```

## Training Pipeline Integration

### Export Training Data
```python
from app.core.database import LocalSessionLocal
from app.models.document import Document

db = LocalSessionLocal()

# ONLY get PID-linked documents
training_docs = db.query(Document).filter(
    Document.pid.isnot(None),  # CRITICAL FILTER
    Document.processing_status == 'completed'
).all()

for doc in training_docs:
    # doc.pid - authority linkage
    # doc.authority_data - GraphQL metadata with captions
    # doc.extracted_text - Docling-processed content
    # doc.s3_key - link to actual PDF/TIFF in DO Spaces
    
    # Prepare multi-modal training example:
    training_example = {
        'text': doc.extracted_text,
        'caption': doc.authority_data.get('caption'),
        'metadata': doc.authority_data,
        'image_path': doc.s3_key,  # For TIFF images
        'pid': doc.pid
    }
```

## Data Quality Monitoring

### Check PID Coverage
```sql
SELECT 
  COUNT(*) as total_documents,
  COUNT(pid) as documents_with_pid,
  COUNT(*) - COUNT(pid) as orphaned_documents,
  ROUND(COUNT(pid)::numeric / COUNT(*)::numeric * 100, 2) as pid_coverage_percent
FROM documents;
```

### Find Orphaned Assets
```sql
-- Documents without PID (not training-eligible)
SELECT document_id, filename, publication_year, s3_key
FROM documents 
WHERE pid IS NULL
ORDER BY created_at DESC;
```

### Validate PID Linkages
```sql
-- Check if PIDs actually exist in authorities
-- (Requires join with authorities table or GraphQL validation)
SELECT d.document_id, d.pid, d.authority_id
FROM documents d
WHERE d.pid IS NOT NULL
AND d.authority_data IS NULL;  -- Not enriched with GraphQL data
```

## Migration

To add PID columns to existing database:

```bash
psql -d epistemic_drift -f backend/migrations/001_add_pid_to_documents.sql
```

Or run via SQLAlchemy:
```python
from app.core.database import local_engine
from sqlalchemy import text

with local_engine.connect() as conn:
    with open('backend/migrations/001_add_pid_to_documents.sql') as f:
        conn.execute(text(f.read()))
    conn.commit()
```

## Benefits

### 1. **Data Quality Assurance**
- Only curated, authority-linked assets in training corpus
- No "junk" uploads from S3 bucket
- Human-in-the-loop validation via PID assignment

### 2. **Provenance Tracking**
- Every training example traceable to authority record
- GraphQL metadata provides rich context
- Captions aligned with actual digital assets

### 3. **Multi-Modal Coherence**
- Text (GraphQL metadata) and images (PDFs/TIFFs) linked by PID
- Training examples are harmonized
- Prevents mismatched text-image pairs

### 4. **Scalability**
- PID validation can be async
- GraphQL caching reduces redundant API calls
- S3 sync can run incrementally (skip processed PIDs)

## Future Enhancements

1. **Real-time PID Validation**
   - Validate against DDR Archive GraphQL on upload
   - Reject invalid PIDs immediately

2. **Automatic Authority Enrichment**
   - Fetch GraphQL metadata on PID assignment
   - Cache captions, descriptions in `authority_data`

3. **S3 Metadata Tagging**
   - Auto-tag S3 objects with PID on upload
   - More reliable than filename parsing

4. **Training Manifest Generation**
   - Export PID-filtered dataset for Grantie training
   - Include both PDFs/TIFFs and GraphQL metadata
   - JSON Lines format for ML pipelines

## Questions?

This architecture ensures **only authority-linked, curated assets** enter the Grantie training corpus, maintaining data quality and provenance throughout the ML pipeline.
