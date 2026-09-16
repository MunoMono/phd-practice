# Turin v2 Qwen Runtime

The original 12-question Turin formal experiment used Granite 3.1 2B and is preserved as an immutable historical dataset. The subsequent Turin v2 research instrument uses Qwen3 8B Q4_K_M as its active local inference model.

## Active Runtime

- Runtime identifier: `turin-runtime-v2`
- Provider: Ollama
- Exact model: `qwen3:8b-q4_K_M`
- Configuration source: `TURIN_MODEL`
- Status endpoint: `/api/runtime/health`

The active runtime fails clearly when the configured model is unavailable. It has no Granite fallback. Ollama generation uses `think: false` so structured-output requests do not expose model reasoning text.

## Qwen Comparison Series

The planned comparison family is `turin-qwen-comparison-v2`, under the distinct protocol identity `turin-comparison-protocol-v2.0-qwen`.

It will compare Qwen3 8B against the completed Granite formal experiment using the same frozen corpus (`corpus_f40d78dbce52`), exact registered question wording, final plan used by each completed run, retrieval implementation, ranking, context construction, provenance validation, and evidence boundaries. It must persist `qwen3:8b-q4_K_M` for every comparison run and never overwrite the Granite records.

Before any comparison execution, an append-only governance registration must derive the twelve final plan IDs directly from completed persisted runs and bind each comparison authorization. No Qwen comparison runs are authorized or executed by this document.