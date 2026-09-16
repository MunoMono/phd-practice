# Source Integration, Absences, Cross-readings and Semantic Atlas Statement of Work

**Project:** Testamentary Traces research instrument

**Research phase:** PhD visual and comparative analytical workstream

**Version:** 0.1

**Date:** 10 September 2026

**Status:** Active implementation and research-validation specification

## 1. Purpose

Activate three complementary, researcher-led analytical capabilities for the RCA Department of Design Research (DDR) corpus:

1. **Absences**: a structured record of scoped retrieval, description, access, registry, institutional, and computational limits.
2. **Cross-readings**: a structured comparison between attributable testimony and selected archival records.
3. **Semantic Atlas**: a reproducible visual projection of embedded archival passages or documents, used to formulate reading questions rather than establish historical claims.

This work extends the research instrument beyond the completed Turin archival-evidence benchmark. It does not amend the Turin retrieval contract, rewrite frozen experiment records, or treat computational similarity as historical proof.

The operational outcome is a researcher-facing Source interrogation workflow in which a document-grounded question produces clear, source-bound prose in the Answer view, with inspectable retrieval and claim provenance. Absences, Cross-readings, and Semantic Atlas must then provide rigorously typed, source-reopenable records of limits, comparative annotations, and visual reading hypotheses without collapsing any of them into historical fact.

## 2. Research Rationale

The DDR archive is heterogeneous. Catalogue records, documents, oral histories, researcher observations, and generated analytical outputs are different kinds of trace. Comparative and visual tools can make relationships and tensions more legible, but they also create specific risks: testimony may be flattened into fact; a retrieval ranking may be mistaken for corroboration; a visual cluster may be named as an historical group; or an unavailable computational surface may be mistaken for archival absence.

The workstream therefore treats both capabilities as apparatuses for disciplined inquiry:

- Absences retain the evidence, source/run references, typology, reviewer assessment, and resolution state that define a limitation's scope.
- Cross-readings retain the testimony passage, archival candidate, retrieval run, provenance, and researcher relation annotation as separate records.
- The Semantic Atlas retains its corpus version, embedding model, vector-generation configuration, projection configuration, filter state, point identities, and interpretative warnings.
- Neither capability promotes a relation, cluster, outlier, or empty result into a documentary claim without separate source-based review.

## 3. Existing Baseline

The following capabilities already exist and are to be extended rather than replaced.

### 3.1 Cross-readings

- `cross_read_passages` persists passage text, speaker/source, label, source type, memory-position note, status, and audit timestamps.
- `cross_read_mappings` persists candidate document/chunk mappings, relation annotation, reviewer note, provenance, citation, retrieval-run identity, and audit timestamps.
- `POST /api/cross-read/passages/{passage_id}/run` creates a bounded, retrieval-only PostgreSQL FTS probe and persists its `QueryRun` and mappings.
- The existing relation vocabulary is `supports`, `complicates`, `contradicts`, and `no_documentary_trace`.
- CSV and Markdown testimony-to-record map exports already exist.
- The active corpus has no persisted cross-read testimony passages. The empty state is currently an honest capability/readiness state, not a software failure.

### 3.2 Absences

- `MissingnessEvent` persists the missingness type, bounded question/entity/field, evidence, linked run/document/chunk where available, review status, note, and audit timestamps.
- `GET /api/missingness/summary` distinguishes metadata coverage, local chunk representation, entity-registry availability, and persisted institutional events.
- `GET`, `POST`, and `PATCH /api/missingness/events` provide filtered event retrieval and researcher review state; a query-run route can create a retrieval-missingness event from a failed or partial run.
- The existing interface supports typology filtering, exports, event selection, reviewer notes, and status updates. These record conditions in the available system and corpus; they do not establish historical absence.

### 3.3 Semantic Atlas

- `GET /api/viz/umap` accepts chunk or document points and supports year, theme, source-type, and output filters.
- The endpoint consumes persisted vectors, calculates two-dimensional coordinates, falls back to PCA only when UMAP is unavailable, and returns point identities, source metadata, scope counts, and interpretative warnings.
- The active corpus currently has no embedded chunks, documents with embeddings, projection candidates, or points. The atlas must therefore remain visibly inactive until a governed embedding run is complete.
- Current atlas empty states and source-interrogation handoff behavior are valid only while the corpus has no projection candidates.

## 4. Governing Constraints

