# Technology Statement of Work
## Retrieval-Augmented Archival Interrogation Experiment

**Project:** RCA Department of Design Research archive activation
**Research phase:** PhD Year 2, early-stage practice-led experiment
**Primary output:** Conference paper for *Generative AI and Cultural Heritage*, University of Turin, 29–30 October 2026
**Document status:** Working specification
**Version:** 0.2
**Date:** 7 August 2026

**v0.2 change:** Adds explicit use of existing DDR GraphQL database authorities as an inspectable structural layer for entity resolution, filtering, controlled query expansion, optional authority context and corroborative checking. Authority assertions remain distinct from source-document evidence and generated inference.

---

## 1. Purpose

This Statement of Work defines the technical scope, deliverables, methods, controls and acceptance criteria for an early-stage experiment using retrieval-augmented inference to interrogate a bounded corpus of digitised records from the Royal College of Art’s Department of Design Research (DDR).

The experiment operationalises three parts of the wider PhD research instrument:

1. **Retrieval-augmented archival interrogation** as the primary mode of inquiry.
2. **Corroborative checking and interpretative control** as the evaluation method.
3. **Retrieval-augmented missingness**, developed in the paper as **scoped missingness**, as a secondary analytical contribution.

The experiment does not aim to reconstruct the history of the DDR, benchmark frontier language models or prove that generative AI can resolve archival incompleteness. It tests whether a resource-aware, provenance-led system can surface relationships between dispersed archival traces while keeping generated interpretation, evidential support and uncertainty inspectable.

---

## 2. Research objectives

The experiment will test whether the existing technical architecture can:

- ingest and structure a corpus of approximately 160 OCR-processed PDF files;
- retain document, page, chunk and provenance identifiers through the processing pipeline;
- retrieve relevant passages using PostgreSQL full-text search;
- generate bounded responses using IBM Granite 3.1 2B Instruct;
- distinguish retrieved evidence from model inference;
- preserve disagreement and ambiguity where the corpus contains conflicting material;
- report insufficient evidence without inventing completion;
- distinguish retrieval failure from corpus-level missingness where technically possible;
- produce reproducible records suitable for scholarly analysis and conference presentation;
- support researcher-led evaluation rather than autonomous historical judgement;
- use existing GraphQL database authorities for transparent entity resolution, filtering, controlled query expansion and optional contextual enrichment without treating authority assertions as source-document evidence.

---

## 3. Research questions

### 3.1 Primary experimental question

> Under what conditions can retrieval-augmented inference make dispersed testamentary traces more legible without presenting generated synthesis as recovered historical fact?

### 3.2 Supporting questions

- Can the retrieval layer surface relevant records across separate DDR documents?
- Can generated responses remain traceable to specific documents, pages and chunks?
- Does the model preserve contested or contradictory accounts?
- When evidence is weak, can the system state what the corpus does not establish?
- How do OCR quality, chunking, lexical retrieval and model capacity shape the resulting interpretation?
- What becomes visible only through researcher corroboration?
- How do archive/database authorities condition what becomes retrievable or legible, and can their influence remain inspectable?
- What forms of absence can the system identify, and which require further archival investigation?

---

## 4. Scope

### 4.1 In scope

- Ingestion of approximately 160 OCR-processed PDFs.
- Structured extraction using Docling.
- Semantic or structure-aware chunking using the existing ingestion pipeline.
- Storage in PostgreSQL with document, chunk, page and persistent identifier metadata.
- PostgreSQL full-text search using `tsvector` and GIN indexing.
- BM25-style or equivalent lexical ranking within the existing implementation.
- Generation using IBM Granite 3.1 2B Instruct.
- Quantised CPU inference at 4-bit or 8-bit precision.
- Constrained response lengths in the range already supported by the system.
- GraphQL and/or REST endpoints required for search, analysis and provenance retrieval.
- Existing GraphQL database authorities, including staff, staff registry/roles and tenure, job/project registers, fonds, publication types, students, DDR periods and selected controlled categories such as methodology, project theme, project outcome, beneficiary audience and epistemic stance where relevant to a test case.
- Transparent authority-assisted entity resolution, metadata filtering and controlled query expansion.
- Optional bounded authority context supplied to Granite when explicitly enabled and recorded.
- Logging of prompts, retrieved chunks, model outputs, configuration and researcher assessment.
- A small set of deliberately selected archival test cases.
- Screenshot-ready output views for the conference presentation.
- Qualitative analysis for the conference paper.
- Optional limited sensitivity comparison against one larger model using identical retrieved context.

