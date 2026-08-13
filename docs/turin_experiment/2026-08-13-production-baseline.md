# Turin Production Baseline - 13 August 2026

## Release

- Application release: `9c54304144e05e38ca84e3ce2fea8796d59a5f31`
- Feature commit: `f529c41` (Sources metadata sync closeout)
- Deployment hardening: `c3b5399` (build-before-cutover and attestation)
- Reproducibility fix: `9c54304` (tracked `researchState` dependency)
- Backup database-resolution tooling: `323d7856aa80744b1693c34d8a2c0d15d7adc49f`
- Frontend health-probe tooling: `4411a446876695dcb66d136cfc4509b674d49d03`
- Release-status database lookup tooling: `80107b45487d582bd3aca8a9daa636e0060443be`
- Deployed: `2026-08-13T14:48:56Z`
- Backend image: `sha256:5aa0d50f8c5843d894743cc7ba0f45e8b0d7dae3ba72b357157f39ad3d5915e8`
- Frontend image: `sha256:31f2a8fa3073266e097035ca3f15bf7edef5cabf1fa5655e225f2218fca224dc`
- Retained build log: `/root/phd-practice/.prod-sync/builds/9c54304144e0-20260813143145.log`
- Rollback references: `phd-practice-backend:rollback-20260813144842`, `phd-practice-frontend:rollback-20260813144842`

## Database

- Database: `testamentary-traces`
- Documents: `138`
- Chunks: `606`
- Migration `013_archive_metadata_sync_provenance.sql`: applied
- Provenance columns confirmed, including `archive_metadata_fetched_at` and `source_asset_identity_hash`
- Valid backup: `/root/phd-practice/backups/phd_practice_backup_20260813_144200.sql.gz` (`504K`, gzip integrity check passed)
- Previous backup preserved: `/root/phd-practice/backups/phd_practice_backup_20260813_134442.sql.gz`

## Validated Conduit

```
DDR Admin
-> DDR GraphQL
-> explicit metadata sync
-> InnovationDesign persisted metadata
```

The live sync endpoint confirmed the production backend reaches the configured DDR GraphQL source. No generic network-connectivity substitution was used.

## Separate Ingestion Path

```
PDF/source asset
-> Docling
-> extracted text
-> chunks
-> PostgreSQL FTS
```

This path was not triggered by metadata refresh.

## Production Metadata Validation

Target source:

- Production document: `doc_230440137378_4276b6f6cf6d`
- Archive PID: `451248821104`
- Attached-media PID: `230440137378`
- Local title before refresh: `The education of industrial designers`
- Policy before and after: `use_for_ml=true`, `ml_page_scope=all_pages`, `ml_policy_status=eligible_unrestricted`
- Extraction state before and after: no `extracted_text`

First refresh at `2026-08-13T14:51:32.501871+00:00`:

- Result: `updated`
- Title updated to `KMA box 32 | RCA SC`
- Changed fields: title, creators, date range, caption, keywords, consent/access metadata, location/accession, and reference code
- Policy change: `false`
- Source asset change: `false`
- Reingestion required: `false`
- Corpus counts remained `138` documents and `606` chunks

Second refresh at `2026-08-13T14:51:43.376316+00:00`:

- Result: `current`
- Changed fields: none
- Policy change: `false`
- Source asset change: `false`
- Reingestion required: `false`
- Persisted provenance: `ddr_graphql.record_v1` with a snapshot hash

## Production State

### Initial Server-Side Validation

- Backend `/health`: healthy
- Frontend root and `/sources`: HTTP `200`
- Sources API: responsive
- Backend and frontend restart counts: `0` after release activation
- Retrieval inventory: `606` existing chunks; no chunk or FTS rebuild occurred during this release
- Granite/Ollama: runtime was ready at backend startup; no Granite task was run during validation
- Frontend logs contain non-blocking unresolved Plex font requests; no material Sources runtime failure was observed

### Reconciliation Update

The initial server-side validation above was not sufficient to establish browser-facing Sources parity. An authenticated researcher subsequently observed `Corpus load failed: Failed to fetch` and an empty Sources view. That observation invalidated the earlier UI acceptance.

Read-only reconciliation identified the cause in the active frontend bundle: production Compose defaulted `VITE_API_URL` to `http://localhost:8000`. Vite embedded that value in the browser client, causing a researcher browser to request its own localhost rather than the same-origin `/api/documents` proxy.

