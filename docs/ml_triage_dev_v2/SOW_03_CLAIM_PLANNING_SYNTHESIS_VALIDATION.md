---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_03
title: Claim planning, synthesis and claim-level validation
status: human_gate
sequence: 3
depends_on:
  - ML_TRIAGE_V2_SOW_02
primary_uat:
  - MLT-DOC-07
  - MLT-DOC-10
  - MLT-DOC-13
  - MLT-DOC-15
  - MLT-DOC-16
  - MLT-HYB-01
  - MLT-HYB-02
  - MLT-HYB-05
  - MLT-HYB-07
  - MLT-LIM-08
sentinel_uat:
  - MLT-DOC-07
  - MLT-DOC-10
  - MLT-DOC-13
  - MLT-DOC-16
  - MLT-HYB-05
  - MLT-HYB-07
  - MLT-LIM-08
  - MLT-DOC-18
---

# SoW 03 - Claim Planning, Synthesis and Claim-Level Validation

## Objective

Replace chunk-by-chunk paraphrase with argument-level synthesis that is planned from typed evidence and validated at claim level before rendering.

## Problem statement

Several baseline cases retrieve useful evidence but produce:

- repetitive numbered paraphrases;
- one sentence per chunk;
- weak comparison across sources;
- weak chronology/change-over-time articulation;
- generic conclusions disconnected from cited evidence;
- unsupported source attributions;
- `Synthesis unavailable` despite apparently adequate retrieved evidence.

## Required design

### A. Introduce a claim-plan stage

Synthesis should not receive an undifferentiated raw chunk list.

Create a machine-readable plan with fields equivalent to:

```text
question_intent
answer_shape
claims:
  - claim_id
    claim_type
    proposition
    supporting_evidence_ids
    contradicting_or_qualifying_evidence_ids
    evidence_status
    temporal_position_if_relevant
    required_qualification
comparison_axes
open_uncertainties
proposed_scoped_limit
```

The planner may be deterministic, model-assisted or hybrid, but critical evidence admissibility must remain deterministic.

### B. Respect answer shape from UAT/research route

Support general answer shapes such as:

- thematic synthesis;
- compare/contrast;
- temporal change;
- authority fact plus documentary interpretation;
- bounded missingness;
- single-report summary.

Do not make one universal list template the default.

### C. Synthesize across sources, not chunks

The answer should normally group multiple evidence items into a smaller number of historically meaningful propositions.

Desired default for interpretive cases:

- concise opening answer;
- 2-3 coherent evidence-led paragraphs where appropriate;
- explicit comparison/chronology where asked;
- bounded final limitation where required.

Do not force this exact length for authority-only or single-report questions.

### D. Add sentence/claim-local evidence validation

Each factual or interpretive claim must resolve to admissible supporting evidence IDs.

Validation outcomes:

```text
SUPPORTED
SUPPORTED_WITH_QUALIFICATION
CONFLICTING_EVIDENCE
INSUFFICIENT_EVIDENCE
INVALID_EVIDENCE_TYPE
```

Unsupported claims must be removed, rewritten as a scoped limit, or explicitly qualified. They must not survive merely because the model wrote them fluently.

### E. Preserve disagreement and ambiguity

Do not flatten several formulations into one synthetic historical truth if the evidence shows variation.

For temporal/contested cases, explicitly allow:

- change;
- coexistence;
- disagreement;
- ambiguous terminology;
- insufficient evidence of causation.

### F. Repair synthesis fallback behaviour

Investigate cases such as `MLT-DOC-16` where retrieved evidence exists but the final answer collapses to `Synthesis unavailable` or equivalent.

Make fallback typed and informative:

- retrieval coverage unsatisfied;
- evidence validation failed;
- synthesis service/model error;
- no admissible claims after validation.

Do not hide these states behind a generic fallback.

### G. Prevent citation laundering

A citation/evidence marker attached to a sentence does not make the sentence supported unless the evidence actually supports its proposition and is of the right type.

## Out of scope

- Changing source corpus.
- Replacing authority records.
- Visual UI redesign.
- Hard-coded prose for known UAT questions.

