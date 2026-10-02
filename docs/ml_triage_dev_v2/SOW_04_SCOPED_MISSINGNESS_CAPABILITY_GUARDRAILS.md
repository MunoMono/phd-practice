---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_04
title: Scoped missingness and capability guardrails
status: accepted
sequence: 4
depends_on:
  - ML_TRIAGE_V2_SOW_03
primary_uat:
  - MLT-LIM-01
  - MLT-LIM-02
  - MLT-LIM-03
  - MLT-LIM-04
  - MLT-LIM-05
  - MLT-LIM-06
  - MLT-LIM-07
  - MLT-LIM-08
sentinel_uat:
  - MLT-LIM-01
  - MLT-LIM-02
  - MLT-LIM-03
  - MLT-LIM-04
  - MLT-LIM-05
  - MLT-LIM-06
  - MLT-LIM-07
  - MLT-LIM-08
---

# SoW 04 - Scoped Missingness and Capability Guardrails

## Objective

Generalise scoped missingness from the working DDR-closure exemplar into a claim-specific mechanism that reports what a bounded searched evidence surface can and cannot establish without claiming historical non-existence.

Also add hard capability gates so the system cannot invent interpretations from media that are not available to the ML pipeline.

## Problem statement

Baseline failures show:

- a closure-specific limitation sentence leaking into unrelated missingness questions;
- missingness being declared before targeted documentary retrieval is exhausted;
- absence of reception evidence being confused with absence of historical reception;
- metadata association being over-read;
- employment overlap being either over-read or used to stop further documentary retrieval;
- visual properties invented from photographs that are not ML-enabled.

## Required design

### A. Create a typed missingness decision object

Minimum conceptual fields:

```text
target_claim
claim_subject
claim_predicate
requested_evidence_type
searched_surfaces
required_surfaces
coverage_status
relevant_evidence_found
counterevidence_or_ambiguity
capability_constraints
missingness_state
bounded_limit_text_inputs
```

### B. Use explicit missingness states

Use deterministic states equivalent to:

- `NOT_YET_ADEQUATELY_SEARCHED`
- `REQUIRED_SURFACE_UNAVAILABLE`
- `NO_SUPPORT_IN_SEARCHED_DIGITISED_CORPUS`
- `EVIDENCE_SUPPORTS_ONLY_WEAKER_CLAIM`
- `CONFLICTING_OR_AMBIGUOUS_EVIDENCE`
- `MEDIA_NOT_ML_ENABLED`
- `SUPPORTED_NO_LIMIT_REQUIRED`

Names may differ to fit the codebase, but the distinctions must survive.

### C. Missingness comes after retrieval adequacy

Never produce a strong scoped-limit conclusion until the retrieval contract has been attempted adequately.

If retrieval was inadequate, say the search was inadequate or a required surface was unavailable. Do not convert retrieval failure into archival absence.

### D. Generate limit text from the current claim

Do not reuse static closure language across unrelated cases.

The final limit must refer to:

- the actual proposition being tested;
- the actual searched corpus/surfaces;
- the evidence status reached.

Example structure, not hard-coded prose:

```text
The searched <bounded evidence surface> does not establish <specific proposition>. This does not show that <historical event/relationship/reception> did not occur; it states only what the current digitised evidence surface can establish under the retrieval conditions used.
```

### E. Distinguish provision from reception

For educational/programme history:

- documents showing a programme was proposed, provided or described do not establish how it was received;
- absence of reception evidence does not establish no reception or impact.

### F. Add media/capability gates

Before synthesis, attach media capability metadata such as:

```text
media_type
text_available
image_pixels_available_to_model
ocr_available
visual_analysis_allowed
```

If image pixels are unavailable to the ML pipeline, block visual claims about:

- posture;
- comfort;
- materials;
- spatial arrangement;
- accessibility;
- appearance;
- other visual properties.

The answer may still state that a photo source family exists if archival metadata supports that claim.

### G. Weaker-claim fallback

Where evidence supports a weaker proposition, answer the weaker proposition explicitly instead of either hallucinating the stronger claim or declaring total absence.

Examples:

- employment overlap -> co-presence in employment records, not collaboration;
- source association -> association in metadata, not authorship;
- project documentation -> project activity/context, not necessarily who initiated it.

## Required regressions

