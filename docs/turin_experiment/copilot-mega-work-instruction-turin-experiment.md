# Copilot Work Instruction
## Build the Retrieval-Augmented Archival Interrogation Experiment

> **Use this file as the controlling implementation brief for the experiment.**
>
> Work incrementally. Inspect the repository before changing code. Reuse the existing architecture and conventions. Do not invent services that are not needed. Do not replace the current PostgreSQL full-text retrieval pipeline with vector search. Do not introduce paid APIs. Do not fine-tune or retrain the language model on archive records.

---

## 0. Role and operating mode

Act as a senior Python, FastAPI, PostgreSQL, GraphQL and applied-ML engineer supporting a practice-led PhD experiment.

Your task is to help implement a reproducible research workflow for retrieval-augmented archival interrogation over a bounded corpus of approximately 160 OCR-processed PDFs.

The system must prioritise:

- provenance;
- inspectability;
- reproducibility;
- modest resource use;
- separation of retrieval, inference and researcher judgement;
- explicit handling of uncertainty and missingness;
- stable saved outputs for academic analysis.

Do not optimise for conversational fluency, visual polish or benchmark performance before the evidential workflow is reliable.

---

## 1. Read before coding

First inspect the repository and report:

1. top-level directory structure;
2. back-end entry points;
3. ingestion pipeline;
4. Docling integration;
5. PostgreSQL schema and migrations;
6. full-text search implementation;
7. GraphQL schema;
8. REST endpoints;
9. Granite model wrapper;
10. front-end routes and components;
11. Docker and environment configuration;
12. current test coverage;
13. existing provenance or PID logic;
14. existing experiment or analysis data models.

Then produce:

- a concise architecture summary;
- a gap analysis against this instruction;
- a phased implementation plan;
- a list of files likely to change;
- risks or ambiguities that require confirmation.

Do not make broad refactors until the current system has been mapped.

---

## 2. Non-negotiable research constraints

### 2.1 Model

Use:

- IBM Granite 3.1 2B Instruct;
- local CPU inference;
- 4-bit or 8-bit quantisation;
- bounded context;
- bounded generation;
- deterministic or near-deterministic generation for recorded experiments.

Recommended defaults:

```yaml
temperature: 0.0
top_p: 1.0
max_tokens: 512
do_sample: false
```

Use the actual supported settings of the model runtime. Record all settings with every run.

### 2.2 Retrieval

The active retrieval method is PostgreSQL full-text search.

Use:

- `tsvector`;
- GIN index;
- lexical ranking;
- metadata filters;
- top-k retrieval;
- stored ranking scores.

Do not activate pgvector for the main experiment.

pgvector may remain installed but disabled.

### 2.3 Data use

- Do not train or fine-tune on archive records.
- Do not send archive records to external APIs.
- Do not add analytics that leak document content.
- Do not make generated responses public by default.
- Retain provenance for every retrieved chunk.
- Keep master documents separate from derived structured text.

### 2.4 Interpretation

The model must not be presented as an autonomous historian.

The system must separate:

1. retrieved evidence;
2. model-generated inference;
3. missingness or uncertainty;
4. researcher assessment.

---

## 3. Target experiment

Implement a workflow that supports three case types.

```python
from enum import StrEnum

class ResearchCase(StrEnum):
    KNOWN_RELATIONSHIP = "known_relationship"
    CONTESTED_INTERPRETATION = "contested_interpretation"
    SCOPED_MISSINGNESS = "scoped_missingness"
```

### 3.1 Known relationship

A relationship already supported by archival reading.

The system should:

- retrieve relevant passages;
- show ranked evidence;
- generate a bounded account;
- cite each substantive claim;
- allow researcher comparison.

### 3.2 Contested interpretation

A topic represented through disagreement or shifting language.

The system should:

- retrieve diverse evidence;
- identify disagreement;
- avoid consensus unless supported;
- preserve source-specific claims;
- state unresolved points.

### 3.3 Scoped missingness

A question for which the corpus is partial or insufficient.

The system should:

- report no-evidence or weak-evidence conditions;
- distinguish no retrieval result from no corpus support;
- identify concentration of evidence;
- suggest follow-up queries;
- avoid historical absence claims.

---

## 4. Desired end-to-end workflow

```text
PDF/TIFF source
    ↓
Docling ingestion
    ↓
structured document
    ↓
page-aware / heading-aware chunks
    ↓
document + page + chunk metadata
    ↓
PostgreSQL storage
    ↓
PostgreSQL FTS query
    ↓
ranked retrieved chunks
    ↓
context assembly
    ↓
Granite 3.1 2B bounded inference
    ↓
structured response
    ↓
provenance validation
    ↓
saved experiment run
    ↓
researcher assessment
    ↓
JSON / CSV / screenshot-ready report
```

Each stage must be observable and testable.

---

## 5. Repository deliverables

Create or adapt the following logical components. Match existing repository conventions rather than forcing this exact path structure.

```text
backend/
  app/
    ingestion/
      docling_pipeline.py
      chunking.py
      metadata.py
      manifest.py
    retrieval/
      fts.py
      query_expansion.py
      schemas.py
    inference/
      granite_client.py
      prompts.py
      context_builder.py
      response_parser.py
    experiments/
      models.py
      service.py
      evaluator.py
      exports.py
      provenance_validator.py
    api/
      rest/
      graphql/
    db/
      models.py
      migrations/
    tests/
      test_ingestion.py
      test_retrieval.py
      test_inference.py
      test_provenance.py
      test_experiments.py

frontend/
  src/
    pages/
      ExperimentRunPage.*
      ExperimentListPage.*
    components/
      QueryPanel.*
      RetrievedEvidencePanel.*
      GeneratedResponsePanel.*
      MissingnessPanel.*
      ResearcherAssessmentPanel.*
      RunMetadataPanel.*

docs/
  experiment/
    corpus-manifest.md
    prompt-register.md
    evaluation-rubric.md
    runbook.md
    data-dictionary.md

scripts/
  ingest_corpus.py
  validate_corpus.py
  run_experiment.py
  export_experiments.py
```

---

## 6. Data model

Implement or adapt persistent models for the following entities.

### 6.1 Document

Required fields:

```python
class Document:
    id: UUID
    pid: str
    source_filename: str
    title: str | None
    creator: str | None
    date_text: str | None
    document_type: str | None
    archive_reference: str | None
    checksum_sha256: str
    page_count: int | None
    ocr_status: str
    source_uri: str | None
    rights_note: str | None
    ingestion_version: str
    created_at: datetime
```

### 6.2 Chunk

Required fields:

```python
class DocumentChunk:
    id: UUID
    document_id: UUID
    chunk_id: str
    page_start: int | None
    page_end: int | None
    heading_path: list[str]
    sequence_number: int
    text: str
    token_count: int | None
    metadata_json: dict
    search_vector: object
    created_at: datetime
```

### 6.3 Experiment prompt

```python
class ExperimentPrompt:
    id: UUID
    name: str
    version: str
    research_case: ResearchCase
    prompt_text: str
    rationale: str
    expected_evidence: str | None
    known_limitations: str | None
    created_at: datetime
```

### 6.4 Experiment run

```python
class ExperimentRun:
    id: UUID
    run_id: str
    prompt_id: UUID
    corpus_version: str
    git_commit: str
    model_name: str
    model_quantisation: str
    model_parameters_json: dict
    retrieval_parameters_json: dict
    query_text: str
    generated_answer: str
    structured_response_json: dict
    duration_ms: int
    status: str
    error_message: str | None
    created_at: datetime
```

### 6.5 Retrieved evidence

```python
class RetrievedEvidence:
    id: UUID
    experiment_run_id: UUID
    chunk_id: UUID
    rank: int
    score: float
    excerpt: str
    included_in_context: bool
```

### 6.6 Researcher assessment

```python
class ResearcherAssessment:
    id: UUID
    experiment_run_id: UUID
    retrieval_relevance: int
    provenance_accuracy: int
    interpretative_restraint: int
    preservation_of_contestation: int
    missingness_handling: int
    failure_categories: list[str]
    notes: str
    assessed_at: datetime
```