### 4.2 Out of scope

- Live demonstration at the conference.
- Training or fine-tuning the model on archive records.
- Treating generated outputs as independent historical findings.
- Comprehensive evaluation of all 160 documents.
- Claims about the complete DDR archive.
- Claims that corpus absence establishes historical absence.
- Active embedding-based retrieval.
- Full embedding-based visual analytics.
- Oral-history cross-reading unless oral-history transcripts are already included in the test corpus.
- Production deployment for public use.
- High-volume concurrent access.
- Automated publication of generated interpretations.
- Formal benchmarking against a large suite of language models.
- Treating database-authority assertions, catalogue classifications or controlled terms as if they were statements contained in source documents.
- Unrecorded or opaque authority-based query expansion.
- Automatically injecting every available authority field into every Granite prompt.
- Replacement of researcher judgement with model scoring.

---

## 5. Existing technical baseline

The experiment builds on an existing resource-aware architecture designed for an 8 GB RAM, CPU-only environment.

### 5.1 Core stack

| Layer | Current technology | Experimental role |
|---|---|---|
| Document processing | Docling 2.15.0 | Converts OCR’d PDFs into structured text |
| Database | PostgreSQL | Stores documents, chunks and metadata |
| Retrieval | PostgreSQL full-text search, `tsvector`, GIN index | Retrieves ranked textual evidence |
| Optional vector layer | pgvector installed but inactive | Reserved for later phases |
| Language model | IBM Granite 3.1 2B Instruct | Produces bounded responses over retrieved context |
| Inference | Quantised 4-bit or 8-bit, CPU-only | Supports low-resource local generation |
| Back end | FastAPI, Strawberry GraphQL, Python 3.11 | Exposes search, analysis and provenance services |
| Front end | React, IBM Carbon, D3 / Carbon Charts | Supports query, evidence and visual output |
| Deployment | Docker, Docker Compose | Enables reproducible runtime |
| Storage | PostgreSQL and existing object storage | Retains source and derivative assets |
| Archive authority layer | Existing DDR GraphQL database authorities and presets | Entity resolution, structural context, transparent filters and controlled query expansion |

### 5.2 Evidence-layer distinction

For the experiment, the archive is treated as a layered evidential system rather than a flat text corpus:

1. **Source-document evidence** — OCR-derived PDF/page/chunk text.
2. **Archive/catalogue metadata** — descriptive metadata about records and media.
3. **Database authorities** — structured assertions about people, projects, job numbers, fonds, publication types and controlled categories.
4. **Corpus-control and provenance metadata** — ML eligibility, page scope, identifiers, checksums, rights/access state and processing/version information.
5. **Model-generated inference** — provisional synthesis produced from supplied context.
6. **Researcher assessment** — corroboration, scoring, caveats and interpretation.

These layers must remain distinguishable in storage, retrieval, context assembly, experiment runs and exports.

### 5.3 Architectural principle

The language model is one component within an evidential pipeline. It does not retrieve independently, retrain on archive records or act as a historical authority. Its role is to generate provisional, bounded interpretations from retrieved document segments.

---

## 6. Experimental design

### 6.1 Corpus preparation

The corpus will consist of approximately 160 OCR-processed PDF files.

For each document, the ingestion process should retain or generate:

- stable document identifier;
- source file name;
- collection or archive reference where available;
- title;
- date or date range where available;
- creator or attributed author where available;
- page number;
- chunk identifier;
- chunk sequence;
- document type;
- OCR status;
- ingestion timestamp;
- checksum;
- access or rights note where relevant;
- persistent identifier or internal PID;
- authority links used for the document or media asset, where available;
- authority-context version or snapshot reference where authority data affects retrieval or inference.

### 6.2 Database authorities

The existing archive GraphQL API exposes database authorities and query presets that may include:

