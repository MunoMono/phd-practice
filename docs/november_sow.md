# November Statement of Work: Generalising Archival Evidence Stress Tests

## Purpose

Turn the Turin evidence-pipeline work into a reusable protocol for archival research questions beyond the current 12-question DDR benchmark. The goal is a fit-for-purpose system that preserves provenance and evidential restraint without embedding Turin-specific assumptions in application code.

## Starting Point

The current implementation already provides reusable foundations:

- archive-first source nomination
- separate archival metadata, documentary evidence, inference, and missingness layers
- source/chunk/quotation provenance validation
- staged source analysis and synthesis
- stress-test dimensions for reconstruction, inference restraint, disagreement, temporal interpretation, causality, origin claims, reception, and sparse evidence

The Turin question set remains valuable as a fixed regression benchmark. It should not become the hidden rule set for later collections.

## Implementation Status (8 September 2026)

- [x] Versioned benchmark-question schema and onboarding documentation: `archival-evidence-benchmark-v1`, configurable evidence layers, temporal boundaries, reservations, missingness, authority context, source selection, and synthesis guards.
- [x] Migration of all 12 Turin question definitions into `turin-v1.json`.
- [x] Configurable evaluation runner with JSON and Markdown matrix output, explicit `--config` selection, collection/corpus report metadata, and unknown-policy rejection.
- [x] Researcher response and export accounting for retained sources, direct claims, final direct claims, classifications, authority evidence, and missingness.
- [x] Bounded non-Turin Harbor fixture configuration covering known relationship, contested interpretation, and scoped missingness; its configured guard and evaluator path are regression-tested.
- [x] Operational guide for configuring, validating, evaluating, deploying, and inspecting another collection.
- [x] Configured oral-history review counters and source-family diversity diagnostics; Q7 and Q9-Q11 production probes preserve documentary/oral-history separation.
- [x] Configured authority-to-controlled-asset coverage audit, including an explicit `CONTROLLED_LINKAGE_UNAVAILABLE` status when snapshot metadata cannot support the audit.
- [x] Focused regression and production validation for the deployed configuration, evidence pipeline, evaluator, fixture, source-family, oral-history, and authority-audit slices.
- [x] Complete retrieval/synthesis generalisation: active Q2-Q12 retrieval and deterministic synthesis use versioned reservations, document-page declarations, and synthesis guards; Q1 remains intentionally generic archive-first. Configured model-stage fallbacks replace the remaining question-wording fallback checks.
- [x] Complete archival-association formalisation: configurable association claims require record scope, controlled fields, source provenance, and a limiting description; the API and researcher interface render them separately from documentary and authority evidence.
- [x] Complete ingestion hardening within available upstream capabilities: snapshot flattening preserves inherited controlled people and aliases, while the authority audit emits `CONTROLLED_LINKAGE_UNAVAILABLE` when the current Archive GraphQL `ItemV1` and `DigitalAsset` schema cannot supply controlled-person or alias fields. This is an external API dependency, not evidence of absent archival linkage.
- [x] Complete evaluator coverage: reports source/asset diversity, final-claim provenance, expected facts and missingness, inference restraint, temporal boundaries, source-family compliance, model-stage fallback, and authority-asset coverage.
- [x] Complete end-to-end regression evidence: the focused Turin/Harbor suite passes, frontend production build passes, and the deployed all-question `turin-v1` smoke report passed all 12 policies on 8 September 2026.

## Evidence From Active Stress Tests

The Q5-Q10 work has made the generalisation boundary concrete:

- Concept-only questions can retrieve relevant documents but still fail if the evidence compiler requires a named person or project. The protocol needs configurable concept anchors, including unquoted research concepts, with explicit term and phrase matching rules.
- Source diversity is a research requirement. Lexical ranking alone can return repeated passages from one record family while excluding a prospectus, report, correspondence, proposal, or interview that supplies a materially different form of evidence.
- Contemporary records and later oral histories must be selected and labelled as different source forms. A later interview may support an attributed retrospective characterisation, but cannot be promoted to contemporaneous institutional fact or post-closure activity.
- Oral histories are not optional background material. Each interrogation must inspect the eligible oral-history corpus as a distinct source family and nominate relevant passages, retaining speaker, interview date, quotation, and any expressed uncertainty as part of the claim.
- A database-authority match must expand to every ML-permitted asset linked through controlled people, role, alias, project, or record fields. That complete linked set is a coverage audit, not an unbounded model prompt: passage selection remains relevance-ranked, provenance-bound, and source-diverse.
- Exact documentary text remains the basis for historical claims. Archive metadata can nominate, identify, date, and associate sources, but must not silently become claim evidence.
- Structured model stages can fail from malformed responses or input-budget limits. When deterministic, provenance-validated direct evidence is available, the system needs a configured fallback rather than returning an empty or model-flattened answer.
- Question matching must normalise typographic quotation marks and equivalent punctuation before applying configured concept or comparison rules. A semantically identical query must not bypass its evidence policy because it uses curly quotation marks.
- A collection can have multiple corpus representations with uneven document coverage. The protocol must declare representation choice or a compatible cross-representation retrieval strategy per question, while retaining stable document, page, chunk, and asset identities for provenance.
- Source reservations must select the documentary clause that supports the claim, rather than an arbitrary first chunk from a page or a title-only extraction. The final source count shown to researchers must describe the actual retained, inspectable source set.
- Scoped-missingness questions still require positive, typed evidence: the protocol must preserve what a programme intended, what an institution recorded, or what a witness retrospectively attributed, while preventing those claims from being converted into evidence of reception, causation, initiation, or a complete role history.
- Administrative authority context must be emitted as a structured response field and rendered separately from documentary evidence. A valid authority record may bound a title or tenure, but it must neither be presented as a quotation nor silently disappear into answer prose.
- The interface and exports must distinguish retained-source count, direct-claim count, and source classifications. Provenance validity alone is insufficient when a selected passage is contextual or not relevant to the final claim.

The current Turin implementation expresses these bounded retrieval and synthesis policies through the versioned benchmark configuration. Collection facts, entity names, relationship expectations, and temporal limits are configuration rather than active application-code conditions; the generic safeguards remain reusable for another collection.

## Scope

### 1. Configurable benchmark protocol

Define a versioned, human-readable question specification. Each question should be able to declare:

- collection and corpus boundaries
- research question and stress-test category
- entity anchors and aliases
- project or record anchors
- permitted evidence layers
- temporal boundaries and retrospective-evidence policy
- prohibited inference classes
- expected missingness and evidential limits
- whether a scoped-missingness answer requires direct boundary evidence, authority context, or both
- optional expected direct facts for regression evaluation

The specification must support a new collection without code changes for named people, projects, or local chronology.

### 2. Generalise current special cases

Replace code paths specific to Turin questions with protocol-driven behaviour:

- `Job <number>` project-record recognition
- named-person and named-pair retrieval diversity
- controlled-keyword and parent-record archival associations
- collection-specific closure or end-date constraints
- deterministic answer controls for typed evidence shapes
- concept-only and competing-formulation retrieval, including unquoted concepts
- temporal source-form diversity, including contemporary records and later retrospective accounts
- oral-history review and authority-to-controlled-asset expansion, with bounded passage selection and auditable coverage counts
- deterministic, provenance-bound fallbacks for model schema or input-budget failures

Retain generic safeguards in code. Move collection facts, entity names, relationship expectations, and temporal limits to configuration.

### 3. Typed archival association evidence

Formalise archival metadata as a first-class evidence type distinct from documentary text and administrative authority context.

An archival-association claim must identify its record, attached-media or asset scope, controlled fields, and source API/snapshot provenance. It may establish catalogue grouping or controlled association, but must not be represented as verbatim documentary content or proof of collaboration, authorship, role, or event unless separately supported by documentary evidence.

### 4. Retrieval and ingestion hardening

