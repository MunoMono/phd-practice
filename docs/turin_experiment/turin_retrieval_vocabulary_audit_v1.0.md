# Turin Retrieval Vocabulary Audit v1.0

## Audit method

This is a pre-approval, read-only audit of the frozen corpus version `corpus_f40d78dbce52`, `database_authorities`, and frozen document catalogue metadata. No retrieval plan was approved, persisted, or executed.

Counts labelled **FTS** use the Retrieval Protocol compiler's `websearch_to_tsquery('english', value)` behaviour: tokens are stemmed and ANDed. They describe what the proposed plan would retrieve, not necessarily literal phrase use. Literal counts use case-insensitive source-text matches; `171`, `DDR`, `DEU`, and `DGE` were additionally checked as whole tokens. Catalogue counts search source titles, filenames, authority data, and document metadata.

## Job 171 terminology

| Term | Frozen corpus evidence | Authority/catalogue evidence | Appropriate classification | Recommendation |
|---|---|---|---|---|
| `171` | FTS: 10 chunks/2 documents; whole-token: 43/4. Representative wording: `Ref: 171/06`; `Summary Report [171]/01`. | `ddr_projects` authority ID `171` has title `Designer-computer interaction in the early stages of design` and project lead Pierre Goumain. | Authority-derived identity term; documentary variant only where reference context is checked. | RESEARCHER DECISION |
| `Job 171` | FTS: 0/0; literal: 0/0. | Project number exists as `171`, not as the phrase `Job 171`. | Reject as a lexical FTS value; retain only as research-question wording. | REJECT |
| `Designer-computer interaction in the early stages of design` | FTS: 0/0; literal: 0/0. | Exact `ddr_projects` title for ID `171`. | Authority-derived variant, not a corpus-supported documentary phrase. | RESEARCHER DECISION |
| `designer computer interaction` | FTS: 56/12, but literal: 0/0; representative FTS context is about `Human Factors`, showing tokenised overreach. | No authority value in this unhyphenated form. | Not a defensible documentary synonym. | REJECT |
| `man-computer interaction` | FTS: 26/3; literal: 18/3. Representative wording: `NATO Advanced Study Institute on Man Computer Interaction`. | No matching authority value. | Documentary variant; researcher-approved synonym if its pre-run diagnostic provenance is retained. | APPROVE |
| `man computer interaction` | FTS: 36/4; literal: 6/2. Same source wording uses the unhyphenated form `Man Computer Interaction`. | No matching authority value. | Documentary variant; researcher-approved synonym. | APPROVE |
| `man-computer design systems` | FTS: 23/3; literal: 9/3. Representative wording: `interface design, for man-computer design systems`. | No matching authority value. | Documentary variant; researcher-approved synonym. | APPROVE |
| `Pierre Goumain` | FTS: 31/17; literal: 26/15. Representative wording: `Pierre Goumain, who has been leading the current pilot study`. | `agent_employment` canonical label `Pierre Goumain`; `ddr_projects` ID `171` names him as project lead. | Identity term and transparent authority-derived variant. | APPROVE |

The Job 171 computing terms are admissible only as transparent **pre-run diagnostic knowledge**, not as tuning to a formal Retrieval Protocol v1.0 result. The exact project title has authority support but no literal corpus occurrence; its approval would materially privilege the authority record over documentary wording.

## Person-name variants

No initials, alternative spellings, aliases, or shortened forms are recommended. The table reports only canonical values supported by corpus usage or authority data.

| Person | Frozen corpus evidence | Authority evidence | Supported variants | Recommendation |
|---|---|---|---|---|
| Bruce Archer | FTS: 134 chunks/70 documents; literal: 126/69. | `agent_employment` canonical `Bruce Archer`; project authorities identify him as lead on several projects. | `Bruce Archer` only. `Archer` is not independently verified as a safe retrieval value. | APPROVE canonical; REJECT unqualified surname |
| Ken Baynes | FTS/literal: 54/27. | No matching `database_authorities` person record found. | `Ken Baynes` only. | APPROVE as documentary wording; no authority variant |
| Phil Roberts | FTS/literal: 18/9. Representative wording: `Phil Roberts 16 March 1983`. | No matching `database_authorities` person record found. | `Phil Roberts` only. | APPROVE as documentary wording; no authority variant |
| John Wood | FTS: 27/19; literal: 26/18. | `agent_employment` canonical `John Wood`; `ddr_projects` records him as lead on several control-console projects. | `John Wood` only. | APPROVE canonical |
| Henrietta Ryott | FTS/literal: 4/4. Representative wording identifies her among manuscript typists. | `agent_employment` canonical `Henrietta Ryott`, 1973-1977, `Departmental Secretary (Research & Practice)`. | `Henrietta Ryott` only. `Ryott` is not independently verified as a safe retrieval value. | APPROVE canonical; REJECT unqualified surname |

## Unit/programme terminology

