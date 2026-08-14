# DDR ML/LLM Handover: Evidence-Surface Diagnostics, Scoped Missingness, and Authority Data

**Purpose:** handover note for the ML/LLM repository before supervised training, retrieval, UMAP, and visual analytics work.

**Status:** local-development methodology and data-contract handover. Do **not** deploy to production during the current review window.

---

## 1. Why this matters

The DDR archive ML/LLM pipeline must not treat GraphQL payloads as neutral or complete archival truth.

The key methodological position is:

> The GraphQL payload is a computational evidence surface. It defines what the model can see, retrieve, interpret, embed, cluster, and cite. Absence from that payload is not the same as absence from the archive.

This means the ML/LLM repo should not simply “train on everything returned by GraphQL” without understanding:

- what is present in the archive but not exposed to GraphQL;
- what is exposed to GraphQL but not passed to the LLM;
- what is digitised but not text-searchable;
- what is visible as an asset but obscure as a contributor, authority relation, voice, project relation, or provenance trace;
- what has been processed by Docling/OCR and what remains image-only or unknown.

The purpose of the scoped-missingness work is to make these limits explicit before model training and visual analytics begin.

---

## 2. Current production freeze

The following production surfaces are currently under review and should remain stable:

- `admin.ddrarchive.org`
- `ddrarchive.org`
- `https://api.ddrarchive.org/graphql`

During the review window:

- do not deploy scoped-missingness changes to production;
- do not alter the production GraphQL schema;
- do not run production migrations;
- do not mutate production Postgres;
- do not mutate DigitalOcean Spaces assets;
- do not change public/admin behaviour.

All current scoped-missingness work should remain:

- local;
- branch-based;
- fixture-first;
- read-only;
- documented;
- tested against saved GraphQL fixtures.

---

## 3. Repository boundary

This handover assumes two repo roles.

### DDR admin / archive API repo

Responsible for:

- Postgres record and asset metadata;
- GraphQL API;
- admin ingestion platform;
- GraphQL presets;
- fixture generation;
- scoped-missingness diagnostics;
- evidence-surface reports;
- authority data extraction and exposure policy.

### ML/LLM repo

Responsible for:

- Docling ingestion;
- OCR/text extraction;
- authority-data ingestion as a provisional evidence layer;
- chunking;
- metadata attachment to chunks;
- retrieval;
- Granite/LLM prompting;
- supervised training or instruction tuning if used;
- embedding generation;
- UMAP / clustering / anomaly or proximity analysis;
- model evaluation;
- critical interpretation workflow.

The ML/LLM repo should consume **evidence payloads, diagnostics, extraction outputs, and provisional authority data**, not raw admin assumptions.

---

## 4. Evidence surfaces

Do not collapse these surfaces together.

### 4.1 Stored archival/admin data

Data in Postgres and the admin interface.

This may include fields not exposed to the public or LLM-facing GraphQL payload.

Absence from the LLM payload does **not** prove absence from this layer.

### 4.2 LLM/public GraphQL evidence payload

The curated GraphQL response intended for public sandbox / LLM interpretation.

This is the main payload the ML/LLM repo should treat as its metadata evidence surface.

Preset file in admin/API repo:

```text
docs/graphql_presets/llm_public_evidence.graphql
```

Properties:

- read-only;
- must not include `signed_url`;
- should include stable metadata, asset IDs, public URLs where appropriate, rights, date fields, exposed context fields, and diagnostics;
- should be the main basis for scoped missingness.

### 4.3 Internal Docling asset-fetch payload

Operational payload used to fetch PDFs/TIFFs/JPGs for processing.

Preset file:

```text
docs/graphql_presets/docling_asset_fetch.graphql
```

Properties:

- internal only;
- may request `signed_url`;
- signed URLs must be redacted from committed fixtures;
- must not be passed directly to the LLM as interpretive evidence.

### 4.4 Docling extraction output

Output from document/image processing.

Should include, where possible:

- extraction status;
- OCR status;
- page-level text;
- chunk IDs;
- warnings;
- low-confidence regions;
- whether material is image-only;
- whether tables/figures were detected;
- whether handwritten or marginal material was detected but not reliably transcribed.

### 4.5 Authority data evidence layer

