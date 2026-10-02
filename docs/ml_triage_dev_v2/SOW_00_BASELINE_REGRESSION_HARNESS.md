---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_00
title: Baseline regression harness and anti-overfitting controls
status: ready
sequence: 0
depends_on: []
input_csv: /docs/ml_triage_dev_v2/clean_ml_triage_dev_UAT_50_v2.csv
must_not_regress:
  - MLT-DOC-18
  - MLT-LIM-01
sentinel_uat:
  - MLT-DOC-18
  - MLT-LIM-01
  - MLT-DOC-01
  - MLT-DOC-11
  - MLT-HYB-08
  - MLT-LIM-05
---

# SoW 00 - Baseline Regression Harness and Anti-Overfitting Controls

## Objective

Create the instrumentation, regression fixtures and guardrails required to remediate the first 50 UAT cases safely. This SoW must not intentionally change answer behaviour.

## Inputs

- `/docs/ml_triage_dev_v2/clean_ml_triage_dev_UAT_50_v2.csv`
- Existing ML triage routes, retrieval code, authority lookups, synthesis code and UI.
- Existing tests.

## Required baseline

The harness must record:

- 50 total cases.
- 2 current PASS: `MLT-DOC-18`, `MLT-LIM-01`.
- 47 current explicit FAIL.
- 1 unresolved blank: `MLT-HYB-14`.

Treat the blank case as operationally unresolved, not as a PASS.

## Scope

### A. Create a deterministic UAT trace model

For every query/run, capture a machine-readable trace containing, where available:

```text
run_id
uat_id_or_external_test_id
question_text
question_classification
retrieval_mode
resolved_presets
authority_lookups
entity_anchors
project_anchors
temporal_constraints
candidate_sources
candidate_chunks
selected_sources
selected_chunks
evidence_type_per_item
source_pid
source_title
source_date
chunk_id
relation_derivation_if_any
claim_plan
model_input_evidence_ids
raw_model_output
validated_claims
rejected_or_qualified_claims
scoped_limit_state
final_answer
ui_source_stack
errors
latency/timing where already available
```

Do not force fields that do not exist yet. Add them incrementally without fabricating values.

### B. Persist run artefacts outside production data

Create a development artefact location such as:

```text
/artifacts/ml_triage_dev_v2/uat_runs/<run_id>/
```

Do not write UAT traces into archival source data or authority tables.

### C. Freeze regression exemplars

Create automated regression coverage for:

- `MLT-DOC-18`: single-document hospital bedstead case.
- `MLT-LIM-01`: DDR closure scoped-missingness case.

The purpose is to preserve behaviour while generalising the architecture.

### D. Add anti-overfitting tests

Add a static/test-time guard that searches production code/config/prompts for:

- literal `MLT-DOC-`, `MLT-AUTH-`, `MLT-HYB-`, `MLT-LIM-` branching;
- complete UAT question strings;
- direct use of `graham_newman_subjective_comments`;
- direct use of `uat_pass_fail` in production inference;
- hard-coded expected answer prose copied from the CSV.

UAT IDs may appear in tests, fixtures, documentation and test runners. They must not drive production answer logic.

### E. Add execution failure visibility

`MLT-HYB-14` is currently blank. Ensure all query executions terminate in a visible, logged state:

- success;
- validated bounded answer;
- scoped limit;
- explicit synthesis/validation error;
- retrieval coverage error.

A silent blank result is not acceptable.

## Out of scope

- Retrieval tuning.
- Prompt redesign.
- Evidence-type rule changes.
- UI redesign other than minimal trace visibility required to debug.
- Changing UAT expected answers or pass criteria.

## Implementation constraints

- Do not change the corpus.
- Do not change authority values.
- Do not alter the baseline CSV.
- Do not make case-specific answer fixes in this SoW.

## Automated acceptance criteria