The following are non-negotiable acceptance constraints.

1. PostgreSQL FTS remains the principal retrieval method for the Turin evidence pipeline. Embedding similarity must not silently replace or expand its source selection.
2. A testimony passage, archival document, catalogue metadata association, database authority assertion, researcher annotation, and generated inference remain separately typed and visibly labelled.
3. No retrieved result, missing result, point, proximity, cluster, or outlier establishes historical presence, absence, relationship, consensus, causation, authorship, role, or chronology on its own.
4. Existing corpus identifiers, page scope, rights/access controls, source provenance, and immutable research-run records must be retained.
5. No seed testimony, synthetic document passage, mock embedding, fake cluster, or invented mapping may be created to demonstrate a feature.
6. All data-transforming jobs must be versioned, idempotent, resumable, observable, and capable of reporting partial failure without overwriting a prior successful output.
7. Model, embedding, and projection configurations must be exportable with enough detail for a researcher to reproduce the same analytical surface from the same corpus release.
8. Researcher annotations are interpretations and must retain author, timestamp, status, and relation to the source records they discuss.
9. Any use of oral-history material must respect rights, consent, access restrictions, and the distinction between speaker attribution and documentary verification.
10. Production activation occurs only after machine validation and researcher acceptance against a written UAT dataset.

## 5. Scope

### 5.1 In Scope

- Provenance-governed ingestion or researcher creation of attributable cross-reading passages.
- Source-integrated creation, review, export, and navigation of scoped missingness events.
- Passage validation, review workflow, retrieval-only candidate nomination, researcher annotation, and durable exports.
- Corpus inventory and readiness checks for embedding eligibility.
- Deterministic, versioned embedding generation for approved text-bearing corpus material.
- Reproducible two-dimensional projection, cluster-summary computation, filter semantics, point inspection, and exports.
- Explicit handoffs among Sources, Source interrogation, Cross-readings, and Semantic Atlas that preserve identifiers and never hard-code a particular PID or chunk.
- Automated tests, operational runbooks, UAT scripts, and implementation closeout records.

### 5.2 Out of Scope

- Replacing the Turin FTS retrieval path with vector search.
- Training a historical classifier, fine-tuning a language model, or generating autonomous historical conclusions.
- Claiming that semantic proximity establishes intellectual influence, collaboration, chronology, or causation.
- General public publication of restricted testimony or archive material.
- Ingesting material without a recorded rights/access basis.
- Treating an empty result as an archival absence finding.

## 6. Workstream A: Absences

### 6.1 Research Question

How can the instrument record what a defined corpus, description layer, access condition, registry, retrieval process, or computational surface does not currently establish without converting that limit into a claim that the historical event or person was absent?

### 6.2 Functional Requirements

1. Every event must state a controlled typology, bounded subject, inspectable evidence, status, and creation time.
2. Where an event derives from a source, retrieval, interrogation, mapping, or atlas surface, it must carry stable run, document, chunk, corpus, projection, or embedding identifiers as applicable.
3. A manually created event must identify its evidence basis and whether it is researcher-observed, system-derived, or imported from a governed source process.
4. Summary cards must label coverage measures precisely and distinguish local database coverage from frozen-corpus coverage, historical completeness, and archival completeness.
5. Review status and notes are researcher assessment. Editing them must preserve event evidence and audit history.
6. A retrieval zero-result must remain scoped to its recorded query, corpus, date, source-selection configuration, and access state.
7. Atlas and embedding unavailability must be recordable as computational missingness, distinct from absent archival content.
8. Cross-reading `no_documentary_trace` mappings may nominate a linked retrieval missingness event, but no event is created automatically without a researcher confirmation step.
9. Exports include event type, evidence, all available source/run references, reviewer status, notes, dates, and the interpretative limitation.

### 6.3 Absences Acceptance Criteria

- The event table, selection state, reviewer note, status update, filter, and export load and persist without changing the underlying evidence.
- A source-interrogation run can create a scoped retrieval event only when it is recorded as failed or partial; the UI explains why a complete run cannot be reclassified in this way.
- A representative source, cross-reading, and atlas handoff preserves the available identifiers and names any unavailable prerequisite clearly.
- Summary wording does not imply corpus completeness, historical absence, or entity absence when a local registry/table is unavailable.
- API, persistence, accessibility, export, and browser regression checks pass, followed by researcher UAT.

## 7. Workstream B: Cross-readings

