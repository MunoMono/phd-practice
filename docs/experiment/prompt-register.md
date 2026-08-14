# Turin Experiment Prompt Register

Status: candidate prompt set. These prompts are registered for researcher-led execution; no expected answer is asserted and this register does not execute them.

| ID | Case | Research question | Retrieval query | Rationale / evidential challenge | Context mode | Authority assistance | Variant | Prompt version |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | known relationship | What relationship does the supplied archival evidence establish between Bruce Archer and design education? | `Bruce Archer design education` | Multi-chunk relationship with documentary support across records. | document_only | no | baseline relationship | v4 |
| A2 | known relationship | What relationship does the supplied archival evidence establish between Bruce Archer and the Design Education Unit? | `Bruce Archer Design Education Unit` | Tests named-unit retrieval and page-aware citation. | document_only | no | A1 narrowing | v4 |
| B1 | contested interpretation | How do the supplied passages characterize the relationship between design research and industrial design education, and where do they differ? | `design research industrial design education` | Requires separation of direct support, inference and disagreement. | document_only | no | baseline contestation | v3 |
| B2 | contested interpretation | What tensions or disagreements concerning computer aided design are present in the supplied archival passages? | `computer aided design` | Tests contradiction preservation rather than consensus synthesis. | document_only | no | terminology variant | v3 |
| C1 | scoped missingness | What does the retrieved Turin corpus context not establish about the relationship between Bruce Archer and design education? | `Bruce Archer design education` | Requires a bounded statement about supplied context, not historical absence. | document_only | no | paired with A1 | v3 |
| C2 | scoped missingness | What support for the requested relationship is absent from passages returned for industrial design education? | `industrial design education` | Tests corpus/query-scoped missingness and follow-up searches. | document_only | no | independent missingness | v3 |
| V1 | known relationship | What relationship does the supplied evidence establish between Archer and design education? | `Archer design education` | Wording sensitivity against A1 without authority use. | document_only | no | A1 wording variant | v4 |
| V2 | contested interpretation | How does controlled entity expansion affect retrieved context for Bruce Archer and design education? | `design education` plus registered researcher-supplied expansion `Bruce Archer` | Transparency comparison only; authority fields must remain separately labelled. | document_only | permitted for query expansion only | A1 authority/query variant | v3 |

Execution workflow: select this prompt ID deliberately, create an immutable run, inspect retrieved and supplied evidence, record a separate researcher assessment, and export the saved run. Runs are serial. Failed runs are persisted and are not automatically retried or tuned.
