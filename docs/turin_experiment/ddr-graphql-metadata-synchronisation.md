# DDR GraphQL to InnovationDesign metadata synchronisation

## Purpose

DDR Admin remains the authority for archive/catalogue and corpus-control metadata. InnovationDesign keeps a persisted, inspectable snapshot so its Sources view and future research work are reproducible.

```
DDR Admin
  -> DDR GraphQL
  -> one-source metadata synchronisation
  -> InnovationDesign documents.authority_data
```

`POST /api/documents/{document_id}/sync-metadata` fetches one current DDR record, refreshes the local archive metadata snapshot, records a fetch timestamp and deterministic normalised-payload hash, and returns the fields that changed. DDR does not expose a metadata version in the current query, so the snapshot hash is the reproducible version identifier. `metadata_roles_version` is retained in the snapshot.

## What refreshes

The operation updates archive/catalogue metadata, rights/access metadata, authority/provenance metadata, and asset-level corpus-control metadata. It re-evaluates `use_for_ml`, `ml_pages`, and the stored ML policy status using the existing policy evaluator. This allows a source which becomes ineligible to be excluded by the existing policy logic without re-running document extraction.

## What does not refresh

Archive metadata is not source-document evidence. The operation does not download the PDF, run Docling, alter `extracted_text`, recreate chunks, or rebuild FTS content. It does not mutate saved experiment-run provenance.

## Asset changes

The synchronisation compares stable DDR asset identity fields (asset ID, asset PID, source URI, filename, and master role). A difference records `source_asset_changed` and `reingestion_required` rather than silently replacing local evidence.

```
source asset change
  -> reingestion_required
  -> existing PDF / checksum / Docling / chunks / FTS ingestion workflow
```

`source_asset_checksum` is recorded only when DDR supplies an upstream checksum. It remains distinct from `checksum_sha256`, which is the checksum of the locally ingested source bytes.