| Term | Frozen corpus evidence | Authority/catalogue usage | Recommendation | Rationale |
|---|---|---|---|---|
| `Design Education Unit` | FTS: 79/38; literal: 47/28. | Authority `ref_fonds` code `DEU`, label `Design Education Unit sub-fonds`; catalogue: 36 documents. | APPROVE | Exact corpus, authority, and catalogue wording. |
| `DEU` | FTS: 4/2; whole-token: 5/3. Representative wording: `DEU memos SEMINARS AND PAPERS`. | Authority `ref_fonds` code `DEU`; catalogue: 24 documents. | APPROVE | Well-evidenced archive-specific abbreviation. |
| `Design in General Education` | FTS: 102/34; literal: 38/17. | Project authority ID `150`: `Investigation into the role of design in general education`; catalogue: 24 documents. | APPROVE | Exact corpus and catalogue programme wording; authority project title supports a related formulation. |
| `DGE` | FTS: 464/65, caused by token matching; whole-token literal: 0/0. | No matching authority code or evidenced catalogue abbreviation; apparent catalogue matches are substring noise. | REJECT | Not an evidenced abbreviation and materially unsafe. |
| `Department of Design Research` | FTS: 279/61; literal: 140/50. Representative wording: `Department of Design Research Royal College of Art Kensington Gore London SW7 2EU`. | Catalogue: 4 documents, including `The future of the Department of Design Research memo`. | APPROVE | Direct RCA DDR corpus and catalogue wording. |
| `DDR` | FTS: 20/7; whole-token: 94/9. | Authority `ref_fonds` code/label `DDR`, `DDR fonds`; catalogue: 109 documents. | APPROVE | Stable archive-specific fonds abbreviation, though it should remain paired with a contextual facet where precision matters. |
| `Design Research Department` | FTS: 279/61; literal: 3/2. Representative wording: `newly titled Design Research Department`. | No direct authority or catalogue label found. | RESEARCHER DECISION | It has limited RCA source use but is less stable than `Department of Design Research`; FTS broadens to many generic design/research/department chunks. |

`Design Research Department` is not rejected as historically false: it occurs in two source documents. It is not recommended as a default primary facet because the compiler-style result is highly non-specific and no matching authority/catalogue value was found.

## Broad lexical terms

| Term | FTS chunks/documents | Representative context | Vocabulary basis | Draft question(s) | Retrieval risk | Recommendation |
|---|---:|---|---|---|---|---|
| `education` | 650/71 | `THE EDUCATION OF INDUSTRIAL DESIGNERS SECOND SEMINAR` | Contemporary source wording, but very broad. | Q02 | High | REJECT |
| `pedagogy` | 6/3 | `contribution to design pedagogy` | Limited source wording. | Q02 | Medium | RESEARCHER DECISION |
| `human factors` | 59/12 | `applications of Human Factors ... ergonomics` | Contemporary technical wording. | Q04 | Medium | RESEARCHER DECISION |
| `design methodology` | 78/28 | `Design methodology Mechanical engineering ...` | Source wording, but potentially curricular/general. | Q05 | Medium | RESEARCHER DECISION |
| `scientific method` | 23/9 | `The popular idea of 'scientific ...` | Source wording, phrase requires context review. | Q06 | Medium | RESEARCHER DECISION |
| `design method` | 319/52 | FTS sample combines `design` and `methods` in general academic text. | Proposed formulation; compiler matching is broad. | Q06, Q08 | High | RESEARCHER DECISION |
| `methodology` | 101/32 | `methodology Mechanical engineering Basic electrical engineering ...` | Source wording, not necessarily DDR interpretation vocabulary. | Q08 | Medium | RESEARCHER DECISION |
| `recollection` | 2/1 | `recollection is that these guys were ...` | Limited retrospective wording. | Q07 | Medium | RESEARCHER DECISION |
| `termination` | 57/18 | `terminated by a final criticism ...` | Stemmed FTS match, not evidenced as DDR closure vocabulary. | Q09 | High | REJECT |
| `winding up` | 10/6 | FTS sample concerns `wind` and movement, not organisational closure. | Proposed modern/administrative synonym without archive-specific support. | Q09 | High | REJECT |
| `schools` | 480/63 | `school places on different parts of its curriculum` | Contemporary source wording, but highly generic. | Q11 | High | REJECT |

`websearch_to_tsquery` treats several apparent phrases as separate required stems. The counts for `design method`, `termination`, and `winding up` therefore do not establish literal historical wording and cannot by themselves justify inclusion.

## Decision table

