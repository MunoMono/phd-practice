---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_05
title: Authority answers, hybrid reconciliation and provenance UI
status: accepted
sequence: 5
depends_on:
  - ML_TRIAGE_V2_SOW_04
primary_uat:
  - MLT-AUTH-01
  - MLT-AUTH-02
  - MLT-AUTH-03
  - MLT-AUTH-04
  - MLT-AUTH-05
  - MLT-AUTH-06
  - MLT-AUTH-07
  - MLT-AUTH-08
  - MLT-AUTH-09
  - MLT-AUTH-10
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
sentinel_uat:
  - MLT-AUTH-01
  - MLT-AUTH-06
  - MLT-AUTH-09
  - MLT-AUTH-10
  - MLT-HYB-05
  - MLT-HYB-08
  - MLT-HYB-09
  - MLT-HYB-11
  - MLT-HYB-14
---

# SoW 05 - Authority Answers, Hybrid Reconciliation and Provenance UI

## Objective

Make deterministic authority answers readable without weakening their evidential status, and make hybrid answers visibly separate database authority, archival metadata, documentary text, testimony and synthesis.

The researcher must be able to inspect provenance in the UI without reverse-engineering raw chunks.

## Problem statement

Baseline failures show two related issues:

1. Authority-only answers may contain correct controlled values but render too crudely to meet the intended answer experience.
2. Hybrid answers allow authority and documentary evidence to collapse into each other or become visually ambiguous.

Source provenance is also too repetitive, for example multiple identical cards titled only `Rector's report` with no date/PID distinction.

## Required design

### A. Authority-only answer renderer

Keep authority-only routes deterministic.

Do not add documentary retrieval merely to make the prose more fluent.

Render a concise natural-language answer from the structured authority fields, followed by visible provenance and an evidential boundary where useful.

Conceptual pattern:

```text
According to the controlled <authority_type> authority, <entity> is recorded as <value(s)>.

Authority provenance: <authority_type> | <authority_key>
Boundary: this establishes the controlled authority value only; it does not by itself establish documentary activity/intent/authorship where those are separate questions.
```

Use only boundaries relevant to the query. Do not add boilerplate mechanically to every answer.

### B. Authority completeness and ordering

Fix deterministic scope issues including:

- period authority queries return the requested eight periods in coherent chronological/hierarchical order;
- methodology authority queries return the requested methodology entries only, unless the user asks for the complete registry;
- project authority fields remain exact.

### C. Hybrid evidence blocks

For hybrid answers, keep evidence types visibly separate in both data and UI.

Minimum presentation semantics:

- Authority facts.
- Documentary evidence.
- Retrospective testimony where present.
- Metadata-derived relationships where present.
- Qualified synthesis.
- Scoped limit where needed.

Do not imply these are equal kinds of evidence.

### D. Source-level provenance grouping

Group repeated chunks under the source asset rather than rendering every chunk as an independent source card.

Each source header should expose, where available:

```text
source title
source date
PID/asset identifier
evidence type
collection/preset
number of retrieved chunks
```

Allow expansion to chunk-level passages for auditability.

Example target rendering:

```text
Rector's report | December 1972 | PID 613671017198 | DIRECT_DOCUMENTARY
  3 retrieved passages
```

Do not fabricate dates or identifiers that are absent in metadata.

### E. Claim-to-evidence inspection

Where feasible in the current UI architecture, allow the researcher to inspect which source/evidence item supports a claim.

At minimum, clicking or expanding a citation/source should reveal:

- evidence type;
- source title/date/PID;
- supporting passage or structured authority value;
- relation derivation for metadata relationships.

### F. Conflict/reconciliation rendering

When controlled authority and documentary front matter use different role labels, present the distinction.

Do not silently choose a winner.

Example conceptual output:

```text
Project authority: project_lead = X
Report front matter: group_leader = Y; report_author = Z
```

Then allow synthesis to explain that these fields represent different documentary/authority categories unless evidence shows equivalence.

### G. Human-in-the-loop visual guardrails

Add clear evidence-type labels/badges using the existing design system. Do not rely on colour alone.

The UI must make it difficult to mistake:

- authority value for documentary quotation;
- metadata relation for authorship;
- retrospective testimony for contemporary evidence;
- synthesis for source text.

## Out of scope

- New archival ingestion.
- Rewriting all application navigation.
- UAT-specific answer templates.
- Changing authority data to agree with documentary text.

## Automated tests

Add tests for:

