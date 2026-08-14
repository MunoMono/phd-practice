# Data Dictionary

## Document identity fields

- `document_id`: deterministic local identifier derived from `pid + source_filename + source_uri`.
- `pid`: archive media/item PID for the source PDF.
- `authority_id`: archive media/item ID from GraphQL.
- `archive_record_id`: parent archive record ID when present.
- `archive_record_pid`: parent archive record PID when present.
- `source_uri`: authoritative master-PDF URL exposed by the archive system.
- `source_path`: local materialized PDF path when the source is downloaded for validation.
- `checksum_sha256`: SHA-256 checksum of the local PDF bytes.
- `page_count`: page count from `pdfinfo` when a local PDF is available.
- `ocr_status`: current Phase 2A values are `unverified_remote_source`, `text_layer_present`, `text_layer_empty`, `unreadable`, or `unknown`.

## Metadata fields

- `title`: PDF label if available, otherwise media title, otherwise parent record title.
- `creator`: `creator_agent_label` when present, otherwise a semicolon-joined list of `creators` labels.
- `date_text`: normalized from `date_begin/date_end` or `artefact_date_from/artefact_date_to`.
- `document_type`: currently mapped from archive `category`.
- `archive_reference`: currently mapped from archive `reference_code`.
- `rights_note`: `rights_holders` when present, otherwise `copyright_holder`.
- `metadata_source`: GraphQL route used to derive metadata. Phase 2A uses `archive_graphql.records_v1` for inventory and `archive_graphql.search_media_items` for point lookup.

## Metadata role partitions

`authority_data` now preserves three explicit role buckets so the Turin pipeline does not collapse archive control metadata, catalogue description, and source-document evidence into one blob.

- `authority_data.corpus_control`: eligibility, access, takedown/rights, ML page scope, source locator, and asset/media identity used to govern ingestion and provenance.
- `authority_data.retrieval_provenance`: archive/source labels used for retrieval filters, deterministic context headers, citation display, and provenance validation.
- `authority_data.catalogue_metadata`: archive or catalogue description that may support retrieval or contextual interpretation but must not be presented as if quoted from the source PDF.

Current role version: `turin-phase2-metadata-v1`.

## Versioning fields

- `ingestion_version`: implementation/configuration version of the inventory or ingestion pipeline. Phase 2A default is `turin-phase2a-archive-inventory-v1`.
- `corpus_version`: deterministic SHA-derived identifier based on sorted corpus membership and `ingestion_version`.
- `context_builder_version`: `turin-context-budget-v2` for future runs using deterministic full-input budgeting; earlier budgeted runs retain their recorded version.
- `input_budget_chars`, `fixed_prompt_chars`, `available_evidence_chars`, `assembled_input_chars`: immutable final-input budget accounting persisted in `experiment_runs.context_budget_json`.
- `included_in_context`: whether a retrieved chunk was actually supplied to Granite.
- `original_chars`, `supplied_chars`, `supplied_excerpt`, `excerpted`, `exclusion_reason`: per-retrieved-chunk packing provenance; `excerpt` remains the full retrieved passage.
- `authority_context_json`: separately labelled authority source/type/role/fields/version and supplied-state information; never source-document evidence.
- `ExperimentRunAssessment`: mutable researcher assessment separate from immutable run/evidence snapshots.

## Pending later Phase 2 fields

- `chunk_count`: reserved for page-aware / heading-aware chunking after Docling structure extraction is wired into ingestion.
- stable chunk IDs, page ranges, and heading paths are not yet persisted in this checkpoint.