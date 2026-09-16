# Statement of Work: Evidence-Led Comparative Research Instrument

**Project:** Testamentary Traces / RCA Department of Design Research archive

**Version:** 1.0

**Date:** 10 September 2026

**Status:** Delivery specification

## 1. Purpose

Deliver a live, researcher-led PhD methods instrument for interrogating, comparing, tracing, and visually exploring the DDR archive without presenting generated, retrieved, or computational output as historical fact.

The instrument must let a researcher:

- ask evidence-led questions of a defined source or corpus;
- select document A and document B and compare them on an explicit research question;
- inspect the passages, pages, source identity, retrieval configuration, and model output supporting every response;
- record scoped limits as absences without equating them with historical absence;
- compare attributable testimony with documentary evidence through reviewed cross-readings;
- use a semantic atlas to formulate candidate readings while retaining the distinction between computational proximity and documentary support.

## 2. Current Baseline

The production corpus release is `corpus_f40d78dbce52`.

| Measure | Current state |
| --- | --- |
| Manifest source assets | 109 |
| Successfully materialised PDFs | 107 |
| Source-representation failures | 2 published PDF URIs return JPEG bytes |
| Current Docling chunks | 15,019 |
| Documents with complete extracted text | 107 |
| ML-eligible sources available to interrogation | 97 |
| ML-excluded sources retained for archival inspection | 12 |
| Electrohome lectures | 259 passages, `eligible_unrestricted` |

The two failed source representations must remain visible as bounded corpus limitations. They must not be described as historically absent or silently omitted.

## 3. Non-Negotiable Methodological Constraints

1. PostgreSQL full-text search remains the evidence-selection method for source interrogation. Vector similarity must not silently determine or expand documentary evidence.
2. Archive record, source document, page passage, testimony, researcher annotation, retrieval run, embedding, visual point, and generated model output remain separately typed.
3. Every model claim must link to retrieved passages. A result with no sufficient passage must state that the defined retrieval did not establish an answer.
4. A zero result, unavailable file, missing metadata field, absent embedding, or no cross-reading match is a scoped system/corpus condition, never a historical absence claim.
5. Explicit document targeting is mandatory for comparison. A corpus-wide search result cannot be relabelled as a document-A versus document-B comparison.
6. All batch work must be versioned, idempotent, resumable, observable, and retain failure records.
7. Existing source IDs, PIDs, page scope, rights/access controls, checksums, corpus versions, and immutable run records must be retained.
8. No synthetic testimony, mock source, invented relation, or generated historical claim may be used as evidence or to make an interface appear complete.

## 4. Workstream A: Targeted Comparative Interrogation

### Objective

Enable a researcher to select one or more archive documents and ask either a single-source question or an explicit comparison question.

### Required capabilities

- Add document selection from Sources, document detail, and Source interrogation.
- Support `target_document_ids` in the interrogation API, with a maximum documented selection size and stable document/PID validation.
- Support a `comparison` mode requiring exactly two selected documents.
- Retrieve independently from each selected document, preserving document-specific ranking, page scope, and zero-result diagnostics.
- Produce a structured comparison with separate sections for document A, document B, convergences, differences/tensions, and evidence limits.
- Prohibit the model from inferring an omission, contradiction, influence, consensus, or causal relation unless the retrieved passages explicitly support that bounded statement.
- Persist an immutable comparison run containing question, selected identities, corpus version, retrieval configuration, ranked passages, prompt/model configuration, answer, citations, diagnostics, and timestamp.
- Provide exports suitable for research records: Markdown, CSV/JSON evidence table, and a citation/provenance bundle.

### Acceptance criteria

- “What is the key takeaway from the Electrohome lectures?” returns evidence from the Electrohome document only when it is selected.
- “Compare document A with document B” refuses to run until two valid documents are selected.
- The response visibly separates claims/evidence for each document and identifies pages for every source-backed statement.
- A document with no matching passage returns a document-specific insufficiency result rather than borrowing evidence from the other document.
- A saved run reproduces its selected corpus, source identities, passage set, and configuration.
- API, database, frontend, accessibility, and end-to-end browser tests pass before production release.

## 5. Workstream B: Provenance and Explainability

### Objective

Make it practical for a researcher to inspect why an answer, comparison, absence event, or visual point was produced.

### Required capabilities

- Display source title, PID, document ID, page, section, excerpt, source URI, checksum, corpus version, page-scope status, and retrieval rank/score for each passage.
- Display retrieval diagnostics: nominated archive candidates, ML-eligible candidates, materialised candidates, selected passages, rejected candidates, and precise exclusion classifications.
- Make model configuration and prompt version available for every inference run.
- Provide a navigable trace from answer to passage to document record, and from document record to the originating archive asset.
- Expose whether an item is documentary evidence, archive metadata, authority data, testimony, researcher interpretation, computational output, or generated synthesis.

### Acceptance criteria

- A researcher can open the Electrohome source passages supporting an answer from the answer view.
- A missing source is classified as a representation, access, policy, extraction, page-scope, or query-match limitation where that information is available.
- Exports retain all IDs and provenance required to re-open the evidence later.

## 6. Workstream C: Absences

### Objective

Support disciplined recording of what a bounded corpus, source description, access condition, retrieval configuration, or computational process does not establish.

### Required capabilities

