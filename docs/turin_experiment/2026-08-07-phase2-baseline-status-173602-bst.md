# Turin Phase 2 baseline status

Generated: 2026-08-07 17:36:02 BST

## Scope

This note captures the current baseline for the Turin Phase 2 metadata/provenance correction work at the end of the latest bounded Sources-card repair pass.

Scope explicitly excluded from this pass:

- Phase 2C
- retrieval changes
- Granite changes
- authority behavior changes

## Current production baseline

- Production corpus inventory-backed source rows: 109
- Policy split preserved: 62 eligible_unrestricted / 35 eligible_page_restricted / 12 excluded_use_for_ml_false
- Metadata role version on repaired rows: `turin-phase2-metadata-v2`
- Pre-mutation production backup created earlier at: `/root/phd-practice/backups/manual/pre_source_reenrich_20260807_161248.sql.gz`

## What was corrected

### 1. Corpus-wide production re-enrichment

Previously completed and accepted in principle:

- 109 inventory-backed asset rows re-enriched in place
- stable asset identities preserved
- stable `document_id` values preserved

### 2. Endpoint parity

The document detail endpoint and annotations endpoint now resolve researcher-facing metadata through the same shared backend mapping layer.

Representative exact asset:

- archive record PID: `873981573030`
- media PID: `338541406157`
- asset PID: `987235129265`
- document ID: `doc_338541406157_72774d03522b`

Validated outcome:

- `/api/documents/{id}` now includes structured `rights_access`, `retrieval_provenance`, and `catalogue_metadata`
- `/api/documents/{id}/ml-annotations` remains complete
- factual parity between the two endpoints was confirmed locally and on production for the representative record

### 3. Sources detail card cleanup

Bounded frontend correction completed for the Sources detail card:

- explicit rights rows rendered instead of generic fallback copy
- explicit provenance rows rendered instead of generic fallback copy
- keywords rendered as Carbon tags/chips
- date presentation cleaned for researcher-facing use
- raw `date_unknown` field no longer exposed literally in the main card
- `normalized_date` retained in API/persistence but omitted from the main card presentation
- researcher-facing labels retained for accession / shelfmark, box / container, location note, and related provenance fields

## Important semantics established during audit

### Exact asset `987235129265`

Authoritative GraphQL audit showed:

- `location_repository` comes from the digital asset level
- `location_accession` is null for this exact asset
- `location_box` is `AU.AAD.20718` for this exact asset
- `location_note` comes from the digital asset level

Therefore, for this exact asset, `AU.AAD.20718` should be treated as `Box / container`, not `Accession / shelfmark`.

Rights provenance for this exact asset:

- `copyright_holder`, `image_rights`, and `data_rights` are sourced from the digital asset level
- `rights_statement_uri` and `takedown_contact` fall back from higher source levels when absent on the asset
- `rights_owner = RCA` is present at the attached-media level, not the digital-asset level

### Indicative acceptance-check record

Indicative production record:

- title: `A five year programme for design in general education, 2nd draft`
- archive record PID: `014262507600`
- production document ID: `doc_287080879712_14c4a9f6818d`

Observed production API state after deploy:

- rights fields present
- repository present
- location note present
- keyword list present
- language present
- extent present when available
- date rendered as `Circa 1980`
- date qualifier preserved as `Circa`
- `normalized_date` retained internally as `1980`
- `date_unknown` remains internal and false for this record

## Files changed in the bounded correction pass

- `backend/app/services/document_source_service.py`
- `backend/tests/test_document_source_service.py`
- `backend/tests/test_corpus_inventory.py`
- `frontend/src/components/corpus/DocumentDetailPanel.jsx`

## Validation completed

### Backend

- `python tests/test_document_source_service.py` -> passed (8 tests)
- `python tests/test_corpus_inventory.py` -> passed (20 tests)

### Frontend

- `npm run build` -> passed
- frontend linting still has pre-existing unrelated repo errors outside this bounded Sources-card change

### Local behavior

- localhost detail vs annotations parity check -> passed
- local rendered Sources card check -> passed for a live row with explicit rights, provenance, keyword tags, and cleaned date presentation

### Production behavior

- signed-out app shell served successfully
- production `/api/documents/{id}` smoke -> passed for `doc_338541406157_72774d03522b`
- production `/api/documents/{id}/ml-annotations` smoke -> passed for `doc_338541406157_72774d03522b`
- production `/api/documents/{id}` smoke -> passed for `doc_287080879712_14c4a9f6818d`
- production `/api/documents/{id}/ml-annotations` smoke -> passed for `doc_287080879712_14c4a9f6818d`
- production asset count and policy split -> preserved at 109 / 62 / 35 / 12

## Production deploy status

Base committed backend fix previously deployed: `6ba0f03`

Latest bounded Sources-card correction was deployed as a working-tree snapshot layered on top of that base, covering only the four files listed above.

## Remaining status / caveats

- Final authenticated researcher UI check on the production Sources card is still pending
- No further authority-count investigation is required this session
- Historical count discrepancy remains recorded as unresolved because no prior per-authority snapshot exists

## Freeze recommendation

Current recommendation:

- Phase 2 metadata/provenance foundation is safe to freeze at the API and renderer level
- next session may proceed to Phase 2C after the researcher completes the final authenticated production card check