Use integer constraints from 0 to 3 for rubric fields.

---

## 7. Corpus manifest

Implement a corpus manifest that can be exported as CSV and JSON.

Required fields:

```text
pid
source_filename
checksum_sha256
title
creator
date_text
document_type
archive_reference
page_count
ocr_status
ingestion_status
ingestion_error
chunk_count
ingestion_version
```

Add a validation command:

```bash
python scripts/validate_corpus.py --manifest path/to/manifest.csv
```

The command should:

- identify duplicate checksums;
- identify missing PIDs;
- identify zero-page or zero-chunk documents;
- identify missing source files;
- report ingestion failures;
- report suspiciously small or large chunks;
- produce a machine-readable validation report;
- exit non-zero on blocking errors.

---

## 8. Ingestion requirements

### 8.1 Docling

Use Docling for PDF-to-structured-text conversion.

Preserve where available:

- page numbers;
- headings;
- paragraph order;
- lists;
- tables;
- captions;
- footnotes;
- document hierarchy.

### 8.2 OCR awareness

The PDFs are already OCR-processed, but the pipeline must still record extraction problems.

Add issue flags such as:

```python
class ExtractionIssue(StrEnum):
    EMPTY_PAGE = "empty_page"
    LOW_TEXT_DENSITY = "low_text_density"
    POSSIBLE_COLUMN_ORDER_ERROR = "possible_column_order_error"
    POSSIBLE_HYPHENATION_ERROR = "possible_hyphenation_error"
    TABLE_FLATTENED = "table_flattened"
    HANDWRITING_NOT_CAPTURED = "handwriting_not_captured"
    UNKNOWN = "unknown"
```

Do not pretend OCR quality is uniform.

### 8.3 Chunking

Chunking should be:

- page-aware;
- heading-aware;
- sequence-preserving;
- configurable;
- reproducible.

Store chunking configuration with the corpus version.

Avoid splitting:

- names from their associated statements;
- headings from the following paragraph;
- list labels from list content;
- captions from referenced figures where possible.

Add tests for:

- first and last chunk;
- page boundary handling;
- heading inheritance;
- overlap;
- empty text;
- very long paragraphs.

---

## 9. Retrieval implementation

### 9.1 PostgreSQL FTS

Implement or verify:

```sql
CREATE INDEX IF NOT EXISTS idx_document_chunks_search_vector
ON document_chunks
USING GIN (search_vector);
```

Use a weighted search vector where fields exist.

Example:

```sql
setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
setweight(to_tsvector('english', coalesce(heading_text, '')), 'B') ||
setweight(to_tsvector('english', coalesce(chunk_text, '')), 'C')
```

Use the repository’s preferred PostgreSQL configuration. Do not claim exact BM25 equivalence unless the implementation provides it.

### 9.2 Retrieval service contract

```python
@dataclass(slots=True)
class SearchRequest:
    query: str
    top_k: int = 5
    document_types: list[str] | None = None
    date_from: str | None = None
    date_to: str | None = None
    pids: list[str] | None = None

@dataclass(slots=True)
class SearchResult:
    rank: int
    score: float
    pid: str
    document_id: str
    title: str | None
    page_start: int | None
    page_end: int | None
    chunk_id: str
    text: str
```

### 9.3 Query transparency

Record:

- original researcher query;
- normalised query;
- expanded query, if used;
- filters;
- top-k;
- ranking function;
- ranking score;
- whether each result entered the model context.

### 9.4 Query expansion

Implement only transparent, controlled expansion.

Permitted:

- researcher-supplied synonyms;
- archive-specific glossary terms;
- known name variants;
- spelling variants;
- acronym expansions.

Do not use an opaque model-generated query expansion step for the main experiment unless its output is saved and inspectable.

---

## 10. Context assembly

Create a deterministic context builder.

Requirements:

- preserve rank;
- preserve source labels;
- preserve PID;
- preserve page number;
- preserve chunk ID;
- enforce total context limit;
- avoid silent truncation;
- log omitted chunks;
- optionally de-duplicate overlapping text.

Suggested context format:

```text
[SOURCE 1]
PID: DDR-000123
DOCUMENT: Example project report
PAGE: 14
CHUNK: DDR-000123-p014-c03
TEXT:
...

[SOURCE 2]
...
```

The model should see the same identifiers shown to the researcher.

---

## 11. Prompt templates

Create versioned prompt templates in source control.

### 11.1 System instruction

```text
You are assisting with a bounded archival research experiment.

Use only the supplied archival context.
Do not use general knowledge to complete missing information.
Do not claim that an event, person or relationship is absent from history because it is absent from the supplied context.
Separate direct evidence from interpretation.
Preserve disagreement and uncertainty.
Cite each substantive claim using the supplied PID, page and chunk identifiers.
When evidence is insufficient, state exactly what the supplied context does not establish.
Return valid JSON matching the required schema.
```

### 11.2 Known relationship template

```text
RESEARCH CASE: known relationship

QUESTION:
{question}

TASK:
1. Identify passages relevant to the proposed relationship.
2. State what the passages directly support.
3. State any interpretation required to connect them.
4. Identify contradictory or limiting evidence.
5. State what remains unresolved.
6. Suggest one follow-up archive search.

ARCHIVAL CONTEXT:
{context}
```

### 11.3 Contested interpretation template

```text
RESEARCH CASE: contested interpretation

QUESTION:
{question}

TASK:
1. Identify distinct positions or accounts in the context.
2. Attribute each position to its source.
3. Do not merge disagreement into consensus.
4. Identify changes in terminology or framing.
5. State what the context supports and what remains interpretative.
6. Identify evidence that would be needed to resolve the issue.

ARCHIVAL CONTEXT:
{context}
```

### 11.4 Scoped missingness template

```text
RESEARCH CASE: scoped missingness

QUESTION:
{question}

TASK:
1. Identify relevant evidence in the supplied context.
2. State whether the context supports a complete, partial or unsupported answer.
3. Describe the scope of missingness precisely.
4. Distinguish:
   a. no relevant retrieved passage;
   b. weak or partial evidence in the ingested corpus;
   c. possible OCR or retrieval failure;
   d. questions requiring further archival investigation.
5. Do not infer historical absence.
6. Suggest follow-up search terms or document types.

ARCHIVAL CONTEXT:
{context}
```

---

## 12. Structured response schema

Use Pydantic.

```python
from pydantic import BaseModel, Field

class EvidenceItem(BaseModel):
    claim: str
    pid: str
    page: int | None = None
    chunk_id: str
    quotation_or_paraphrase: str

class InferenceItem(BaseModel):
    inference: str
    supporting_sources: list[str]
    confidence: str = Field(pattern="^(low|medium|high)$")
    rationale: str

class ContradictionItem(BaseModel):
    description: str
    sources: list[str]

class MissingnessItem(BaseModel):
    scope: str
    category: str
    explanation: str
    follow_up_action: str | None = None

class ArchivalAnalysisResponse(BaseModel):
    answer: str
    evidence: list[EvidenceItem]
    inferences: list[InferenceItem]
    contradictions: list[ContradictionItem]
    missingness: list[MissingnessItem]
    follow_up_queries: list[str]
```

If Granite cannot reliably return valid JSON:

1. use constrained generation if supported;
2. retry once with a repair prompt;
3. retain the raw response;
4. record parse failure;
5. do not silently alter substantive content;
6. allow manual coding for analysis.

---

## 13. Model wrapper

The Granite client must:

- load once and reuse the model;
- expose health state;
- record load time;
- record inference time;
- reject requests beyond configured limits;
- use deterministic settings for experiment runs;
- return raw text and parsed response;
- record token counts if available;
- handle timeout and memory errors clearly;
- avoid automatic fallback to external APIs.

Suggested interface:

```python
class GraniteInferenceService:
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> InferenceResult:
        pass
```

Add typed exceptions:

```python
class ModelNotReadyError(RuntimeError): pass
class InferenceTimeoutError(RuntimeError): pass
class ContextLimitError(ValueError): pass
class ResponseParseError(ValueError): pass
```

---

## 14. Provenance validation

