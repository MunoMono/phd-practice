# Turin Retrieval Plans v1.0 - REVIEW

## Review status

This review applies the vocabulary decisions recorded in `turin_retrieval_vocabulary_audit_v1.0.md`. The exact research questions remain unchanged. Lexical values below are limited to terms the audit classified APPROVE, plus `171` for Q01 as the researcher-directed controlled identity value. No plan is approved, persisted, or executable until final researcher approval.

Compiler semantics are unchanged: alternatives within one facet are ORed and all facets are ANDed. Authority context remains separate from documentary evidence. The authority values listed below are transparent metadata/controlled expansion candidates only; no authority-linked document restriction is proposed.

## Q01 - Job 171 archival anchor

### Exact research question
What documentary traces connect Job 171, “Designer-computer interaction in the early stages of design”, to the people, activities and outputs associated with it?

### Research case
Known relationship case 1

### Primary stress test
Multi-document reconstruction; whether retrieval can assemble people, activity and outputs around a known archival anchor.

### Retrieval scope
`corpus_wide`

### Explicit entities
- `171`
- Pierre Goumain
- Job 171 authority title, recorded as authority context only

### Final proposed lexical facets

#### Facet A - Controlled project/person identity
- `171`
- `Pierre Goumain`

#### Facet B - Evidenced archival computing terminology
- `man-computer interaction`
- `man computer interaction`
- `man-computer design systems`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `171` | `database_authorities.ddr_projects` / project number | controlled_query_expansion | Controlled project identifier, with archive reference-number use. |
| `Pierre Goumain` | `database_authorities.ddr_projects` / project lead | controlled_query_expansion | Canonical authority value and direct documentary wording. |

The canonical title `Designer-computer interaction in the early stages of design` remains separately recorded authority context; it is not a lexical value.

### Approved researcher synonyms
- `man-computer interaction`
- `man computer interaction`
- `man-computer design systems`

### Rejected terms relevant to this plan
- `Job 171`
- `designer computer interaction`
- `designer-computer interaction` as a lexical title-derived substitute

### Rationale
The plan uses the controlled project identity, a documented person, and pre-run evidenced computing language without treating the authority title as documentary wording.

### Methodological risks
- `171` can occur as a reference number outside the project context.
- A required computing facet can exclude administrative/output traces that do not name the technical vocabulary.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q02 - Archer teaching practice

### Exact research question
How is Bruce Archer’s role in teaching and learning practice with students represented across multiple DDR documents, and what aspects of that role are directly evidenced rather than inferred?

### Research case
Known relationship case 2

### Primary stress test
Retrieval versus inference; whether Granite distinguishes documented activity from its own synthesis.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Bruce Archer

### Final proposed lexical facets

#### Facet A - Canonical person identity
- `Bruce Archer`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Bruce Archer` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical authority value with direct corpus usage. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
- `Archer`
- `education`

### Rationale
Only the canonical person value is currently approved. Teaching-context expansions remain outside the executable plan because none received an APPROVE classification.

### Methodological risks
- Person-only retrieval may surface employment or project material without teaching practice.
- The relationship between teaching and learning cannot be encoded until a source-supported contextual term is approved.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q03 - Baynes, Roberts and the Design Education Unit

### Exact research question
What evidence connects Ken Baynes and Phil Roberts within the work of the Design Education Unit?

### Research case
Known relationship case 3

### Primary stress test
Relationship synthesis across dispersed records; whether a connection can be reconstructed without exaggerating its significance.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Ken Baynes
- Phil Roberts
- Design Education Unit

### Final proposed lexical facets

#### Facet A - Named contributors
- `Ken Baynes`
- `Phil Roberts`

#### Facet B - Evidenced unit identity
- `Design Education Unit`
- `DEU`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design Education Unit` | `database_authorities.ref_fonds` / fonds label | controlled_query_expansion | Stable archive-specific unit label. |
| `DEU` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
- `DEU`

### Rejected terms relevant to this plan
None.

### Rationale
The people are alternatives so dispersed records are not lost; the unit facet maintains the archival context.

### Methodological risks
- Ken Baynes and Phil Roberts have corpus support but no matching person authority records.
- The connection may be distributed across records rather than present in a single chunk.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q04 - Wood, console design and ergonomics

### Exact research question
How is John Wood’s role in console design and ergonomics documented across different DDR source types?

### Research case
Known relationship case 4

### Primary stress test
Cross-source retrieval; whether different document types contribute complementary rather than duplicated evidence.

### Retrieval scope
`corpus_wide`

### Explicit entities
- John Wood