- DDR staff and staff registry data, including roles and tenure;
- DDR job/project registers;
- fonds;
- publication types;
- students;
- DDR periods;
- beneficiary audiences;
- methodologies;
- project themes;
- project outcomes;
- epistemic stances;
- other controlled archive-specific categories exposed by the live schema.

These authorities are not equivalent to source-document evidence.

They may support four bounded functions:

1. **Entity resolution** — for example, reconciling name variants or linking documents to canonical people/projects.
2. **Transparent retrieval support** — filters, known variants and controlled query expansion.
3. **Structural context** — optional labelled authority context supplied alongside retrieved chunks.
4. **Corroborative checking** — comparison between generated relationships, documentary traces and existing structured archive relationships.

Authority context must never be silently concatenated with source text. If supplied to Granite, it must be explicitly labelled as archive/database authority context and its fields must be saved with the run.

Interpretative authorities such as `epistemic stance`, beneficiary classification or methodology may encode prior institutional or researcher interpretation. Their use therefore requires particular caution and must remain inspectable.

### 6.3 Test-case structure

The experiment should include at least three case types.

#### Case A: known relationship

A relationship already supported by conventional archival reading.

Purpose:

- test retrieval recall and precision;
- test whether the model expresses the relationship accurately;
- compare generated synthesis with known archival evidence.

#### Case B: contested interpretation

A topic represented through disagreement, shifting terminology or uneven institutional positions.

Purpose:

- test whether the model preserves conflict;
- identify false consensus;
- assess the relation between source diversity and generated coherence.

#### Case C: scoped missingness

A question for which the digitised corpus contains partial, uneven or insufficient evidence.

Purpose:

- test refusal and uncertainty behaviour;
- identify candidate absences;
- distinguish insufficient retrieval from insufficient corpus evidence;
- generate research questions for human review.

### 6.4 Minimum prompt set

Target: **6–10 primary prompts**.

Recommended distribution:

- 2–3 prompts for known relationships;
- 2–3 prompts for contested interpretation;
- 2–3 prompts for scoped missingness;
- 1–2 prompt variants to test sensitivity to wording.

### 6.5 Prompt constraints

Prompts should require the system to:

- answer only from supplied context;
- cite document, page and chunk identifiers;
- separate evidence from inference;
- identify contradiction;
- state when evidence is insufficient;
- avoid filling gaps;
- return structured output where possible;
- suggest follow-up searches rather than fabricate completion;
- distinguish source-document evidence from archive/catalogue metadata and database-authority assertions;
- state when authority context materially contributed to a relationship or interpretation.

---

## 7. Required output schema

Each experimental run should record the following fields.

```json
{
  "run_id": "string",
  "timestamp": "ISO-8601",
  "research_case": "known_relationship | contested_interpretation | scoped_missingness",
  "prompt_version": "string",
  "prompt_text": "string",
  "model": {
    "name": "ibm-granite-3.1-2b-instruct",
    "quantisation": "4-bit | 8-bit",
    "max_tokens": 512,
    "temperature": 0.0,
    "context_window": "record actual value"
  },
  "retrieval": {
    "method": "postgresql_fts",
    "query": "string",
    "top_k": 5,
    "filters": {},
    "ranking_scores": []
  },
  "retrieved_chunks": [
    {
      "pid": "string",
      "document_id": "string",
      "page": 1,
      "chunk_id": "string",
      "text": "string",
      "score": 0.0
    }
  ],
  "authority_context": {
    "used": false,
    "sources": [],
    "fields_supplied": [],
    "values_snapshot": [],
    "version": "string | null"
  },
  "generated_response": {
    "answer": "string",
    "evidence": [],
    "inferences": [],
    "contradictions": [],
    "missingness": [],
    "follow_up_queries": []
  },
  "researcher_assessment": {
    "retrieval_relevance": 0,
    "provenance_accuracy": 0,
    "interpretative_restraint": 0,
    "preservation_of_contestation": 0,
    "missingness_handling": 0,
    "notes": "string"
  }
}
```

The exact field names may be adapted to the existing API. The distinction between retrieved evidence, generated inference and researcher assessment must remain explicit.

---

## 8. Evaluation framework

Each run will be assessed using five primary criteria, with authority transparency recorded as an additional methodological check when authority data is used.