The production-only default was corrected to an empty value, preserving the API client's same-origin fallback. Application release `bf4d6eafc5ac619a0accb8abd84973d2648367d8` was deployed at `2026-08-13T15:17:32Z`; its backend and frontend containers passed health checks, its active client compiles the API base as an empty string, contains no `http://localhost:8000`, and `https://innovationdesign.io/api/documents?limit=1` returns HTTP `200`.

No migration, metadata synchronization, ingestion, chunk rebuild, or data deletion was performed during this reconciliation. Direct inventory observations made during the investigation conflicted with the release-status helper's historical `606`-chunk assertion; that discrepancy remains open and must not be resolved by destructive action.

Authenticated researcher visual confirmation of `/sources` after a hard refresh remains required before production parity is declared.

### Whole-Corpus DDR Metadata Reconciliation

Authenticated researcher inspection subsequently identified stale persisted rights metadata despite the corrected Sources UI. The exemplar was `doc_338541406157_72774d03522b`, archive PID `873981573030`: production had persisted `Royal College of Art` for both image and data rights, while current DDR GraphQL returned `The Board and Trustees of the Victoria and Albert Museum` for the matched media PID `338541406157` and asset PID `987235129265`.

The reconciliation used the existing `SourceMetadataSyncService` mapping, extended with a non-mutating comparison and a thin whole-corpus orchestration command. A first dry run inspected all `138` production documents:

- `109` resolved to current DDR GraphQL records;
- `108` had metadata differences and `1` was current;
- `0` policy differences and `0` source-asset identity differences;
- `29` legacy records could not be resolved to a matching attached media; `0` GraphQL/API request failures.

The main stale fields were title (`107` before title-precedence correction), creators (`108`), date begin/end (`108` each), keywords (`108`), caption (`68`), reference code (`108`), accession (`86`), and image/data rights (`12` each). These differences arose from persisted historical snapshots and incomplete prior per-source refreshes, not a different local/production mapping. The inventory mapper established asset/PDF label title precedence over the parent media title; the canonical sync was corrected accordingly before the final title-only reconciliation.

Before mutation, a fresh gzip-verified PostgreSQL backup was created from `testamentary-traces`:

- `/root/phd-practice/backups/phd_practice_backup_20260813_153733.sql.gz`
- `516826` bytes

The metadata-only apply updated all resolvable records through the canonical one-document service. It did not invoke Docling, rewrite extracted text, regenerate chunks, rebuild FTS, or re-ingest assets. Document and chunk counts were `138` and `606` before and after. No source asset was flagged for later re-ingestion.

The final whole-corpus dry run reported `109` current resolvable records, `0` metadata differences, `0` policy differences, `0` asset changes, `29` explicitly unresolved legacy records, and `0` GraphQL/API errors. The exemplar production API now returns its asset-level title and both image/data rights as `The Board and Trustees of the Victoria and Albert Museum`, with `ddr_graphql.record_v1` provenance and a persisted snapshot hash.

The unresolved records are legacy/non-asset rows that lack a matching current attached-media record. They were not re-ingested, deleted, or otherwise altered beyond recording their sync error status. They remain a separate Turin source-model reconciliation task.

### Final Accepted Production State

Authenticated researcher browser verification passed for the Sources UI, the V&A-rights exemplar, and representative current, page-restricted, and excluded-from-ML records. Production metadata parity is accepted: the reconciled current DDR GraphQL metadata state is the production baseline.

The production evidence baseline remains `138` documents and `606` chunks. The bounded set of `29` unresolved legacy/non-current-asset rows remains untouched and does not block the Turin Experiment SoW. No ingestion or retrieval evidence was rewritten during reconciliation: Docling was not run, extracted text was not rewritten, chunks were not regenerated, PostgreSQL FTS was not rebuilt, and no source-asset re-ingestion flags were created.

**Production metadata parity achieved: YES.**

### Turin SoW starting point — 14 August 2026

- Sources UI: current and verified
- DDR GraphQL metadata parity: achieved
- Documents: `138`
- Chunks: `606`
- Metadata reconciliation: complete for `109` resolvable records
- Unresolved legacy rows: `29`
- Docling/extraction/chunks: preserved
- PostgreSQL FTS evidence: preserved
- Database authorities: still part of the v0.2 SoW and upcoming implementation phases
- Next step: resume the Turin Experiment SoW from the next unfinished checkpoint

Do not begin further implementation tonight.
