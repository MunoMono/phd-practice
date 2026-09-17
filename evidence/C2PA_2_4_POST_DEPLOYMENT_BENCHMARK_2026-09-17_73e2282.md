# C2PA 2.4 Post-deployment Provenance Benchmark

## Scope

This follow-up compares the deployed provenance changes in revision `73e2282` with the read-only baseline benchmark recorded on 2026-09-17. It is a comparative research-provenance benchmark, not C2PA certification or a conformance assessment.

## Observed result

Applicable score: $50 / 84 = 59.52\%$.

The score rises by three points from the baseline $47 / 84 = 55.95\%$. Only two criteria changed:

| Criterion | Baseline | Observed post-deployment result | Score |
| --- | ---: | --- | ---: |
| C2PA-BM-013 Integrity and tamper evidence | 0 | A persisted query run exposes a `provenance_sha256` binding and all ten retained chunks expose `content_sha256`; the deployed schema includes the append-only provenance-events table. This is retained-record integrity evidence, not source-byte hard binding, signature, or a C2PA manifest. | 2 |
| C2PA-BM-020 Portability and interoperability | 1 | Two GET requests each for JSON and Markdown exports returned byte-identical output for the same persisted query run. | 2 |

All other benchmark rows retain their baseline scores. In particular, the sampled pre-existing experiment has `output_sha256: null` and five `evidence_sha256: null` fields, so this follow-up does not claim legacy experiment-output coverage. No source-byte cryptographic binding, C2PA manifest, signature, certificate, trust list, or authenticity verdict was implemented or demonstrated.

## Runtime evidence

- Production health returned `{"status":"healthy"}` after backend/frontend recreation.
- The `provenance_events` and `claim_revisions` relations exist in production after migrations `074` through `077`.
- `GET /api/query-runs/retrieval-8eba129f058d` returned a `provenance_sha256` and ten chunks with `content_sha256`.
- JSON export was fetched twice: both responses were 84,108 bytes with SHA-256 `e03b8847bce23295888b928ae88d8ac77b1b42f8f7d851b92826972d73cb1b45`.
- Markdown export was fetched twice: both responses were 2,655 bytes with SHA-256 `1ee89197a5f3eb5ddc0d3dda9350b0d1d93133279a9f9e5d315032150aa835d4`.
- `GET /api/experiments/experiment-b9b2282d5199` returned `output_sha256: null`; its five legacy evidence rows returned `evidence_sha256: null`.

## Limits

The shared production Workbench remained in a query-run loading state after refresh, so the selected-run integrity notification was not visually verified in this run. The API behavior, deployed service health, database migration presence, and deterministic exports were verified directly. No production mutations or tamper attempt were made during the benchmark rerun.