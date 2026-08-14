# Phase 2A Runbook

## Current frozen-corpus research-run workflow

Do not use the active `testamentary-traces` development database for the frozen corpus. Restore the accepted backup into `testamentary_traces_retrieval_validation`, validate it read-only, then apply additive migrations only to that isolated target.

```bash
scripts/restore-innovationdesign-isolated.sh --backup /path/to/backup.sql.gz \
  --database testamentary_traces_retrieval_validation
scripts/validate-isolated-corpus.sh --database testamentary_traces_retrieval_validation
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres \
  -d testamentary_traces_retrieval_validation < backend/migrations/016_experiment_context_budget_provenance.sql
POSTGRES_DB=testamentary_traces_retrieval_validation backend/venv/bin/python \
  backend/scripts/run_turin_full_corpus_commissioning.py
```

Select a candidate from `docs/experiment/prompt-register.md` deliberately. Runs are serial and immutable: do not automatically retry a failed output or tune a prompt from output quality. Inspect the saved run through `/research-runs`, record the mutable researcher assessment, and use raw JSON or the saved-run report export.

```bash
POSTGRES_DB=testamentary_traces_retrieval_validation backend/venv/bin/python \
  backend/scripts/run_turin_registered_prompt.py A1 --top-k 5 --context-budget 4200
```

Start local services with `docker compose up -d db ollama backend frontend`. Run retrieval validation with `backend/scripts/verify_turin_determinism.py`; run the focused experiment tests with `cd backend && ./venv/bin/python tests/test_turin_experiment_service.py && ./venv/bin/python tests/test_experiment_run_service.py`.

For future assets, unchanged identity/checksum skips ingestion; a new asset uses controlled ingestion; changed source representation, policy, or pipeline requires an explicit new corpus/version treatment. The frozen 2026 corpus is never changed in place.

## Source location

Prepared Turin OCR PDFs are not checked into this repository.

Current confirmed access route:

- Archive GraphQL endpoint: `https://api.ddrarchive.org/graphql`
- Master PDF URLs exposed through `records_v1(status: "published") -> attached_media -> pdf_files(role: "pdf_master")`
- Example source host: `https://archive-media.lon1.digitaloceanspaces.com/...`

## Generate an inventory manifest

```bash
backend/venv/bin/python scripts/generate_corpus_manifest.py \
  --output-csv artifacts/turin-phase2a/manifest.csv \
  --output-json artifacts/turin-phase2a/manifest.json
```

## Materialize a small representative sample and persist document identities

```bash
backend/venv/bin/python scripts/generate_corpus_manifest.py \
  --pid 287080879712 \
  --output-csv artifacts/turin-phase2a/sample-manifest.csv \
  --output-json artifacts/turin-phase2a/sample-manifest.json \
  --download-dir .phase2-samples/materialized \
  --materialize-limit 1 \
  --persist-db
```

This produces a local PDF copy for checksum and page-count validation without mutating the archive master source.

## Known limitations at this checkpoint

- The live archive schema does not expose the older `authority(pid: ...)` or `authorities(...)` query roots assumed by the previous repository code.
- Multiple master PDFs can share a single archive/media PID.
- The repository now treats `source_uri` as the unique source-document locator and no longer relies on PID uniqueness.
- Page-aware and heading-aware chunk persistence is not yet implemented in this checkpoint.
- Docling structure has been verified manually in the backend runtime: `DoclingDocument.pages` is a dict, `num_pages` is available, and export methods include markdown, text, dict, element tree, and document tokens.

## Metadata handling checkpoint

- Live metadata schema snapshot used for Phase 2 mapping: `artifacts/turin-phase2-metadata-schema.json`.
- Role separation is persisted in `documents.authority_data` under `corpus_control`, `retrieval_provenance`, and `catalogue_metadata`.
- Granite context assembly now sends provenance headers plus a separate `ARCHIVE / CATALOGUE METADATA` block when descriptive metadata is present.
- Control metadata such as ML eligibility, page scope, rights, and takedown/access fields remain persisted for pipeline control and provenance, but are withheld from Granite answer context by default.

## Current live inventory snapshot

- `109` master PDFs discovered through the live `records_v1(status: "published")` route.
- `97` ML-eligible assets.
- `12` ML-excluded assets.
- Of the eligible set: `62` unrestricted and `35` page-restricted.

These figures describe the live remote archive inventory discovered through the current GraphQL route. They should not be substituted for local dashboard corpus counts unless the relevant UI endpoint is backed by this same inventory source.

## Isolated accepted-corpus restore

The accepted production-derived corpus must be restored only into an isolated database. Do not use the active `testamentary-traces` development database.

```bash
scripts/restore-innovationdesign-isolated.sh \
  --backup /path/to/phd_practice_backup_20260813_144200.sql.gz \
  --database testamentary_traces_retrieval_validation

scripts/validate-isolated-corpus.sh \
  --database testamentary_traces_retrieval_validation

scripts/run-isolated-retrieval-validation.sh \
  --database testamentary_traces_retrieval_validation \
  --query "Bruce Archer" --expansion "Archer" --top-k 5
```

The restore script verifies gzip integrity, rejects active/system database names, refuses to overwrite an existing target, and creates only names matching `testamentary_traces_*_retrieval_validation`. Cleanup is deliberate:

```bash
scripts/restore-innovationdesign-isolated.sh \
  --cleanup --database testamentary_traces_retrieval_validation --yes-really-drop
```

`validate-isolated-corpus.sh` is read-only. It reports the accepted baseline (`138` documents: `109` current and `29` legacy; `13,490` chunks: `12,884` current and `606` legacy), FTS-vector coverage, chunk representation by resolution state, and GIN-index presence. It reports mismatches without changing data.

## Local Granite fixture validation

This starts the repository-local Ollama service only. The backend reaches it through Docker service DNS at `http://ollama:11434`; do not use `127.0.0.1:11434` from inside the backend container.

```bash
docker compose up -d ollama
docker compose up -d --force-recreate --no-deps backend
docker compose exec -T ollama ollama list
docker compose exec -T backend python -c \
  "from app.services.granite_service import get_granite_service; import json; print(json.dumps(get_granite_service().get_load_status()))"
docker compose exec -T backend python scripts/run_granite_fixture_smoke.py
```

The first backend startup pulls only the configured local tag (`granite3.1-dense:2b-instruct-q4_K_M`) if it is absent from the persistent `ollama_data` volume. The smoke command is labelled `FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN`; it sends the known-relationship fixture through context assembly, the versioned prompt, local Granite, structured parsing, and provenance validation twice for a repeatability observation.

Stop only the runtime when it is no longer needed:

```bash
docker compose stop ollama
```

## Immutable fixture experiment persistence

Apply the additive experiment-run migration to the local development database, then run one real local Granite call over fixture evidence only:

```bash
docker compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d testamentary-traces \
  < backend/migrations/014_immutable_experiment_runs.sql
docker compose exec -T backend python scripts/run_persisted_granite_fixture_smoke.py
```

For immutable run snapshots to include the checked-out commit in this development topology, recreate only the backend with the current commit exported to Compose:

```bash
GIT_COMMIT="$(git rev-parse HEAD)" docker compose up -d --force-recreate --no-deps backend
```

The command saves, reloads, and emits the full JSON export for a run explicitly labelled `FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN`. `experiment_runs` and `experiment_run_evidence` are write-once snapshots; only the separate `experiment_run_assessments` table can be edited later through `POST /api/experiments/{run_id}/assessment`.