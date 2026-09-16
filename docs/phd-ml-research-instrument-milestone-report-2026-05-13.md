# PhD ML Research Instrument Milestone Report

## 1. Current Route / Navigation State

- Current routes and page labels:
  - `/` — Research dashboard
  - `/corpus` — Corpus explorer
  - `/tracer` — Evidence tracer
  - `/visual-analytics` — Visual analytics
  - `/sessions` — Interpretive sessions
  - `/experiments` — Provenance log
  - `/ml-dashboard` — Model dashboard
- Old route compatibility:
  - `/dashboard` is still supported and redirects to `/`.
- UI shell order:
  - The header order is: Research dashboard → Corpus explorer → Evidence tracer → Visual analytics → Interpretive sessions → Provenance log → Model dashboard.
  - This now broadly matches the research workflow from corpus reading into trace, then visual analysis, then session/provenance review, with model operations last.

## 2. Completed Features

### Research Dashboard
- Implemented:
  - Route is live.
  - Workflow tiles link into the current research flow.
  - Granite model info is fetched from `/api/granite/model-info`.
  - Stats and existing visualization components are still wired into the page.
- Still placeholder / partial:
  - Dashboard messaging is thesis-facing, but it does not yet surface scoped missingness as a first-class layer.

### Corpus Explorer
- Implemented:
  - Endpoint-driven list/detail flow.
  - Uses `/api/documents`, `/api/documents/{id}`, `/api/documents/{id}/ml-annotations`, `/api/search/similar-documents/{id}`, and `/api/search/autocomplete`.
  - Includes search panel, table, detail panel, and handoff actions.
- Still placeholder / partial:
  - List contract is still thin.
  - Richer archive obscurity / missingness is not yet surfaced in the corpus UI.

### Evidence Tracer
- Implemented:
  - Uses stable Granite retrieval via `/api/granite/analyze`.
  - Enriches sources through provenance and citation endpoints.
  - Includes answer panel, evidence chain, status controls, evidence graph, and memo export.
  - Handoff to Corpus Explorer and Visual Analytics exists.
- Still placeholder / partial:
  - Agent trace mode remains intentionally disabled.
  - Final scoped missingness / obscurity metadata is not yet shown on trace cards or exported memos.

### Visual Analytics
- Implemented:
  - Route is live and no longer placeholder.
  - Consumes `chunkId`, `pid`, and `documentId` query params from Evidence Tracer.
  - Uses `/api/viz/umap` through the shared API layer.
  - Renders UMAP projection, point detail, cluster panel, concept bridge, and memo export.
  - Displays evidence-surface scope, projection method, interpretation warnings, and “not a complete archive map” framing.
  - Point detail displays evidence-surface and missingness sections.
- Still placeholder / partial:
  - Actual plotted data depends on persisted embeddings in the DB.
  - Concept bridge still depends on the current placeholder semantic search backend.
  - Final DDR archive `scoped_missingness_v02` payload is not yet wired end-to-end.

### Interpretive Sessions
- Implemented:
  - Route and page shell exist.
  - Carbon data table layout exists.
- Still placeholder / partial:
  - Uses static sample rows.
  - No `/api/sessions/list`, session detail, evidence-flow, or memo export wiring yet.

### Provenance Log
- Implemented:
  - Route and page shell exist.
  - Training metrics chart component is present.
  - Page correctly frames provenance/training-run intent.
- Still placeholder / partial:
  - The page still describes intended provenance endpoints more than it operationalizes them.
  - It is not yet a fully wired provenance exploration surface.

### Model Dashboard
- Implemented:
  - Existing dashboard stats and visualization tabs remain wired.
  - Uses `/api/viz/document-network`, `/api/viz/theme-distribution`, `/api/viz/temporal-trends`, `/api/viz/entity-network`, `/api/viz/dashboard-stats`, and `/api/viz/refresh-stats`.
  - Existing Granite chat panel remains present and was left untouched.