1. A test runner can execute or replay all 50 UAT inputs without relying on the PASS/FAIL column for inference.
2. Every run produces a trace artefact or a typed execution error.
3. `MLT-DOC-18` and `MLT-LIM-01` remain behaviourally intact.
4. Anti-overfitting checks fail if UAT IDs or complete literal UAT questions are introduced into production branching logic.
5. Existing production tests pass.

## Human-in-the-loop UI sentinel gate

Manually run:

- `MLT-DOC-18`
- `MLT-LIM-01`
- `MLT-DOC-01`
- `MLT-DOC-11`
- `MLT-HYB-08`
- `MLT-LIM-05`

For each sentinel, confirm that the debugging trace can answer:

- Which route ran?
- Which presets/surfaces were searched?
- Which authority lookups ran?
- Which sources/chunks were selected?
- What evidence type was assigned?
- What reached synthesis?
- What validation/fallback ran?

Do not proceed to SoW 01 until the trace is sufficient to diagnose a failure without guessing.

## Definition of done

This SoW is complete when the system has a reliable baseline, auditable per-query traces and anti-overfitting checks, while preserving the current two PASS cases.

## Implementation status

SoW 00 implementation and trace-sufficiency validation are complete. The six sentinels were run against a production-equivalent local stack using the verified corpus `corpus_turin_targeted_5b176946674f`, and `MLT-LIM-01` was also submitted through the actual UI. The UI rendered the bounded answer, dated source cards, retrieval diagnostics, evidential limits and claim/source provenance.

The SoW 00 trace-sufficiency gate passed, so progression to SoW 01 is permitted. The sentinel run also recorded release-critical defects: `MLT-DOC-11` attributes claims to an unselected 2013 oral-history source, `MLT-HYB-08` contradicts displayed project authority, and `MLT-LIM-05` invents visual and ergonomic properties without photograph evidence. Those defects remain blockers for final programme acceptance and are assigned to their owning remediation SoWs; they do not invalidate SoW 00's completed trace gate.

Live gate artefacts:

- `MLT-DOC-18`: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20260930T094737Z-9203cf04/`
- `MLT-DOC-01`: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20260930T094917Z-9146a5a8/`
- `MLT-DOC-11`, `MLT-HYB-08`, `MLT-LIM-01` and `MLT-LIM-05`: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20260930T095654Z-d37dc9d8/`
- Consolidated assessment: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20260930T095654Z-d37dc9d8/SENTINEL_GATE.md`

Implemented components:

- `backend/app/services/query_execution_trace.py` projects endpoint responses into `query-execution-trace-v1` records with typed terminal outcomes.
- `backend/scripts/run_ml_triage_dev_v2.py` executes or replays all 50 cases without sending evaluation columns to inference.
- Run artefacts are written to `artifacts/ml_triage_dev_v2/uat_runs/<run_id>/`, with one trace per case and an incrementally updated manifest.
- `backend/tests/test_ml_triage_dev_v2_harness.py` freezes the 50-case baseline and the `MLT-DOC-18` and `MLT-LIM-01` trace contracts.
- `backend/tests/test_ml_triage_anti_overfitting.py` scans live production surfaces for UAT identifiers, evaluator-only fields, complete UAT questions and copied answer prose.
- Canonical UAT manifest matching and expected-asset nomination have been removed from production inference.

Run the automated gate from `backend/`:

```bash
python3 -m unittest tests.test_ml_triage_dev_v2_harness tests.test_ml_triage_anti_overfitting
```

Run all 50 cases against a live local backend:

```bash
python3 scripts/run_ml_triage_dev_v2.py --base-url http://127.0.0.1:8000
```

Run the six UI sentinels through the same endpoint before manual UI inspection:

```bash
python3 scripts/run_ml_triage_dev_v2.py \
  --base-url http://127.0.0.1:8000 \
  --case MLT-DOC-18 --case MLT-LIM-01 --case MLT-DOC-01 \
  --case MLT-DOC-11 --case MLT-HYB-08 --case MLT-LIM-05
```