### 7.1 Research Question

How can situated oral testimony and archival records be compared so that agreement, tension, and lack of documentary trace remain inspectable rather than collapsed into a single historical account?

### 7.2 Data Contract

Every persisted passage must contain:

- immutable `passage_id`;
- full passage text or a permitted reference to a controlled text store;
- source type and speaker/source attribution;
- provenance source, source date where known, access/rights status, and ingestion/creation method;
- a bounded contextual locator such as interview identifier, transcript location, page, timecode, or researcher field-note reference;
- a memory-position note where appropriate, explicitly identified as researcher interpretation;
- review status and timestamps;
- a corpus version or source-set identifier when the passage is linked to a particular corpus release.

Existing fields may be extended through a migration, but no existing passage or mapping may be silently reinterpreted.

### 7.3 Functional Requirements

1. Researchers can create a draft passage only when required provenance, attribution, and access fields are present.
2. Ingested passages retain a source-import record distinct from any subsequent researcher edits.
3. A passage can move through `draft`, `reviewing`, `mapped`, `unresolved`, and an explicit non-public/restricted state where required.
4. Running a passage creates a new immutable retrieval-only run with query expansion, corpus version, retrieval configuration, ranked candidates, and zero-result state.
5. The system never assigns a relation automatically. Candidate mappings begin as unreviewed until a researcher selects a relation.
6. Every mapping displays the passage, archival chunk/document identity, page range, citation/provenance status, source excerpt, retrieval score, reviewer, relation, and note.
7. A mapping relation is one of:
   - `supports`: bounded documentary support for a specific portion of the passage;
   - `complicates`: material that qualifies, narrows, contextualises, or otherwise makes the passage less straightforward;
   - `contradicts`: a direct, inspectable conflict that must identify the conflicting propositions;
   - `no_documentary_trace`: no relevant candidate was returned from the defined corpus and retrieval configuration. It is a retrieval/corpus statement, not historical absence.
8. Exports include all relation annotations, unresolved cases, source and corpus identity, timestamps, and sufficient provenance to reopen the relevant record.
9. The interface distinguishes candidates returned by retrieval from researcher-confirmed mappings.
10. The interface supports revision without deleting the original retrieval run or prior interpretation history.

### 7.4 Acceptance Dataset

Before production activation, create a small, rights-cleared researcher-curated validation set with at least:

- two attributable testimony passages with documentary support;
- two passages with material that complicates the testimony;
- one defensible direct contradiction, if present in the corpus;
- two passages with no documentary trace under a recorded corpus and query configuration;
- one restricted or unavailable passage used only to test access-state handling, without exposing content.

The dataset is a validation instrument, not a representative historical sample. Each expected relation must be reviewed and signed off by the researcher before it is encoded as test expectation.

### 7.5 Cross-readings Acceptance Criteria

- A blank passage cannot be persisted, and a missing required provenance field produces a clear, non-destructive error.
- The selected passage, its field values, and all persisted mappings reload after refresh.
- A probe persists a unique run and retains the exact ranked candidate set used at that time.
- A zero-result probe creates a visible `no_documentary_trace` record that states its corpus/retrieval scope.
- Changing an annotation preserves audit history and does not alter the candidate evidence or original retrieval run.
- CSV and Markdown exports match the stored map and include provenance/access status.
- A representative handoff from a source or interrogation trace opens the correct Cross-readings context without fixed IDs.
- Automated API, persistence, and browser tests pass; the researcher completes the matching UAT rows in a new UAT version.

## 8. Workstream C: Semantic Atlas

### 8.1 Research Question

How can a versioned visual projection of the available DDR evidence surface help a researcher identify candidate comparisons while clearly delimiting what the projection does and does not show?

### 8.2 Readiness Gate

No embedding or projection job begins until a documented readiness review confirms:

- a named corpus release with inventory counts and stable document/chunk IDs;
- an approved text-bearing source set, page scopes, and rights/access policy;
- recorded exclusions and their reasons;
- a chosen embedding model, model revision or checksum, vector dimension, runtime, and licensing assessment;
- an approved normalisation/chunking input version;
- available compute/storage capacity and a rollback/retention plan;
- a plan to keep vectors and visual projection separate from FTS evidence selection;
- a researcher-approved analytical question for the first projection.

Failure of any item keeps the atlas inactive and exposes the readiness state without claiming evidence is absent.

### 8.3 Embedding Pipeline Requirements

