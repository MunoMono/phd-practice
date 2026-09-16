# Turin Retrieval Plans v1.0 - DRAFT

## Method note

The historical research question is an immutable interpretive input, whereas PostgreSQL full-text search needs a short, explicit lexical strategy. Separating them avoids treating generic analytical wording as archival search terms. Each plan requires researcher review before it can be approved, persisted, or executed.

Primary retrieval is corpus-wide so that documentary evidence is not silently limited to authority-linked documents. Authority-derived variants are transparent controlled query expansions, never documentary evidence or a candidate-document restriction. The variants below are proposals only and remain outside a compiled plan unless individually approved. No post-result silent tuning is permitted: any later methodological change must be a new, versioned plan.

Compiler semantics: within a facet, alternatives are ORed; all declared facets are ANDed. These drafts therefore use alternatives for potentially dispersed people or formulations, rather than requiring every name in every chunk.

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
- Job 171
- Designer-computer interaction in the early stages of design
- Pierre Goumain

### Lexical facets

#### Facet A - Project and person anchor
- `Job 171`
- `Pierre Goumain`

#### Facet B - Pre-run archival computing terminology
- `man-computer interaction`
- `man-computer design systems`
- `designer-computer interaction`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `171` | `database_authorities.ddr_projects` / project number | controlled_query_expansion | Controlled project identifier, subject to checking its archival use. |
| `Designer-computer interaction in the early stages of design` | `database_authorities.ddr_projects` / project title | controlled_query_expansion | Canonical project title; retain only if its punctuation and wording are verified. |
| `Pierre Goumain` | `database_authorities.ddr_projects` / project lead | controlled_query_expansion | Resolved project-lead name that can surface dispersed project traces. |

### Proposed researcher-approved synonyms
- `man-computer interaction` - diagnostic pre-run terminology finding; approve only with its documented provenance.
- `man-computer design systems` - diagnostic pre-run terminology finding; approve only with its documented provenance.

### Proposed plan logic
Facet A requires a project/person anchor and Facet B requires one historically used computing formulation. Alternatives in each facet are ORed; the two facets are ANDed.

### Rationale
The plan uses documented pre-run terminology knowledge transparently rather than the full interrogative question as an FTS query.

### Methodological risks
- The exact project number may be absent from OCR or transcribed pages.
- Requiring a computing term may exclude administrative or output records with only the project/person anchor.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- students
- teaching
- learning

### Lexical facets

#### Facet A - Person
- `Bruce Archer`
- `Archer`

#### Facet B - Teaching context
- `teaching`
- `learning`
- `students`
- `student`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Bruce Archer` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical named-person value, subject to authority resolution. |

### Proposed researcher-approved synonyms
- `education` - broadens the teaching context, but risks pulling institutional material unrelated to students.
- `pedagogy` - approve only if it occurs in the corpus's historical vocabulary.

### Proposed plan logic
Require one person alternative and one teaching-context alternative. The surname-only alternative needs review because it may introduce false positives.

### Rationale
This seeks traces of practice without encoding a conclusion about Archer's role.

### Methodological risks
- Pedagogical language may be described without naming Archer in the same chunk.
- `education` may over-broaden the corpus-wide result.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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

### Lexical facets

#### Facet A - Named contributors
- `Ken Baynes`
- `Phil Roberts`

#### Facet B - Unit context
- `Design Education Unit`
- `DEU`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Ken Baynes` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical person name, pending resolution. |
| `Phil Roberts` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical person name, pending resolution. |
| `Design Education Unit` | DDR controlled programme/unit authority | controlled_query_expansion | Canonical unit name, pending authority confirmation. |

### Proposed researcher-approved synonyms
- `DEU` - only if verified as an archival abbreviation rather than a modern shorthand.

### Proposed plan logic
Require one named-contributor alternative and one unit-context alternative. The plan deliberately does not require both people in one chunk.

### Rationale
The plan allows retrieval of dispersed records while keeping the institutional setting explicit.

### Methodological risks
- The acronym may be ambiguous or absent from source text.
- A connection may emerge only across documents, not at chunk level.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- console design
- ergonomics

### Lexical facets

#### Facet A - Person
- `John Wood`

#### Facet B - Design and ergonomics context
- `console design`
- `ergonomics`
- `ergonomic`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `John Wood` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical person name, pending disambiguation from namesakes. |

### Proposed researcher-approved synonyms
- `control console` - approve only after checking it is a corpus term.
- `human factors` - potentially relevant historical terminology, but may broaden beyond the intended subject.

### Proposed plan logic
Require the person and one design/ergonomics alternative; source type is evaluated from retrieved metadata, not added as unsupported FTS syntax.

