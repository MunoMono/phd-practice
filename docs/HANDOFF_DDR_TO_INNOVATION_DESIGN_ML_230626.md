# DDR -> Innovation Design ML Handoff

## 1. Current status

DDR is ready for ML Phase 1 ingestion, with caveats.

- Production GraphQL endpoint: `https://api.ddrarchive.org/graphql`
- Primary ingestion preset: `LLM evidence surface v0.2 — advanced ML/diagnostics`
- Fixture/debug preset: `Full PID exemplar evidence bundle — advanced ML/diagnostics`
- All eight API presets currently execute successfully on production.
- Seeded keyword count: `118` unambiguous assets verified in production.
- Excluded duplicate count: `12` duplicate-collision asset IDs remain excluded for future DDR data-integrity cleanup.
- Diagnostics status: `diagnostics` and `scoped_diagnostics_v02` are live on production.
- Signed URL warning: the approved ML presets do not request `signed_url`, but `signed_url` is still queryable from public GraphQL if explicitly requested. The ML repo must not request, store, prompt, train on, or commit signed URLs.

## 2. Source-of-truth boundary

- DDR API and DigitalOcean asset references remain authoritative.
- The innovation-design ML repo should store research derivatives only.
- The ML repo must not become a second archive.
- DDR remains the source of truth for metadata, public evidence payloads, record/media/asset identifiers, and archival references.
- The ML repo should store snapshots, Docling outputs, chunks, embeddings, retrieval logs, claims, UMAP coordinates, evaluation artifacts, and case-study exports.

## 3. Recommended Phase 1 corpus

- Use the `118` seeded, unambiguous, ML-approved assets first.
- Do not wait for the `12` duplicate-collision assets.
- Do not wait for the additional V&A PDFs.
- Treat the four existing PDFs as regression/smoke fixtures rather than the main corpus.

## 4. GraphQL evidence contract

The ML repo should consume the following from the API:

- PID / record ID
- title / caption / label
- attached media
- digital assets
- asset IDs
- roles
- keywords
- rights fields
- date fields
- `use_for_ml`
- `ml_pages`
- `diagnostics`
- `scoped_diagnostics_v02`
- asset-context provenance fields when production GraphQL exposes them
- public or stable URLs only where appropriate

Hard rules:

- Do not request `signed_url`.
- Do not commit signed URLs.
- Do not pass signed URLs to LLM prompts.
- Do not include signed URLs in training data or fixtures.

## 5. Asset-context provenance metadata

DDR admin asset rows include provenance metadata that is useful for ML explainability and chunk-level context:

- extent number
- extent unit
- repository
- accession / shelfmark
- box / container
- location note
- language / locale

Asset-context metadata is now part of the planned ML evidence contract. The DDR repo has local additive GraphQL support for extent, repository, accession/shelfmark, box/container, location note, and language fields on DigitalAsset. These fields should be treated as deploy-pending until production GraphQL verification confirms them.

Current implementation status:

- Additive GraphQL work has been made locally in DDR.
- `DigitalAsset` now exposes these fields locally:
  - `extent_number`
  - `extent_unit`
  - `location_repository`
  - `location_accession`
  - `location_box`
  - `location_note`
  - `language_codes`
- The advanced ML evidence presets have been updated locally to request them.
- Local runtime smoke passed against a temporary in-container validator after backend schema reload.
- Blank values returned as `null` in the tested local exemplar.
- `language_codes` is currently exposed as a scalar field, not a list, but the local test only observed `null` because no populated local values were available.
- This change has not yet been deployed to production.
- Once deployed, the ML repo should ingest these fields as provenance metadata for each asset and chunk.

Important caveat:

- Do not represent these asset-context fields as already production-live unless they have been deployed and verified on `https://api.ddrarchive.org/graphql`.
- `location_box` is the GraphQL field corresponding to Box / container.
- These values may be `null` until manually entered in DDR admin.
- The ML repo should preserve them as provenance fields, not treat nulls as archival absence.
- Box/container values are useful for physical provenance and explainability but should not block Phase 1 ingestion.

## 6. Diagnostics and missingness policy

- Diagnostics are not archival truth.
- Scoped missingness is a versioned reading of the evidence surface.
- Absence from GraphQL is not absence from the archive.
- OCR or Docling absence is not proof the source contains no text.
- Authority absence is not proof a person, project, or contributor is absent.
- Diagnostics and scoped missingness are appropriate for evidence auditing, readiness assessment, retrieval filtering, and research interpretation with provenance.