1. Generate embeddings only for approved, text-bearing chunks or documents with stable identifiers.
2. Persist embedding model identifier, revision/checksum, dimensions, normalisation, input text version, timestamp, job ID, corpus release, and success/failure state for every vector.
3. Make the job idempotent by keying outputs to corpus release, point identity, text fingerprint, and embedding configuration.
4. On resume, process only missing or invalidated vectors; never overwrite a prior valid vector without preserving a versioned replacement record.
5. Record exclusions, empty text, extraction failures, rights restrictions, and model/job failures as readiness diagnostics.
6. Validate vector dimension, finite values, duplicate point IDs, corpus membership, and representative provenance links before projection.
7. Publish coverage counts: eligible, excluded, attempted, embedded, failed, and represented documents/PIDs.

### 8.4 Projection and Cluster Requirements

1. Projection input is a named immutable embedding set.
2. Persist the projection algorithm, library/version, random seed, all parameters, input point count, input ordering/fingerprint, generated timestamp, and failure state.
3. UMAP is the preferred exploratory method; a PCA fallback is permitted only when explicitly marked in the response, interface, and export.
4. Re-running an identical input/configuration must reproduce coordinates within a documented numerical tolerance, or the implementation must record why exact reproduction is not possible.
5. Cluster labels are computational summaries, not historical categories. Any cluster method, parameters, label-generation rule, and quality diagnostic must be recorded.
6. Filters change visible points only; they must not recompute an unrecorded projection or alter source metadata.
7. Every point opens source identity, document/chunk ID, PID, page/section where available, excerpt, provenance status, embedding set, projection ID, and caveats.
8. Empty, sparse, unavailable, and failed states identify the technical condition and scope. They never imply a historical absence.
9. Atlas exports contain filter state, point identities, corpus release, embedding/projection configuration, warnings, and generated time.

### 8.5 Semantic Atlas Acceptance Criteria

- The current corpus remains in its truthful zero-point state until the readiness gate and embedding pipeline succeed.
- A valid embedded test corpus produces points with stable identities and source detail links.
- The point count equals the validated projection input after documented filters/exclusions.
- A filter for year, source type, or theme changes only the declared visible set and is represented in exports.
- A handoff from Sources or Source interrogation locates a matching point when it is in the active projection; otherwise it names the missing technical/data condition and preserves the originating trace context.
- The interface visibly differentiates evidence metadata, visual hypothesis, and any researcher cluster note.
- Projection/export records can be regenerated from the documented corpus and configuration.
- Automated API, data-validation, and browser tests pass; the researcher completes the matching UAT rows in a new UAT version.

## 9. Integration Boundaries

| Boundary | Required behaviour | Prohibited behaviour |
|---|---|---|
| Sources and source interrogation to Absences | Create or open a scoped event with stable source/run/corpus references and the limiting evidence. | Treating an event as a finding of historical nonexistence. |
| Sources to Cross-readings | Pass stable document, PID, chunk, page, and provenance references. | Creating a testimony claim from source metadata. |
| Source interrogation to Semantic Atlas | Pass run, document, chunk, PID, and corpus identifiers; restore the interrogation trace on Back. | Treating a nearby point as supporting the generated answer. |
| Cross-readings and Semantic Atlas to Absences | Permit researcher-confirmed nomination of a scoped limitation with the originating mapping/projection identity. | Automatically converting no match, no point, or no embedding into historical absence. |
| Cross-readings to Claims and evidence | Allow a researcher to nominate a reviewed mapping for claim review with its relation and caveat. | Auto-creating a supported claim from a mapping. |
| Semantic Atlas to Claims and evidence | Allow a researcher to open a point's documentary source for reading. | Exporting a cluster membership as claim evidence. |
| Atlas to Turin retrieval | Keep visual analytics separate from FTS retrieval selection. | Silent vector augmentation or ranking substitution. |

## 10. Delivery Plan

### Phase 0: Research and Data Governance

- Confirm intended research questions, source permissions, testimony protocol, and researcher roles.
- Produce a data dictionary, provenance/access vocabulary, retention policy, and acceptance dataset register.
- Record the active corpus baseline and no-embedding state.

### Phase 1: Absences Source Integration

- Define source/run/mapping/projection reference rules and distinction between system-derived and researcher-created events.
- Verify summary-card semantics, event handoffs, reviewer audit history, and exports.
- Add API, persistence, export, and browser tests, then conduct researcher UAT.

