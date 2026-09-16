# Metadata Field Mapping

This table is grounded in the live DDR Archive GraphQL schema snapshot at `artifacts/turin-phase2-metadata-schema.json`, captured from `ItemV1` and `DigitalAsset` on 2026-08-07.

The table covers the Turin-relevant live fields verified in the schema and now handled explicitly by this repository. `Used for retrieval` means eligible for retrieval filters, ranking, lexical search support, or source labeling. `Sent to Granite` means included in structured source headers or the separate catalogue block by default, not concatenated into source text.

| GraphQL field | Meaning | Stored | Used for eligibility | Used for retrieval | Sent to Granite | Provenance only | Notes |
|---|---|---|---|---|---|---|---|
| `DigitalAsset.use_for_ml` | Asset-level ML inclusion flag | Yes | Yes | No | No | No | Authoritative policy gate for Turin PDFs. |
| `DigitalAsset.ml_pages` | Allowed ML page scope for the asset | Yes | Yes | Filter only | No | No | Parsed conservatively as numeric pages/ranges only. |
| `ItemV1.used_for_ml` | Media-level ML flag | Yes | Secondary only | No | No | No | Retained for audit; asset-level flag takes precedence. |
| `ItemV1.access_level` | Access restriction / access class | Yes | Yes | Filter only | No | No | Control field, not lexical evidence. |
| `ItemV1.rights_holders` | Rights holder text | Yes | Yes | No | No | Yes | Used for control/audit, not answer context. |
| `ItemV1.copyright_holder` | Copyright holder text | Yes | Yes | No | No | Yes | Same handling as `rights_holders`. |
| `ItemV1.rights_statement_uri` | Rights statement URI | Yes | Yes | No | No | Yes | Control/provenance only. |
| `ItemV1.current_consent_status` | Consent/takedown-related state | Yes | Yes | No | No | Yes | Control field; withhold from Granite. |
| `ItemV1.takedown_contact` | Takedown contact metadata | Yes | Yes | No | No | Yes | Stored for governance, not interpretation. |
| `ItemV1.pid` | Media/item PID | Yes | Yes | Yes | Yes | No | Part of provenance header and local identity chain. |
| `DigitalAsset.pid` | Asset PID | Yes | Yes | Yes | Yes | No | Sent in provenance header when present. |
| `DigitalAsset.assetId` | Stable asset identifier | Yes | Yes | Yes | Yes | No | Preferred asset identity in Phase 2B provenance chain. |
| `pdf_files.url` | Master source URI | Yes | Yes | Filter only | No | Yes | Used as authoritative locator and uniqueness key, withheld from Granite by default. |
| `pdf_files.filename` / `DigitalAsset.filename` | Source filename | Yes | Yes | Yes | Yes | No | Included in provenance header, not source text. |
| `ItemV1.title` | Media/object title | Yes | No | Yes | Yes | No | Retrieval/support label, not treated as quoted source text. |
| `pdf_files.label` | PDF label/caption from file metadata | Yes | No | Yes | Yes, under catalogue heading | No | Treated as catalogue description, not source evidence. |
| `ItemV1.reference_code` | Archive reference | Yes | No | Yes | Yes | No | Provenance header field. |
| `ItemV1.public_uri` | Archive public URL | Yes | No | Filter/source label | No | Yes | Used for provenance validation and UI links. |
| `record.pid` via `records_v1` parent | Archive record PID | Yes | No | Yes | Yes | No | Provenance header field for parent record context. |
| `records_v1.title` parent | Collection/record title | Yes | No | Yes | Yes | No | Used as collection label in provenance header. |
| `ItemV1.creator_agent_label` | Creator label | Yes | No | Yes | Yes | No | Provenance/support field, not source quotation. |
| `ItemV1.creators` | Structured creator list | Yes | No | Yes | Yes | No | Collapsed to displayable creator where needed. |
| `ItemV1.date_begin` / `date_end` | Archive-assigned date span | Yes | No | Yes | Yes | No | Normalized into `date_text` for provenance headers. |
| `ItemV1.artefact_date_from` / `artefact_date_to` | Artefact date range | Yes | No | Yes | Yes | No | Fallback date provenance when begin/end absent. |
| `ItemV1.location_repository` | Repository label | Yes | No | Yes | Yes | No | Provenance/support label. |
| `ItemV1.parent_collection` | Parent collection metadata | Yes | No | Yes | Yes, under catalogue heading if needed | No | Retained inspectably; not merged into source text. |
| `ItemV1.category` | Archive document/object type | Yes | No | Yes | Yes, under catalogue heading | No | Descriptive catalogue metadata. |
| `ItemV1.scope_and_content` | Catalogue description / scope note | Yes | No | Yes | Yes, under catalogue heading | No | Potentially useful but explicitly separated from source text. |
| `ItemV1.abstract` | Abstract/summary metadata | Yes | No | Yes | Yes, under catalogue heading | No | Descriptive metadata only. |
| `ItemV1.caption` | Archive caption | Yes | No | Yes | Yes, under catalogue heading | No | Descriptive metadata only. |
| `ItemV1.subjects` | Subject terms | Yes | No | Yes | Yes, under catalogue heading | No | Can aid retrieval but may encode institutional interpretation. |
| `ItemV1.project_theme` | Project/theme classification | Yes | No | Weighting only | Yes, under catalogue heading | No | Inspectable descriptive influence. |
| `ItemV1.project_title` | Project title metadata | Yes | No | Yes | Yes, under catalogue heading | No | Descriptive support, not source text. |
| `ItemV1.methodology` | Catalogue methodology field | Yes | No | Weighting only | Yes, under catalogue heading | No | Treated as archive description. |
| `ItemV1.language_codes` | Language codes | Yes | No | Filter only | Yes, under catalogue heading when relevant | No | Useful for retrieval filtering. |
| `ItemV1.level` | Archival level | Yes | No | Filter only | Yes, under catalogue heading when relevant | No | Structural metadata, not source evidence. |
| `ItemV1.fonds_code` | Fonds code | Yes | No | Filter/source label | Yes, under catalogue heading when relevant | No | Structural archival metadata. |
| `ItemV1.series_id` | Series identifier | Yes | No | Filter/source label | Yes, under catalogue heading when relevant | No | Structural archival metadata. |
| `ItemV1.ddr_period` | DDR period classification | Yes | No | Weighting/filter only | Yes, under catalogue heading when relevant | No | Descriptive classification, not source quotation. |
| `ItemV1.ml_annotation` / `DigitalAsset.ml_annotation` | Human annotation note for ML handling | Yes | Policy audit only | No | No | Yes | Not used as lexical evidence. |

## Current retrieval policy

- Provenance only: rights, consent/takedown, source URI, ML eligibility state, ML annotation notes.
- Retrieval filters or weighting: title, creator, date, archive reference, repository, collection title, document type, language codes, selected descriptive fields such as `scope_and_content`, `subjects`, `project_theme`, and `abstract`.
- Sent to Granite: retrieval/provenance header fields plus selected descriptive metadata under `ARCHIVE / CATALOGUE METADATA:`.
- Withheld from Granite: control metadata and governance fields, including ML policy, rights/takedown, and raw source URIs.

This preserves the methodological distinction:

archive/catalogue description
!= source-document evidence
!= model-generated inference