Implement a provenance validator that checks every cited source in the generated response.

Validation rules:

- PID exists;
- chunk ID exists;
- chunk belongs to PID;
- cited page matches stored page range;
- cited source was included in the supplied context;
- quoted text, when used, is present or approximately present in the chunk;
- no invented source identifier;
- no citation to excluded context.

Return:

```python
class ProvenanceValidationResult(BaseModel):
    valid: bool
    checked_claims: int
    valid_claims: int
    invalid_claims: int
    issues: list[str]
```

Do not mark the historical interpretation as valid merely because the citation exists.

---

## 15. Missingness logic

Add system-level missingness signals before model inference.

Examples:

```python
class RetrievalDiagnostics(BaseModel):
    result_count: int
    max_score: float | None
    score_spread: float | None
    unique_document_count: int
    unique_creator_count: int
    date_coverage: list[str]
    possible_low_recall: bool
    notes: list[str]
```

Rules may include:

- zero results → `no_retrieved_evidence`;
- very low scores → `weak_lexical_match`;
- all results from one document → `evidence_concentration`;
- repeated near-duplicate chunks → `retrieval_redundancy`;
- extraction issue flags in top results → `possible_extraction_failure`;
- missing page metadata → `provenance_incomplete`.

These are diagnostics, not historical conclusions.

---

## 16. Experiment service

Implement one orchestration method.

```python
async def run_archival_experiment(
    prompt_id: UUID,
    query: str,
    retrieval_params: RetrievalParams,
    model_params: ModelParams,
) -> ExperimentRunResult:
    # 1. Load prompt definition.
    # 2. Execute transparent retrieval.
    # 3. Generate retrieval diagnostics.
    # 4. Assemble bounded context.
    # 5. Call Granite.
    # 6. Parse structured response.
    # 7. Validate provenance.
    # 8. Store run, evidence and diagnostics.
    # 9. Return saved run.
    pass
```

All runs must be immutable after creation except for researcher assessment and explicit annotations.

Do not overwrite an earlier run when a prompt changes. Create a new prompt version and run.

---

## 17. API requirements

### 17.1 REST

Provide or adapt:

```http
POST /api/analyse
GET  /api/search
GET  /api/provenance/{pid}/{chunk_id}
GET  /api/experiments
GET  /api/experiments/{run_id}
POST /api/experiments/{run_id}/assessment
GET  /api/experiments/export
```

### 17.2 GraphQL

Expose equivalent read operations if GraphQL is the primary front-end interface.

Minimum query fields:

- experiment run metadata;
- prompt;
- retrieval parameters;
- retrieved evidence;
- structured response;
- provenance validation;
- retrieval diagnostics;
- researcher assessment.

### 17.3 Error responses

Use structured errors.

```json
{
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "The local model did not return within the configured time limit.",
    "details": {}
  }
}
```

Never return stack traces to the front end.

---

## 18. Front-end experiment view

Build a screenshot-ready experiment page.

Required panels:

### A. Run metadata

Show:

- run ID;
- date;
- corpus version;
- git commit;
- model;
- quantisation;
- generation parameters;
- retrieval method;
- top-k;
- duration.

### B. Research question

Show the exact prompt and case type.

### C. Retrieved evidence

For each result show:

- rank;
- score;
- PID;
- document title;
- page;
- chunk ID;
- text excerpt;
- whether it entered model context.

### D. Generated response

Show:

- answer;
- evidence;
- inference;
- contradictions;
- missingness;
- follow-up queries.

### E. Provenance status

Show:

- valid or invalid citations;
- validation issues;
- links to source chunks.

### F. Researcher assessment

Provide 0–3 rubric controls and notes.

### G. Export

Allow:

- JSON;
- CSV summary;
- print-friendly HTML.

Do not make a live-response animation central. Slow inference is expected. Use a clear queued/running/completed state.

---

## 19. Experiment CLI

Implement a CLI for reproducible runs.

Example:

```bash
python scripts/run_experiment.py \
  --prompt-id 2f62... \
  --query "What relationship is documented between X and Y?" \
  --top-k 5 \
  --max-tokens 512 \
  --output ./exports/run-001.json
```

