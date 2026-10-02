---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_01
title: Retrieval contracts, source diversity and scope control
status: ready
sequence: 1
depends_on:
  - ML_TRIAGE_V2_SOW_00
primary_uat:
  - MLT-DOC-01
  - MLT-DOC-02
  - MLT-DOC-03
  - MLT-DOC-04
  - MLT-DOC-05
  - MLT-DOC-06
  - MLT-DOC-08
  - MLT-DOC-09
  - MLT-DOC-11
  - MLT-DOC-12
  - MLT-DOC-14
  - MLT-DOC-15
  - MLT-DOC-17
  - MLT-HYB-03
  - MLT-HYB-04
  - MLT-HYB-10
  - MLT-HYB-12
  - MLT-HYB-13
sentinel_uat:
  - MLT-DOC-01
  - MLT-DOC-05
  - MLT-DOC-09
  - MLT-DOC-11
  - MLT-DOC-14
  - MLT-HYB-03
  - MLT-HYB-10
  - MLT-HYB-13
  - MLT-DOC-18
---

# SoW 01 - Retrieval Contracts, Source Diversity and Scope Control

## Objective

Replace best-effort top-chunk retrieval with bounded retrieval contracts that enforce the evidence surfaces, subject/project scope, temporal coverage and source diversity required by each question class.

The purpose is not to force known UAT sources. The purpose is to make the retrieval system able to satisfy equivalent unseen questions using general rules.

## Problem statement

The current system frequently allows one long relevant document to occupy most or all of the top-k source stack. It also treats source presets/evidence families as optional hints. This causes:

- duplicate-title source stacks;
- missing required oral histories, prospectuses or project reports;
- weak temporal coverage;
- project leakage from unrelated jobs;
- false missingness after an inadequate search;
- synthesis from an evidence surface that cannot satisfy the question.

## Required design

### A. Introduce a retrieval contract

Create or extend a typed retrieval contract. Reuse existing structures where possible.

Minimum conceptual fields:

```text
retrieval_mode
required_evidence_types
required_source_presets
preferred_source_presets
required_authority_types
entity_anchors
project_anchors
collection_anchors
temporal_requirement
temporal_buckets
minimum_distinct_sources
minimum_sources_per_required_surface
initial_max_chunks_per_source
allow_cross_preset_backfill
allow_scoped_limit_if_coverage_unmet
```

The contract must be derived from question intent/classification and configured research routes, not from UAT IDs.

### B. Make required presets binding

If a route says a source family is required, the system must either:

1. retrieve evidence from that family; or
2. explicitly mark the required surface as unsatisfied.

Do not silently proceed as if an absent required evidence family were present.

Examples of general rules:

- retrospective-vs-contemporary comparison requires both testimony and contemporary documentary surfaces;
- prospectus-history questions require prospectus coverage;
- project-specific questions require the target project/job surface;
- person-specific teaching questions must keep the named person/entity as an anchor;
- period-change questions require evidence from more than one temporal bucket.

### C. Retrieve candidates first, diversify second

Keep the current approved retrieval technology unless there is a demonstrated defect requiring a change. Do not change embedding models or corpus contents in this SoW.

Use a two-stage pattern:

```text
bounded candidate retrieval
  -> group by source asset/PID
  -> rank within source
  -> source-level diversification
  -> satisfy required surfaces/buckets
  -> select final evidence chunks
```

Do not let a single document exhaust the final evidence stack before coverage requirements are considered.

### D. Add a configurable per-source chunk cap

Introduce an initial cap such as 1-2 chunks per source while satisfying source diversity, then allow additional chunks from a source only after minimum coverage is met.

Do not hard-code one global cap if some single-report questions legitimately need multiple chunks. The retrieval contract must allow single-document mode.

Regression example:

- `MLT-DOC-18` is legitimately a single-report question and must not be degraded by forced diversity.

### E. Add temporal coverage logic

For questions asking about change across time, require at least two date/period buckets where the corpus/preset contains candidates.

Do not infer causation from chronological sequence.

Relevant UAT exemplars include:

- Archer formulations across decades;
- DEU early vs later accounts;
- prospectus/rector-report institutional change;
- DDR periodisation comparisons.

### F. Add strict project/job scoping

When a question targets one or more job numbers/projects:

- prioritise exact project authority and source preset constraints;
- reject unrelated project/job documents from the final evidence stack unless explicitly needed for a comparative question;
- log any cross-project backfill.

This must address leakage such as Job 181 questions retrieving Jobs 170/97/146/171.