1. authority-only answers use only authority data;
2. requested period count/order;
3. requested methodology scope;
4. hybrid response data retains separate evidence classes;
5. repeated chunks group under a single source asset;
6. title/date/PID/evidence type render when available;
7. conflicts between authority and report roles are preserved, not overwritten;
8. blank/failed hybrid execution cannot render as an apparently successful empty answer.

## Human-in-the-loop UI sentinel gate

Run:

- `MLT-AUTH-01`
- `MLT-AUTH-06`
- `MLT-AUTH-09`
- `MLT-AUTH-10`
- `MLT-HYB-05`
- `MLT-HYB-08`
- `MLT-HYB-09`
- `MLT-HYB-11`
- `MLT-HYB-14`

Human checks:

- Are authority values exact and readable?
- Is provenance visible without opening developer tools?
- Are repeated document chunks grouped under one source?
- Are title/date/PID/evidence type available where metadata exists?
- Can authority and documentary roles be distinguished at a glance?
- Does `MLT-HYB-14` produce a complete auditable state?

## Acceptance criteria

Proceed to SoW 06 only when:

- all authority-only sentinels preserve deterministic authority provenance;
- hybrid sentinels do not collapse evidence classes;
- source stacks are source-oriented rather than duplicate-chunk-oriented;
- conflicting role vocabularies remain visible and traceable;
- the researcher can inspect provenance through the UI.

## Human gate evidence

### Authority validation

- `MLT-AUTH-01` through `MLT-AUTH-10` completed successfully.
- Authority provenance is deterministic and authority-type boundaries are explicit.
- Authority-only responses render correctly with zero documentary sources.

### Hybrid validation

- `MLT-HYB-01` through `MLT-HYB-14` completed as `validated_bounded_answer`.
- Authority and documentary evidence roles remain distinct; reconciliation does not silently resolve evidential conflicts.
- Grouped documentary passages remain inspectable.

### MLT-HYB-04 diagnosis

The apparent stall was a harness-observability issue, not a backend stall. The
`narrative_synthesis` stage took approximately 40.7 seconds and the complete
HTTP 200 response took approximately 64.42 seconds. The harness emits no
per-case progress or trace until request completion.

The bounded diagnostic artifact is
`artifacts/ml_triage_dev_v2/diagnostics/mlt-hyb-04/summary.json`. It records
successful retrieval, eight retrieved sources, `JANETDALEY` authority lookup,
reconciliation, synthesis, grouping/provenance state, and serialization.

### SoW 05 defects fixed

- Successful hybrid responses now return `source_groups`, allowing grouped passages to reach the UI.
- Citation targets use unique `#grouped-source-N` anchors, avoiding collisions with legacy source-card anchors.
- Focused backend regression coverage was added for successful hybrid source-group projection.

### UI audit

The hybrid browser audit passed: Janet Daley authority context, reconciliation,
and grouped provenance render; a claim citation resolves to exactly one visible,
open grouped passage.

### Regression and engineering validation

- Frozen SoW 04 guardrails: 4/4 pass.
- Frontend production build: pass.
- Touched-file diagnostics: clean.
- `git diff --check`: pass.

### Known non-blocking conditions

1. Temporary 180-second diagnostic bounds for `MLT-HYB-05` and `MLT-HYB-06`
  timed out while disconnected server requests continued. Both passed with the
  canonical 900-second timeout.
2. An existing, unrelated provenance-order baseline failure remains in the
  broader analysis test file.
3. Existing Carbon Sass deprecation warnings remain during frontend production
  builds.

## Human review checklist

- [ ] Authority-only readability: exact controlled values, deterministic provenance, and explicit boundaries.
- [ ] Authority/documentary role distinction: evidence types remain visibly separate.
- [ ] Hybrid conflict preservation: differing role labels remain unresolved unless evidence supports equivalence.
- [ ] Grouped provenance visibility: asset-level metadata and passages are inspectable.
- [ ] Claim-to-evidence navigation: citations resolve to one visible grouped passage.
- [ ] Failed/bounded synthesis auditability: retrieved provenance remains available with bounded outcomes.
- [ ] SoW 04 regression preservation: frozen guardrails remain passing.
- [ ] Known non-blocking conditions reviewed and accepted for this gate.

Feature implementation is frozen pending human review. Do not change this SoW
to `accepted` without explicit human approval, and do not begin SoW 06.

## Acceptance record

Human approval was recorded on 2026-10-01. SoW 05 is accepted and closed.
Its implementation and acceptance evidence are frozen; subsequent remediation
must proceed under SoW 06 without reopening this scope.