- Still placeholder / partial:
  - Evaluation-chart and research-instrument framing are still mixed with the older ML dashboard structure.
  - Missingness / evidence-surface accountability is not yet surfaced here.

### API Client / Normalizers
- Implemented:
  - Shared API request layer exists.
  - Error objects now carry HTTP status.
  - Normalizers exist for visualization payloads, evidence tracing, corpus documents, provenance, and UMAP.
- Still placeholder / partial:
  - Final archive-side scoped missingness contract is not yet finalized, so normalizers currently support the current ML app contract rather than the final DDR archive payload.

### Memo Exports
- Implemented:
  - Evidence Trace memo export exists.
  - Visual Analytics memo export exists.
  - Cluster memo export exists.
- Still placeholder / partial:
  - Memo exports do not yet fully embed scoped missingness / obscurity metadata as a first-class interpretive layer.

### UMAP Endpoint
- Implemented:
  - `/api/viz/umap` exists in the backend.
  - The route is evidence-surface-aware and does not claim archive completeness.
  - It returns honest empty states when no embeddings exist.
  - It includes evidence-surface scope, interpretation warnings, evidence-surface point metadata, and stubbed scoped missingness sections.
- Still placeholder / partial:
  - It is only data-bearing when the DB has stored embeddings.
  - It does not yet consume a final DDR archive `scoped_missingness_v02` payload.

## 3. Scoped Missingness / Evidence-Surface State

- Currently expected or stubbed:
  - Visual Analytics UMAP normalization and backend contract currently expect or support:
    - `evidence_surface`
    - `missingness.item_field_missingness`
    - `missingness.asset_missingness`
    - `missingness.graphql_exposure_missingness`
    - `missingness.llm_evidence_missingness`
    - `missingness.interpretation_limits`
    - `metadata.evidence_surface_scope`
    - `metadata.interpretation_warnings`
    - `metadata.projection_method`
- What the app displays if scoped missingness is unavailable:
  - Visual Analytics falls back to empty objects and arrays.
  - Point detail shows conservative “None flagged” / “Unavailable” output rather than inventing archival claims.
  - The page still shows scope framing and interpretation warnings from the current ML-app-side contract when available.
- Where final DDR archive `scoped_missingness_v02` should be consumed later:
  - Visual Analytics point detail and scope metadata.
  - Corpus Explorer document detail and listing badges.
  - Evidence Tracer source cards, evidence graph context, and exported memos.
  - Shared memo export helpers so interpretive claims carry explicit evidence-surface limits.
- Current constraint:
  - The ML app does not yet have the final archive-side `scoped_missingness_v02` payload wired through. Current fields are a conservative, app-local scaffold rather than the final archive contract.

## 4. Backend State

- Backend endpoints currently used by the frontend:
  - Granite:
    - `/api/granite/analyze`
    - `/api/granite/model-info`
    - `/api/granite/load-status`
    - `/api/granite/load-model`
    - `/api/granite/unload-model`
    - `/api/granite/health`
  - Documents / corpus:
    - `/api/documents`
    - `/api/documents/{document_id}`
    - `/api/documents/{document_id}/ml-annotations`
  - Search:
    - `/api/search/semantic`
    - `/api/search/similar-documents/{document_id}`
    - `/api/search/entity-search`
    - `/api/search/autocomplete`
  - Provenance:
    - `/api/provenance/chunk/{chunk_id}/citation`
    - `/api/provenance/chunk/{chunk_id}/provenance`
    - `/api/provenance/inference/{inference_id}`
    - `/api/provenance/training/{run_id}`
  - Visualization:
    - `/api/viz/document-network`
    - `/api/viz/theme-distribution`
    - `/api/viz/temporal-trends`
    - `/api/viz/entity-network`
    - `/api/viz/dashboard-stats`
    - `/api/viz/refresh-stats`
    - `/api/viz/umap`
