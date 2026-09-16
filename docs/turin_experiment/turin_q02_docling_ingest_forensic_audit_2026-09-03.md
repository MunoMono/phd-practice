# Turin Q02 Docling and Ingest Forensic Audit

Audit date: 2026-09-03

## Scope and controls

This is a read-only audit of the production `testamentary-traces` database, retained manifests/logs, mounted storage, and live public Archive GraphQL metadata. No PDF was downloaded, no Docling or OCR process was run, and no document, chunk, corpus, or historical run was modified. Qwen calls: `0`.

## Finding

The three Q02 assets are not absent from the Archive. They are absent from the original 109-row asset-selection inventory and from every retained local documentary representation. The old exporter used an oversized nested `records_v1` request and exact master-filename matching. The live target records expose a canonical `pdf_master` asset but only a `pdf_display` access file with a `__display` filename. That filename relationship cannot pass the old exact-match rule.

The current Archive schema exposes no asset created, modified, or eligibility-history timestamp. Therefore this audit cannot prove whether the assets were added or had their eligibility changed after the 2026-08-14 freeze. It can prove that they were not selected by the retained freeze inventory, were never represented in retained ingestion state, and have no recoverable Docling output in the audited storage.

## Q02 asset forensic audit

| Asset PID | Label | Record PID | Attached-media PID | Freeze manifest | Local document/chunks | Retained Docling/ingest evidence | Root-cause classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `062054716175` | Professor Archer course, spring term | `989478384551` | `321843234637` | Absent | None in current or legacy corpus | None | `UNKNOWN`: non-selection is proven; either later Archive state or historic discovery/mapping failure cannot be separated without Archive history. |
| `852120727979` | Memo from Frank Height to Bruce Archer on allocation of tutorial days of research staff | `475236004017` | `940221533316` | Absent | None in current or legacy corpus | None | `UNKNOWN`: same evidence boundary. |
| `723660822664` | Richard Langdon introductory week, autumn term | `475236004017` | `940221533316` | Absent | None in current or legacy corpus | None | `UNKNOWN`: same evidence boundary. |

### `062054716175` identity chain

- Canonical asset ID: `aea78f2ca8d19f4bc3c36732f5319046399be04847c42af5b066638fa668c94b`
- Canonical filename: `aea78f2ca8d19f4bc3c36732f5319046399be04847c42af5b066638fa668c94b.pdf`
- Canonical master key: `prod/records/321843234637/master/aea78f2ca8d19f4bc3c36732f5319046399be04847c42af5b066638fa668c94b__pdf_master__v1.pdf`
- Display filename: `aea78f2ca8d19f4bc3c36732f5319046399be04847c42af5b066638fa668c94b__display.pdf`
- Display source URI: `https://archive-media.lon1.digitaloceanspaces.com/prod/records/321843234637/derivative/aea78f2ca8d19f4bc3c36732f5319046399be04847c42af5b066638fa668c94b__pdf_display__v1.pdf`
- Current policy: `use_for_ml=true`; `ml_pages=null`; archival display date `March 1976` (`197603`).

### `852120727979` identity chain

- Canonical asset ID: `618cb52e6d7ff79b0f9a0e2b6d43448c9146841d30538fc8309babb64a35a52c`
- Canonical filename: `618cb52e6d7ff79b0f9a0e2b6d43448c9146841d30538fc8309babb64a35a52c.pdf`
- Canonical master key: `prod/records/940221533316/master/618cb52e6d7ff79b0f9a0e2b6d43448c9146841d30538fc8309babb64a35a52c__pdf_master__v1.pdf`
- Display filename: `618cb52e6d7ff79b0f9a0e2b6d43448c9146841d30538fc8309babb64a35a52c__display.pdf`
- Display source URI: `https://archive-media.lon1.digitaloceanspaces.com/prod/records/940221533316/derivative/618cb52e6d7ff79b0f9a0e2b6d43448c9146841d30538fc8309babb64a35a52c__pdf_display__v1.pdf`
- Current policy: `use_for_ml=true`; `ml_pages=null`; archival display date `May 1975` (`197505`).

### `723660822664` identity chain

- Canonical asset ID: `66574cf9c6229653814a37dbc092c887a409aab7dd3445bb39be4d0a1d4e121b`
- Canonical filename: `66574cf9c6229653814a37dbc092c887a409aab7dd3445bb39be4d0a1d4e121b.pdf`
- Canonical master key: `prod/records/940221533316/master/66574cf9c6229653814a37dbc092c887a409aab7dd3445bb39be4d0a1d4e121b__pdf_master__v1.pdf`
- Display filename: `66574cf9c6229653814a37dbc092c887a409aab7dd3445bb39be4d0a1d4e121b__display.pdf`
- Display source URI: `https://archive-media.lon1.digitaloceanspaces.com/prod/records/940221533316/derivative/66574cf9c6229653814a37dbc092c887a409aab7dd3445bb39be4d0a1d4e121b__pdf_display__v1.pdf`
- Current policy: `use_for_ml=true`; `ml_pages=null`; archival display date `October 1977` (`197710`).

