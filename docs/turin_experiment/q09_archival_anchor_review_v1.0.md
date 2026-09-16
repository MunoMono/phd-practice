# Q09 Archival Anchor Review

## Research question

Does the current digitised corpus establish why the decision to close the DDR was made?

## Late-period corpus evidence

The frozen corpus (`corpus_f40d78dbce52`) contains two late-period institutional documents with explicit status-change wording relevant to Q09.

| Document ID | Record PID | Asset PID | Date/year | Source type | Archive reference | Relevant pages/chunks | Explicit organisational-change wording |
|---|---|---|---:|---|---|---|---|
| `doc_896818280654_09993a200136` | `873981573030` | `162595746534` | 1985 | PDF memorandum | No reference recorded in frozen catalogue metadata | Page 1: `turin_doc_896818280654_09993a200136_1_6_375636c2d50918e8` and `_1_7_f5a5bcdcde4175d9`; page 3: `_3_10_7a212e735b463288` | Yes. Reports the 21 November 1984 Senate resolution that Design Research and Environmental Design should close; records the proposed merger, later abandonment of that merger, proposals to convert activities into research-support services, and the Rector's stated view. |
| `doc_521129471965_1ff812723a53` | `788065484899` | `208660726919` | 1985 | PDF Rector's report | No reference recorded in frozen catalogue metadata | Page 23: `turin_doc_521129471965_1ff812723a53_23_9_42ab372ee0c3f729` | Yes. States: `The Department of Design Research will close in August 1986.` |
| `doc_338541406157_15ef98daa711` | `873981573030` | `266939971608` | 1985 | PDF proposal | No reference recorded in frozen catalogue metadata | Page 1: `turin_doc_338541406157_15ef98daa711_1_1_09b7c5f1bc79b918` | Institutionally relevant but not an explicit closure record. Opens `Proposed Inter-University INSTITUTE OF DESIGN RESEARCH`. |
| `doc_521129471965_974869d7cd51` | `788065484899` | `226920447318` | 1984 | PDF Rector's report | No reference recorded in frozen catalogue metadata | Relevant institutional material in page 3 and page 24 chunks | No explicit DDR closure wording found. It records college funding pressure and DEU organisational concerns, neither of which should be inferred as the cause of DDR closure. |

The 1985 memorandum is a source document, not an authority assertion. Its relevant wording is precise but describes a proposed merger that the Academic Policy Committee subsequently ceased to support. The Rector's report independently records a future closure date. Neither record alone permits the system to infer a complete causal explanation beyond what its text establishes.

## Literal evidence

The following diagnostic literal searches were run against the frozen corpus. Generic terms were not promoted solely because they occurred.

| Wording | Documentary occurrences | Documents | Finding |
|---|---:|---:|---|
| `Senate resolved` | 1 | 1 | In the 1985 memorandum: Senate resolved on 21 November 1984 that the departments of Design Research and Environmental Design should close. |
| `departments of Design Research and Environmental Design` | 1 | 1 | Same memorandum; names the departments proposed for closure and merger. |
| `Department of Architectural and Design Studies` | 1 | 1 | Same memorandum; names the proposed merged department. |
| `Academic Policy Committee` | 2 | 1 | Same memorandum; records that it later ceased to support the merger's pursuit. |
| `conversion of some or all of the activities of the Department of Design Research` | 1 | 1 | Same memorandum; identifies alternative proposals for research-support services. |
| `no place for the continued pursuit of the discipline of Design Research` | 1 | 1 | Same memorandum; reports the Rector's position at a 31 January 1985 Board of Faculty meeting. |
| `The Department of Design Research will close in August 1986` | 1 | 1 | In the 1985 Rector's report, page 23. |
| `reorganisation` / `restructuring` / `transfer` / `merger` | 4 / 3 / 27 / 3 | 4 / 3 / 18 / 1 | Most occurrences are unrelated institutional, educational, technical, or project contexts. Only the merger occurrence above is specific to DDR closure. |
| `disbanding` / `dissolution` / `termination of the department` / `status change` | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | No literal frozen-corpus support. |

