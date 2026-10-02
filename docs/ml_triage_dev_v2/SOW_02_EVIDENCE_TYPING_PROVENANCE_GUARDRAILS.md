---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_02
title: Evidence typing and provenance guardrails
status: human_gate
sequence: 2
depends_on:
  - ML_TRIAGE_V2_SOW_01
primary_uat:
  - MLT-DOC-11
  - MLT-DOC-12
  - MLT-DOC-16
  - MLT-HYB-01
  - MLT-HYB-02
  - MLT-HYB-03
  - MLT-HYB-04
  - MLT-HYB-05
  - MLT-HYB-06
  - MLT-HYB-07
  - MLT-HYB-08
  - MLT-HYB-09
  - MLT-HYB-10
  - MLT-HYB-11
  - MLT-HYB-12
  - MLT-HYB-13
  - MLT-HYB-14
  - MLT-LIM-04
  - MLT-LIM-06
  - MLT-LIM-07
sentinel_uat:
  - MLT-DOC-11
  - MLT-HYB-04
  - MLT-HYB-05
  - MLT-HYB-08
  - MLT-HYB-09
  - MLT-HYB-11
  - MLT-LIM-06
  - MLT-LIM-07
---

# SoW 02 - Evidence Typing and Provenance Guardrails

## Objective

Make evidence class a hard part of the inference pipeline so the model cannot silently convert database authority, archival metadata, documentary text and retrospective testimony into one undifferentiated evidence pool.

## Problem statement

Baseline failures show category collapse, including:

- documentary statements attributed to database authority;
- teaching text described as oral-history testimony when no interview was retrieved;
- employment overlap treated as collaboration;
- metadata/source association treated as authorship, leadership or action;
- report front-matter roles and controlled project authority treated as automatically equivalent;
- generated prose contradicting authority values displayed in the same answer.

These are provenance failures, not merely writing-quality failures.

## Required design

### A. Create a typed evidence ledger

Before synthesis, normalise selected evidence into a ledger. Minimum conceptual fields:

```text
evidence_id
evidence_type
source_pid_or_authority_key
source_title
source_date
collection_or_preset
chunk_id_or_record_id
exact_span_or_structured_value
subject_entities
project_entities
relation_type_if_any
relation_derivation_if_any
contemporary_or_retrospective
media_type
ml_capabilities
retrieval_contract_reference
```

Do not invent missing metadata. Null is preferable to fabricated certainty.

### B. Enforce evidence types

Minimum evidence types:

- `DATABASE_AUTHORITY`
- `ARCHIVAL_METADATA`
- `DIRECT_DOCUMENTARY`
- `RETROSPECTIVE_TESTIMONY`

`QUALIFIED_SYNTHESIS` and `SCOPED_LIMIT` are output statuses, not substitutes for source evidence.

### C. Add an admissibility matrix

Create deterministic rules that govern which evidence type may support which claim class.

At minimum:

| Claim class | Admissible direct support | Not sufficient alone |
|---|---|---|
| employment role/dates | DATABASE_AUTHORITY | documentary mention, metadata association |
| project lead/funder/duration authority field | DATABASE_AUTHORITY | generic report text unless explicitly stated as a separate documentary claim |
| what a document says | DIRECT_DOCUMENTARY | DATABASE_AUTHORITY, ARCHIVAL_METADATA |
| what an interviewee later recalled | RETROSPECTIVE_TESTIMONY | contemporary document, metadata |
| authorship/leadership/activity | explicit documentary or exact authority field where defined | `PERSON_ASSOCIATED_WITH_SOURCE`, keyword metadata |
| collaboration | explicit documentary relationship evidence | overlapping employment dates |
| intent/causation | explicit evidence supporting intent/causation | sequence, co-occurrence, metadata association |

### D. Preserve relation derivation

For graph/metadata relations, retain how the relation was derived, for example:

```text
relation_type: PERSON_ASSOCIATED_WITH_SOURCE
relation_derivation: keyword_metadata
```

The UI and validator must be able to distinguish this from documentary authorship or action.

### E. Separate report roles from authority roles

Do not automatically map these fields onto each other:

- controlled `project_lead`;
- report author;
- group leader;
- head of department;
- main researcher;
- funder.

If two typed sources differ, preserve both with labels and dates rather than forcing reconciliation.

### F. Add evidence-consistency validation

Before final rendering:

- authority claims must match the structured authority values used;
- oral-history attributions require testimony evidence in the ledger;
- documentary attributions require the named document in the ledger;
- metadata-derived associations must not be rendered as direct action without additional support.

If validation fails, remove, qualify or block the unsupported claim. Do not replace it with a guessed fact.

## Key UAT risks to eliminate

