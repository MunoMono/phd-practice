# Sources metadata synchronisation closeout

Generated: 2026-08-13

## Outcome

The Sources metadata synchronisation enhancement is complete. Real-source validation passed against the restored local DDR inventory.

The local database had been empty because the local environment had no restored source-inventory rows; this was an inventory/state issue, not a DDR GraphQL metadata-sync failure. The supported Phase 2 asset-inventory backfill restored 109 DDR GraphQL source rows.

## Real-source validation

Representative source:

- Document ID: `doc_230440137378_063f52d0a4b3`
- DDR title after refresh: `KMA box 32 | RCA SC`

Before refresh, the local row held stale catalogue metadata, including the title `The education of industrial designers` and date `April 1966`. DDR GraphQL returned the current catalogue title `KMA box 32 | RCA SC` and date `July 1968`.

The first explicit metadata sync completed with status `updated` and persisted the corrected DDR metadata. The second sync completed with status `current`, confirming that the normalised upstream snapshot was unchanged.

Persisted provenance includes the source, fetch timestamp, deterministic normalised snapshot hash, sync status/error, asset identity/checksum details where available, and re-ingestion-required state. The matching DDR asset was unchanged in this validation, so no re-ingestion was required.

## Architectural conclusion

```
DDR Admin -> DDR GraphQL -> explicit metadata sync -> InnovationDesign persisted metadata
```

This pipeline is now validated for metadata-only changes.

Source-document ingestion remains a separate operation:

```
PDF/source asset -> Docling -> extracted text -> chunks -> PostgreSQL FTS
```

It has not been run for the restored 109-source local inventory. The explicit metadata sync did not download source files, run Docling, modify extracted text, create or modify chunks, or rebuild FTS.

Metadata synchronisation and source-document ingestion are therefore deliberately separate operations. The local inventory currently contains 109 documents and 0 chunks.

## Scope boundary

No subsequent Turin Statement of Work phase is started by this closeout.