## Automated tests

Add tests for:

1. two-source synthesis into one supported proposition;
2. comparison preserving disagreement;
3. chronology without causation overclaim;
4. unsupported claim rejection;
5. wrong evidence-type rejection;
6. sentence-local source traceability;
7. non-generic synthesis fallback states;
8. single-document regression preserving `MLT-DOC-18` behaviour.

## Human-in-the-loop UI sentinel gate

Run:

- `MLT-DOC-07`
- `MLT-DOC-10`
- `MLT-DOC-13`
- `MLT-DOC-16`
- `MLT-HYB-05`
- `MLT-HYB-07`
- `MLT-LIM-08`
- regression: `MLT-DOC-18`

Human checks:

- Does the answer make a small number of coherent propositions rather than paraphrasing each chunk?
- Are comparisons explicit where asked?
- Are temporal differences preserved?
- Does each important sentence resolve to supporting evidence?
- Are unsupported claims removed/qualified rather than hallucinated?
- Are fallback/error states diagnostic rather than opaque?

## Acceptance criteria

Proceed to SoW 04 only when:

- sentinel answers are evidence-led syntheses rather than chunk lists;
- unsupported attributions are blocked by validation;
- `MLT-DOC-18` remains a PASS-quality single-report answer;
- synthesis failure states are typed and traceable.

## Gate Record - 2026-10-01

### Delivered

- Deterministic final claim plans now record question intent, answer shape, local evidence status, qualification/contradiction references, temporal position, comparison axes, uncertainties, and scoped limits.
- Prose realization groups validated propositions into answer-shape-specific argument moves rather than defaulting to one paragraph per source chunk.
- Rendered claims are classified as `SUPPORTED`, `SUPPORTED_WITH_QUALIFICATION`, `CONFLICTING_EVIDENCE`, `INSUFFICIENT_EVIDENCE`, or `INVALID_EVIDENCE_TYPE`; unsupported high-risk assertions are rejected before rendering.
- OCR headings and table fragments are excluded from final claim plans, preventing unreadable source fragments from being rendered as otherwise cited claims.
- Response, query-execution trace, and Source Interrogation UI now expose claim-local statuses and evidence IDs. Unavailable synthesis responses expose typed failure reasons.

### Automated Verification

- Focused claim-plan and rendered-claim tests: passed, including citation laundering, disagreement, temporal qualification, wrong evidence type, and OCR/table-fragment exclusion.
- Full evidence-pipeline suite: 100/101 passed. The sole failure is the previously accepted stale telemetry expectation (`narrative_synthesis`: expected `skipped`, actual `success`).
- Analysis projection suite: 25/30 passed, exactly the five previously accepted stale expectations; no additional failure from this SoW.
- Claim-move tests: 2/2 passed.
- Frontend production build: passed (existing third-party Sass deprecation warnings only).

### Sentinel Evidence

- `MLT-DOC-07`, `MLT-DOC-10`, and `MLT-DOC-13`: `validated_bounded_answer` in `ml-triage-v2-20261001T052459Z-9d723e7c` before the final OCR-fragment admission fix.
- `MLT-DOC-16`: `validated_bounded_answer` in `ml-triage-v2-20261001T053318Z-c6578721`; it now renders two readable, locally supported documentary propositions rather than OCR/table fragments.
- `MLT-HYB-05`, `MLT-HYB-07`, `MLT-LIM-08`, and regression `MLT-DOC-18`: all `validated_bounded_answer` in `ml-triage-v2-20261001T053500Z-87bd3bc0`.

### Live UI Gate

- Verified at `http://localhost:3000/source-interrogation` with the Job 171 question.
- The rendered answer contained the two readable documentary propositions; Model-claim provenance visibly showed `c1` and `c2` as `SUPPORTED` with evidence IDs `ev:5bb18798fdd42c70` and `ev:fde85c497853cfed`.

### Human Approval Required

SoW 03 is complete pending review of the claim-level provenance presentation and sentinel prose. Do not begin SoW 04 without explicit approval.