- New backend endpoint added in this milestone:
  - `/api/viz/umap`
- `/api/viz/umap` status:
  - Yes, it exists.
  - It prefers UMAP if available.
  - It can use PCA fallback when projection dependencies are limited.
  - With no embeddings, it returns an honest empty 200 response with scope metadata and warnings.
- Granite status:
  - Existing Granite endpoints and the working Granite chat path were left untouched.

## 5. Data Limitations

- Only four oral-history PDFs are currently ingested into Granite / the ML corpus.
- The UI/API now represents this as a partial evidence surface rather than a total archive representation:
  - Visual Analytics explicitly frames the projection as the current ML-ingested / public GraphQL evidence surface.
  - UMAP metadata includes scope notes and interpretation warnings.
  - Empty or limited projection results are treated as evidence-surface limits, not archival absence.
- Current DB reality in this app instance:
  - The local DB currently reports zero stored extracted-text documents and zero stored embeddings.
  - That means the current UMAP endpoint still resolves to an honest empty state rather than plotted points.
- Conclusion:
  - The UMAP should not be interpreted as the full DDR archive.
  - It is a projection of the currently ingested, text-extracted, embedded evidence surface only.

## 6. Validation

- Frontend build result:
  - `cd frontend && npm run build` passed.
- Backend startup / test result:
  - Available validation: `python -m py_compile backend/app/api/routes/viz.py` passed.
  - Full backend app import from the local `.venv` is not currently available because the environment is missing `fastapi`.
- Warnings:
  - Sass legacy JS API deprecation warnings still appear during frontend build.
  - IBM Plex font asset resolution warnings still appear during frontend build.
  - Vite warns that the main frontend bundle remains larger than 500 kB after minification.
- Runtime caveats:
  - `localhost:8080` may still be serving the separate `phd-practice-frontend` container snapshot rather than this workspace build.
  - The current running frontend container has no source mounts from this repo, so browser output at `localhost:8080` should not be assumed to reflect the latest main-repo code without rebuilding/redeploying that runtime.

## 7. Known Issues / Risks

- Endpoint contract mismatches:
  - The frontend and backend UMAP contract are aligned for the current ML app, but the final DDR archive `scoped_missingness_v02` payload is not yet the live source of truth.
- Mock or placeholder backend routes:
  - `/api/search/semantic` remains a placeholder text-matching route rather than a true embedding-backed semantic search.
  - Interpretive Sessions remains static.
  - Provenance Log is only partially wired.
- Missing final `scoped_missingness_v02` payload:
  - The current app-local missingness shape is a scaffold, not the final archive apparatus payload.
- Missing Docling/OCR text extraction status:
  - Final text-extraction / OCR / Docling state is not yet surfaced across the app as a stable user-facing contract.
- Auth state:
  - The main repo still uses Auth0 in the standard app shell.
  - Runtime behavior at `localhost:8080` can diverge if the browser is hitting the separate production-sync container with different auth bypass settings.
- Sass / font warnings:
  - Sass legacy JS API deprecation warnings persist.
  - IBM Plex font resolution warnings persist at build time.

## 8. Recommended Next Steps

- Quick UI check / rebuild runtime:
  - Rebuild or restart the runtime serving `localhost:8080` so the browser reflects the current main-repo Visual Analytics and UMAP framing.
- Complete `scoped_missingness_v02` payload in the DDR archive repo:
  - Finalize the archive-side payload and wording there first.
- Wire final `scoped_missingness_v02` into the ML app:
  - Replace the current local scaffold with the archive-side contract across Visual Analytics, Corpus Explorer, Evidence Tracer, and memo exports.
- Then continue Interpretive Sessions:
  - Replace static rows with session endpoints and evidence-flow views.
- Then Provenance Log:
  - Make training/inference provenance views fully data-bearing.
- Then Model Dashboard evaluation charts:
  - Add evaluation-oriented charts and evidence-surface accountability without disturbing the working Granite chat path.
