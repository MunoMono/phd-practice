---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_07
title: Full 50-question human UAT release gate
status: in_progress
sequence: 7
depends_on:
  - ML_TRIAGE_V2_SOW_06
baseline_csv: /docs/ml_triage_dev_v2/clean_ml_triage_dev_UAT_50_v2.csv
required_pass_count: 40
required_pass_rate: 0.80
must_pass:
  - MLT-DOC-18
  - MLT-LIM-01
critical_violations_allowed: 0
---

# SoW 07 - Full 50-Question Human UAT Release Gate

## Objective

Run the authoritative human-in-the-loop UI rerun of Questions 1-50 after remediation and decide whether ML Triage Dev V2 is ready to proceed to the later Questions 51-100 holdout/generalisation phase.

This is a release gate, not another coding phase.

## Release Preparation Plan

### Objective and frozen release input

Deploy one production build that preserves accepted SoW 01-06 behaviour, then hand the fixed build to the researcher for the manual 50-question UAT. This plan does not authorize that UAT to start automatically.

- The release candidate must be a recorded Git commit and immutable deployment tag that includes accepted SoW 06 changes. Record both as `release_commit` and `release_build_id`; do not substitute the working-tree `HEAD` when it omits those changes.
- Preserve `corpus_turin_targeted_5b176946674f`, the production Ollama runtime/model `qwen3:8b-q4_K_M`, the UAT manifest identity, the backend image digest, frontend build digest, compose-file revision, and deployment timestamp.
- Required dev parity baseline: 490 documents, 54,612 chunks, 136 archive snapshots, 222 authority-graph relations, archive-first migrations, and the successor corpora used by the SoW 06 validation traces.

### Production parity and database gate

1. Record the production database name, schema-migration inventory, effective corpus identifier, document/chunk/snapshot/authority-graph counts, model configuration, and current image/build IDs.
2. Verify production has the archive-first migrations and materialised snapshot/authority data required by the frozen build. Do not treat `init-db.sql` as proof of parity.
3. Take and verify a production database backup before changing services. No ordinary database migration or corpus rematerialisation is planned for this release.
4. If a restore becomes necessary, use a pre-reviewed backup and strict `ON_ERROR_STOP` procedure. First prove it in an isolated validation database; do not use a non-strict in-place restore as a rollback method.

### Deployment and rollback sequence

1. Record the rollback backend image/digest, frontend build, compose revision, production database backup, and pre-deployment health/provenance sample.
2. Build and deploy only the recorded release commit using `deploy-to-droplet.sh`; preserve the production `.env` and do not run `git pull` or an unreviewed production migration.
3. Confirm container health, API reachability, model readiness, effective corpus, and release identifiers before opening the UI smoke checks.
4. On any blocker, stop the release gate and restore the recorded backend image, frontend build, configuration, and service state. Database rollback is not expected because no data migration is planned; use the verified backup only if the database was explicitly changed.

### Production smoke and UI checks

Run these before the researcher begins the full-50 UAT:

- Authority: `MLT-AUTH-07` to confirm exact project lead, funder, duration, and authority provenance.
- Documentary: `MLT-DOC-18` to confirm evidence cards, claim/source bindings, citations, and bounded answer rendering.
- Temporal documentary: `MLT-DOC-15` to confirm application-owned chronological order and no unsupported temporal relation.
- Hybrid: `MLT-HYB-08` to confirm authority/documentary separation and source-bound documentary claims.
- Scoped missingness: `MLT-LIM-01` and `MLT-HYB-10` to confirm an explicit, correctly targeted limit without unsupported direct support.

For every smoke result, inspect grouped source cards, citation navigation, claim IDs, source/authority type labels, evidence limits, and UI rendering. A missing provenance surface, category collapse, wrong-target missingness statement, or authority/documentary contradiction is a blocker.

### Monitoring and preserved identifiers