| Criterion | Core question |
|---|---|
| Retrieval relevance | Did the system surface the most pertinent passages available in the corpus? |
| Provenance accuracy | Can substantive claims be traced to the cited document, page and chunk? |
| Interpretative restraint | Does the response distinguish evidence from inference? |
| Preservation of contestation | Does the response retain disagreement, ambiguity and uneven evidence? |
| Scoped missingness | Does the response state what the retrieved corpus cannot establish? |
| Authority transparency | Where authority data influenced retrieval or inference, is that influence visible and kept distinct from source evidence? |

### 8.1 Suggested scoring

Use a simple 0–3 scale.

- **0 — failed:** absent, misleading or unsupported.
- **1 — weak:** partially present but unreliable.
- **2 — adequate:** mostly correct with identifiable limitations.
- **3 — strong:** clear, traceable and methodologically appropriate.

Scores support comparison. They do not replace qualitative analysis.

### 8.2 Failure classification

When a run fails, classify the likely source:

- source document limitation;
- OCR failure;
- document parsing failure;
- metadata failure;
- chunking failure;
- lexical mismatch;
- retrieval ranking failure;
- context assembly failure;
- prompt failure;
- model instruction-following failure;
- unsupported model inference;
- interface or API failure;
- researcher uncertainty;
- authority-data mismatch or stale authority snapshot;
- authority-conditioned inference presented as documentary evidence.

A single run may have more than one classification.

---

## 9. Scoped missingness protocol

The system must not claim historical absence solely because retrieval returns no evidence.

Each missingness output should specify its scope.

### 9.1 Permitted statements

- No relevant passage was returned by the current query.
- No supporting passage was found within the ingested corpus.
- Evidence is concentrated in a limited number of documents.
- The retrieved material describes a person only through another person’s account.
- The corpus contains conflicting dates or descriptions.
- The available text does not establish the requested relationship.
- OCR or document structure may have affected retrieval.

### 9.2 Prohibited overclaims

- The event did not happen.
- The person had no role.
- The archive contains no evidence.
- The historical record is silent.
- The institution deliberately excluded the subject.

Such claims require further archival and historical investigation.

---

## 10. Provenance and reproducibility requirements

Every substantive generated claim should be inspectable against retrieved evidence.

The system must record:

- model name and version;
- quantisation;
- generation parameters;
- retrieval method;
- query string;
- top-k value;
- filters;
- retrieved chunks and ranking scores;
- source identifiers;
- exact prompt;
- exact response;
- software commit hash;
- corpus version;
- ingestion version;
- date and time of the run;
- whether database-authority context was used;
- authority source(s), fields supplied and version/snapshot where authority data affected retrieval or inference.

Experimental runs should be exportable as JSON and readable in a simple human-facing report.

---

## 11. Interface requirements for conference evidence

The experiment will be presented through screenshots rather than a live demonstration.

The interface should support capture of:

1. the query;
2. the retrieved passages;
3. source and page identifiers;
4. the generated response;
5. separated evidence and inference;
6. missingness output;
7. researcher annotation or assessment;
8. model and retrieval configuration;
9. authority context used, if any, clearly separated from retrieved source evidence.

Screenshots should show genuine saved runs. They must not simulate outputs.

---

## 12. Optional large-model sensitivity test

A limited comparison may be undertaken if affordable and technically practical.

Conditions:

- use the same retrieved chunks;
- use the same prompt;
- do not permit the larger model to perform independent web or corpus retrieval;
- record model and endpoint version;
- compare evidence use, ambiguity, unsupported synthesis and instruction following;
- treat the comparison as a sensitivity check, not as the main experiment.

The primary experiment remains the local Granite system.

---

## 13. Deliverables

### D1. Ingested experimental corpus

- approximately 160 PDFs processed;
- document and chunk metadata retained;
- ingestion errors recorded;
- corpus manifest exported.

### D2. Search and provenance workflow

- FTS query endpoint operational;
- ranked chunks returned;
- document, page and chunk identifiers visible;
- provenance lookup operational;
- authority links and any authority-assisted retrieval/context influence remain inspectable.

### D3. Structured analysis workflow

- prompt plus retrieved context sent to Granite;
- structured response returned;
- evidence, inference and missingness separated;
- run record stored.