Support batch execution from YAML.

```yaml
experiments:
  - id: known-relationship-01
    prompt_name: known_relationship
    prompt_version: "1.0"
    query: "..."
    top_k: 5

  - id: contested-interpretation-01
    prompt_name: contested_interpretation
    prompt_version: "1.0"
    query: "..."
    top_k: 7
```

Command:

```bash
python scripts/run_experiment.py --batch experiments/turin-2026.yaml
```

---

## 20. Exports

Produce:

### 20.1 Full JSON

Contains all run data.

### 20.2 CSV summary

Columns:

```text
run_id
research_case
query
model
quantisation
top_k
retrieval_result_count
unique_document_count
duration_ms
provenance_valid
retrieval_relevance
provenance_accuracy
interpretative_restraint
preservation_of_contestation
missingness_handling
failure_categories
```

### 20.3 Paper-ready Markdown

Generate a report block:

```markdown
## Run {run_id}

**Case:** scoped missingness  
**Question:** ...  
**Model:** Granite 3.1 2B Instruct, 4-bit  
**Retrieval:** PostgreSQL FTS, top-k 5

### Retrieved evidence
...

### Generated response
...

### Researcher assessment
...

### Methodological significance
...
```

Do not auto-write the methodological significance. Leave it as a researcher-authored field.

---

## 21. Testing requirements

Use the repository’s existing test framework.

### 21.1 Unit tests

Test:

- metadata normalisation;
- PID generation;
- chunk creation;
- search query construction;
- ranking order;
- context limits;
- prompt rendering;
- structured parsing;
- provenance validation;
- rubric bounds;
- export schemas.

### 21.2 Integration tests

Test:

- sample document ingestion;
- database persistence;
- known-item retrieval;
- experiment run creation;
- failed model response;
- malformed JSON response;
- provenance mismatch;
- zero-result retrieval;
- saved assessment;
- export generation.

### 21.3 Golden test fixtures

Create a very small non-sensitive fixture corpus with:

- one known relationship;
- one contradiction;
- one absent answer;
- one OCR-damaged passage.

Use it to verify behaviour without running the full corpus.

### 21.4 No false success

Tests must fail when:

- a citation refers to a chunk not in context;
- a run lacks model configuration;
- a saved run lacks corpus version;
- a generated claim has an invented PID;
- an assessment score is outside 0–3;
- the system labels zero retrieval as historical absence.

---

## 22. Observability

Use structured logging.

Every experiment log should include:

```text
run_id
prompt_id
corpus_version
git_commit
retrieval_duration_ms
retrieval_result_count
context_chunk_count
context_character_count
model_load_state
inference_duration_ms
parse_status
provenance_status
overall_status
```

Do not log full document text in production logs. Store archival text only in authorised database records and experiment exports.

---

## 23. Performance expectations

This is a research system, not a low-latency chat service.

Priorities:

1. correctness;
2. provenance;
3. reproducibility;
4. stability;
5. speed.

Expected behaviour:

- ingestion may be batched;
- inference may take time on CPU;
- one experiment run may be queued;
- the UI should preserve state during long-running inference;
- timeouts should be configurable;
- completed runs should be cached and reloadable.

Do not introduce complex distributed infrastructure unless the existing repository already uses it.

---

## 24. Security and access

Maintain existing Auth0 and role controls.

Suggested roles:

- `researcher`: run experiments and assess outputs;
- `viewer`: view approved saved runs;
- `admin`: manage corpus and configuration.

Do not expose source documents or generated outputs publicly without explicit approval.

Validate:

- file type;
- file size;
- PID format;
- query length;
- model parameter bounds;
- export permissions.

---

## 25. Documentation to generate

Create or update:

### `docs/experiment/runbook.md`

Include:

- how to start services;
- how to ingest corpus;
- how to validate manifest;
- how to run one experiment;
- how to run a batch;
- how to assess a run;
- how to export results;
- troubleshooting.

### `docs/experiment/data-dictionary.md`

Define every stored field.

### `docs/experiment/prompt-register.md`