For the first production observation window, monitor backend/frontend health, container restarts, API error rate, model latency/timeouts, structured-output validation failures, narrative fallback rate, and database connectivity. Preserve a deployment record containing:

```text
release_commit
release_build_id
backend_image_digest
frontend_build_digest
compose_revision
deployment_timestamp_utc
production_database_backup_id
database_schema_migration_inventory
effective_corpus_id
document_chunk_snapshot_authority_counts
model_runtime_and_configuration
smoke_trace_run_ids
smoke_ui_capture_ids
```

Only after the smoke set is accepted may the researcher manually run the full 50-question UAT against this exact recorded build. Do not tune production behaviour during that UAT; preserve each human run ID and UI capture with the release record.

## Pre-conditions

Before starting:

- SoW 00-06 complete.
- Automated test suite green.
- No known critical provenance/capability violation.
- Current build/deployment identifier recorded.
- Baseline CSV retained unchanged as the original diagnostic record.

## UAT method

Manually run all 50 questions through the production-equivalent UI using the same human evaluation approach used for the baseline.

For each case capture:

```text
uat_id
build_id
run_id
actual_answer
actual_documentary_evidence
actual_retrieved_source_stack_and_evidence_chain
human_subjective_comments
uat_pass_fail
critical_violation_type_if_any
```

Do not overwrite `clean_ml_triage_dev_UAT_50_v2.csv`.

Create a new results artefact for this release candidate, for example:

```text
/docs/ml_triage_dev_v2/ml_triage_dev_UAT_50_v3_results.csv
```

The exact version suffix may be changed to match repo conventions.

## PASS decision

Use the existing per-case UAT pass criteria from the baseline CSV.

Do not mark a case PASS solely because the answer is fluent or approximately correct. Provenance, evidential status, required retrieval coverage and prohibited overclaim rules still apply.

## Release thresholds

All must be true:

1. At least 40/50 cases PASS.
2. Overall PASS rate is at least 80%.
3. `MLT-DOC-18` PASS.
4. `MLT-LIM-01` PASS.
5. Zero critical provenance/capability violations.
6. `MLT-HYB-14` returns a complete auditable result.
7. No evidence of UAT-specific memorisation/hard coding.
8. UI provenance remains inspectable for sampled documentary, authority, hybrid and missingness cases.

## Critical release blockers

Any one of these forces release FAIL regardless of pass count:

- fabricated source/testimony attribution;
- authority/documentary category collapse that changes the claim;
- metadata relation presented as authorship/leadership/action without support;
- employment overlap presented as collaboration without documentary support;
- visual claims from unavailable image evidence;
- generated prose contradicting exact displayed authority values;
- missingness statement about the wrong target claim;
- hard-coded UAT-specific production behaviour.

## Required release report

Create a short machine-readable Markdown release report with front matter equivalent to:

```yaml
build_id: <value>
total_cases: 50
pass_count: <value>
fail_count: <value>
pass_rate: <value>
critical_violations: <value>
must_not_regress_doc18: PASS|FAIL
must_not_regress_lim01: PASS|FAIL
hyb14_execution_state: COMPLETE|INCOMPLETE
release_decision: PASS|FAIL
```

Then list:

- failures by question class;
- failures by root-cause family;
- any provenance/capability blocker;
- recommended pre-holdout fixes if release fails.

## Holdout transition rule

If release decision is PASS:

- freeze/tag the remediated first-50 build;
- do not tune further against Questions 1-50 before constructing the holdout unless a critical defect is discovered;
- create Questions 51-100 with new entities, new evidence combinations and harder edge cases;
- use Questions 51-100 to test generalisation rather than memorisation;
- later run the complete 100-question audit as planned.

If release decision is FAIL:

- return only the remaining root-cause families to SoW 06;
- do not weaken pass criteria;
- do not add one-off question-specific answer patches.

## Definition of done

This SoW is complete when all 50 cases have been manually re-run, the release report exists, and a PASS/FAIL decision has been made against the thresholds above.