### Phase 2: Cross-readings Activation

- Extend migration/schema only where the data contract requires it.
- Implement provenance/access validation, audit history, candidate-versus-reviewed mapping states, and bounded validation dataset ingestion.
- Add API, persistence, export, and browser tests.
- Run researcher UAT and produce a closeout record.

### Phase 3: Embedding Readiness and Pipeline

- Complete the readiness review and select a documented embedding implementation.
- Run embedding generation on the approved corpus release.
- Validate coverage, vector integrity, exclusions, and resource use.
- Publish an embedding-run manifest and rollback instructions.

### Phase 4: Atlas Activation

- Persist versioned projections and cluster summaries.
- Complete source-detail, filter, handoff, empty-state, and export behavior.
- Add reproducibility tests and a visual/browser regression suite.
- Run researcher UAT and produce a closeout record.

### Phase 5: Comparative Research Evaluation

- Use the approved validation dataset to assess whether Cross-readings preserves distinctions among support, complication, contradiction, and no documentary trace.
- Use documented atlas sessions to assess whether visual exploration produces useful, source-reopenable reading questions.
- Record failures, unexpected clusters, unresolved mappings, and methodological limitations as research findings, not defects to be hidden.

## 11. Quality and Evaluation Measures

The implementation report must include:

- corpus and rights/access coverage counts;
- cross-reading passage, probe, candidate, reviewed-mapping, and unresolved counts;
- annotation agreement or documented researcher-review procedure;
- embedding eligibility, success, exclusion, and failure counts;
- projection input/output counts, model/configuration fingerprints, and reproduction outcome;
- handoff success rate for representative identifiers;
- API, persistence, frontend build, and browser test results;
- accessibility review for keyboard operation, labels, errors, and non-colour-only status communication;
- performance/resource observations for ingestion, embedding, projection, and interactive filtering;
- a register of limitations, including all cases where source material, permissions, embeddings, or projections are unavailable.

## 12. Deliverables

1. Approved data dictionary and governance checklist.
2. Absences source-integration and review workflow, with migration and regression coverage.
3. Cross-readings provenance and review workflow, with migration and regression coverage.
4. Curated, rights-cleared validation dataset register and researcher sign-off record.
5. Versioned embedding-run manifest, integrity report, and operational runbook.
6. Versioned projection records, export schema, reproducibility report, and atlas interaction tests.
7. Updated researcher-facing guide for all three workstreams.
8. UAT v0.2-or-later results and implementation closeout, preserving prior UAT evidence unchanged.
9. A research-method appendix explaining what the scoped-limit, comparative, and visual outputs may and may not be used to claim.

## 13. Definition of Done

This SoW is complete only when:

- all governing constraints are demonstrably met;
- absence events can be traced from their scoped condition through source/run/mapping/projection references and researcher review to export;
- cross-reading data can be traced from attributable passage through retrieval run and researcher annotation to export;
- the atlas is either activated from a versioned, validated embedding set or remains explicitly deferred with a documented unmet readiness gate;
- every active point and mapping can reopen its underlying source context;
- no workflow conflates computational output, testimony, metadata, authority context, and documentary evidence;
- automated validation and researcher UAT pass for the released scope;
- deployment, runbook, limitations, and reproducibility records are available to future researchers.

## 14. Decision Log Required Before Implementation

Before Phase 1 or Phase 2 begins, the researcher must approve and record:

1. The missingness-event provenance and handoff protocol.
2. The testimony source and consent/access protocol.
3. The first validation dataset and reviewers.
4. The embedding model, execution environment, licensing, and resource budget.
5. The corpus release and inclusion/exclusion policy.
6. The projection method, seed, parameter-selection procedure, and repeatability tolerance.
7. The process by which a scoped limit, visual, or comparative observation becomes a candidate for documentary review rather than an asserted finding.

Without these decisions, Absences remains limited to its current scoped-event workflow, Cross-readings may remain in a provenance-preserving draft state, and Semantic Atlas must remain visibly inactive.

## 15. Draft Document-Grounded Model Evaluation Register

This 26-question register uses a random sample of distinct `eligible_unrestricted` records from `backend/authoritative-turin-ingestion-manifest.json`, plus one researcher-nominated corpus record. It tests whether a model answers from the named source, keeps source forms distinct, and gives a bounded limitation where the document does not establish the requested point. It is an evaluation draft: before execution, the researcher must verify each source title, PID, page/chunk locator, access state, and expected boundary against the active corpus release. A passing answer must name or link the inspected record and must not add facts beyond the stated boundary.

