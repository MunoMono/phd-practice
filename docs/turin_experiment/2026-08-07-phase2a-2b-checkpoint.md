# Turin Phase 2A/2B Checkpoint

Timestamp: 2026-08-07

## Scope completed in this checkpoint

- Phase 2A corpus identity and provenance foundation.
- Phase 2B asset-level ML policy and metadata-role separation.
- Small workbench UI alignment so the existing Sources view reflects the backend provenance and policy state accurately.

Phase 2 as a whole is not complete.

## Live GraphQL route used

- Endpoint: `https://api.ddrarchive.org/graphql`
- Inventory route: `records_v1(status: "published") -> attached_media -> pdf_files(role="pdf_master")`
- Asset policy route: matching `digital_assets` entry by filename for `assetId`, `pid`, `use_for_ml`, `ml_pages`, and `ml_annotation`

## Asset-level ML policy semantics

- `DigitalAsset.use_for_ml` is the authoritative inclusion flag for Turin corpus control.
- `ItemV1.used_for_ml` is retained for audit, but does not override asset-level policy.
- `DigitalAsset.ml_pages` is a nullable page-scope string.
- Blank or null `ml_pages` means unrestricted inclusion when `use_for_ml = true`.
- `use_for_ml = false` excludes the asset from the ML corpus while keeping it visible in manifest and provenance outputs.

## Observed `ml_pages` syntax

- Single pages, for example `10`
- Inclusive ranges, for example `22-25`
- Comma-separated combinations, for example `19-20, 22-23`

Current parsing is intentionally conservative and only accepts observed numeric page/range forms. Unsupported free-form syntax is treated as unresolved policy and fails safe.

## Current live inventory counts

- Master PDFs discovered: `109`
- ML eligible: `97`
- ML excluded: `12`
- Eligible unrestricted: `62`
- Eligible page restricted: `35`

These figures describe the live remote archive inventory reachable through the current GraphQL route. They are not automatically equivalent to the local experimental corpus shown by dashboard endpoints.

## Asset identity model

The current provenance chain is:

`archive record PID -> assetId or asset PID -> source filename/source URI -> SHA-256 -> deterministic local document_id`

This replaced the earlier false assumption that archive/media PID alone uniquely identified a source document.

## Metadata-role separation

`documents.authority_data` now persists three role buckets:

- `corpus_control`
- `retrieval_provenance`
- `catalogue_metadata`

This distinction now survives:

GraphQL acquisition -> document persistence -> retrieval/provenance assembly -> Granite context construction

Granite receives provenance headers plus a separate `ARCHIVE / CATALOGUE METADATA` block when descriptive metadata is present. Corpus-control metadata is withheld from the answer context by default.

## Representative persistence proof

The checkpoint script in `backend/scripts/phase2b_checkpoint.py` persisted three representative records into the local `documents` table:

- one eligible unrestricted asset
- one eligible page-restricted asset
- one excluded asset with `Use for ML = false`

Verification artifact:

- `artifacts/turin-phase2b-sample-persistence.json`

Stored rows include:

- archive record PID
- asset ID / asset PID
- source URI
- checksum where materialized
- page count where materialized
- ML policy status
- ML exclusion reason where applicable
- `metadata_roles_version = turin-phase2-metadata-v1`

## UI alignment completed

The existing Sources detail panel now distinguishes:

- corpus control
- retrieval and provenance
- archive / catalogue metadata
- persistence and handoff

Stale placeholder language about ML pages and ML use was replaced with the authoritative backend policy state.

## Current tests

Backend tests validated in this checkpoint:

- `backend.tests.test_corpus_inventory`
- `backend.tests.test_metadata_roles`

These remain green.

## Documentation updated

- `docs/experiment/metadata-field-mapping.md`
- `docs/experiment/data-dictionary.md`
- `docs/experiment/runbook.md`
- `docs/turin_experiment/2026-08-07-phase2a-2b-checkpoint.md`

## Known caveat

The host local PostgreSQL instance used during this checkpoint does not currently provide the `pgvector` extension, so vector-specific tables in `init-db.sql` are not fully reproducible on that host database without additional setup. This did not block the document/provenance checkpoint.

## Unresolved corpus-size question

The live inventory currently yields `109` master PDFs, which remains below the earlier planning estimate of roughly `160`. That discrepancy remains unresolved and appears to be an inventory-scope question rather than a Phase 2A/2B provenance bug.

## Next Phase 2 task

Phase 2C: page-aware / heading-aware chunk persistence with policy enforcement.

This checkpoint does not begin Phase 2C.