For each target: freeze-time eligibility is not observable because the asset is absent from the manifest; it was not selected for ingestion; no Docling attempt, failure, deduplication, quarantine, OCR output, document row, chunk row, or historical-document mapping is retained; and a later Archive addition or eligibility change is not observable from the public schema.

## Original 97 eligible / 95 ingestible reconciliation

The authoritative freeze manifest, timestamped `2026-08-14 05:40:56 UTC`, contains exactly 109 rows: 97 eligible (`62` unrestricted and `35` page restricted) plus 12 explicit `use_for_ml=false` exclusions. The target PIDs are absent.

The frozen corpus `corpus_f40d78dbce52` contains 95 documents and 12,884 chunks, created between `2026-08-14 06:11:03 UTC` and `07:38:58 UTC`. The difference of two is retained as two eligible, unmaterialised source rows, not a Q02 condition:

| Asset PID | Asset ID | Record / media | Status |
| --- | --- | --- | --- |
| `094896213245` | `7903ef10cbf52e1b4d3377845e6544484c0b05374f73bc90cf7557d191b2977d` | `989478384551` / `321843234637` | `eligible_unrestricted`, `unverified_remote_source`, no chunks |
| `359001684832` | `491fdbf612455d205b8c3d5fbff488cdc69b256e2fd5095d8317917683b874fc` | `989478384551` / `321843234637` | `eligible_unrestricted`, `unverified_remote_source`, no chunks |

Asset `062054716175` shares the same record/media as these two anomalies, but has a distinct asset PID, asset ID, canonical filename, and source URI. The other two Q02 assets share neither anomaly's canonical identity.

## Current 124 ML-eligible reconciliation

| Classification | Count | Evidence |
| --- | ---: | --- |
| Current governed document with chunks | 95 | Exact asset PID or asset ID mapping to `corpus_f40d78dbce52`. |
| Known source-representation mismatch | 2 | Exact current document rows exist but are `unverified_remote_source` and have no chunks. |
| Historical document only | 0 | No current eligible asset maps only to the legacy 606-chunk namespace. |
| Existing Docling output without document | 0 | No source-specific output in database, retained artifacts, mounted logs, or mounted volumes. |
| Ingest failure | 0 | No matching `ingestion_state`, `ml_processing_log`, missingness, or failed document row. |
| Explicitly excluded | 0 | The audited set is restricted to current `use_for_ml=true` assets. |
| Selection/mapping-unresolved expansion | 27 | Present in complete export but absent from the retained August 109-row inventory and freeze manifest. |
| **Total** | **124** | |

The 27 are not evidenced as archival additions: the public API lacks the necessary temporal fields. They are evidenced as an expansion exposed by the corrected discovery traversal. One record (`232731654562`) was absent from the old inventory; the other 26 assets are newly exposed within records that the old inventory already partially represented. The exact historic cause for each is therefore not reducible below `UNKNOWN` without an Archive revision/history source.

## Existing Docling outputs recoverable

None for the three Q02 assets or the 27-asset expansion. The backend bind mount retains code and artifacts; its only persistent mounted data volume is backend logs. Searches found no source-specific Docling JSON, Markdown, page text, OCR output, temporary extraction directory, cached extraction, or source-level log outside Python package resources. `documents.extracted_text`, `documents.ocr_text`, and `document_chunks` also contain no exact target identity.

## Assets with no recoverable local documentary representation

These are the 27 current ML-eligible assets absent from the original 109-row inventory. They require a first-time local extraction only after a separate, approved successor-corpus decision:

`677535823295`, `307228090394`, `024904482450`, `482546702591`, `282880471664`, `955898485395`, `811851964393`, `372992327673`, `162507935500`, `062054716175`, `605448081264`, `108613991466`, `192332138415`, `898142847946`, `721082739050`, `800173568827`, `665092576421`, `852120727979`, `723660822664`, `572636842017`, `170011218223`, `733098223276`, `674929523479`, `982829068110`, `492782087857`, `636738521596`, `098776258047`.

## Timeline explanation and decision

- 2026-08-07: the retained re-enrichment inventory had 109 rows and 97 eligible assets; 95 document rows were Docling-complete and two were unverified remote sources.
- 2026-08-14: the retained authoritative 109-row manifest was frozen; the 95-document corpus was chunked.
- 2026-09-03: the corrected Archive traversal produced 136 canonical masters and 124 current eligible assets, exposing 27 asset identities absent from the old inventory, including all three Q02 assets.
- Archive-created, Archive-modified, and historical `use_for_ml` transition dates are unavailable, so a late-addition or late-policy-change explanation remains unproven.

The frozen 95-document corpus is **QUALIFIED** as historically valid for the original, retained 97-eligible/109-asset selection snapshot: its documented two representation mismatches are preserved and it is not rewritten. The current Archive API exposes a materially larger ML-eligible evidence surface: **YES**.

A successor corpus is **MAYBE**, not yet required by this audit alone. It would be justified only after a researcher accepts the corrected source-selection scope and wants to use the 27 assets with no recoverable local documentary representation. Reprocessing required now: **NO**. Historical data modified: **NO**.