| Term | Evidence basis | Relevant questions | Retrieval risk | Recommendation | Rationale |
|---|---|---|---|---|---|
| `171` | Project authority ID; reference-number corpus occurrences | Q01 | Medium | RESEARCHER DECISION | Good controlled identifier, but not always literal `Job 171`. |
| `Job 171` | No corpus occurrence | Q01 | High | REJECT | No FTS or literal support. |
| Exact Job 171 title | Project authority only | Q01 | Medium | RESEARCHER DECISION | Authority value lacks literal corpus support. |
| `designer computer interaction` | No literal occurrence; broad FTS matches | Q01 | High | REJECT | Unhyphenated value overreaches. |
| `man-computer interaction` | 18 literal chunks/3 documents | Q01, Q10 | Low | APPROVE | Direct source wording. |
| `man computer interaction` | 6 literal chunks/2 documents | Q01, Q10 | Low | APPROVE | Direct source wording variant. |
| `man-computer design systems` | 9 literal chunks/3 documents | Q01 | Low | APPROVE | Direct source wording. |
| `Pierre Goumain` | Authority plus 26 literal chunks/15 documents | Q01 | Low | APPROVE | Canonical identity and documentary use. |
| Canonical person names | Corpus and, except Baynes/Roberts, authority | Q02-Q04, Q12 | Low | APPROVE | Use full canonical names only. |
| `Archer`, `Ryott` | No independent safety evidence | Q02, Q12 | High | REJECT | Unqualified surnames broaden and may be ambiguous. |
| `Design Education Unit` | Corpus, fonds authority, catalogue | Q03, Q07 | Low | APPROVE | Stable exact unit term. |
| `DEU` | Corpus whole-token, fonds authority, catalogue | Q03, Q07 | Low | APPROVE | Stable documented abbreviation. |
| `Design in General Education` | Corpus, project authority, catalogue | Q11 | Low | APPROVE | Stable named programme. |
| `DGE` | No whole-token corpus/authority support | Q11 | High | REJECT | FTS results are substring noise. |
| `Department of Design Research` | 140 literal chunks/50 documents; catalogue | Q09, Q10, Q12 | Medium | APPROVE | Direct RCA wording. |
| `DDR` | Fonds authority and 94 whole-token chunks | Q05, Q07, Q09-Q12 | Medium | APPROVE | Stable acronym; use with another facet. |
| `Design Research Department` | 3 literal chunks/2 documents | Q09, Q10, Q12 | High | RESEARCHER DECISION | Limited source use; unsafe as default facet. |
| `education`, `schools` | Broad contemporary usage | Q02, Q11 | High | REJECT | Recall-oriented, insufficiently specific. |
| `pedagogy`, `human factors` | Limited/direct source usage | Q02, Q04 | Medium | RESEARCHER DECISION | Evidence exists; scope effect needs approval. |
| `design methodology`, `scientific method`, `design method`, `methodology` | Source usage with broad compiler behaviour | Q05, Q06, Q08 | Medium/High | RESEARCHER DECISION | Need inspection of source-type and sense distribution. |
| `recollection` | 2 chunks/1 document | Q07 | Medium | RESEARCHER DECISION | Could privilege retrospective voice. |
| `termination`, `winding up` | No archive-specific closure evidence | Q09 | High | REJECT | Does not defensibly represent DDR closure language. |

## Proposed changes to draft plans

- Q01: remove `Job 171` and `designer computer interaction` as proposed FTS alternatives. Retain the canonical project title only as a transparent, unresolved authority-derived proposal. Retain the three evidenced `man-computer` forms as documented pre-run variants.
- Q02: remove unqualified `Archer` and reject `education`; hold `pedagogy` for researcher decision.
- Q03 and Q07: retain `Design Education Unit` and `DEU`; the abbreviation is evidenced.
- Q04: retain canonical `John Wood`; hold `human factors` for researcher decision rather than treating it as automatically approved.
- Q05, Q06, and Q08: do not auto-approve methodology/method vocabulary; decide after source-sense review.
- Q09: use `Department of Design Research` and `DDR` as supported institutional anchors; do not add `termination` or `winding up`. Treat `Design Research Department` as unresolved.
- Q10: `Department of Design Research` and `DDR` are supported; `man-computer` vocabulary requires a scope decision because it may foreground a particular technical strand.
- Q11: retain `Design in General Education`; remove `DGE` and `schools`.
- Q12: retain canonical `Henrietta Ryott`; remove unqualified `Ryott`.

## Questions requiring researcher judgement

- Q01: whether the authority-only exact Job 171 title and controlled number `171` should enter the primary lexical formulation despite their different source-text behaviour.
- Q02: whether the limited source term `pedagogy` is appropriate for teaching-and-learning practice.
- Q04: whether `human factors` is sufficiently specific to console design and ergonomics.
- Q05-Q08: whether methodology/method terms represent historical source vocabulary in the intended sense, rather than broad curricular or analytic language.
- Q07: whether `recollection` is a controlled way to surface retrospective accounts without privileging them.
- Q09-Q12: whether `Design Research Department` should be admitted alongside the better-evidenced `Department of Design Research` and `DDR`; whether Q10 should include the evidenced `man-computer` terminology.

## Validation

- Plans approved: 0.
- Plans persisted to production: 0.
- Formal Retrieval Protocol v1.0 runs executed: 0.
- `findings_matrix.csv`: unchanged.
- Draft-plan question text: unchanged.