Ensure archive snapshots preserve metadata needed for governed retrieval:

- inherit and retain parent record/media controlled terms alongside asset-level terms
- preserve field-level provenance for inherited values
- resolve question entities through database authorities, then enumerate all ML-permitted controlled-linked assets before selecting a bounded, diverse documentary bundle
- inspect eligible oral-history transcripts on every interrogation as a separate retrieval stratum; expose the number checked, nominated, selected, and excluded for relevance
- make named-entity retrieval diverse across source assets rather than consuming the retrieval budget with duplicate passages
- expose retrieval version and source-selection rationale consistently through inspection and interrogation endpoints
- enforce a source-family diversity policy when a configured question requires contrasting document forms
- bound per-source context independently from source-count limits, so evidence selection does not fail solely because a model-stage prompt is too large

### 5. Evaluation harness

Build an evaluation runner that executes configured questions and reports:

- retrieved source and asset diversity
- evidence type and provenance validity
- recovered expected facts
- prohibited or unsupported inferences
- temporal-boundary violations
- stated missingness
- model/schema failures

Results should be exportable as structured JSON and a researcher-readable matrix. The existing Turin Q1-Q12 matrix becomes one generated or reconciled report, not the only evaluation surface.

### 6. Researcher interface

Make the evidence distinctions visible in the interrogation interface:

- documentary passage
- archival metadata association
- authority/administrative context
- inference
- missing or not established

Each visible claim should show its evidence type, source identity, and applicable limit. Interface wording must not flatten typed metadata into documentary proof.

## Deliverables

1. Versioned benchmark-question schema and documentation.
2. Migration of the 12 Turin questions into the schema.
3. Generalised retrieval and synthesis policy implementation.
4. Typed archival-association response contract and UI presentation.
5. Snapshot ingestion regression coverage for parent and asset metadata.
6. Configurable evaluation runner with JSON and matrix outputs.
7. Regression suite covering Turin Q1-Q12 and at least one non-Turin fixture collection.
8. Deployment and operational guide for adding a new archival collection.

## Acceptance Criteria

- A new collection can add a benchmark question through configuration rather than a new question-specific conditional.
- A configured temporal comparison can retrieve contrasting contemporary and retrospective source forms, label them accurately, and prohibit retrospective material from establishing later activity.
- Every interrogation records oral-history coverage, and a relevant interview passage cannot be excluded solely because an institutional record scored first.
- A resolved authority produces an auditable controlled-asset coverage set before the final source budget is applied.
- A configured concept-only question can retain direct text evidence without requiring a named person or project anchor.
- Every answer distinguishes documentary evidence from archival metadata and authority context.
- A scoped-missingness answer preserves its supporting source-specific claims while explicitly withholding the broader claim that the evidence cannot establish.
- Administrative authority context is present in the structured API response and researcher interface, with its record identifier, source, field values, and non-documentary status.
- All direct documentary claims have valid source, chunk, page, and quotation provenance.
- Evaluation reports retained sources, final direct claims, and their classifications separately, so a provenance pass cannot conceal irrelevant or contextual retrieval.
- Collection-specific temporal rules are declared by configuration and enforced in generated output.
- Named-pair questions retrieve a deliberately diverse source set where the collection metadata supports it.
- The evaluation report identifies unsupported inference, missingness, source duplication, and provenance failure.
- Turin Q1-Q12 retain their current evidence boundaries as regression cases.

## Out of Scope

- Claiming that metadata alone proves historical events or interpersonal collaboration.
- Reprocessing unrestricted external collections without confirmed rights and ML-use policy.
- Replacing scholarly interpretation with automated truth determination.
- Expanding the Turin research-question set before the protocol is generalised.

## Indicative Sequence

1. Agree the schema and evidence-type vocabulary.
2. Migrate Turin question definitions and remove question-specific conditions.
3. Generalise ingestion and retrieval selection.
4. Implement the evaluator and regression fixtures.
5. Update the researcher interface and deployment documentation.
6. Validate with Turin and one additional bounded collection.