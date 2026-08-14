# Authoritative Turin Experimental Corpus

## Decision

The authoritative source manifest for the Turin experiment is:

```text
artifacts/turin-phase2a/authoritative-turin-ingestion-manifest.json
```

It was generated through the repository's read-only DDR GraphQL inventory route on 14 August 2026. It records `109` current master-PDF source assets and corpus version `corpus_f40d78dbce52`.

The experimental source population is not the set of `138` persisted database rows and is not the legacy `606` chunk rows. The manifest is the source-of-truth membership list for the next controlled ingestion.

## Source Population

| Population | Count |
| --- | ---: |
| Current master-PDF assets | 109 |
| ML-eligible assets | 97 |
| Eligible, all-page scope | 62 |
| Eligible, page-restricted scope | 35 |
| ML-excluded assets | 12 |
| Policy-unresolved assets | 0 |
| Assets without a source URI or filename | 0 |
| Manifest-tracked materialised eligible assets | 0 |

Each manifest row has a stable `document_id`, archive record PID, asset identity, source filename, source URI, title, ML policy status, and pending materialisation state. Checksums and page counts are intentionally absent until the source bytes are materialised. Three matching eligible PDFs exist as earlier Phase 2 sample files, but none are recorded as materialised in this manifest and they are not a controlled corpus population.

## Legacy Chunk Population

### APR Alpha Proof-of-Concept

Approximately three months before this controlled Turin work, the APR alpha proved the technical chain `S2 media bucket -> four oral-history PDFs -> Docling -> retrieval -> local Granite`. The Christopher Frayling, Brian Reffin Smith, George Mallen, and Anthony Finkelstein interviews produced the historical rows below. This was a successful alpha proof-of-concept, preserved as development evidence; it was never intended to be the current Turin experimental corpus.

The restored historical `document_chunks` population remains preserved as evidence only:

| Property | Value |
| --- | ---: |
| Legacy chunk rows | 606 |
| Legacy document IDs | 8 |
| Joined to current `documents` | 0 |
| Source interviews represented | 4 |

The four identifiable source files are interviews with Christopher Frayling, Brian Reffin Smith, George Mallen, and Anthony Finkelstein. Their chunks use legacy `pid_113304873833_*` identities and do not join to the current source-document identities.

Status: **historical ingestion evidence, not the current Turin retrieval corpus**.

Do not delete these rows or derive replacements through heuristic ID substitution. Current Turin retrieval must be limited to the authoritative corpus version and must join every result to a current document.

## Current Ingestion Contract

The next ingestion surface must admit only manifest rows with `ml_policy_status` of `eligible_unrestricted` or `eligible_page_restricted`.

For every materialised source asset, persist:

- stable manifest `document_id` and deterministic `chunk_id`;
- `archive_record_pid`, `asset_id` or `asset_pid`, `source_filename`, `source_uri`, and source SHA-256;
- `page_start`, `page_end`, sequence number, and heading path when present;
- source text, ingestion version, chunking configuration/version, and ML page scope;
- a non-null `search_tsv` vector.

The document-to-chunk relationship must enforce referential integrity for all new rows. A non-validating foreign key on `document_chunks.document_id` is sufficient to preserve the legacy orphan rows while requiring future chunk inserts to reference `documents(document_id)`. New chunks must also carry the manifest corpus/ingestion version, and retrieval must filter to that version in addition to joining `documents`.

## Why Controlled Docling Ingestion Is Required

**YES.** No eligible manifest source is currently materialised or has a checksum, page count, extracted text, or valid joined chunk population. Controlled ingestion creates the first correctly joined Turin retrieval corpus from authoritative current assets; it does not reprocess or replace the historical `606` legacy rows.

The existing Phase 2A inventory path already supplies deterministic document identity, asset policy, source materialisation, checksum calculation, and page-count capture. The old Docling scripts are not suitable for this run because they generate random document IDs, omit page-aware chunking and policy filtering, and do not enforce a document foreign key.

## Controlled Pilot Status

The first three-document controlled pilot was prepared against `corpus_f40d78dbce52` with two all-page assets and one restricted asset (`19-20, 22-23`). The isolated database contract was applied successfully, including a non-validating foreign key that preserves APR alpha rows while protecting all future chunk inserts. The pilot did not reach persistence: its disposable local Docker runtime was OOM-killed while Docling initialized detection and recognition models. No current chunks, source checksums, page counts, FTS vectors, or retrieval results were created; the historical `606` APR alpha chunks remain unchanged. The explicit result is recorded in `artifacts/turin-phase2a/controlled-pilot-ingestion-result.json`.

The follow-up runtime uses the profile-only `docling-worker`: one document at a time, OCR disabled for text-layer PDFs, one Docling/BLAS thread, a persistent Docling artifacts cache, and a 6 GB container limit with a 4 GB reservation. The worker must be run only after its non-persisting initialization check succeeds.

## Acceptance Gate Before Retrieval

- Every manifest source is accounted for as eligible, excluded, or failed with an explicit error.
- Only the 97 eligible sources are materialised and ingested; the 12 exclusions produce no chunks.
- Restricted sources emit chunks only from explicitly allowed pages.
- Every materialised source has a SHA-256 checksum and stable manifest identity.
- Every current chunk joins to a current document; current orphan chunks equal zero.
- Every current chunk has page provenance, sequence/order, corpus/ingestion version, and non-null `search_tsv`.
- A GIN index exists for current FTS queries.
- Retrieval filters to the authoritative corpus version, excluding the legacy `606` rows.

## Next Task

Ingest a 3-5 document representative pilot from the authoritative manifest into the clean joined Turin chunk surface, validate provenance and FTS end-to-end, then scale the same pipeline to the remaining eligible corpus.