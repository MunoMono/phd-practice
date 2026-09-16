# Turin Retrieval Protocol v1.2

## Status

Prospective output-capacity amendment. It supersedes v1.1 only for the governed structured-output limit. It does not change approved Retrieval Plans, the corpus, PostgreSQL FTS, ranking, top-k, Granite model, prompt meaning, response schema, input ceiling, or v1.1 context assembly.

## Motivation

The 350-token structured-output limit reached `done_reason = length` in the first generation of Q05 and in both the original and repair generations of non-evaluable Q06 (`experiment-2bc7c95f1c98`). The response schema requires long source PIDs, chunk IDs, quotations, and field names even for concise responses. This amendment addresses output serialization capacity only; it does not improve or change interpretation.

## Governed Change

For future v1.2 executions, `max_tokens` is 500. Temperature remains 0.0, top-p remains 1.0, `do_sample` remains false, and seed remains 0. The same 500-token limit applies to the existing single formatting/schema-only repair call.

## Unchanged Controls

- Input ceiling: 6,000 characters.
- Context assembly: deterministic max-min fair representation of every retrieved top-k source.
- Evidence priority: documentary evidence before authority context.
- Output contract: native Ollama JSON-schema output using `turin-archival-analysis-response-v1`.
- Retrieval: approved plans, PostgreSQL FTS, ranking, corpus-wide scope, and top-k 5.
- Model: `granite3.1-dense:2b-instruct-q4_K_M` with deterministic generation settings.

## Run Interpretation

Q01-Q05 remain recorded under their original execution protocols and are not invalidated. Q06 remains `NON-EVALUABLE — OUTPUT TOKEN EXHAUSTION` under v1.1. A future Q06 replacement requires separate authorization and is not created by this amendment.