### D4. Experimental prompt set

- 6–10 documented prompts;
- case classification;
- prompt versions;
- rationale for each test.

### D5. Experimental run dataset

- raw JSON export;
- human-readable summary;
- researcher assessment;
- failure classification.

### D6. Conference evidence pack

- architecture diagram;
- research-instrument alignment diagram;
- corpus overview;
- selected screenshots;
- prompt–retrieval–response comparisons;
- limitations slide content.

### D7. Paper-ready findings memo

A concise analytical memo organised under:

- relationships surfaced;
- interpretations generated;
- ambiguity flattened;
- missingness reported or concealed;
- implications for archival activation.

---

## 14. Acceptance criteria

The experiment will be considered complete for the conference paper when:

- the corpus manifest confirms successful processing of the intended document set or clearly records exceptions;
- at least six complete experimental runs are stored;
- all reported runs preserve prompt, retrieval and model configuration;
- each reported output can be traced to source chunks;
- at least one successful retrieval case is documented;
- at least one interpretative overreach or failure is documented;
- at least one scoped-missingness case is documented;
- failure causes are analysed rather than described only as model error;
- screenshots can be captured from saved runs;
- the findings can support bounded claims in the paper;
- limitations are explicitly documented.

---

## 15. Risks and mitigations

| Risk | Likely effect | Mitigation |
|---|---|---|
| Slow CPU inference | Delayed experimentation | Use saved runs, queue jobs, avoid live demo |
| 2B model limitations | Weak synthesis or instruction following | Short prompts, small context, structured outputs, low temperature |
| OCR errors | Missed or distorted evidence | Sample-check source pages, record OCR confidence or issue flags |
| Lexical mismatch | Relevant passages not retrieved | Query expansion, controlled synonyms, metadata filters |
| Overlong chunks | Context dilution | Test chunk sizes and overlap |
| Fragmented chunks | Loss of meaning | Preserve headings, page and sequence metadata |
| False coherence | Unsupported narrative | Separate evidence and inference, require uncertainty fields |
| Provenance mismatch | Misleading citations | Validate cited PID/page/chunk against context |
| Corpus bias | Reproduction of institutional visibility | Describe corpus composition and uneven representation |
| Missingness overclaim | False historical absence | Apply scoped missingness protocol |
| Configuration drift | Irreproducible results | Pin versions and store commit hashes |
| Authority over-conditioning | Model restates catalogue/database classifications as if discovered from documents | Keep authority context labelled, optional and logged; compare document-only and authority-assisted runs where useful |
| Stale or conflicting authorities | Structured archive data conflicts with documentary evidence or later corrections | Snapshot/version authority context and preserve disagreement rather than resolving it automatically |
| Over-expansion of experiment | Paper becomes unmanageable | Limit to three case types and 6–10 prompts |

---

## 16. Milestones

### Phase 1 — Corpus readiness

- confirm file inventory;
- validate OCR and source metadata;
- ingest documents;
- export ingestion report.

### Phase 2 — Retrieval validation

- test known-item searches;
- verify ranking and provenance;
- identify query expansion needs;
- define which authority sources may be used for entity resolution, filters or controlled query expansion;
- freeze retrieval and authority-assistance configuration for the paper.

### Phase 3 — Structured inference

- implement response schema;
- validate evidence and missingness fields;
- test constrained prompts;
- freeze model configuration.

### Phase 4 — Experimental runs

- execute 6–10 prompts;
- store all outputs;
- assess each run;
- select paper cases.

### Phase 5 — Analysis and reporting

- create findings matrix;
- capture screenshots;
- draft findings memo;
- document limitations and next steps.

---

## 17. Definition of done

The experiment is done when it has produced a small, inspectable body of evidence that can answer the paper’s methodological question. Completion does not depend on the model performing well in every case. A documented failure is a valid result when its source and significance can be analysed.

The experiment should support the following bounded claim while preserving the distinction between documentary evidence, archive/database authorities and generated inference:

> Retrieval-augmented inference can support archival activation when generated interpretations remain attached to their sources and when evidential limits are returned as part of the output. The experiment also tests where this arrangement fails through retrieval error, model inference, corpus limits and false coherence.