| ID | Specific document or record | Evaluation question | Pass boundary |
|---|---|---|---|
| DG01 | `doc_338541406157_72774d03522b`, PID `338541406157`: Bruce Archer Fig. 5 taxonomy transparency | What categories or relationships are shown in Archer's Fig. 5 taxonomy diagram? | Describes only legible diagram labels and relations, and says when the diagram alone is insufficient. |
| DG02 | `doc_287080879712_f1d3b8ea4fcc`, PID `287080879712`: Ken Baynes letter concerning DEU appointments | What appointment matter does Ken Baynes discuss in this August 1984 letter? | Attributes the account to the letter and does not infer a final appointment outcome unless explicitly recorded. |
| DG03 | `doc_546216480663_d30d6979348e`, PID `546216480663`: Job 170 report `108.4` | What aspect of the Design Analysis project is addressed in Job 170 report `108.4`? | Uses the report's own wording and does not generalise to the whole project. |
| DG04 | `doc_404613335296_abe79cd10b57`, PID `404613335296`: *Biography* | Whose biography is this April 1970 document, and what biographical facts does it explicitly record? | Names only the subject and facts visible in the document. |
| DG05 | `doc_338541406157_1cb3d7b8e15f`, PID `338541406157`: Archer, *An introduction to design research* | How does Archer introduce or define design research in this February 1976 paper? | Attributes each formulation to this paper, without claiming it represents all DDR views. |
| DG06 | `doc_546216480663_d284c46b5001`, PID `546216480663`: Job 170 report `108.2` | What problem, method, or result is documented in Job 170 report `108.2`? | Identifies only direct evidence from this June 1973 report. |
| DG07 | `doc_940221533316_403ace0e8414`, PID `940221533316`: design game for layout decisions | How does this design game propose that playing cards are used in modelling layout decisions? | Describes the method as documented; does not claim it was deployed or effective without explicit evidence. |
| DG08 | `doc_287080879712_1f266fad7f24`, PID `287080879712`: Design Dimension advisory papers | What role or decisions are recorded for the Design Dimension project advisory group? | Keeps proposals, advice, and final decisions distinct. |
| DG09 | `doc_287080879712_e68aa903d7c8`, PID `287080879712`: curriculum report outline | What scope or structure is proposed in the March 1984 curriculum report outline? | Reports the outline's stated scope and does not treat it as an implemented curriculum. |
| DG10 | `doc_287080879712_c776e78a6d5b`, PID `287080879712`: Design Dimension aims, methods and content | What aims, methods, or content does this Design Dimension paper identify? | Separates each direct statement from any broader interpretation. |
| DG11 | `doc_546216480663_37a7e8b448e6`, PID `546216480663`: Job 170 report `108.3` | What does Job 170 report `108.3` record about the Design Analysis project? | Limits the answer to this December 1973 report and names the source. |
| DG12 | `doc_512813169945_c4c92a4138cc`, PID `512813169945`: *The management of design* course report | What course content, participants, or aims are recorded in *The management of design* course report? | Does not infer attendance, learning outcomes, or later impact unless the report states them. |
| DG13 | `doc_767973606400_989abba82642`, PID `767973606400`: Job 97 report `97.4` | What feasibility question does Job 97 report `97.4` address? | States the document's stated feasibility scope only; no claim that a system was built. |
| DG14 | `doc_338541406157_fde8dc3a316d`, PID `338541406157`: secondary education working-party minutes | What issues, attendees, actions, or unresolved matters are recorded in these confidential working-party minutes? | Treats minutes as a bounded meeting record, not evidence of institutional consensus or policy adoption. |
| DG15 | `doc_321843234637_b514872d126c`, PID `321843234637`: *Computers in design* course notes | What concepts, examples, or teaching activities appear in the March 1976 *Computers in design* course notes? | Attributes content to the notes and does not infer a complete course or student response. |
| DG16 | `doc_338541406157_3c95cfa4ad23`, PID `338541406157`: ICI paper on learning curves, entropy and cybernetics | How are learning curves, entropy, or cybernetics used in this ICI business-modelling paper? | Gives a source-specific account and does not claim ICI adopted the approach. |
| DG17 | `doc_930287260339_cf797b8d4ce2`, PID `930287260339`: Christopher Frayling interview | What does Christopher Frayling say about the topic asked in this June 2013 interview? | Labels all statements as later oral testimony and preserves qualifications or uncertainty. |
| DG18 | `doc_338541406157_ba2e3cef8801`, PID `338541406157`: Archer, *How designers design* | What account of design practice is presented in Archer's *How designers design* paper? | Attributes the account to Archer and does not treat it as a universal model. |
| DG19 | `doc_287080879712_7061158bd9df`, PID `287080879712`: Design Dimension heads of agreement | Which participating institutions, commitments, or governance arrangements are set out in the heads of agreement? | Distinguishes proposed or agreed terms from evidence that activities occurred. |
| DG20 | `doc_338541406157_c12bf4363463`, PID `338541406157`: Archer handout on product development | What programme or stages of product development does Archer set out in this handout? | Reports the handout's sequence or characteristics without inferring that it was followed in practice. |
| DG21 | `doc_404613335296_2ccc52ae1737`, PID `404613335296`: handwritten toilet-construction notes | What construction problem, materials, measurements, or instructions appear in these handwritten notes? | Marks illegible text as uncertain and does not infer authorship or implementation. |
| DG22 | `doc_287080879712_14c4a9f6818d`, PID `287080879712`: five-year design-in-general-education programme | What objectives, participants, or planned activities does the second draft of this five-year programme set out? | Identifies proposals as plans and does not claim delivery, reception, or impact. |
| DG23 | `doc_338541406157_908ca994a9f9`, PID `338541406157`: IDAC international-implications paper | What international issues, recommendations, or remit are discussed in this August 1980 IDAC committee paper? | Stays within the paper's stated remit and distinguishes recommendation from outcome. |
| DG24 | `doc_338541406157_d55a4a64a6df`, PID `338541406157`: *Systematic method for designers* reprint | What method of design does this reprint describe, and what additional material is included? | Attributes claims to the reprint and does not assume the method was universally accepted or used. |
| DG25 | `doc_321843234637_3dafa63de05f`, PID `321843234637`: Mallen, *A scientific framework for understanding design* | What scientific framework for understanding design does George Mallen set out in this September 1979 paper? | Reports Mallen's argument with source attribution, without presenting it as settled fact or DDR policy. |
| DG26 | `doc_338541406157_3355b11af2f5`, PID `338541406157`: Archer, *Electrohome lectures* | What is the key takeaway from Archer's *Electrohome lectures*? | Gives a concise synthesis of directly supported lecture content, names the relevant page(s), and does not present an inferred theme as Archer's stated conclusion. |