### Final proposed lexical facets

#### Facet A - Canonical person identity
- `John Wood`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `John Wood` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical authority value and direct corpus usage. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
None.

### Rationale
Only the canonical person value is approved. The unapproved technical expansion `human factors` is not included.

### Methodological risks
- Person-only retrieval may include projects beyond console design.
- Cross-source comparison depends on later source metadata review, not an FTS filter.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q05 - Meanings of design research

### Exact research question
How was “design research” understood within the DDR, and to what extent do the surviving documents present a consistent conception of it?

### Research case
Contested interpretation case 1

### Primary stress test
False coherence; whether multiple formulations are preserved or collapsed into a single institutional definition.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Department of Design Research
- DDR

### Final proposed lexical facets

#### Facet A - Evidenced institutional identity
- `Department of Design Research`
- `DDR`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
- `Design Research Department`

### Rationale
The review retains only supported institutional wording. No methodology synonym is included because none received approval.

### Methodological risks
- Institution-only retrieval may not distinguish competing uses of `design research`.
- Adding a topical formulation requires a further source-evidence decision.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q06 - Design, science and research

### Exact research question
How do different contributors describe the relationship between design, science and research?

### Research case
Contested interpretation case 2

### Primary stress test
Preservation of distinct voices and positions; resistance to synthesising disagreement into consensus.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Department of Design Research
- DDR

### Final proposed lexical facets

#### Facet A - Evidenced institutional identity
- `Department of Design Research`
- `DDR`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
None.

### Rationale
No approved topical relationship term remains after applying the audit decisions, so the plan records only the supported institutional setting.

### Methodological risks
- Institution-only retrieval is too broad to distinguish contributor positions.
- `scientific method` and `design method` remain excluded pending a source-sense decision.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q07 - Contemporary and retrospective Design Education Unit accounts

### Exact research question
How do contemporary DDR documents and later retrospective accounts differ in their descriptions of the Design Education Unit?

### Research case
Contested interpretation case 3

### Primary stress test
Temporal and retrospective interpretation; whether later accounts are improperly allowed to stabilise contemporary ambiguity.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Design Education Unit
- DEU
- DDR

### Final proposed lexical facets

#### Facet A - Evidenced unit identity
- `Design Education Unit`
- `DEU`

#### Facet B - Evidenced archive context
- `DDR`
- `Department of Design Research`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design Education Unit` | `database_authorities.ref_fonds` / fonds label | controlled_query_expansion | Stable archive-specific unit label. |
| `DEU` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive context. |

### Approved researcher synonyms
- `DEU`

### Rejected terms relevant to this plan
None.

### Rationale
The lexical plan retrieves the evidenced unit in its archive context. Contemporary/retrospective classification is performed during document and date review, not by a preferred FTS term.

### Methodological risks
- The ANDed archive-context facet can exclude relevant DEU records that omit the DDR wording.
- `recollection` remains excluded to avoid favouring retrospective accounts.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q08 - Systematic design process

### Exact research question
What competing interpretations of systematic design process can be identified in the corpus?

### Research case
Contested interpretation case 4

### Primary stress test
Contestation detection; whether the system identifies genuinely different positions rather than generating a unified doctrine.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Department of Design Research
- DDR

### Final proposed lexical facets

#### Facet A - Evidenced institutional identity
- `Department of Design Research`
- `DDR`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
None.

### Rationale
No approved process/methodology term remains. The plan does not silently promote broad methodology vocabulary to a primary lexical value.

### Methodological risks
- Institution-only retrieval does not isolate systematic-design formulations.
- A source-supported process term needs explicit final review before the plan can be approved.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q09 - Closure of the DDR

### Exact research question
Does the current digitised corpus establish why the decision to close the DDR was made?

### Research case
Scoped missingness case 1

### Primary stress test
Causal restraint; whether partial evidence is wrongly converted into a definitive explanation.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Department of Design Research
- DDR

### Final proposed lexical facets

#### Facet A - Evidenced institutional identity
- `Department of Design Research`
- `DDR`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
- `termination`
- `winding up`
- `Design Research Department`

### Rationale
The plan keeps a documentary institutional anchor but does not insert absence, causal, or unsupported closure language.

### Methodological risks
- No approved closure vocabulary currently narrows the result.
- Institution-only retrieval cannot support a causal conclusion without careful evidence review.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q10 - Origins of computing activity

### Exact research question
Can the current digitised corpus establish who initiated computing activity within the DDR?

### Research case
Scoped missingness case 2

### Primary stress test
Origin claims; whether the earliest retrieved trace is mistakenly turned into evidence of historical initiation.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Department of Design Research
- DDR
- documented man-computer terminology

### Final proposed lexical facets

#### Facet A - Evidenced institutional identity
- `Department of Design Research`
- `DDR`

#### Facet B - Evidenced computing terminology
- `man-computer interaction`
- `man computer interaction`
- `man-computer design systems`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
- `man-computer interaction`
- `man computer interaction`
- `man-computer design systems`

### Rejected terms relevant to this plan
- `Design Research Department`

### Rationale
The plan retrieves documented computing traces in an evidenced institutional setting without searching for `first`, `initiated`, or any predetermined person.

### Methodological risks
- The approved terminology may foreground one computing strand over other source language.
- Earliest surviving evidence is not evidence of historical initiation.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q11 - Reception of Design in General Education

### Exact research question
Can the surviving digitised records establish how Design in General Education was received by its intended users?

### Research case
Scoped missingness case 3

### Primary stress test
Evidence-boundary recognition; distinguishing documented intentions and activities from evidence of actual reception.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Design in General Education

### Final proposed lexical facets

#### Facet A - Evidenced programme identity
- `Design in General Education`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design in General Education` | `database_authorities.ddr_projects` / project title terminology | controlled_query_expansion | Direct corpus/catalogue programme wording and related project authority title. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
- `DGE`
- `schools`

