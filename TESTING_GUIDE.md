# Testing the PID-Gated Architecture

## Your Data Summary

From your GraphQL response, you have **3 authority records**:

| PID | Title | PDF? | Training Eligible? |
|-----|-------|------|-------------------|
| 564310168393 | Archer Systematic method for designers \| 1963-4 | ✅ Yes | ✅ **YES** |
| 001808484369 | Lower limb surgical plaster table \| Job 73 | ❌ No (JPG only) | ❌ **NO** |
| 362524095549 | Strathclyde Police console 146 2 \| 1975 | ✅ Yes | ✅ **YES** |

**Result: Only 2 out of 3 records are training-eligible** (66% PID coverage)

## Test Sequence

### 1. Run Database Migration

```bash
cd /Users/graham/Documents/repos/phd-practice

# Option A: Via psql
psql -d epistemic_drift -f backend/migrations/001_add_pid_to_documents.sql

# Option B: Via Python
python -c "
from app.core.database import local_engine
from sqlalchemy import text

with local_engine.connect() as conn:
    with open('backend/migrations/001_add_pid_to_documents.sql') as f:
        conn.execute(text(f.read()))
    conn.commit()
print('✅ Migration complete')
"
```

### 2. Test GraphQL Parsing (Dry Run)

```bash
cd backend
python test_graphql_sync.py
```

**Expected Output:**
```
Training-eligible (PDFs): 2
JPG-only (not eligible): 1

Allowed PIDs (training corpus): ['564310168393', '362524095549']
Filtered PIDs: ['001808484369']
```

### 3. Test Sync via API (Safe - Dry Run)

Save your JSON to a file:
```bash
cat > /tmp/graphql_response.json << 'EOF'
{
  "all_media_items": [
    {
      "id": "87",
      "pid": "564310168393",
      "title": "Archer Systematic method for designers | 1963-4",
      "pdf_files": [
        {
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/87/master/308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9__pdf_master__v1.pdf",
          "filename": "308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9.pdf"
        }
      ]
    },
    {
      "id": "97",
      "pid": "001808484369",
      "title": "Lower limb surgical plaster table | Job 73",
      "pdf_files": []
    },
    {
      "id": "85",
      "pid": "362524095549",
      "title": "Strathclyde Police console 146 2 | 1975",
      "pdf_files": [
        {
          "url": "https://archive-media.lon1.digitaloceanspaces.com/ddr-archive/records/362524095549/master/37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c__pdf_master__v1.pdf",
          "filename": "37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c.pdf"
        }
      ]
    }
  ]
}
EOF
```

Then test via curl (once your backend is running):
```bash
curl -X POST http://localhost:8000/api/v1/sync/graphql \
  -H "Content-Type: application/json" \
  -d @/tmp/graphql_response.json \
  -G -d "dry_run=true"
```

**Expected Response:**
```json
{
  "total_items": 3,
  "training_eligible": 2,
  "synced": 2,
  "skipped": 0,
  "errors": 0,
  "dry_run": true
}
```

### 4. Actual Sync (Creates Database Records)

```bash
curl -X POST http://localhost:8000/api/v1/sync/graphql \
  -H "Content-Type: application/json" \
  -d @/tmp/graphql_response.json \
  -G -d "dry_run=false"
```

### 5. Verify Database

```sql
-- Check all documents with PIDs
SELECT 
    document_id,
    pid,
    title,
    publication_year,
    file_type,
    processing_status
FROM documents 
WHERE pid IS NOT NULL
ORDER BY pid;
```

**Expected Result:**
```
document_id    | pid          | title                                     | publication_year | file_type       | processing_status
---------------|--------------|-------------------------------------------|------------------|-----------------|------------------
doc_abc123     | 362524095549 | Strathclyde Police console 146 2 | 1975  | 1975             | application/pdf | pending
doc_def456     | 564310168393 | Archer Systematic method for designers... | 1963             | application/pdf | pending
```

**Note: PID 001808484369 should NOT appear (filtered - no PDF)**

### 6. Check Training Corpus Stats via GraphQL

```graphql
query {
  trainingCorpusStats {
    totalDocuments
    totalWithPid
    totalWithoutPid
    pidCoveragePercent
  }
}
```

**Expected:**
```json
{
  "data": {
    "trainingCorpusStats": {
      "totalDocuments": 2,
      "totalWithPid": 2,
      "totalWithoutPid": 0,
      "pidCoveragePercent": 100.0
    }
  }
}
```

### 7. Validation Check

```bash
curl -X POST http://localhost:8000/api/v1/sync/validate \
  -H "Content-Type: application/json" \
  -d @/tmp/graphql_response.json
```

**Expected Response:**
```json
{
  "graphql_pid_count": 2,
  "database_pid_count": 2,
  "needs_sync": [],
  "needs_sync_count": 0,
  "orphaned": [],
  "orphaned_count": 0,
  "already_synced": ["564310168393", "362524095549"],
  "already_synced_count": 2
}
```

## Key Validations

### ✅ Allowlist Filter Working If:

1. **Only 2 documents created** (not 3)
2. **PIDs match**: 564310168393, 362524095549
3. **PID 001808484369 is NOT in database** (JPG-only record filtered out)
4. All documents have `pid IS NOT NULL`
5. All documents have `file_type = 'application/pdf'`

### ❌ Filter NOT Working If:

1. 3 documents created (should be 2)
2. PID 001808484369 appears in database
3. Any document has `pid IS NULL`
4. JPG derivatives are ingested (we only want PDFs/TIFFs)

## S3 Sync Validation

When you sync from S3, **only these exact files** should be processed:

```
✅ ALLOWED:
ddr-archive/records/87/master/308e67089fda8f54fd8e9e0a4dba7e054208e78ad7c49052eaa3ee72773250b9__pdf_master__v1.pdf
   → PID: 564310168393

✅ ALLOWED:
ddr-archive/records/362524095549/master/37f3fbe5a62400e5c59cc38bb4458157de6c0ff909d39b31e74ca5567b09c35c__pdf_master__v1.pdf
   → PID: 362524095549

❌ IGNORED (everything else in bucket):
- All JPG derivatives
- Any PDFs without matching PIDs
- Temporary uploads
- Backup files
- etc.
```

## Quick Sanity Checks

```python
from app.core.database import LocalSessionLocal
from app.models.document import Document

db = LocalSessionLocal()

# Should return 2
total = db.query(Document).count()
print(f"Total documents: {total}")

# Should return 2
with_pid = db.query(Document).filter(Document.pid.isnot(None)).count()
print(f"Documents with PID: {with_pid}")

# Should return specific PIDs
pids = [d.pid for d in db.query(Document).all()]
print(f"PIDs in database: {pids}")
# Expected: ['564310168393', '362524095549']

# Should NOT include this PID
assert '001808484369' not in pids, "❌ FAIL: JPG-only record was ingested!"

print("✅ Allowlist filter is working correctly!")
```

## Troubleshooting

**If all 3 records are synced:**
- Check `parse_graphql_media_response()` - should filter for `pdf_files` presence
- Check `bulk_sync_from_graphql_response()` - should only process training_eligible items

**If PIDs are NULL:**
- Migration didn't run
- Check document creation code has `pid=item['pid']`

**If sync fails:**
- Check database connection
- Check table exists: `\d documents` in psql
- Check for unique constraint violations (duplicate PIDs)