### Rationale
The query retrieves the relevant lexical traces while leaving cross-source comparison to evidence review.

### Methodological risks
- `John Wood` may be insufficiently distinctive.
- Terminology may vary between technical and administrative source types.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- design research
- DDR

### Lexical facets

#### Facet A - Core formulation
- `design research`
- `research in design`

#### Facet B - Design practice vocabulary
- `design`
- `designing`

### Proposed authority-derived variants
None proposed.

### Proposed researcher-approved synonyms
- `research in design` - possible wording variant requiring corpus verification.
- `design methodology` - may be relevant, but risks substituting an analytic category for source language.

### Proposed plan logic
Require a core formulation alternative and a design-practice alternative. Do not add terms such as `consistent` or `conception`, which are analytic rather than archival language.

### Rationale
The plan is broad enough to surface different formulations without presuming agreement or disagreement.

### Methodological risks
- `design methodology` may import a preferred framing.
- Exact phrase matching through FTS may still miss OCR variants.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- design
- science
- research

### Lexical facets

#### Facet A - Design and science vocabulary
- `design science`
- `science of design`

#### Facet B - Research vocabulary
- `research`
- `researcher`

### Proposed authority-derived variants
None proposed.

### Proposed researcher-approved synonyms
- `scientific method` - possible source formulation; requires corpus verification.
- `design method` - possible source formulation; may produce generic methodology material.

### Proposed plan logic
Require one design/science formulation and one research alternative. Contributor identity is retained from documentary metadata and text, not imposed as a query constraint.

### Rationale
The plan can surface multiple contributors' formulations without choosing a preferred relation in advance.

### Methodological risks
- Broad `research` language can generate substantial unrelated material.
- Phrased alternatives may under-retrieve documents that use separated terms.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- DDR

### Lexical facets

#### Facet A - Unit anchor
- `Design Education Unit`
- `DEU`

#### Facet B - Account vocabulary
- `account`
- `history`
- `retrospective`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design Education Unit` | DDR controlled programme/unit authority | controlled_query_expansion | Canonical unit name, pending authority confirmation. |

### Proposed researcher-approved synonyms
- `DEU` - only if verified as an archival abbreviation.
- `recollection` - may surface retrospective accounts, but may bias retrieval toward later voice.

### Proposed plan logic
Require a unit anchor and one account-vocabulary alternative. Contemporary versus retrospective status is determined during source/date review, not asserted by the query.

### Rationale
The plan retrieves potentially comparable accounts without allowing later retrospective language to predetermine interpretation.

### Methodological risks
- `history` and `retrospective` may overweight later source types.
- Some contemporary documents may not name the unit in the same chunk.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- systematic design process
- design process

### Lexical facets

#### Facet A - Systematic design formulation
- `systematic design`
- `systematic design process`

#### Facet B - Process vocabulary
- `design process`
- `design method`
- `methodology`

### Proposed authority-derived variants
None proposed.

### Proposed researcher-approved synonyms
- `design method` - candidate historical formulation requiring corpus verification.
- `methodology` - broad candidate that may pull analytic or administrative language.

### Proposed plan logic
Require one systematic-design formulation and one process alternative. Do not query for `competing`, `interpretations`, or `doctrine` because they presuppose the analytical result.

### Rationale
The plan retrieves formulations from which competing positions may be assessed rather than searching for disagreement itself.

### Methodological risks
- Method terms may be used in unrelated project-management contexts.
- Narrow phrasing may fail where systematicity is implied rather than named.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- DDR
- close
- closure

### Lexical facets

#### Facet A - Closure vocabulary
- `close`
- `closure`
- `closed`

#### Facet B - Institutional anchor
- `Design Research Department`
- `DDR`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design Research Department` | DDR controlled organisation authority | controlled_query_expansion | Canonical organisation name, pending verification against archive terminology. |

### Proposed researcher-approved synonyms
- `termination` - potential administrative vocabulary; requires corpus verification.
- `winding up` - potential administrative vocabulary; requires corpus verification.

### Proposed plan logic
Require closure vocabulary and an institutional anchor. Do not include absence language or causal terms such as `why`, `reason`, or `decision` as required terms.

### Rationale
The plan seeks relevant traces while allowing limited or absent causal support to emerge.

### Methodological risks
- `close` is polysemous and may retrieve unrelated correspondence.
- Administrative closure may be described without the DDR acronym or full name.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- computing
- DDR

### Lexical facets

#### Facet A - Computing vocabulary
- `computer`
- `computing`
- `computer-aided`

