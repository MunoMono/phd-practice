# Turin Experiment Method Note

## Frozen corpus

All current runs must use `corpus_f40d78dbce52`, the bounded 2026 Turin corpus: 97 eligible members, 95 controlled-ingestible PDFs, 12,884 current chunks, and 35 restricted assets with zero page-scope violations. The frozen manifest SHA-256 is `aed395d090aa16a1a6b435746b1e36410374428e261a80287fa587c8a5818a76`.

## Retrieval and bounded inference

Retrieval is PostgreSQL FTS only. Ranking is preserved before context assembly. `turin-context-budget-v2` packs ranked retrieved chunks against the complete rendered Granite input budget of 6,000 characters: system prompt, question/template, response schema, source evidence headers/text, and any separately labelled authority context. Full catalogue metadata remains in immutable retrieval snapshots; supplied evidence headers include only citation-relevant title/date/creator/archive-reference/document-type fields.

The builder measures fixed prompt characters first, then packs evidence in retrieval rank order. A source block is included whole when it fits. If its text does not fit but its complete provenance header does, its text is deterministically excerpted from the beginning to the remaining character count. A header is never removed or truncated. Chunks whose headers cannot fit remain retrieved but are not supplied. There is no post-construction prompt truncation.

Future immutable runs record the input budget, fixed prompt characters, available evidence characters, assembled input characters, context-builder version, and an evidence decision for every retrieved chunk: rank, chunk ID, original and supplied character counts, included state, excerpt state, exclusion reason, full retrieved text, and supplied excerpt.

Prompt version `v3` additionally requests a concise schema-complete response (short answer and at most one concise item per category) so the constrained local runtime can return complete JSON within its fixed 350-token response ceiling. This changes neither corpus, retrieval, model family, nor the 6,000-character input cap. It does not alter the earlier `experiment-a5c3f1f5c5d5` commissioning failure, which remains valid evidence of the previous context-assembly boundary.

Known-relationship commissioning prompt version `v4` further asks for one short evidence item and empty non-applicable arrays. It is a resource-constrained commissioning profile, not a claim that other research cases lack contradiction, missingness, inference, or follow-up searches.

## Evidential layers

Source-document evidence is not catalogue metadata or authority context. Authorities may be used for entity resolution, transparent query expansion, filters, optional structural context, and corroborative checking. They never become documentary evidence. When authority context is supplied it is separately labelled and persisted with source, role, fields, snapshot/version, and whether it influenced Granite.

## Missingness

Missingness statements are limited to the query, retrieved passages, supplied context, or ingested corpus. They do not claim historical, archive-wide, or ontological absence. Researcher assessment remains separate and mutable; model output is not an autonomous quality verdict.