- Retain the existing missingness typology and review workflow.
- Create scoped events from interrogation/comparison runs only with explicit researcher confirmation.
- Attach source, passage, document-pair, corpus, run, and diagnostic references where available.
- Enable comparison-specific events such as “no relevant passage retrieved from selected document B under this query and corpus configuration.”
- Keep descriptive, retrieval, access, computational, and archival limitations distinguishable in interface and export.

### Acceptance criteria

- No result is rendered as a claim that a person, event, relationship, or idea did not historically exist.
- A comparison run can create a reviewed, source-scoped absence event without modifying the underlying evidence.
- Event exports include scope, evidence, configuration, reviewer, date, and interpretative limitation.

## 7. Workstream D: Cross-Readings

### Objective

Support reviewed comparison between attributable testimony and selected documentary passages.

### Required capabilities

- Introduce a governed, rights-cleared testimony ingestion/creation workflow with source attribution, locator, access status, and review state.
- Retain immutable retrieval probes and candidate mappings.
- Require researcher annotation for `supports`, `complicates`, `contradicts`, or `no_documentary_trace`; never assign a relation automatically.
- Permit handoff from a selected document/comparison run to a cross-reading context.
- Preserve prior interpretations and retrieval runs when mappings are revised.

### Acceptance criteria

- A small researcher-approved UAT set covers support, complication, a defensible contradiction if available, and no documentary trace.
- Restricted material remains protected and is never exposed merely to demonstrate the feature.
- Mapping exports retain testimony provenance, documentary citations, retrieval run, relation, reviewer, and caveat.

## 8. Workstream E: Semantic Atlas

### Objective

Embed the 107 materialised PDFs and expose a reproducible exploratory atlas for locating candidate readings and comparisons.

### Readiness gate

Before generating vectors, record and approve:

- corpus release and inventory (`107` materialised PDFs, two explicit representation failures);
- eligible source/page/rights set;
- embedding model, revision/checksum, dimensions, licence, runtime, and normalisation;
- compute, storage, retention, and rollback plan;
- embedding input fingerprint and chunking version;
- researcher question motivating the first projection.

### Required capabilities

- Generate embeddings for approved chunks/documents only, keyed by corpus version, point ID, text fingerprint, and embedding configuration.
- Resume only missing/invalidated vectors and retain versioned replacement records.
- Validate dimension, finite values, duplicate IDs, corpus membership, and provenance before projection.
- Record coverage: eligible, excluded, attempted, embedded, failed, and represented documents.
- Generate a reproducible UMAP projection with recorded library version, seed, parameters, input ordering/fingerprint, and generated timestamp. PCA fallback must be visibly labelled.
- Allow filters by year, source type, theme, and selected document without silently recomputing the stored projection.
- Make every point open its document/chunk, page, excerpt, provenance, embedding set, projection ID, and caveats.
- Allow a researcher to nominate two documents from the atlas for targeted comparison; proximity itself is never evidence.

### Acceptance criteria

- All approved eligible chunks have valid vectors or a durable per-item failure record.
- Atlas coverage and point counts match the named embedding/projection inputs.
- Re-running the same configuration produces documented reproducibility within stated tolerance.
- Exports retain point IDs, filters, source identities, corpus version, embedding/projection configuration, and interpretative warnings.

## 9. Delivery Order

1. **Comparative interrogation foundation:** API contracts, source selector, paired retrieval, evidence-first comparison output, immutable run storage, and focused tests.
2. **Provenance and explainability integration:** inspection surfaces, diagnostics, exports, and handoffs.
3. **Absences integration:** comparison-scoped missingness, researcher confirmation, and export/UAT.
4. **Cross-readings activation:** testimony governance, UAT data, mapping workflow, and audit/export validation.
5. **Semantic Atlas readiness and embeddings:** approve configuration, generate/resume vectors for the 107-PDF corpus, validate coverage, then generate the first versioned projection.
6. **Atlas-to-comparison integration:** select two documents from the atlas and open a pre-populated comparative interrogation.
7. **Production release:** security/access review, migration rehearsal, regression suite, researcher UAT, deployment, post-deploy health checks, and a versioned release report.

## 10. Deliverables

- Targeted interrogation and document-pair comparison API, persistence model, and research interface.
- Evidence/provenance trace and export bundle for interrogations and comparisons.
- Scoped missingness integration for source and comparison workflows.
- Governed cross-reading passage and mapping workflow with UAT evidence.
- Versioned embedding pipeline, coverage report, and model/configuration registry for the 107-PDF corpus.
- Reproducible Semantic Atlas with point inspection, filters, exports, and comparison handoff.
- Automated tests, browser UAT scripts, deployment runbook, operational monitoring, and research-methods closeout report.

## 11. Production Acceptance Gate

Production release is permitted only when:

- corpus counts, failures, source policy, and checksums are reported for the active release;
- all comparison answers retain document-specific evidence and do not make unsupported claims;
- all provenance links and exports resolve to the recorded source/run identities;
- absence states remain scoped and reviewed;
- no unauthorised/restricted source becomes visible through search, comparison, cross-reading, embedding, or atlas output;
- embedding/projection coverage and failures are reported honestly;
- automated tests and researcher UAT pass;
- deployment, migration, and rollback procedures are documented and exercised.

## 12. Explicit Exclusions

This work does not authorise autonomous historical conclusions, automated truth adjudication, automatic testimony-to-document relation assignment, replacement of FTS retrieval with semantic similarity, or treatment of clusters and empty results as historical evidence.
