# UAT-018 Implementation Record

**Status:** Machine-validation approved; pending formal human production rerun in UAT v0.2.

## Root Cause

The dashboard displayed archive-resolution counts without stating that both were complementary categories within the same local persisted-document population. The underlying data contract was valid: 138 persisted document records = 97 archive-resolved current records + 41 unresolved legacy records.

## Label Change

| Before | After |
|---|---|
| `Archive-resolved/current records` | `Archive-resolved current document records (of 138 local records)` |
| `Unresolved legacy records` | `Legacy document records without current archive resolution (of 138 local records)` |

The displayed denominator remains dynamic and is sourced from `persistedDocumentCount`; 138 is the validated local value, not a hard-coded application value.

## Files Changed

- `frontend/src/pages/Dashboard/Dashboard.jsx`
- `frontend/tests/workbench-corpus-status.spec.js`
- `docker-compose.dev.yml`

## Regression Coverage

Added `frontend/tests/workbench-corpus-status.spec.js`, which verifies that both archive-resolution labels are visible and declare their shared local-record population.

## Commands and Results

- `BACKEND_PORT=8002 docker compose -f docker-compose.dev.yml up -d --build` - initial start exposed an unrelated host-port conflict on 8000.
- `BACKEND_PORT=8002 docker compose -f docker-compose.dev.yml up -d --force-recreate backend frontend` - local services started.
- `BACKEND_URL=http://localhost:8002 FRONTEND_URL=http://localhost:3000 ./scripts/check-local-ready.sh` - passed before and after the remediation.
- `curl -sS http://localhost:8002/api/viz/dashboard-stats` - confirmed `persistedDocumentCount: 138`, `archiveResolvedDocumentCount: 97`, `unresolvedLegacyDocumentCount: 41`, and `invariantSatisfied: true`.
- Integrated-browser check at `http://localhost:3000` - confirmed both updated labels render with `of 138 local records`.
- `BACKEND_PORT=8002 docker compose -f docker-compose.dev.yml exec -T frontend npm run build` - passed; Carbon Sass deprecation warnings only.
- Targeted Playwright command discovered the new test but could not launch Chromium in the Alpine development image after download; the integrated-browser check provided the rendered UI validation.

## Data and Method Confirmation

No corpus counts, API fields, database calculations, retrieval behavior, provenance behavior, or runtime data were changed. PostgreSQL full-text search remains the active retrieval method. No embeddings, vector retrieval, or PID/record mappings were created or altered.

## Development-Validation Compose Changes

The `docker-compose.dev.yml` changes are development-validation only and do not alter the production deployment contract, research method, corpus, retrieval behavior, provenance behavior, or runtime data:

- `BACKEND_PORT` allows the local backend to bind to `8002` when another local Docker project already owns host port `8000`; the default remains `8000`.
- The read-only `frontend/tests` mount makes browser tests available in the frontend development container.
- The read-only `docs/turin_experiment` mount makes the Turin documents available to Vite's static-copy build step.

No further infrastructure change is required unless a specific UAT item establishes that need.