# Turin Archive-First Qwen v1.1 Researcher Assessment (Post-run)

- Protocol: `turin-archive-first-qwen-evaluation-v1.1`
- Corpus modified: `NO`
- Retrieval rerun: `NO`
- Historical runs modified: `NO`
- Assessment basis: retained first-call outputs only; no repair or retry.

## Structural Result

No v1.1 response is a valid completion. Q05 is incomplete JSON. Q06, Q08, Q11, and Q12 exceed the compact schema limits. Q01-Q04, Q07, Q09, and Q10 otherwise parse but each has an uncited `limits` claim. Raw-output review identifies `MISSECTIONED_LIMIT` in Q11 and Q12, despite their schema failures.

## Per-Question Assessment

| Question | Outcome | Contribution type | Researcher rationale |
| --- | --- | --- | --- |
| Q01 | LARGELY_RESTATEMENT | QWEN_ONLY_REPHRASES | Restates Job 171 passages; the HCI, education, and holistic-design implications add little warranted analysis. |
| Q02 | MISLEADING | QWEN_OVERREACHES | Does not recognise the direct Archer course/tutorial control; substitutes broad biography and makes unsupported influence claims. |
| Q03 | MISLEADING | QWEN_OVERREACHES | Treats shared association/project involvement as collaboration without sufficient support. |
| Q04 | MISLEADING | QWEN_OVERREACHES | Converts console work into an ergonomic focus; this is an unsupported inference. |
| Q05 | NON_EVALUABLE | QWEN_ONLY_REPHRASES | Incomplete JSON prevents assessment. |
| Q06 | NON_EVALUABLE | QWEN_ONLY_REPHRASES | Schema-limit violation prevents assessment. |
| Q07 | LARGELY_RESTATEMENT | QWEN_ONLY_REPHRASES | Repeats the retrieved contemporary and retrospective material but does not analyse their different formulations. |
| Q08 | NON_EVALUABLE | QWEN_ONLY_REPHRASES | Schema-limit violation prevents assessment. |
| Q09 | LARGELY_RESTATEMENT | RETRIEVAL_ALREADY_ESTABLISHES | Preserves a useful non-establishment limit, but the closure/restructuring material is already supplied by retrieval. |
| Q10 | LARGELY_RESTATEMENT | RETRIEVAL_ALREADY_ESTABLISHES | Rephrases curricular and computing evidence; the collaboration claim is too general to be a distinct contribution. |
| Q11 | NON_EVALUABLE | QWEN_FLATTENS | Schema failure and missingness mis-sectioned in `direct`. |
| Q12 | NON_EVALUABLE | QWEN_FLATTENS | Schema failure and role-history missingness mis-sectioned in `direct`. |

Counts: `CLEARLY_USEFUL 0`; `USEFUL_WITH_QUALIFICATION 0`; `LARGELY_RESTATEMENT 4`; `MISLEADING 3`; `NON_EVALUABLE 5`.

## Three-Run Comparison

The historical Qwen V2 and archive-first v1 remain immutable comparison records. Archive-first retrieval materially improved the documentary evidence surface, especially for source-controlled questions such as Q02. The v1.1 protocol envelope did not make the same model output structurally evaluable: v1 structural completion was `8/12`; v1.1 valid completion was `0/12`. No interpretive improvement is inferred from the compact protocol.

For Q01-Q12, v1.1 is respectively restatement (Q01, Q07, Q09, Q10), misleading overreach (Q02-Q04), or non-evaluable (Q05-Q06, Q08, Q11-Q12). This cannot be preferred over either historical V2 or archive-first v1 on interpretive grounds. Its only additional evidence is negative: the 1,024-token envelope and compact schema still fail to reliably constrain this model on these fixed evidence sets.

## Research Question

Once archive-first retrieval has supplied the appropriate documentary constellation and passages, Qwen adds value beyond retrieval: `NO`.

The protocol is technically reliable enough for formal researcher use: `NO`. This is a structural reliability conclusion, independent of interpretive usefulness.