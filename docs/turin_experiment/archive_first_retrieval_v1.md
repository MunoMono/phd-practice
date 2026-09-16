# Turin Archive-First Retrieval V1

`turin-archive-first-retrieval-v1` is the source-discovery architecture for the interactive `/source-interrogation` workflow. It does not alter V3.16, its corpus, historical runs, or Qwen records.

## Pipeline

```text
QUESTION
  -> QUESTION FACETS / TYPED ANCHORS
  -> PERSISTED ARCHIVE ASSET SNAPSHOT
  -> CANONICAL DIGITAL-ASSET NOMINATION
  -> ML ELIGIBILITY / PAGE SCOPE
  -> DOCUMENT AVAILABILITY
  -> DOCLING WITHIN-SOURCE PASSAGE RETRIEVAL
  -> EVIDENCE SET
  -> QWEN
```

Archive metadata nominates sources only. Docling-derived chunks provide documentary evidence. Qwen receives only the selected evidence packets and minimal source identity/provenance.

## Persisted Snapshot

Migration `backend/migrations/063_turin_archive_asset_snapshot_v1.sql` adds `turin_archive_asset_snapshots`. Each row is one canonical digital asset and stores record/media/asset identifiers, label and date, ML policy, page scope, controlled people/projects/aliases, source type, collection/box context, and archive preset groups.

Create a snapshot outside interrogation using the established Archive client:

```bash
docker exec -w /app -e PYTHONPATH=/app phd-practice-backend python scripts/materialize_turin_archive_asset_snapshot.py --export /app/artifacts/turin-archive-asset-snapshot-v1.json
```

After applying migration 063, materialise that persisted snapshot locally:

```bash
docker exec -w /app -e PYTHONPATH=/app phd-practice-backend python scripts/materialize_turin_archive_asset_snapshot.py /app/artifacts/turin-archive-asset-snapshot-v1.json --replace
```

The request path never calls the live Archive API.

## Response Contract

`POST /api/analysis/retrieve?v=4` returns no model output and exposes:

- `archival_discovery`: nominated assets, matched controlled fields, and nomination reasons.
- `document_availability`: asset-specific local/Docling classification.
- `documentary_evidence`: passages selected only within nominated, ML-eligible assets.
- `corpus_representation_gaps`: ML-eligible nominated assets without a local governed document.
- `archival_context_only`: relevant assets excluded by `use_for_ml = false`.

`POST /api/analysis/interrogate` uses the same retrieval output and additionally returns Qwen's generated interpretation. It preserves these four layers rather than treating metadata as text evidence.

## Availability and Missingness

- `ARCHIVAL_CONTEXT_ONLY`: archival candidate is not ML eligible and is excluded from documentary inference.
- `CORPUS_REPRESENTATION_GAP`: ML-eligible archive asset has no matching governed local document.
- `DOCLING_TEXT_MISSING`: local document exists but no chunks are available.
- `DOCUMENTARY_EVIDENCE_INSUFFICIENT`: nominated Docling text has no quality-gated passage for the question.

`ARCHIVAL_ABSENCE`, `RETRIEVAL_FAILURE`, and `GENERATIVE_OVERREACH` remain distinct assessment categories. The retrieval service does not infer archival absence from a corpus gap.