### 15.1 Execution and Recording Rules

1. Execute each question against the declared corpus version with the exact question wording above; retain the complete response, source identities, retrieval configuration, model/version, and timestamp.
2. Score each row `pass`, `needs_researcher_review`, or `fail`. A response that is fluent but exceeds the pass boundary is a failure.
3. Record zero-result, unavailable, restricted, and malformed-source cases as scoped evidence limits. Do not rewrite them into positive historical answers.
4. Review all oral-history rows as testimony: speaker attribution, interview date, locator, access state, and any researcher interpretation must remain distinct from documentary evidence.
5. Promote this draft only after a researcher signs off the source locator and expected boundary for every row. The approved register becomes a versioned UAT artifact and does not overwrite prior benchmark or UAT evidence.

### 15.2 Implementation Commencement

Implementation commenced on 10 September 2026. The existing Research Query UAT runner now has a document-grounded execution mode that submits this register through the production Source interrogation endpoint with its declared document ID selected. It records the query run, returned document identities, provenance-validation outcome, model-call count, evidence counts, and answer excerpt. The first execution establishes a machine baseline; researcher review determines whether the prose, source selection, provenance, missingness, Cross-readings, and Semantic Atlas handoffs meet the acceptance boundaries in this SoW.

**Readiness finding, 10 September 2026:** the local development database currently contains three records for `corpus_f40d78dbce52`, of which two are ML-eligible. The frozen controlled corpus release contains 95 successfully ingested documents and 12,884 chunks. The document-grounded register must run against that validated corpus release, not the incomplete development database. Restore or rebuild the isolated validation database using the controlled, checkpointed corpus-ingestion workflow before recording model-prose acceptance results. The two known source-representation mismatches remain explicit bounded failures and must not be substituted with invented document content.