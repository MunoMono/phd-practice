# Turin Archive-First Qwen Researcher Assessment

- Protocol: `turin-archive-first-qwen-evaluation-v1`
- Corpus: `corpus_turin_archive_first_cc11e8678168`
- Fixed evidence sets: yes
- Retrieval rerun: no
- Qwen calls in this task: 0

## Completed Responses

| Question | Research mode | Direct-evidence handling | Cross-source synthesis | Contestation / missingness | Provenance | Usefulness | Main issue | Value labels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Q02 | Known relationships | Identifies course, tutorial and student-facing material; some role claims need source-by-source review. | Adds explicit, labelled links between programme material and broader teaching role. | States pedagogy, observation and outcomes are not established. | PASS | `USEFUL_WITH_QUALIFICATION` | Broad curriculum/supervision claims may be stronger than the cited excerpts. | `RETRIEVAL_ALREADY_ESTABLISHES`; `QWEN_ADDS_CROSS_SOURCE_RELATION`; `QWEN_ADDS_HELPFUL_QUALIFICATION` |
| Q03 | Known relationships | Preserves the distinction between shared DEU association and direct collaboration. | Relates dispersed association without claiming a confirmed collaboration. | Explicitly says the collaboration's nature is not established. | PASS | `USEFUL_WITH_QUALIFICATION` | The synthesis remains close to the source cards. | `RETRIEVAL_ALREADY_ESTABLISHES`; `QWEN_ADDS_HELPFUL_QUALIFICATION` |
| Q04 | Known relationships | Calls Wood's console-design involvement direct, then acknowledges that his exact contribution is not detailed. | Connects ergonomics and console material. | The qualification is present but does not fully neutralise the earlier stronger wording. | PASS | `MISLEADING` | Direct-role wording risks upgrading association to involvement. | `QWEN_ADDS_CROSS_SOURCE_RELATION`; `QWEN_OVERREACHES`; `QWEN_FLATTENS` |
| Q05 | Contested interpretation | Keeps formulations tied to supplied sources. | Supplies labelled inference rather than a single institutional definition. | The only completed contested case with explicit qualified/contested evidence. | PASS | `USEFUL_WITH_QUALIFICATION` | Researcher should test whether the listed differences are genuinely divergent rather than merely varied. | `QWEN_ADDS_CROSS_SOURCE_RELATION`; `QWEN_ADDS_HELPFUL_QUALIFICATION` |
| Q09 | Scoped missingness | Does not convert closure material into a complete cause. | Limited additional synthesis. | States evidential limits. | PASS | `LARGELY_RESTATEMENT` | Cross-source statements were not all explicitly labelled as inference. | `RETRIEVAL_ALREADY_ESTABLISHES`; `QWEN_ONLY_REPHRASES` |
| Q10 | Scoped missingness | Maintains an origin boundary rather than treating surviving computing traces as initiation. | Adds a bounded relation among traces. | States what the evidence cannot establish. | PASS | `USEFUL_WITH_QUALIFICATION` | Researcher should check that no chronology is read as priority. | `RETRIEVAL_ALREADY_ESTABLISHES`; `QWEN_ADDS_HELPFUL_QUALIFICATION` |
| Q11 | Scoped missingness | Distinguishes programme material from evidence of reception. | Limited additional synthesis. | States the reception boundary. | PASS | `LARGELY_RESTATEMENT` | Value is principally disciplined restatement of the evidence boundary. | `RETRIEVAL_ALREADY_ESTABLISHES`; `QWEN_ONLY_REPHRASES` |
| Q12 | Scoped missingness | The key missingness conclusion is placed incorrectly in the direct-evidence section without citations. | No safe additional synthesis established. | The wording remains bounded to direct evidence, not archival absence. | FAIL | `USEFUL_WITH_QUALIFICATION` | `CITATION_FORMAT_FAILURE`; direct-section placement is wrong. | `RETRIEVAL_ALREADY_ESTABLISHES`; `QWEN_ADDS_HELPFUL_QUALIFICATION` |

## Research-Mode Reading

**Known relationships:** Q02 and Q03 are potentially useful where cross-source linkage remains labelled and role claims are kept bounded. Q04 shows why source-level provenance alone is insufficient: a source-cited claim can still strengthen an association into a role claim.

**Contested interpretation:** Only Q05 is evaluable. It preserves qualification, but three of four contested questions are non-evaluable schema failures. No claim about the protocol's general ability to preserve plurality is warranted.

**Scoped missingness:** Q09-Q11 handle documentary limits without converting them to archival absence. Q12 has the same bounded orientation but fails the citation and section contract.

## Non-Evaluable Responses

`Q01`, `Q06`, `Q07`, and `Q08`: `NON_EVALUABLE_SCHEMA_FAILURE`.

## Conclusion

Does Qwen add value beyond retrieval: `MIXED`.

The completed responses sometimes add useful, explicitly labelled cross-source relations and evidential qualifications. Their value is uneven: Q09 and Q11 mostly restate archive-first retrieval boundaries; Q04 overstrengthens a role claim; and Q12 violates the citation contract. This is an assessment of the eight completed responses only.

The current generative protocol is technically reliable enough for formal use: `NO`.

This conclusion concerns structured-output reliability, not whether Qwen can ever provide useful interpretation. Four of twelve calls were structurally incomplete, and one of eight completed outputs failed its direct-evidence citation rule.

Historical runs modified: `NO`.