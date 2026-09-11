# Analysis Workbench Connected UAT Statement of Work

**Version:** 0.1

**Date:** 11 September 2026

**Status:** Active UAT and remediation specification

## Purpose

Validate and complete the connected researcher workflow across Source Interrogation, Absences, Cross-readings, and Semantic Atlas. The workbenches must preserve durable identifiers and researcher-controlled state while keeping retrieval, testimony, visual patterns, and missingness distinct from historical findings.

## Core Method Rule

A retrieval result, testimony, visual pattern, missing record, cluster, or no-match can start an investigation. None alone establishes a historical finding.

The interface must distinguish direct documentary evidence, cautious cross-source inference, testimony or retrospective material, computational or retrieval limitation, and what remains unestablished. It must never silently convert a system condition into a historical claim.

## Workstream 1: Source Interrogation Session

### Required behaviour

- Preserve the active query, submitted settings, answer, citations, source stack, source/document/chunk IDs, classifications, provenance, and retrieval trail across Analysis-route navigation.
- Retain the active result until a researcher submits another query or selects **Clear current research**.
- Editing an input without submission must not alter the active completed result.
- Keep a previous result visible while a replacement query is loading where practical.

### Acceptance checks

1. Source Interrogation -> Absences -> Semantic Atlas -> Cross-readings -> Source Interrogation retains the exact active result.
2. Browser refresh restores the active same-tab research session.
3. A submitted Query B replaces Query A only after Query B is intentionally run.
4. Clear removes query, answer, sources, citations, and retrieval state; that clear state survives navigation.

## Workstream 2: Scoped Missingness

### Required data

Every persisted `MissingnessEvent` must retain event ID, typology, source run, query/entity/field, scoped evidence note, document and chunk identifiers where relevant, status, reviewer note, follow-up action, and timestamps.

### Safety requirements

- Support `documentary`, `descriptive`, `retrieval`, `institutional`, `historiographic`, and `computational` typologies.
- Record only what the current corpus, selected records, retrieval configuration, or embedded surface did not establish.
- Never generate automatic language that a thing did not happen, did not exist, has no historical evidence, or proves historical silence.
- Keep real query-linked events visibly distinct from development seeds.

### Source Interrogation handoff

- Provide an explicit researcher action for zero-result and weak-result runs.
- Persist the actual source run and retained source stack before creating the event.
- Default to `retrieval`; allow review to change typology, status, note, and follow-up action.
- The reception UAT query must create a scoped event even when several relevant sources are returned but intended-user reception is not established.

## Workstream 3: Cross-readings

### Required behaviour

- Treat attributable testimony as a situated probe, not transparent fact.
- Retain passage label/text, speaker/source, source type, date, access status, durable reference, memory-position note, and status.
- Run saved testimony as a retrieval probe and preserve candidate document/chunk provenance.
- Require researcher assignment of `convergence`, `contradiction`, `complication`, `contextual relation`, or `no_documentary_trace`, with a reviewer note.
- Do not infer confirmation from similarity or falsehood from no documentary trace.
- A `no_documentary_trace` mapping can create a scoped Absences event retaining testimony, probe, source-run, and corpus context.
- Export testimony-mapping provenance, relation, scope, and review data.

## Workstream 4: Semantic Atlas

### Required behaviour

- Present UMAP as a hypothesis-generation surface only: proximity is not equivalence, causation, collaboration, authorship, historical relationship, or archive completeness.
- Expose readiness and coverage: documents, extracted text, embedded items, image-only/no-asset records, failed embeddings, exclusions, and warnings.
- Support chunk and document point modes, inspection of durable IDs/provenance, filters, and filter reset without mutating source evidence.
- Source cards can locate represented items in the Atlas while retaining the Source Interrogation session.
- Atlas selection can seed a new Source Interrogation question; its answer, not UMAP proximity, determines support.
- A known unrepresented source can create a scoped `computational` Absences event. This must refer to embedding/text coverage, never archival absence.
- Atlas exports retain point, document, chunk, corpus, embedding, and projection identifiers.

## Connected UAT Flows

| Flow | Pass condition |
| --- | --- |
| A. Evidence trail | A cited source opens in Atlas; returning retains Source Interrogation; a researcher may run a new sharpened question. |
| B. Weak retrieval | The Design in General Education reception query records a real retrieval event with source-run provenance and scoped language. |
| C. Zero retrieval | A no-match query records a real query-linked retrieval event, not a seed row. |
| D. Testimony convergence | A researcher-created convergence mapping persists testimony and archival provenance. |
| E. Testimony qualification | Contradiction and complication remain researcher annotations, not factual adjudications. |
| F. No documentary trace | A no-trace mapping hands off a scoped event without calling testimony false. |
| G. Atlas coverage gap | A non-embedded known source creates a scoped computational event, not an archival-absence claim. |

## Required Negative Tests

- Zero retrieval and weak retrieval are not historical absence.
- Metadata co-occurrence is not collaboration.
- UMAP proximity is not a historical relationship.
- Testimony is not transparent fact.
- No documentary trace is not false testimony.
- Image-only or non-embedded is not absent from the archive.
- Navigation is not a state reset.

## Delivery Phases

1. Establish baseline and run existing focused tests for all four workbenches.
2. Complete Cross-readings persistence, relation, no-trace, export, and Absences handoff gaps.
3. Complete Atlas coverage, point inspection, filtering, and inter-workbench handoff gaps.
4. Run focused browser/API tests and the seven connected UAT flows.
5. Deploy only verified changes, apply migrations explicitly, and record production UAT results.

## Current Start State

- Source Interrogation session persistence is implemented with same-tab browser session storage, explicit clear, and browser regression coverage.
- Source Interrogation to Absences handoff persists real query-run/source provenance, scoped evidence, review fields, and follow-up action. Researchers can revise typology, status, note, and follow-up action without changing underlying evidence.
- Cross-readings passage/probe/mapping persistence, no-trace Absences nomination, and exports are implemented. Researcher-facing relation labels use the connected-UAT vocabulary while legacy annotations remain valid. No-trace nominations now retain mapping/probe identifiers, source document/chunk arrays, scoped safety wording, and a follow-up action; exports retain memory-position notes and mapping update time.
- Semantic Atlas has a server-verified computational-missingness handoff for known sources not represented by the current projection. Its advertised colour modes now control the UMAP renderer, with a neutral fallback for unavailable numeric metadata.
- Focused browser coverage now passes against a fresh local Vite server for Source Interrogation session retention, Atlas computational-coverage handoff, Cross-readings blank-passage protection, and persisted no-trace annotation/Absences nomination. The previous Atlas test failure was isolated to a stale port-3000 server that did not have the checkout's resolved `recharts` dependency.
- Remaining execution work: run the researcher-led connected UAT flows A-G against production records and capture their results.

## Acceptance Gate

Release only when every implemented handoff preserves stable IDs (`run_id`, `document_id`, `chunk_id`, `testimony_id`, `missingness_event_id`) and all outputs preserve the core method rule.