- `MLT-LIM-01` remains PASS-quality and becomes a general regression exemplar, not a special-case branch.
- `MLT-LIM-02`, `03`, `04` must not inherit closure-specific limit language.
- `MLT-LIM-05` must never invent visual description without visual evidence.
- `MLT-LIM-06` must explicitly reject metadata=authorship/leadership.
- `MLT-LIM-07` must search direct documentary evidence before concluding collaboration is unestablished.

## Automated tests

Add tests for:

1. missingness text bound to the current claim;
2. retrieval-inadequate vs no-support distinction;
3. provision vs reception distinction;
4. metadata association weak-claim handling;
5. employment overlap weak-claim handling;
6. no visual claim when image evidence capability is false;
7. regression that closure wording cannot appear for an unrelated target claim unless semantically generated from that claim;
8. `MLT-LIM-01` equivalent generic fixture remains valid.

## Human-in-the-loop UI sentinel gate

Run all eight LIM cases.

Human checks:

- Is the limit about the question actually asked?
- Does it state the bounded evidence surface searched?
- Does it avoid claiming historical non-existence?
- Was targeted retrieval adequate before missingness was declared?
- Are weaker supported claims surfaced?
- Are visual claims blocked when visual evidence is unavailable?

## Acceptance criteria

Proceed to SoW 05 only when:

- all LIM sentinels use claim-specific missingness;
- no closure-template leakage remains;
- no visual hallucination occurs in `MLT-LIM-05`;
- metadata/authority limits are expressed without erasing relevant documentary evidence;
- `MLT-LIM-01` remains PASS-quality.

## Gate Record

### Implementation

- Added the typed `ScopedMissingnessDecision` contract and persisted it through the pipeline, API projection, execution trace, and Source Interrogation UI.
- Scoped limits are generated from the active proposition and bounded current digitised corpus, preserving weaker documentary claims without asserting historical non-existence.
- Text-only media capabilities now declare pixels unavailable and return `MEDIA_NOT_ML_ENABLED` for visual requests; visual descriptions are not inferred from OCR or catalogue text.
- Added focused regressions for retrieval-state distinction, current-claim limits, visual gating, and association-versus-authorship handling.

### Verification

- Final all-LIM run: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20261001T062338Z-52d4a82d/`.
  All eight LIM cases completed as `validated_bounded_answer`.
- LIM-05 returned `MEDIA_NOT_ML_ENABLED`, with no visual or ergonomic description inferred.
- LIM-03 keeps provision distinct from intended-user reception; LIM-06 rejects authority association as authorship or leadership; LIM-07 does not infer collaboration from employment overlap.
- Visible UI gate passed at `http://localhost:3000/source-interrogation`: the visual sentinel displayed the capability-bound answer and the scoped-missingness panel with `MEDIA_NOT_ML_ENABLED` and `ADEQUATE` coverage.
- Pipeline suite: 107/108 passed. The sole failure is the previously accepted stale telemetry expectation (`test_staged_pipeline_records_safe_execution_telemetry`: expected `narrative_synthesis=skipped`, actual `success`).
- `git diff --check` passed.

### Known Limitation

Closed under human approval on 2026-10-01.

- Runtime retrieval adequacy is now derived deterministically from retrieval diagnostics. Standard archive-first retrieval is adequate only when `retrieved_documentary_source_count >= 1`, `retrieval_coverage.coverage_status == "satisfied"`, no required surfaces are missing, and at least one distinct source is recorded.
- Configured-reservation retrieval is adequate only when it explicitly records `configured_reservation_exclusive == true` and at least one retrieved documentary source.
- Missing, malformed, partial, or otherwise indeterminate diagnostics are fail-closed as inadequate; no path defaults adequacy to `True`.
- Focused tests cover satisfied coverage, partial coverage, absent diagnostics, and configured-reservation diagnostics.
- Final diagnostic-derived LIM run: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20261001T063824Z-0a4642c5/`; all eight cases completed as `validated_bounded_answer`.
- Final pipeline suite: 109/110 passed. The sole failure remains the accepted stale telemetry expectation (`test_staged_pipeline_records_safe_execution_telemetry`: expected `narrative_synthesis=skipped`, actual `success`).

**SoW 04 accepted and closed. Do not begin SoW 05 without a new explicit instruction.**