#### Facet B - Institutional anchor
- `Design Research Department`
- `DDR`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design Research Department` | DDR controlled organisation authority | controlled_query_expansion | Canonical organisation name, pending verification against archive terminology. |

### Proposed researcher-approved synonyms
- `man-computer` - known historical computing terminology, but needs relevance review for this broader question.
- `computer design` - candidate corpus term requiring verification.

### Proposed plan logic
Require a computing term and an institutional anchor. Do not include `initiated`, `first`, or person names because the plan must not force an origin claim.

### Rationale
The plan retrieves traces relevant to computing activity while preserving the distinction between occurrence and initiation.

### Methodological risks
- Technical terminology can be uneven across document types.
- Early surviving traces are not evidence of historical priority.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- intended users

### Lexical facets

#### Facet A - Programme anchor
- `Design in General Education`
- `general education`

#### Facet B - User and response vocabulary
- `users`
- `teachers`
- `pupils`
- `students`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Design in General Education` | DDR controlled programme authority | controlled_query_expansion | Canonical programme name, pending authority confirmation. |

### Proposed researcher-approved synonyms
- `DGE` - only if verified as an archival abbreviation.
- `schools` - potential context term, but may recover activity rather than reception.

### Proposed plan logic
Require a programme anchor and one user/response context alternative. Do not query for `received`, `reception`, `absence`, or evaluative outcomes as mandatory terms.

### Rationale
The plan seeks relevant records without forcing an evidential claim about reception.

### Methodological risks
- User terms may favour intended audiences over evidence of actual use.
- `general education` may be broader than the named programme.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

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
- DDR
- 1973 to 1977

### Lexical facets

#### Facet A - Person
- `Henrietta Ryott`
- `Ryott`

#### Facet B - Institutional anchor
- `Design Research Department`
- `DDR`

### Proposed authority-derived variants
| Value | Likely authority source/type | Role | Rationale |
|---|---|---|---|
| `Henrietta Ryott` | `database_authorities.agent_employment` / person name | controlled_query_expansion | Canonical person name, pending authority resolution and spelling check. |

### Proposed researcher-approved synonyms
- `Ryott` - surname-only fallback requiring review for ambiguity.

### Proposed plan logic
Require a person alternative and an institutional anchor. The date range is applied in documentary interpretation and metadata review, not represented as a lexical FTS facet.

### Rationale
The plan retrieves relevant traces while leaving sparse evidence capable of supporting a bounded missingness conclusion.

### Methodological risks
- The surname may create false positives.
- Date coverage and source metadata may be incomplete or uneven.

### Plan version
`1.0`

### Classification
`primary`

### Approval state
`DRAFT - researcher review required`

## Additional review table

| Q | Case | Main entities | Main lexical risk | Authority assistance proposed? | Researcher decision required? |
|---|---|---|---|---|---|
| Q01 | Known relationship case 1 | Job 171; Pierre Goumain; computing terminology | Project number/title may be absent; terminology is diagnostic pre-run knowledge | Yes | Yes - approve documented Job 171 terminology and anchors |
| Q02 | Known relationship case 2 | Bruce Archer; students; teaching | Surname ambiguity; broad education terms | Yes | Yes - approve surname and teaching variants |
| Q03 | Known relationship case 3 | Ken Baynes; Phil Roberts; Design Education Unit | Acronym ambiguity; dispersed connection | Yes | Yes - verify DEU as archival abbreviation |
| Q04 | Known relationship case 4 | John Wood; console design; ergonomics | Person-name ambiguity; technical vocabulary variation | Yes | Yes - verify namesake and candidate terms |
| Q05 | Contested interpretation case 1 | design research | Methodology language may import analytic framing | No | Yes - approve historical wording variants |
| Q06 | Contested interpretation case 2 | design; science; research | Broad research vocabulary; phrase coverage | No | Yes - approve candidate formulation variants |
| Q07 | Contested interpretation case 3 | Design Education Unit | Later-account vocabulary may overweight retrospective material | Yes | Yes - verify DEU and retrospective candidates |
| Q08 | Contested interpretation case 4 | systematic design process | Method terms may be unrelated to substantive positions | No | Yes - approve process vocabulary |
| Q09 | Scoped missingness case 1 | DDR; closure | Polysemous closure terms; omitted organisation name | Yes | Yes - verify organisation terminology and administrative variants |
| Q10 | Scoped missingness case 2 | computing; DDR | Occurrence could be mistaken for initiation | Yes | Yes - approve historical computing variants |
| Q11 | Scoped missingness case 3 | Design in General Education; users | Intended audience may be mistaken for reception evidence | Yes | Yes - verify programme name/acronym and audience terms |
| Q12 | Scoped missingness case 4 | Henrietta Ryott; DDR | Surname ambiguity; uneven date/source coverage | Yes | Yes - resolve authority identity and surname use |