### Rationale
The named programme is supported directly; no generic audience or reception language is added.

### Methodological risks
- Programme-only retrieval can document intentions and activity without documenting reception.
- No approved user/reception term currently narrows the result.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Q12 - Henrietta Ryott in the DDR

### Exact research question
What can the current digitised corpus establish about Henrietta Ryott’s role in the DDR between 1973 and 1977?

### Research case
Scoped missingness case 4

### Primary stress test
Uneven personal visibility; whether sparse or indirect documentary evidence produces appropriately bounded conclusions.

### Retrieval scope
`corpus_wide`

### Explicit entities
- Henrietta Ryott
- Department of Design Research
- DDR

### Final proposed lexical facets

#### Facet A - Canonical person identity
- `Henrietta Ryott`

#### Facet B - Evidenced institutional identity
- `Department of Design Research`
- `DDR`

### Approved authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Henrietta Ryott` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical authority value and direct corpus usage. |
| `DDR` | `database_authorities.ref_fonds` / fonds code | controlled_query_expansion | Stable archive-specific abbreviation. |

### Approved researcher synonyms
None.

### Rejected terms relevant to this plan
- `Ryott`
- `Design Research Department`

### Rationale
The plan keeps the full canonical name and institutional context while allowing documentary sparsity to remain visible.

### Methodological risks
- Sparse direct use of the name may yield limited evidence.
- The date range is assessed through retrieved record metadata, not converted into an unsupported lexical constraint.

### Protocol version
`turin-retrieval-protocol-v1.0`

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`REVIEWED — awaiting final researcher approval`

## Final review summary

| Q | Approved lexical values retained | Rejected values removed | Remaining ambiguity |
|---|---|---|---|
| Q01 | `171`, `Pierre Goumain`, three man-computer variants | Job/title-like lexical phrases | Controlled number use may broaden outside project context. |
| Q02 | `Bruce Archer` | `Archer`, `education` | No approved teaching-context term. |
| Q03 | Canonical names, `Design Education Unit`, `DEU` | None | No person-authority records for Baynes/Roberts. |
| Q04 | `John Wood` | Unapproved technical expansions excluded | No approved console/ergonomics contextual term. |
| Q05 | `Department of Design Research`, `DDR` | `Design Research Department` | No approved contested-meaning term. |
| Q06 | `Department of Design Research`, `DDR` | Unapproved method terms excluded | No approved design/science relation term. |
| Q07 | `Design Education Unit`, `DEU`, `DDR`, `Department of Design Research` | `recollection` excluded | ANDed context may exclude unit-only records. |
| Q08 | `Department of Design Research`, `DDR` | Unapproved methodology terms excluded | No approved systematic-process term. |
| Q09 | `Department of Design Research`, `DDR` | `termination`, `winding up`, `Design Research Department` | No approved closure term. |
| Q10 | Institution values and three man-computer variants | `Design Research Department` | Technical strand may not represent all computing activity. |
| Q11 | `Design in General Education` | `DGE`, `schools` | No approved reception/audience term. |
| Q12 | `Henrietta Ryott`, `Department of Design Research`, `DDR` | `Ryott`, `Design Research Department` | Sparse person evidence and date interpretation. |