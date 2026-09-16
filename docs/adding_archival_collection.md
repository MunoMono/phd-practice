# Adding an Archival Collection

## 1. Create the benchmark specification

Create `backend/config/benchmark_questions/<collection>-v1.json` using the `archival-evidence-benchmark-v1` schema. Declare the collection and corpus versions, temporal boundaries, and each question's research case, exact wording, anchors, permitted evidence layers, prohibited inference classes, expected missingness, and optional authority context.

Use `GENERIC_ARCHIVE_FIRST` when passage selection should remain collection-generic. Use a configured reservation only when a regression question needs fixed, provenance-verified passages. A reservation must name exact chunk IDs and must not stand in for a collection-wide retrieval strategy. For a stable page-level reservation, use `CONFIGURED_DOCUMENT_PAGES` and declare ordered `document_pages` entries containing `document_id` and `page`, plus the matching retained `chunk_ids`.

For a bounded regression answer, add `synthesis_guard` with a `claim_templates` mapping from every reserved chunk ID to its direct-claim wording, a `not_established` list, and an `answer`. The guard applies only when every configured chunk is present in the retained packet set; otherwise normal staged synthesis remains responsible for the response. Authority-backed guards may additionally declare user-facing `authority_context`; the typed authority record remains separate from documentary claims. Where a deterministic, provenance-bound answer is appropriate after a malformed model stage, declare `stage_fallback` with `source_analysis: CONTEXTUAL_ONLY` or `final_synthesis: EMPTY_TYPED_SYNTHESIS`.

Declare `archival_associations` only for catalogue scope. Each association requires `record_pid`, `scope`, `controlled_fields`, `source`, and a limiting `description`. It is returned and rendered separately from documentary and authority evidence, and cannot establish collaboration, authorship, role, or event by itself.

## 2. Ingest and verify the collection

Ingest archive snapshots and documentary chunks under a distinct corpus version. Preserve record, media, asset, page, and chunk identities. Retain inherited record and asset metadata with field-level provenance. Confirm rights and ML eligibility before any passage becomes selectable.

## 3. Define evidence boundaries

For every question, identify what direct documentary text may establish, what archival metadata may establish, what administrative authority context may establish, and what must remain missing or not established. Declare the source-form and temporal policy for later oral testimony.

When a question requires review of oral-history material, declare `source_selection.oral_history.review_required: true`. Retrieval diagnostics then report the ML-eligible oral-history assets checked, those nominated by relevance, retained selections, and assets excluded for relevance. These counts document the retrieval stratum; they do not turn an unselected interview into evidence.

Use `source_selection.required_source_families` to require a deliberately mixed retained set, such as `documentary` and `oral_history`. Archive-first supplemental selection prioritises a nominated but not-yet-represented required family, and diagnostics explicitly mark any unmet requirement.

For named-entity questions, declare `source_selection.authority_expansion.review_required: true`. Diagnostics then expose the resolved authority identifier and every ML-permitted asset linked through controlled people or alias fields before passage selection, together with the number retained in the evidence bundle. Textual name mentions alone do not enter this controlled-asset audit.

The snapshot export must preserve controlled people and aliases inherited from asset, attached-media, and record levels. Rebuild and validate the persisted asset snapshot after adding those fields; an empty authority coverage set is an ingestion coverage gap, not evidence that no linked records exist. The present DDR Archive GraphQL `ItemV1` and `DigitalAsset` types do not expose `people`, `controlled_people`, `aliases`, or `controlled_aliases`; therefore current production reports `CONTROLLED_LINKAGE_UNAVAILABLE` transparently. Do not infer an absence of historical linkage from this upstream schema limitation.

When a configured authority expansion has no controlled linked assets, diagnostics report `CONTROLLED_LINKAGE_UNAVAILABLE`. Resolve that ingestion gap before treating the coverage audit as complete.

## 4. Add regression fixtures

Add a bounded fixture collection with at least one known relationship, one contested interpretation, and one scoped-missingness question. Each fixture should contain stable source, page, chunk, and quotation identities plus expected limits.

`backend/config/benchmark_questions/harbor-notes-v1.json` is a deliberately fictional reference fixture with those three question types. It is intended for policy, synthesis, and evaluator regression tests only; it is not ingested into the production corpus.

## 5. Run the evaluator

Create a JSON mapping of policy IDs to saved pipeline artifacts, then run:

```bash
cd backend
../.venv/bin/python scripts/evaluate_archival_benchmark.py artifacts.json \
  --config config/benchmark_questions/<collection>-v1.json \
  --output-json evaluation.json \
  --output-matrix evaluation.md
```

Review source and asset diversity, evidence-type counts, provenance validity, prohibited inference matches, temporal-boundary compliance, and expected missingness before deployment.

For an end-to-end interrogation smoke report, run every configured question against the deployed API:

```bash
cd backend
python scripts/smoke_archival_benchmark.py \
  --url http://127.0.0.1:8000/api/analysis/interrogate \
  --output-artifacts artifacts/<collection>-smoke-artifacts.json \
  --output-json artifacts/<collection>-smoke-evaluation.json \
  --output-matrix artifacts/<collection>-smoke-evaluation.md \
  --retries 10 \
  --retry-delay 15
```

The runner retries transient request and response-decoding failures per question, then evaluates the normalized public response and exits nonzero when any policy is invalid.

## 6. Deploy and inspect

Deploy backend changes, run each configured question through the interrogation interface, and confirm that documentary evidence, archival metadata associations, authority context, inference, and missingness are visibly separate. Verify that every direct claim has source, chunk, page, and quotation provenance.