## 7. Authority data policy

- Authority data is useful but provisional.
- Authority links should be ingested when exposed.
- Candidate unlinked names from Docling text should be flagged for review.
- Authority gaps should become research evidence, not silent failures.
- Treat authority context as incomplete and subject to future enrichment rather than as a complete normalized authority graph.

## 8. ML repo starting tasks

1. Fetch one record with `LLM evidence surface v0.2 — advanced ML/diagnostics`.
2. Build a GraphQL client using the preset query.
3. Store a metadata snapshot per PID, media, and asset.
4. Fetch only approved assets for Docling using safe asset access rules.
5. Run Docling and store page-level outputs.
6. Build stable chunk IDs with PID, asset ID, page range, extraction version, and chunk strategy.
7. Attach keywords, rights, date, diagnostics, scoped missingness, and asset-context provenance fields to chunks.
8. Build embeddings.
9. Build retrieval trail logging.
10. Create the first case-study export pack.

## 9. Minimum chunk metadata contract

```json
{
  "pid": "511010510951",
  "record_id": "175",
  "media_id": "175",
  "asset_id": "e0708b71ca1b87e1832d990dbd3df5a7310d8101f33fc87e1587137729a39ef1",
  "asset_role": "pdf_master",
  "label": "Interview with Anthony Finkelstein",
  "title": "Stephen Boyd Davis DDR oral histories transcripts",
  "page_number": 1,
  "page_range": "1-2",
  "chunk_id": "511010510951__e0708b71ca1b87e1832d990dbd3df5a7310d8101f33fc87e1587137729a39ef1__p1-2__docling-v1__semantic-001",
  "chunk_index": 1,
  "chunk_strategy": "semantic-window",
  "extraction_status": "processed",
  "docling_version": "pin-in-ml-repo",
  "text_extracted": true,
  "keywords": [
    "Anthony Finkelstein",
    "Stephen Boyd Davis",
    "Computing in design"
  ],
  "rights_holders": "See DDR rights fields",
  "date_display": "May 2018",
  "normalized_date": "201805",
  "extent_number": null,
  "extent_unit": null,
  "location_repository": null,
  "location_accession": null,
  "location_box": null,
  "location_note": null,
  "language_codes": null,
  "diagnostics_version": "0.1",
  "scoped_missingness_version": "0.2",
  "evidence_limitations": [
    "Diagnostics are interpretive evidence",
    "Absence from GraphQL is not absence from archive"
  ],
  "source_preset": "LLM evidence surface v0.2 — advanced ML/diagnostics",
  "source_graphql_endpoint": "https://api.ddrarchive.org/graphql",
  "ingestion_timestamp": "2026-06-23T00:00:00Z"
}
```

Notes:

- `location_box` is the field corresponding to Box / container.
- These values may be `null` until manually entered in DDR admin.
- The ML repo should preserve them as provenance fields, not treat nulls as archival absence.
- Box/container values are useful for physical provenance and explainability but should not block Phase 1 ingestion.

## 10. Known non-blocking DDR issues

- `12` duplicate production asset-ID collisions remain unresolved.
- `signed_url` is still queryable if explicitly requested.
- The authority graph is not complete.
- Additional V&A PDFs are not yet ingested or keyworded.
- The scheduled backup flow requires an operations repair.
- Diagnostics remain advanced and governance-sensitive.

## 11. Remaining DDR backlog

1. Deploy and production-verify asset-context `DigitalAsset` fields.
2. Add and manually enter box/container values in DDR admin.
3. Resolve `12` duplicate asset-ID collisions.
4. Harden public `signed_url` exposure.
5. Repair stale scheduled backup flow.
6. Add and keyword extra V&A PDFs as Phase 2 enrichment.

## 12. Go / no-go decision

`GO for innovation-design ML Phase 1 ingestion.`

Caveats:

- Use only approved presets.
- Do not request signed URLs.
- Treat diagnostics as interpretive.
- Preserve provenance.
- Do not overclaim from missingness.
- Asset-context provenance fields are deploy-pending until production GraphQL verification confirms them.
- Manual box/container entry can proceed in DDR admin.
- ML Phase 1 should not wait for every box number to be filled.
- Once deployed, the ML repo should parse the asset-context fields automatically through GraphQL.

## 13. Operating mantra

`No feature without an analytical output. No output without a research question. No AI without provenance. DDR is the source of truth; innovation-design is the research apparatus.`
