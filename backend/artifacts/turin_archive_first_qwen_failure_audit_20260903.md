# Turin Archive-First Qwen Failure Audit

- Protocol: `turin-archive-first-qwen-evaluation-v1`
- Corpus: `corpus_turin_archive_first_cc11e8678168`
- Audit method: persisted evaluation artifacts only; no retrieval or inference was rerun.

## Findings

| Question | Recorded parser evidence | Classification | Fixed sources | Documentary-excerpt characters | Raw/generation retained |
| --- | --- | --- | ---: | ---: | --- |
| Q01 | `EOF while parsing a value` at line 58, column 18; captured parser preview ends at a `statement` field | `OUTPUT_TRUNCATION` | 36 | 11,746 | No |
| Q06 | `EOF while parsing a value` at line 64, column 209; preview ends after a statement string and comma | `OUTPUT_TRUNCATION` | 36 | 10,899 | No |
| Q07 | `EOF while parsing a string` at line 68, column 42; preview ends inside `The DEU's contribution` | `OUTPUT_TRUNCATION` | 32 | 9,293 | No |
| Q08 | `EOF while parsing a string` at line 60, column 82; preview ends inside a statement string | `OUTPUT_TRUNCATION` | 37 | 11,914 | No |

All four failures have a non-empty JSON prefix and an EOF parse error. This rules out `EMPTY_OUTPUT`, `MODEL_REFUSAL`, and a documented `TRANSPORT_FAILURE`. It establishes missing closing JSON structure, not a judgement about historical reasoning quality.

The runner's failure handler retained the parser exception but discarded the raw response and generation envelope after parsing failed. Consequently, actual returned length, Ollama `done_reason`, actual output-token count, whether a full semantic answer preceded the cutoff, and the exact position of omitted closing braces are unavailable. The configured output limit was 768 tokens. The response did not pass the JSON parser, so closing braces are necessarily absent from the persisted parseable response.

## Complexity Pattern

Failed questions averaged 35.25 sources and 10,963 excerpt characters; completed questions averaged 34.0 sources and 10,470 excerpt characters. The failed set contains three contested-interpretation questions (Q06-Q08), but Q05, also contested, completed. No failed-question input-token estimate or returned-generation metadata was retained. The available data supports a modest association with somewhat larger evidence sets and contested questions; it does not establish causation.

## Q12 Provenance Audit

- Section: `direct_documentary_evidence`
- Generated claim: `There is no direct documentary evidence that Henrietta Ryott was involved in the DDR between 1973 and 1977.`
- Source IDs: omitted.
- Fixed excerpts containing `Ryott`: 0 of 35.
- Classification: `CITATION_FORMAT_FAILURE`.

The wording is a bounded conclusion about the supplied excerpts, not a claim of archival absence. It is semantically aligned with scoped missingness, but it is incorrectly placed in the direct-evidence section and lacks the required source IDs. The record therefore remains a provenance failure; it is not silently repaired.

## Protocol Diagnostic

Primary observed limitation: `STRUCTURED_OUTPUT_RELIABILITY`.

Supporting factors: `OUTPUT_TOKEN_BUDGET` and `PROMPT_SCHEMA_COMPLEXITY` are plausible contributors because every failure ends at an incomplete JSON position under a 768-token envelope. `MODEL_REASONING`, `CONTEXT_LENGTH`, and `TRANSPORT` cannot be determined from the preserved failed artifacts.