- `MLT-DOC-11` / `MLT-DOC-12`: fabricated testimony attribution when the interview surface is absent.
- `MLT-HYB-08`: prose contradicting displayed Job 171 authority.
- `MLT-HYB-09` / `MLT-HYB-11`: conflating project authority with report front-matter roles.
- `MLT-LIM-06`: treating source-person metadata association as authorship/leadership.
- `MLT-LIM-07`: treating employment overlap as proof of collaboration.

## Out of scope

- Large-scale prose/style improvements.
- Final UI visual design.
- New corpus ingestion.
- Case-specific source whitelists.

## Automated tests

Add tests that fail if:

1. a testimony claim is generated without testimony evidence;
2. a documentary claim cites a database authority record as its textual source;
3. `PERSON_ASSOCIATED_WITH_SOURCE` alone is used to assert authorship;
4. employment overlap alone is used to assert collaboration;
5. generated project authority values differ from the structured authority values supplied;
6. report roles are silently overwritten by project authority fields;
7. an evidence item loses its derivation/type before synthesis.

## Human-in-the-loop UI sentinel gate

Run:

- `MLT-DOC-11`
- `MLT-HYB-04`
- `MLT-HYB-05`
- `MLT-HYB-08`
- `MLT-HYB-09`
- `MLT-HYB-11`
- `MLT-LIM-06`
- `MLT-LIM-07`

Human checks:

- Can each important sentence be traced to the correct evidence type?
- Are authority values visibly distinct from documentary claims?
- Are testimony and contemporary documents visibly distinct?
- Are derived metadata relations labelled as derived relations?
- If sources disagree or use different role vocabularies, does the answer preserve the difference rather than collapse it?

## Acceptance criteria

Proceed to SoW 03 only when:

- no sentinel contains a cross-type attribution error;
- no sentinel contradicts its displayed authority record;
- metadata association and employment overlap are explicitly prevented from proving stronger claims on their own;
- evidence types survive from retrieval to final rendering trace.

## Implementation and gate record

Completed 30 September 2026.

### Implemented

- Added a typed evidence ledger covering database authority, archival metadata, direct documentary evidence and retrospective testimony.
- Preserved relation type, relation derivation, temporal class and source identity through API, trace and UI projection.
- Added deterministic claim admissibility and post-realisation guards for evidence labels, authorship, leadership, funding and collaboration.
- Kept controlled project authority roles separate from report authorship, principal-investigator, project-team and departmental roles.
- Merged route-resolved authority records into the durable evidence ledger and execution trace.
- Rendered hybrid authority claims deterministically from structured values and retained validated documentary claim-plan text when generated prose was rejected.
- Added visible evidence types, separate authority/documentary/testimony sections and a typed evidence ledger to Source Interrogation.

### Automated validation

- Evidence pipeline: 96 tests; one documented pre-existing stale telemetry expectation remains (`narrative_synthesis` expected `skipped`, runtime records `success`).
- Analysis projection: 30 tests; five documented pre-existing stale expectations remain (three old answer-state expectations, one old source-number expectation and one old repairable-coverage state expectation).
- Focused authority registry, authority graph, trace harness and frontend Playwright checks passed during implementation.
- Frontend production build passed; only existing Carbon Sass deprecation warnings were emitted.
- Changed-file diagnostics and `git diff --check` passed.

The six broader-suite stale expectations above are non-blocking pre-existing issues. They were not repaired because SoW 02 did not require changing those expectations.

### Sentinel evidence

Final run: `artifacts/ml_triage_dev_v2/uat_runs/ml-triage-v2-20260930T140855Z-47140e32/`

- All eight required sentinels completed as `validated_bounded_answer`.
- `MLT-DOC-11` remained direct documentary evidence and did not invent testimony.
- `MLT-HYB-04` retained database authority, documentary and retrospective-testimony types separately.
- `MLT-HYB-05` displayed exact employment authorities without inferring collaboration.
- `MLT-HYB-08` displayed Pierre Goumain and the Science Research Council exactly, separately from cited Job 171 report text.
- `MLT-HYB-09` kept Craig Johnson and the Science Research Council authority separate from the four-report documentary surface.
- `MLT-HYB-11` kept Andrew Garnett and the Consortium for METHOD building authority separate from report feasibility statements.
- `MLT-LIM-06` explicitly rejected authority-source association as proof of authorship or leadership.
- `MLT-LIM-07` explicitly rejected employment overlap as proof of collaboration.

### Live UI check

Source Interrogation was exercised against the final backend with the `MLT-HYB-08` question. The rendered UI showed:

- a distinct Database authority answer naming Pierre Goumain and the Science Research Council;
- a separate Documentary evidence section with four Job 171 propositions;
- a Typed evidence ledger containing four `DIRECT_DOCUMENTARY` rows and one `DATABASE_AUTHORITY` row;
- evidence type on each retained source card;
- no contradictory or cross-type authority prose.

### Gate state

The SoW 02 implementation satisfies the stated sentinel criteria and is now stopped at the human-in-the-loop approval gate. SoW 03 must not begin without explicit approval.
