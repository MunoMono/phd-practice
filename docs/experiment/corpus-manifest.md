# Corpus Manifest

## Accepted frozen corpus

The authoritative Turin experiment corpus is frozen as `corpus_f40d78dbce52`.

- Authoritative eligible assets: 97.
- Controlled-ingestible PDF sources: 95.
- Explicit source-format failures: 2.
- Current documents/chunks: 95 / 12,884.
- Restricted assets: 35; restricted page-scope violations: 0.
- Missing provenance/version/page fields: 0.
- FTS: 12,884 non-null vectors; GIN present.
- Frozen manifest SHA-256: `aed395d090aa16a1a6b435746b1e36410374428e261a80287fa587c8a5818a76`.

The freeze artifact is `artifacts/turin-phase2a/corpus_f40d78dbce52-freeze.json`. Legacy APR alpha (606 chunks) is retained separately and has zero rows in the current-corpus namespace.

## Source-representation / archive-media mismatch

Two ML-eligible members under archive record PID `989478384551` (DDR teaching and learning practice lectures) and attached-media PID `321843234637` (RCA teaching and learning practice lectures) are authoritative non-PDF source representations:

- asset PID `359001684832`, checksum `491fdbf612455d205b8c3d5fbff488cdc69b256e2fd5095d8317917683b874fc`;
- asset PID `094896213245`, checksum `7903ef10cbf52e1b4d3377845e6544484c0b05374f73bc90cf7557d191b2977d`.

GraphQL identifies them as PDF-master assets, while fresh authoritative HTTP retrieval returns `Content-Type: image/jpeg`; the fresh bytes match prior materialisations. This is a source-representation / archive-media mismatch, not a Docling failure, OCR failure, local corruption, or a basis for substitution/conversion.

Phase 2A uses the live archive GraphQL API at `https://api.ddrarchive.org/graphql` as the authoritative inventory source for Turin corpus PDFs.

The current authoritative experimental source manifest is [turin-authoritative-corpus.md](turin-authoritative-corpus.md):

```text
artifacts/turin-phase2a/authoritative-turin-ingestion-manifest.json
```

It contains `109` current master-PDF assets, including `97` ML-eligible assets and `12` exclusions. It replaces the older eligible-only manifest as the membership authority for controlled ingestion.

## Corpus-status scope

The generated manifest is an archive-derived inventory, not a complete export of every persisted local experimental row. It therefore represents documents with a current, resolvable DDR archive identity. Retained unresolved legacy rows remain in the local experimental database but are intentionally absent from this manifest because no archive PID, asset PID/ID, source URI, or authority linkage is inferred for them.

The dashboard/API corpus-status contract reports these populations separately: persisted experimental documents, archive-resolved/current documents, and unresolved legacy documents.

Current repository-specific source route:

1. Query `records_v1(status: "published")`.
2. Traverse each parent record's `attached_media` items.
3. Treat each attached-media `pid` as the stable archive PID for an ingestible PDF source.
4. Select `pdf_files` where `role == "pdf_master"`.
5. Join each `pdf_file` to its matching `digital_assets` entry by filename to recover `use_for_ml`, `ml_pages`, and asset-level annotation.

Important discovered constraint:

- A single attached-media PID can expose multiple master PDFs.
- The repository therefore cannot model source documents as one row per PID.
- Phase 2A changes document identity to `archive PID + source filename/source URI`, with a deterministic `document_id` derived from those values.

Manifest fields currently emitted by `scripts/generate_corpus_manifest.py`:

- `pid`
- `source_filename`
- `checksum_sha256`
- `title`
- `creator`
- `date_text`
- `document_type`
- `archive_reference`
- `page_count`
- `ocr_status`
- `ingestion_status`
- `ingestion_error`
- `chunk_count`
- `ingestion_version`
- `corpus_version`

Additional provenance fields included in this repository:

- `document_id`
- `source_uri`
- `source_path`
- `authority_id` (archive media/item ID)
- `archive_record_id`
- `archive_record_pid`
- `metadata_source`
- `access_level`
- `rights_note`
- `ml_pages`
- `ml_annotation`
- `record_title`
- `record_public_uri`

Fields remain explicit when unavailable. No missing metadata is fabricated.