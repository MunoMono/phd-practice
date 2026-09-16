# Turin Retrieval Protocol v1.1

## Status

Approved protocol amendment for prospective Q02-Q12 formal runs. It does not modify approved retrieval plans, the corpus, PostgreSQL FTS, ranking, top-k, Granite model, or deterministic generation settings.

## Motivation

The non-evaluable Q02 commissioning observation under v1.0 (`experiment-ac4550d6a2d2`) retrieved five archive-resolved documents but supplied only ranks one and two to Granite. The v1.0 rank-first packing method had 2,765 characters available after fixed prompt material and left 26 characters after two full passages. It omitted the remaining documents and authority context. This amendment corrects that observed evidential-representation limitation; it does not claim to improve answers.

## Deterministic Context Assembly

The total input ceiling remains 6,000 characters. After calculating fixed system prompt, schema, and question characters, v1.1 reserves complete provenance headers and separators for every retrieved top-k documentary result. If those headers do not fit, generation does not begin and the run records `context_representation_failure`.

For source-text lengths $l_i$ and remaining text capacity $T$, v1.1 selects the largest shared character cap $c$ where:

$$
\sum_i \min(l_i, c) \leq T
$$

Each source receives its full direct text where it is no longer than $c$; otherwise it receives the direct source-text prefix ending at the final whitespace before $c$. No LLM summary or rewrite occurs before Granite receives a source passage. Every top-k source therefore has complete provenance representation, rank, and score.

## Authority Context

Documentary evidence has priority. Authority context is evaluated only after mandatory documentary representation. Its immutable snapshot records `requested`, `included`, `omitted_reason`, and `character_cost`. It cannot displace documentary evidence invisibly.

## Output Instrumentation

Generation and the permitted repair call persist the raw Ollama metadata, including `done`, `done_reason`, `eval_count`, `eval_duration`, `prompt_eval_count`, and prompt duration. `done_reason = length` is classified as `output_token_exhaustion`. Raw output, repair output, parsed schema-valid output, provenance validation, and failure-safe display output remain distinct.

Ollama native JSON-schema output uses the persisted schema, schema version, and SHA-256 schema hash. This is an output-serialization implementation correction; prompt substance and governed model settings remain unchanged.

## Immutable Run Fields

Each run retains retrieved rank, score, document ID, source PID, record PID, page, chunk ID, original and supplied lengths, exact supplied excerpt, inclusion status, truncation status, and any omission reason. It also retains the context-assembly protocol marker and authority inclusion decision.

## Relationship to v1.0

- Q01 remains an evaluable primary result under v1.0 and is not invalidated.
- Q02 remains a non-evaluable commissioning observation under v1.0.
- Q02-Q12 are prospective v1.1 formal runs only after their separate authorization.
- A future Q01 v1.1 sensitivity run is not part of the primary dataset unless separately approved.