### G. Add coverage status

Before synthesis, produce machine-readable coverage status:

```text
coverage_status: satisfied | partially_satisfied | unsatisfied
required_surfaces_found
required_surfaces_missing
distinct_source_count
temporal_buckets_found
target_entity_evidence_found
target_project_evidence_found
```

Synthesis must be able to consume this status in later SoWs.

## Specific regression expectations from the baseline CSV

These are tests of general rules, not production source whitelists.

- Teaching synthesis should not collapse to repeated George Mallen chunks when broader teaching presets contain relevant evidence.
- Bruce Archer across-time questions should not be answered from a single paper when multiple dated Archer sources are available.
- Oral-history comparison questions must not claim testimony if the testimony surface is missing.
- Prospectus questions must visibly include prospectus evidence or report the required surface unsatisfied.
- Target-job questions must not be polluted by unrelated jobs.
- Patrick Purcell computing questions must remain anchored on Purcell and computing evidence rather than generic Mallen material.

## Out of scope

- Rewriting synthesis prose.
- Designing final missingness language.
- Authority/documentary reconciliation in prose.
- UI visual redesign beyond exposing retrieval coverage needed for UAT.

## Automated tests

Add tests for at least:

1. multi-source teaching retrieval;
2. single-document exemption;
3. two-surface comparison coverage;
4. temporal bucket coverage;
5. exact project/job scoping;
6. target-person anchor preservation;
7. required-surface failure reporting;
8. duplicate-source suppression before coverage is met.

Tests must use synthetic or non-UAT-specific fixtures where practical.

## Human-in-the-loop UI sentinel gate

Run:

- `MLT-DOC-01`
- `MLT-DOC-05`
- `MLT-DOC-09`
- `MLT-DOC-11`
- `MLT-DOC-14`
- `MLT-HYB-03`
- `MLT-HYB-10`
- `MLT-HYB-13`
- regression: `MLT-DOC-18`

Human checks:

- Are required presets actually represented?
- Is the source stack diverse when the question requires diversity?
- Are source dates sufficient for temporal questions?
- Are unrelated project/job sources absent?
- If a required surface is not found, is that visible before synthesis?
- Does the single-report regression still work?

## Acceptance criteria

Proceed to SoW 02 only when:

- sentinel retrieval stacks satisfy their intended evidence surfaces or explicitly report unsatisfied coverage;
- no unrelated-job contamination remains in the project-scoped sentinels;
- source diversification does not break `MLT-DOC-18`;
- the current corpus and authority data remain unchanged;
- no UAT-specific production branching has been introduced.

## Implementation and gate status

SoW 01 implementation and acceptance validation are complete. Retrieval now derives an immutable question contract, selects bounded candidates before deterministic source/time diversification, applies strict Job scope, preserves explicit single-report retrieval, and exposes pre-synthesis coverage through the endpoint response, execution trace, and Source Interrogation UI.

The final affected-sentinel rerun produced four validated bounded answers in `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20260930T104948Z-1b92198d/`:

- `MLT-DOC-14` excludes the out-of-range 2013 testimony and spans the 1960s, 1970s and 1980s within its explicit 1965-85 contract.
- `MLT-HYB-03` finds the Patrick Purcell entity anchor after bounded cross-preset backfill.
- `MLT-HYB-10` resolves to the exact surviving Job 181 report in single-document mode, with no unrelated-job contamination.
- `MLT-HYB-13` includes prospectus and documentary surfaces across 1965-85, using RCA calendars and Rector's reports.

Earlier live sentinel artefacts are retained under `artifacts/ml_triage_dev_v2/uat_runs/`. They establish multi-source and temporal coverage for `MLT-DOC-01`, `MLT-DOC-05`, `MLT-DOC-09` and `MLT-DOC-11`, and preserve `MLT-DOC-18` as a satisfied one-report/eight-passage regression.

The real UI gate submitted `MLT-HYB-10` through `http://localhost:3000/source-interrogation`. The rendered result showed satisfied retrieval coverage, `documentary` and `project_report` as found evidence surfaces, target-project evidence found, and the Job 181 report source stack.

Automated gate results:

```text
12 retrieval-contract tests passed
25 archive-first retrieval service tests passed
16 contract, trace-harness and anti-overfitting tests passed
3 Source Interrogation Playwright tests passed
frontend production build passed
```

No corpus, embedding, synthesis-prose or authority-data changes were made. The SoW 01 acceptance criteria pass, so progression to SoW 02 is permitted.