Authority data from Postgres should be pulled into the ML/LLM pipeline as a **provisional and imperfect evidence layer**, not as definitive ground truth.

This may include:

- people authorities;
- corporate/organisational authorities;
- funder authorities;
- project/job authorities;
- collection/fonds/series relationships;
- creator/contributor links;
- interviewee/interviewer links;
- project team/staff fields;
- related entities;
- authority IDs and labels;
- job numbers or project identifiers;
- authority provenance/status fields, if present.

Authority data is important even when incomplete or erroneous because it shows what the archive currently recognises as machine-linkable, searchable, aggregable, and retrievable.

The ML/LLM repo should treat authority presence, authority absence, ambiguous authority links, missing job numbers, and inconsistent naming as part of the critical evidence surface.

### 4.6 LLM/retrieval evidence context

The combined context actually supplied to Granite/LLM.

This may include:

- GraphQL metadata;
- scoped missingness diagnostics;
- authority data and authority-status metadata;
- Docling chunks;
- retrieval scores;
- provenance information;
- interpretation cautions.

The model should be instructed to distinguish evidence from evidence limitation.

### 4.7 Visual analytics / indexing layer

Embeddings, UMAP projections, clusters, and anomaly/proximity relationships.

These only represent what has been embedded or indexed. They must not be treated as maps of the whole archive unless the evidence coverage is known.

---

## 5. Current scoped-missingness principle

Diagnostics are **not archival truth**.

They are:

> versioned readings of a particular evidence surface.

Therefore:

- do not backfill missingness into existing archival records;
- do not add missingness columns to core archival tables at this stage;
- do not mutate Postgres records;
- do not mutate DO Spaces assets;
- do not treat diagnostics as original metadata.

If persistence is needed later, use a separate snapshot table, not core metadata columns.

Possible future proposal only:

```text
record_diagnostics_snapshots {
  record_id
  pid
  diagnostics_version
  evidence_preset_version
  generated_at
  diagnostics_json
}
```

---

## 6. v0.1 diagnostics status

v0.1 introduced a local additive diagnostics layer.

Important limitation:

> v0.1 flat missingness is experimental and not safe as a standalone interpretive claim.

Example issue discovered:

- `ItemV1.title` was present in the stored item field;
- `payload.title` was absent from the payload snapshot;
- flat v0.1 missingness reported `title` as missing;
- that could be misread by an LLM as “the record has no title,” which is false.

Conclusion:

> Missingness must be scoped.

---

## 7. v0.2 scoped missingness

v0.2 is the defensible path.

The scoped model distinguishes at least five scopes:

1. `itemFieldMissingness`
2. `payloadSnapshotMissingness`
3. `assetMissingness`
4. `graphqlExposureMissingness`
5. `llmEvidenceMissingness`

### 7.1 Required status values

Use explicit statuses rather than a flat missing list.

Recommended values:

```text
present
present_false
present_zero
missing_null
missing_key
blank
empty_list
placeholder
not_exposed_by_graphql_preset
present_at_asset_scope
not_applicable_at_this_scope
unknown_until_docling
requires_human_review
```

Rules:

- `false` is not missing.
- `0` is not missing.
- `""` or whitespace is blank.
- `—` is a placeholder.
- missing keys are different from keys present with `null`.
- absence from GraphQL is not archival absence.
- absence from Docling text is not proof that the source asset contains no text.

### 7.2 Fixture-first implementation

v0.2 should be developed against saved GraphQL fixtures first, not live DB objects.

Current/expected fixture paths:

```text
docs/graphql_fixtures/local_bruce_archer_llm_public_evidence.json
docs/graphql_fixtures/local_bruce_archer_scoped_missingness_v02.json
```

Additional desired fixtures:

```text
docs/graphql_fixtures/local_pdf_rich_llm_public_evidence.json
docs/graphql_fixtures/local_pdf_rich_scoped_missingness_v02.json
docs/graphql_fixtures/local_context_rich_llm_public_evidence.json
docs/graphql_fixtures/local_context_rich_scoped_missingness_v02.json
```

All fixtures committed/shared must exclude signed URLs.

---

## 8. Authority data: include, but treat as provisional

When preparing the ML/LLM repository, pull the authority data from Postgres into the LLM/retrieval pipeline.

This should include, where available:

- people authorities;
- corporate/organisational authorities;
- funder authorities;
- project/job authorities;
- collection/fonds/series relationships;
- creator/contributor links;
- interviewee/interviewer links;
- project team/staff fields;
- related entities;
- authority IDs and labels;
- any job numbers or project identifiers;
- authority provenance/status fields, if present.

### 8.1 Rationale

The authority layer should be treated as part of the archive’s computational evidence surface. It defines which people, organisations, projects, jobs, and relationships are currently machine-linkable, searchable, aggregable, and retrievable.

Even where authority data contains errors, omissions, inconsistent naming, or missing job numbers, it should still be included because those imperfections are methodologically important. They help reveal:

- authority gaps;
- uneven institutional recognition;
- people or contributors present in text but absent from structured authority data;
- project/job records that are administratively visible or invisible;
- discrepancies between archival description, asset metadata, and extracted document text;
- places where human review or authority reconciliation is needed.

### 8.2 Critical caution

The LLM must not treat authority data as complete or definitive.

Authority data should be passed with status/provenance information where possible, for example:

```text
authority_present
authority_missing
not_exposed_by_graphql_preset
present_in_postgres_not_exposed_to_llm
candidate_authority_match
requires_human_review
ambiguous_authority
unlinked_name_detected
authority_error_possible
```

The model should use authorities as evidence for linking and retrieval, but not as proof that unlisted people, contributors, communities, or relationships were absent.

### 8.3 Thesis framing

Authority data does not simply organise the archive; it participates in the production of computational visibility. A person, project, funder, or organisation with an authority identifier becomes searchable, linkable, countable, and retrievable. A contributor mentioned only in free text, inconsistently named, or absent from the authority structure may remain computationally obscure.

Therefore, the ML/LLM pipeline should ingest authorities not because they are perfect, but because their presence, absence, and incompleteness are central to the project’s critical investigation of archival missingness and obscurity.

---

## 9. Current local archive scale

At the time of this handover, there are approximately **19 published PID records** in the local/admin system.

The next local step is a read-only diagnostic sweep across all 19 PIDs.

This should produce reports only, not update the database.

Suggested outputs:

```text
docs/graphql_fixtures/all_records/<pid>_llm_public_evidence.json
docs/graphql_fixtures/all_records/<pid>_scoped_missingness_v02.json

docs/reports/scoped_missingness_v02_all_records.csv
docs/reports/scoped_missingness_v02_all_records.json
```

Aggregate report should include:

- PID;
- title;
- status;
- level;
- asset counts;
- PDF count;
- JPG count;
- TIFF count;
- item title status;
- caption status;
- parent collection status;
- attachment role status;
- date status;
- rights field status;
- authority/context exposure;
- extracted text status;
- main evidence/visibility label;
- main interpretation caution.

---

## 10. ML/LLM repo ingestion requirements

The ML/LLM repo should ingest four kinds of material separately.

### 10.1 Metadata evidence

From `llm_public_evidence.graphql`.

Use for:

- item title/caption;
- date fields;
- status;
- PID;
- asset IDs;
- rights fields;
- exposed context fields;
- public/stable asset URLs where appropriate;
- scoped diagnostics.

Do not require signed URLs.

### 10.2 Authority data

From Postgres/admin authority tables and/or API exposure where available.

Use for:

- linking people, organisations, projects, funders, jobs, collections, series, and related entities;
- retrieval expansion and entity-aware search;
- identifying structured authority gaps;
- detecting candidate unlinked names in Docling-extracted text;
- human-review queues for ambiguous or missing authority links.

Do not treat authorities as complete, neutral, or definitive.

### 10.3 Operational asset access

From `docling_asset_fetch.graphql`.

Use for:

- fetching PDFs/TIFFs/JPGs;
- Docling/OCR processing;
- internal ingestion only.

Do not pass this raw operational payload to the LLM.

### 10.4 Extraction output

From Docling/OCR pipeline.

Use for:

- text chunks;
- page-level references;
- extraction confidence;
- extraction warnings;
- tables/figures;
- image-only warnings;
- provenance mapping back to PID and asset ID.

---

## 11. Recommended chunk metadata contract

Each chunk used for retrieval/training should carry enough provenance to reconstruct its evidence basis.

Recommended chunk metadata:

```json
{
  "pid": "873981573030",
  "record_id": "internal optional",
  "title": "Record title if exposed",
  "asset_id": "stable asset id",
  "asset_role": "pdf_master | pdf_display | tiff_master | jpg_display | jpg_thumb",
  "filename": "source filename",
  "source_surface": "llm_public_evidence + authority_data + docling_output",
  "page_number": 1,
  "chunk_index": 0,
  "docling_extraction_status": "completed | completed_with_warnings | failed | not_processed",
  "ocr_required": true,
  "ocr_confidence": null,
  "text_extracted": true,
  "rights_statement_uri": "if exposed",
  "rights_holders": "if exposed",
  "date_display": "if exposed",
  "date_certainty": "exact | circa | estimated | unknown",
  "authority_status": "authority_present | authority_missing | ambiguous_authority | not_exposed_by_graphql_preset | requires_human_review",
  "authority_ids": [],
  "candidate_unlinked_names": [],
  "scoped_missingness_version": "v0.2",
  "evidence_limitations": [
    "authority fields not exposed by GraphQL preset",
    "OCR confidence unknown",
    "asset is image-derived"
  ]
}
```

---

## 12. Training / supervision guidance

The model should be trained or instructed to make cautious claims.

### 12.1 Desired model behaviour

The model should:

- cite or reference PID/asset/chunk evidence;
- distinguish metadata from extracted text;
- distinguish absence from non-exposure;
- distinguish authority presence from authority completeness;
- flag evidence limitations;
- avoid equating rights holder with creator;
- avoid equating digitisation with discoverability;
- avoid inferring marginalised identity categories from absence alone;
- suggest human review where authority gaps, candidate unlinked names, or unclear provenance are detected;
- explain that a record may be technically visible but contextually obscure.

### 12.2 Undesired model behaviour

The model should not:

- say “the archive has no title” when only `payload.title` is absent;
- infer a person or community is marginalised solely from missing metadata;
- treat `signed_url` as archival evidence;
- treat public/published status as contextual completeness;
- treat OCR failure as proof that the document has no text;
- treat absence from GraphQL as absence from Postgres/admin/archive;
- treat absence from authority tables as proof that a contributor did not exist;
- treat authority records as complete or error-free;
- silently collapse asset-level rights into item-level authorship.

### 12.3 Example supervised labels

Useful training examples should include paired outputs such as:

#### Input condition

```text
Item title present.
Payload snapshot title absent.
Asset label present.
Authority fields not exposed.
PDFs present.
Docling text unknown.
```

#### Preferred model statement

```text
The record is identifiable at item level and has labelled assets, but the payload snapshot does not expose a title field. Authority relationships are not exposed in this evidence surface, so their absence should not be read as archival absence. PDFs are available, but extracted text is not yet confirmed.
```

#### Rejected model statement

```text
The record has no title and no authorities.
```

Reason rejected: overclaims from scoped non-exposure.

#### Authority-focused input condition

```text
A person or contributor name appears in extracted text.
No matching authority ID is exposed in the LLM/public GraphQL preset.
The relevant authority table may be incomplete or not yet reconciled.
```

#### Preferred model statement

```text
The extracted text appears to mention a possible contributor or named person, but no corresponding authority identifier is exposed in the current evidence surface. This should be treated as a candidate authority gap requiring human review, not as proof that the person is absent from the archive.
```

#### Rejected model statement

```text
This person is not part of the archive because there is no authority record.
```

Reason rejected: treats authority non-exposure or incompleteness as archival absence.

---

## 13. Retrieval and RAG guidance

Retrieval should use scoped metadata, authority data, and diagnostics to avoid misleading ranking.

Useful retrieval filters/facets later:

- records with PDFs;
- image-only records;
- records requiring OCR;
- records with extracted text;
- records with authority/context fields not exposed;
- records with uncertain dates;
- records with weak parent/collection context;
- records where title is present at item scope but absent in payload snapshot;
- records with rights statement present;
- records with rights holder present at asset scope;
- records with linked authorities;
- records with candidate unlinked names;
- records requiring authority reconciliation;
- records with missing or ambiguous job numbers.

The retrieval layer should preserve evidence limitations in the context window.

Example prompt context should include:

```text
Evidence limitations:
- Authority fields are not exposed by this GraphQL preset.
- Extracted text is unknown until Docling processing completes.
- Asset rights holders are present at asset scope; this does not establish creator identity.
- Candidate names in extracted text require authority reconciliation before being treated as structured entities.
```

---

## 14. UMAP / visual analytics guidance

UMAP and clustering should be interpreted as maps of **processed evidence**, not maps of the total archive.

Before running UMAP, record:

- number of records included;
- number of assets included;
- number of chunks included;
- number of PDFs processed;
- number of image-only assets;
- number of records excluded;
- reason for exclusions;
- authority data coverage;
- number of linked authorities;
- number of candidate unlinked names;
- embedding model/version;
- chunking strategy;
- diagnostics version.

UMAP labels should include evidence coverage warnings where necessary.

Example:

```text
This cluster reflects OCR-extracted text from PDF-bearing records only. Image-only TIFF records without extracted text are underrepresented.
```

Another example:

```text
This entity cluster reflects currently exposed authority links and candidate names detected in extracted text. It should not be read as a complete map of contributors or relationships.
```

---

## 15. Rights and security cautions

Do not train on or store:

- unredacted signed URLs;
- access tokens;
- credentials;
- cookies;
- internal-only fetch URLs;
- private operational secrets.

Signed URLs may be used only transiently for internal Docling fetch operations.

They must not appear in:

- LLM prompts;
- public fixtures;
- training data;
- supervised examples;
- exported reports;
- model outputs.

---

## 16. Suggested immediate next steps for ML/LLM repo

1. Ingest the saved LLM/public fixture format.
2. Ingest scoped missingness v0.2 diagnostics.
3. Pull authority data from Postgres/admin into a provisional authority layer.
4. Ingest Docling outputs separately.
5. Build a chunk metadata schema that preserves PID, asset ID, page, extraction status, rights, authority status, and evidence limitations.
6. Build a small supervised training/evaluation set focused on:
   - avoiding overclaims;
   - distinguishing non-exposure from absence;
   - citing evidence limitations;
   - explaining asset-rich but context-poor records;
   - distinguishing authority gaps from absence of contribution.
7. Run UMAP only after recording evidence coverage and authority coverage.
8. Build evaluation prompts that test whether Granite respects scoped missingness and provisional authority data.

---

## 17. Evaluation checklist

A model answer is acceptable only if it:

- identifies the evidence it used;
- states when a field is not exposed rather than absent;
- distinguishes item, payload, asset, GraphQL, Docling, authority, and LLM evidence scopes;
- does not infer sensitive identity or marginalisation from absence alone;
- flags uncertain dates and OCR/extraction limitations;
- treats rights holder as rights information, not creator information;
- treats authority data as provisional and possibly incomplete;
- does not treat authority non-exposure as proof of absent contribution;
- preserves PID, asset, and authority provenance where available.

---

## 18. Key thesis formulation

Recommended wording:

> The project treats the GraphQL payload as a critical evidence surface rather than a neutral API response: it defines what the LLM can know, what the retrieval layer can retrieve, what the visual analytics can map, and where archival absence, technical non-exposure, and computational obscurity must be distinguished.

Another useful formulation:

> Missingness diagnostics are not claims about the ontology of the archive. They are versioned readings of what is exposed to a particular computational evidence surface.

Authority-focused formulation:

> Authority data does not simply organise the archive; it participates in the production of computational visibility. A person, project, funder, or organisation with an authority identifier becomes searchable, linkable, countable, and retrievable, whereas contributors mentioned only in free text, inconsistently named, or absent from the authority structure may remain computationally obscure.

---

## 19. Handover summary

Before model training, the ML/LLM repo must understand that:

- the archive is not equivalent to the GraphQL payload;
- the GraphQL payload is not equivalent to the LLM prompt;
- asset availability is not equivalent to text availability;
- digitisation is not equivalent to discoverability;
- missing authority exposure is not proof of absent contribution;
- authority data is useful even when incomplete or erroneous;
- diagnostics must be scoped, versioned, and treated as evidence limitations;
- authority data should be included as a provisional evidence layer, not a ground-truth ontology.

The next academic year’s LLM, UMAP, retrieval, and supervised-training work should build on this accountability layer rather than bypass it.
