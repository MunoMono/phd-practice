# UMAP Visual Analytics Implementation Status

Status date: 2026-10-02
Scope authority: `DDR_UMAP_visual_analytics_development_SoW_v0.3_SCOPE_FROZEN.md`

## Implemented foundation

- The existing dark Carbon three-pane Visual Analytics workbench remains the implementation surface.
- Semantic point payloads now include explicit evidence-surface, missingness, archive-authority, database-authority, annotation, and provenance states. Unavailable data is labelled rather than inferred.
- Evidence-surface scope exposes eligible, represented, rendered, and visible counts, plus rendering policy.
- The inspector exposes representation, missingness, archive authority, database authority, projection, and compact method/provenance fields.

## Semantic Neighbourhoods

- The API validates display `k` with `min=5`, `max=50`, `step=5`, and `default=10`.
- The Carbon `Neighbourhood size (k)` Slider and adjacent numeric field appear only in Semantic Neighbourhoods.
- Requests return fixed projection/embedding identities, original-space cosine metric, requested/returned `k`, bounds, rank, focal point, and ordered neighbours.
- Changing `k` refreshes original-space neighbours without reloading the baseline projection.
- Neighbours can be promoted to focal traces.
- JSON and Markdown evidence packets include focal identity, neighbours, scores, method, projection/embedding identities, `k`, bounded excerpts, caveat, and researcher note.
- The inspector states why a neighbour was retrieved without generating a historical interpretation.

## Comparative Views

- A/B cohorts can be named and retained in the workspace/export with point IDs, creation time, source, version, projection, and embedding scope.
- `POST /api/viz/cohorts` persists a researcher-defined selection rule, explicit point IDs, projection/embedding scope, optional inquiry link, immutable version, and timestamps; `GET /api/viz/cohorts/{cohort_id}` retrieves it.
- `POST /api/viz/projection-fidelity` provides a bounded local Jaccard overlap diagnostic between original cosine and stored 2D projected neighbourhoods.
- Cohort rules support explicit researcher-selected AND or OR semantics over source type, theme, and a bounded year range; their resolved membership and rule definition persist together.
- Comparative A/B membership can be exported as CSV with point, document, chunk, PID, metadata, membership, and projection/embedding scope.
- The fidelity control is independent from the comparison overlay and records diagnostic method, metric, version, projection/embedding IDs, neighbourhood size, and exclusions.
- Fidelity copy explicitly describes neighbourhood preservation as a projection diagnostic, not historical confidence or evidential strength.

## Temporal and Critical Inquiry

- Temporal view defaults to `Fixed projection`; filters change visibility/encoding only and export representation counts.
- Two saved temporal windows report their dated in-window and undated record counts from the same fixed stored projection.
- Authority-backed period presets persist their date bounds, stated source, certainty, and notes. Selecting a preset populates a fixed window without recomputing coordinates, and discloses that provenance in the comparison panel.
- Documentary overlays expose returned file type, extraction state, rights/access state, metadata-completeness state, document text-length bands, and document chunk-count bands. Text/chunk values are returned measures for the represented database document, not archive-wide totals; unavailable fields remain visibly `not_exposed` or `not_evaluated`, not inferred.
- A validated aligned-run ID can load a static, accessible comparison of reviewed slice membership and explicit consecutive relations. It cannot generate coordinates, trails, animation, or historical continuity; those remain unavailable until a separately computed aligned coordinate run exists.
- Critical Inquiry has transparent editable researcher lens presets. The exact selected preset and submitted text persist in workspace/export.
- Critical retrieval remains original-space only. The UI explicitly withholds a transformed probe marker until reducer compatibility is verified.
- Researcher-labelled positive and negative critical probes persist their inquiry, projection/embedding scope, method, and returned result payload through `visual_critical_probes`.
- A saved probe can be compared with a second saved probe by explicit ID; the workbench reports result-set overlap as shared retrieval candidates, never confirmation of the proposition.

## Atlas Encodings

- Atlas color controls support explicit representation, missingness, archive authority, database authority linkage, and researcher annotation status encodings alongside source/theme/year/cluster modes.
- Atlas color controls also support projected local visual density derived from distances between stored displayed coordinates. Its legend explicitly rejects historical concentration, significance, and archive-completeness interpretations.
- A data-derived legend names the active display field, the loaded values, and the limitation that visual encoding is not a historical conclusion.

## Durable Research Records

- `VisualInquiry` records save supported workspace state and projection/embedding scope. A URL with `?inquiryId=` reloads the supported saved state without recomputing coordinates.
- `VisualCohort` records persist server-issued cohort IDs and versions; the workbench cohort actions use the durable endpoint rather than local-only identifiers.
- `VisualAnnotation` records require a document or chunk identifier, a researcher-supplied type/value, optional evidence source/reviewer, and explicit `draft`, `reviewed`, or `contested` status. No automatic social classification is performed.
- The selected-point inspector supplies explicit annotation type, note, and review status controls; it never infers an annotation from display metadata.
- Each new annotation writes an immutable first `VisualAnnotationRevision` snapshot. `PUT /api/viz/annotations/{annotation_id}` appends later numbered snapshots and `GET /api/viz/annotations/{annotation_id}/revisions` returns the ordered history.
- Focused regression coverage verifies owner/reviewer revision authorization, creation, revision persistence, ordered history display, and frontend Bearer-token propagation. Production Auth0 issuer/audience and researcher UAT validation remain required before release.
- `scripts/migrations/20261002_01_visual_analytics_research_records.sql` through `scripts/migrations/20261002_05_visual_temporal_periods.sql` are applied locally through `scripts/apply-db-migrations.sh`.
- `aligned_umap_runs`, slices, explicit consecutive relations, and validation reports are now persisted locally through migrations `20261002_06` and `20261002_07`. Static aligned comparison metadata remains unavailable until persisted relations validate.
- Reducer checkpoint and compatibility-review provenance is persisted locally through migration `20261002_08`; compatibility availability is metadata-only and does not deserialize a checkpoint or render a transformed marker.

## Validation Completed

- Focused backend tests: `backend/tests/test_viz_semantic_atlas_fallback.py`.
- Focused browser tests: `frontend/tests/visual-analytics-fts-only.spec.js`.
- Browser coverage verifies FTS-only availability messaging, documentary aggregate bands, neighbourhood `k` controls and fixed-projection behavior, sourced temporal period application without projection recomputation, validated aligned-run static provenance, comparison capability state, explicit source annotations, durable researcher-defined cohorts, and positive/negative Critical Inquiry probe records.

## Still Required Before SoW Completion

- Production bearer-token, migration/deployment, and researcher validation for annotation access/history.
- Comparative categorical/continuous overlays and source comparison table beyond CSV membership export.
- Independently sourced rights/access and metadata-completeness inputs; the current point contract continues to expose their unavailable state rather than infer them.
- AlignedUMAP coordinate generation/storage and optional reduced-motion Time stack, which require an approved algorithm/runtime plus actual named immutable embedding slices and validated relation mappings.
- Retained reducer runtime validation and transformed non-archival critical probe markers.
- API, accessibility, responsive screenshot, export, migration, deployment, UAT, and release-gate validation required by the frozen SoW.