## Catalogue/authority evidence

Catalogue metadata provides stable document titles and PIDs for the two relevant records: `The future of the Department of Design Research memo` (record PID `873981573030`) and `Rector's report` (record PID `788065484899`). The frozen metadata has no archive reference, scope-and-content note, or explicit closure relationship for either record.

Existing authorities add period context but do not replace documentary evidence:

- `ref_ddr_period` `1984-85`: `Institutional decline`, described as `Stevens era; autonomy curtailed; closure in motion`.
- `ref_ddr_period` `1979-80`: `Transition to college funding (1979-80)`, described as externally funded work being wound up and DDR becoming a wholly college-funded teaching department.
- `ref_fonds` `DDR`: `DDR fonds`.

No authority record provides a stable closure-event identifier, successor/predecessor relation, merger record, or end-date specifically for the Department of Design Research. Authority period labels remain contextual assertions and must remain separately labelled from the memorandum and Rector's report as documentary evidence.

## Candidate anchors

| Candidate anchor | Evidence source | Documentary occurrences | Documents | Specificity to DDR closure | Risk |
|---|---|---:|---:|---|---|
| `The Department of Design Research will close in August 1986` | 1985 Rector's report, record PID `788065484899`, page 23 | 1 | 1 | Exact institutional closure statement and date. | LOW |
| `Senate resolved` | 1985 `The future of the Department of Design Research memo`, record PID `873981573030`, page 1 | 1 | 1 | Explicit decision-process wording, but not specific without the accompanying department phrase. | MEDIUM |
| `departments of Design Research and Environmental Design` | Same 1985 memorandum, page 1 | 1 | 1 | Names the Department of Design Research in the proposed closure/merger decision. | LOW |
| `Department of Architectural and Design Studies` | Same 1985 memorandum, page 1 | 1 | 1 | Names proposed successor department; merger was later not pursued. | MEDIUM |
| `conversion of some or all of the activities of the Department of Design Research` | Same 1985 memorandum, page 1 | 1 | 1 | Specific alternative institutional proposal, not itself a final closure decision. | MEDIUM |
| Catalogue title `The future of the Department of Design Research memo` | Frozen document catalogue, record PID `873981573030` | 0 in chunk text confirmed here | 1 catalogue record | Stable provenance pointer, but title metadata is not itself an FTS lexical facet. | MEDIUM |

## Recommended classification

**B. Q09 READY WITH CAUTION**

A defensible archival anchor exists for the institutional closure event: the 1985 Rector's report supplies an exact closure statement and date, while the contemporaneous memorandum supplies the Senate-resolution and subsequent institutional-proposal context. The evidence is concentrated in two records, and the memorandum itself records that the proposed merger was later abandoned. Therefore the plan can retrieve the closure decision/status evidence, but must not pre-encode or infer a complete explanation of why the closure was made.

## Proposed Q09 retrieval facet

**Institutional closure decision/status**

- `The Department of Design Research will close in August 1986`
- `departments of Design Research and Environmental Design`
- `Senate resolved`

The three values are alternatives in one facet under the existing compiler semantics. They are exact source-document wording, not generated synonyms. They should be used together with the existing institutional identity facet (`Department of Design Research`, `DDR`) when Q09 is later revised for final approval. No authority-linked document restriction is proposed.

## Methodological note

This recommendation is based on explicit source wording and stable record provenance, not on chronology, a generic closure term, or the authority period labels. It does not convert limited documentary coverage into historical absence, nor does it convert the closure statement into an unqualified causal account. A formal Q09 result must distinguish what the 1985 sources state about Senate action, merger/conversion proposals, and the August 1986 closure date from any wider explanation that the retrieved corpus does not establish.

## Validation

- Q09 exact question: unchanged.
- Other 11 plans: unchanged.
- Plans approved: 0.
- Plans persisted to production: 0.
- Formal Retrieval Protocol v1.0 runs executed: 0.
- Production writes: none.