Record:

- prompt name;
- version;
- purpose;
- template;
- changes;
- known limitations.

### `docs/experiment/evaluation-rubric.md`

Define 0–3 scores with examples.

### `docs/experiment/corpus-manifest.md`

Explain corpus boundaries and what is excluded.

### `docs/experiment/method-note.md`

Explain:

- why Granite 3.1 2B is used;
- why FTS is used;
- why pgvector is inactive;
- why no external model is required;
- how scoped missingness is bounded;
- why outputs are provisional.

---

## 26. Implementation phases

Work in this order.

### Phase 1 — Audit

- inspect repository;
- map architecture;
- identify gaps;
- propose file-level plan.

Stop and report before major code changes.

### Phase 2 — Data integrity

- document and chunk models;
- corpus manifest;
- ingestion validation;
- PID and provenance checks.

### Phase 3 — Retrieval

- verify FTS;
- add transparent diagnostics;
- add stable search result schema;
- add tests.

### Phase 4 — Inference

- model wrapper;
- versioned prompts;
- structured response parsing;
- context builder;
- tests.

### Phase 5 — Experiment persistence

- experiment models;
- run orchestration;
- immutable run records;
- researcher assessment.

### Phase 6 — Interface

- saved-run views;
- evidence panels;
- missingness panels;
- screenshot-ready layout;
- exports.

### Phase 7 — Research run

- configure 6–10 prompts;
- execute;
- validate;
- export;
- prepare paper evidence.

---

## 27. Coding standards

- Python 3.11 typing throughout.
- Use Pydantic for API schemas.
- Use SQLAlchemy 2.x patterns already present.
- Use Alembic for schema changes.
- Prefer small functions with explicit inputs and outputs.
- Add docstrings where behaviour is not obvious.
- Do not swallow exceptions.
- Avoid global mutable state.
- Pin dependency versions.
- Preserve existing linting and formatting tools.
- Add tests with every material feature.
- Use UK English in user-facing research labels where practical.
- Keep generated text labels distinct from source text.

---

## 28. Decision rules

When uncertain, use these rules.

### Retrieval vs inference

If a fact can be returned directly from metadata or a source passage, do not ask the model to invent a reformulation unless the experiment specifically requires synthesis.

### Provenance vs fluency

Prefer a clumsy but traceable response over a polished but unsupported one.

### Missingness vs completion

Prefer “the supplied corpus does not establish this” over a plausible completion.

### Small model vs external API

Improve prompt scope, context selection and output structure before proposing a larger paid model.

### Refactor vs incremental change

Prefer the smallest change that produces a reproducible experimental record.

---

## 29. Prohibited implementation shortcuts

Do not:

- fabricate model responses in tests presented as experiment data;
- hard-code citations into generated output;
- use hidden web search;
- send archive text to third-party APIs;
- equate no search result with historical absence;
- silently repair substantive model claims;
- overwrite earlier experiment runs;
- omit model settings from saved records;
- omit failed runs from the research dataset;
- activate vector search without documenting the methodological change;
- describe PostgreSQL ranking as exact BM25 unless implemented and verified;
- claim that provenance validation proves historical truth.

---

## 30. Completion report format

After each phase, report:

```markdown
## Phase completed

### Changes made
- ...

### Files changed
- ...

### Tests added
- ...

### Commands run
- ...

### Results
- ...

### Known limitations
- ...

### Next recommended step
- ...
```

At the end, produce:

1. architecture summary;
2. migration summary;
3. API summary;
4. test summary;
5. corpus validation summary;
6. experiment run summary;
7. unresolved risks;
8. exact commands required to reproduce the reported runs.

---

## 31. Initial Copilot task

Begin with this exact task:

> Inspect this repository against the work instruction in this file. Do not change code yet. Map the existing ingestion, PostgreSQL full-text retrieval, Granite inference, GraphQL/REST APIs, provenance handling, experiment persistence and front-end views. Then produce a gap analysis, a phased implementation plan, and a proposed list of files to create or modify. Flag any ambiguity that would affect data integrity, reproducibility or the distinction between retrieved evidence and generated inference.
