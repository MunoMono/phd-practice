---
document_type: statement_of_work
sow_id: ML_TRIAGE_V2_SOW_06
title: Residual case remediation without memorisation
status: accepted
sequence: 6
depends_on:
  - ML_TRIAGE_V2_SOW_05
input_csv: /docs/ml_triage_dev_v2/clean_ml_triage_dev_UAT_50_v2.csv
---

# SoW 06 - Residual Case Remediation Without Memorisation

## Objective

After the architectural SoWs are complete, identify the remaining failed first-50 cases and fix only genuine residual failure classes.

This SoW exists to prevent premature one-off patching during earlier architecture work.

## Entry conditions

Do not start this SoW until SoW 00-05 acceptance criteria are met.

Before coding:

1. Run the current build against all 50 questions using the automated trace harness.
2. Run targeted human UI UAT for any cases changed materially by SoW 05.
3. Produce a residual failure report.

## Residual failure report schema

For every remaining unresolved case, record:

```text
uat_id
question_class
observed_failure
failure_layer
retrieval_contract_status
evidence_ledger_status
claim_plan_status
validation_status
missingness_status
ui_provenance_status
primary_root_cause
proposed_general_rule
nearest_nonidentical_regression_case
risk_of_regression
```

## Allowed fix rule

A residual fix is allowed only if it can be expressed as a general rule that could apply to an unseen question.

Every fix must include a written generalisation statement in the PR/commit notes:

```text
This change fixes <failure class> by <general mechanism>.
It does not inspect UAT ID, literal UAT wording, expected source identifiers or expected answer text.
The rule should also apply to <nonidentical example/query class>.
```

## Prohibited residual fixes

Do not:

- `if uat_id == ...`;
- compare the query to a complete UAT question string;
- inject a known PID solely because the CSV expects it;
- copy expected prose into prompts/templates;
- use Graham Newman comments at runtime;
- set PASS by bypassing inference;
- relax provenance validation merely to make a case pass;
- modify the baseline CSV expected fields.

## Fix granularity

Prefer one failure class per bounded change.

Examples of acceptable residual classes:

- a general entity alias resolver misses surname-only references;
- period sorting is structurally incorrect;
- source metadata date normalisation fails for a document family;
- synthesis validator incorrectly rejects a supported comparison because of a schema edge case;
- UI grouping loses provenance when source date is null.

Examples of unacceptable residual classes:

- `MLT-DOC-05 needs PID X`;
- `for the Archer question add these four documents`;
- `if the question mentions this exact phrase, return this answer`.

## Testing requirement per residual fix

Each fix needs at least:

1. the failing UAT case as a regression test/fixture where appropriate;
2. one nonidentical test proving the rule generalises;
3. one nearby regression test proving the change does not broaden evidence incorrectly.

## Human-in-the-loop gate

After each coherent residual batch, rerun only the directly affected UAT cases plus the two must-not-regress cases:

- `MLT-DOC-18`
- `MLT-LIM-01`

Do not run the full manual 50 after every tiny fix.

## Remediation Batch 1: Hybrid Query Decomposition

### Generalisation

This change fixes hybrid retrieval contamination by deriving a documentary query surface from the typed documentary clause and retaining only structured documentary anchors. It does not inspect a UAT ID, literal UAT wording, expected source identifiers, or expected answer text. The rule also applies to hybrid questions whose documentary clause refers back to a person or project named in the authority clause.

### Implementation

- `decompose_hybrid_question` deterministically identifies the documentary proposition at the existing hybrid connector and preserves explicit Job/project anchors.
- Archive-first retrieval resolves controlled entities for anchoring, then builds documentary planning, quoted-concept retrieval, and within-document ranking from the documentary query surface.
- A hybrid request without a deterministically recoverable documentary proposition returns a typed zero-documentary result; it does not silently reuse the full hybrid wording.
- Authority lookup and pure documentary routing remain unchanged.

### Regression and Validation

- Focused regression suite: 44 tests passed across question routing, exploratory planning, and archive-first retrieval.
- The tests cover authority/documentary separation, preserved Job anchors, authority-vocabulary ranking exclusion, unchanged non-hybrid behavior, and the fail-closed no-clause path.
- Live run: `artifacts/ml_triage_dev_v2/uat_runs/sow06_hybrid_decomposition/ml-triage-v2-20261001T092036Z-4c1d9458/`.
- The live run completed `MLT-DOC-16`, all 10 authority cases, all 14 hybrid cases, and all 8 scoped-missingness cases: 10 `success`, 23 `validated_bounded_answer`.
- `MLT-HYB-08` moved from residual to resolved. Its post-fix authority result remains Pierre Goumain / Science Research Council; its selected documentary passages are Job 171 reports nominated by the preserved Job 171 anchor and the documentary terms `research` and `needs`. The previous full-query ranking admitted authority-side vocabulary; the post-fix answer identifies the report's management-information-system and successful-system-design research needs from direct documentary passages.
- `MLT-DOC-16`, `MLT-LIM-01`, and the SoW04/SoW05 sentinel cases completed without an execution or provenance regression. They remain classified independently in the residual report unless their own acceptance criteria are met.

## Remediation Batch 2: Project-Family Boundaries for Comparative Hybrids

### Generalisation

This change fixes loss and union treatment of explicitly named project families by parsing Job/project series and requiring deterministic attribution for each requested family before selection backfill. It does not inspect a UAT ID, literal UAT wording, expected source identifiers, or expected answer text. The rule applies to an unseen comparison such as `Projects 146, 175 and 182`, including a shared document that explicitly refers to more than one requested project.

### Implementation

- `project_anchors_from_question` parses singular and plural `Job(s)` / `Project(s)` lists joined by commas, `and`, or `&`.
- Candidate attribution is deterministic: either its exact Job identifier matches, or its metadata/provenance explicitly names the requested Job/project. A generic or different project cannot satisfy requested coverage.
- Comparative selection gives every requested project family one selection pass before duplicate or diversity backfill. Shared documents retain every requested family to which they are explicitly attributable.
- For a project-family comparison, an authority-side person anchor remains available as context but cannot exclude a required project report merely because that report does not name the person.

### Regression and Validation

- Focused contract suite: 16 tests passed. It covers plural extraction, per-family selection ahead of duplicates, exclusion of a non-requested project, shared A/B attribution, and authority-context person filtering not suppressing a requested project family.
- Combined Batch 1/2 suite before the final authority-context regression: 59 tests passed. The final added regression and all 15 earlier contract tests passed as part of the 16-test contract suite.
- Clean post-fix live run: `artifacts/ml_triage_dev_v2/uat_runs/sow06_project_family_boundaries_postfix/ml-triage-v2-20261001T100018Z-46d2ceb3/`.
- `MLT-HYB-06` now parses `146` and `175`, selects Job 175 and Job 146 sources, and reports both project anchors as found with none missing. It is not resolved: the final bounded answer renders only the Job 175 proposition despite the complete selected-family coverage.
- `MLT-HYB-09` selects the four Job 170 design-analysis report families rather than unrelated material, but its final answer synthesizes only the first report's material. It is not resolved because the question requires report-series coverage in the answer.
- Control traces `MLT-HYB-05` and `MLT-DOC-18` completed as `validated_bounded_answer` in the clean post-fix run; their hybrid routing and documentary provenance surfaces remained present. The original six-case Batch 2 run `artifacts/ml_triage_dev_v2/uat_runs/sow06_project_family_boundaries/ml-triage-v2-20261001T095328Z-7fd53f11/` completed all six cases, including `MLT-LIM-01` as `SCOPED_MISSINGNESS` / `configured_question_policy_reservation_v1`.
- The final repeated `MLT-LIM-01` request stalled in the model narrative stage and was stopped; no production guardrail behavior was changed by this batch. This is a harness/runtime interruption, not a passing replacement trace.
- The broader SoW04/SoW05 suite still has its known unrelated baseline drift: 166 tests with 2 failures and 8 errors in stale telemetry and fake exploratory interfaces. Those failures were not modified by this batch.

### Residual Decision

No residual rows were removed. The deterministic project-family retrieval defect is remediated, but both target cases retain a downstream claim-plan/rendered-answer coverage defect. The residual ledger remains at 33 unresolved rows.

## Remediation Batch 3: Required Evidence Family Propagation

### Generalisation

This change fixes required-evidence-family loss by carrying deterministic family attribution from selected retrieval results through evidence packets, evidence cards, final claim planning, rendered claims, and provenance. It does not inspect a UAT ID, literal UAT wording, expected identifiers, or expected answer text. It applies to any multi-family documentary request for which selection establishes required family coverage.

### Implementation and First Loss Stage

- The first loss was the retrieval-result to evidence-packet boundary: Batch 2 `project_anchor_matches` existed on selected results but was not retained by `EvidencePacketBuilder`.
- Evidence cards and final-plan claims now carry `required_evidence_families`.
- If a required family lacks a rendered supported claim, the pipeline appends only the existing validated claim-plan claim for that family. It does not require every selected source to appear.

### Regression and Live Validation

- Two focused Batch 3 regressions pass for partial two-family and multi-family prose: missing planned family claims are completed, while unplanned sources are not introduced.
- Batch 2 retrieval-contract regression suite: 16 passed. The focused Batch 1/2 suite previously remained 60 passed; diagnostics and syntax compilation are clean.
- `MLT-HYB-06` final live trace: `artifacts/ml_triage_dev_v2/uat_runs/sow06_required_evidence_propagation_final/ml-triage-v2-20261001T102359Z-6556ba3c/MLT-HYB-06.json`. Job 175 and Job 146 each have a selected evidence card, supported plan claim, rendered claim, and separate citation. Authority employment context remains separately typed.
- `MLT-HYB-09` canonical live trace: `artifacts/ml_triage_dev_v2/uat_runs/sow06_required_evidence_hyb09_validation/ml-triage-v2-20261001T103411Z-b2b5fba6/MLT-HYB-09.json`. The four Job 170 reports were selected as four distinct sources, produced four direct evidence cards and supported plan claims, and all four claims rendered with corresponding provenance. The final answer retains exact Craig Johnson / Science Research Council authority context and does not manufacture parity or cite unrelated sources.
- The earlier `MLT-HYB-09` stall did not reproduce: canonical execution completed in 88.3 seconds. Retrieval was 199.7 ms, packet construction 3.2 ms, and the sole model narrative synthesis was 52.8 seconds for 477 prompt tokens / 213 output tokens. No recursive construction, duplicated claim IDs, oversized input, or rendering loop was observed.
- Existing control traces remain valid: `MLT-HYB-05` and `MLT-DOC-18` completed as bounded valid answers, and `MLT-LIM-01` remained `SCOPED_MISSINGNESS`. No control route logic changed in Batch 3.

### Residual Decision

`MLT-HYB-06` and `MLT-HYB-09` are resolved and removed from the residual ledger. The ledger now contains 31 unresolved rows. SoW 06 remains `in_progress`.

## Remediation Batch 4: Documentary Proposition Quality

### Generalisation

This change prevents a passage from becoming a documentary claim merely because it is lexically similar to the query. Within an already selected source, it requires the bounded proposition span to be readable text with sufficient alphabetic and lexical content, a sentence boundary within the claim span, no table/layout marker, and a recognisable documentary predicate. It does not inspect a UAT ID, literal question wording, expected identifiers, or expected answer text. The same rule applies to a nonidentical report whose OCR returns a high-scoring repeated fragment beside a lower-scoring complete sentence.

### Implementation and First Loss Stage

- The first deterministic loss point is `ExploratoryRetrievalService._select_best_passage`: it previously used only basic length/alphabetic checks and then allowed the lexical score to choose a label, list, or truncated OCR fragment.
- Passage quality is now evaluated against the same bounded textual span that can reach an evidence card. The rule rejects image/table/layout fragments, short or low-alphabetic spans, incomplete spans, repetitive incomplete OCR, and text without a documentary predicate.
- Existing source nomination, project-family attribution, Batch 3 required-family propagation, evidence-card provenance, and final-plan rendering are unchanged. A source with no adequate selected proposition follows the existing `DOCUMENTARY_EVIDENCE_INSUFFICIENT` path rather than manufacturing a claim.

### Regression and Live Validation

- Focused retrieval regressions cover: a coherent same-source passage defeating a higher-scoring repetitive fragment; a concise complete sentence remaining eligible; labels and incomplete spans being rejected; no adequate proposition for fragment-only material; and a long chunk whose thin first sentence would otherwise be emitted as the claim. The focused selection suite passed 16 tests; the selection plus archive-first suite passed 43 tests.
- `MLT-HYB-04` was the representative evidence-quality trace. Before the quality gate it rendered labels such as `CURRICULUM VITAE; Janet Daley`, recipient lists, and table/list material as direct documentary propositions. The final bounded-span trace, `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch4_proposition_quality_bounded_span/ml-triage-v2-20261001T114056Z-6ff66f07/MLT-HYB-04.json`, omits the thin `Not many people.` proposition and records a documentary-insufficiency classification rather than treating an inadequate source as claim-ready.
- The immediately preceding five-case live control run, `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch4_proposition_quality_final_refined/ml-triage-v2-20261001T113453Z-c25ca9bb/`, completed `MLT-HYB-04`, `MLT-HYB-05`, `MLT-HYB-06`, `MLT-DOC-18`, and `MLT-LIM-01` as `validated_bounded_answer`. The final bounded-span target rerun completed as `validated_bounded_answer`.
- A wider 155-test retrieval/archive/evidence-pipeline run exposed one existing telemetry expectation whose narrative-synthesis stage reports `success` rather than the test's expected `skipped`; it is outside the changed selector path and was not modified. The relevant selection/archive coverage passes, and `git diff --check` passes.

### Residual Decision

No row is removed. The representative trace is cleaner and bounded, but `MLT-HYB-04` still requires its existing person-to-document relevance expectation to be satisfied before it can move from residual to resolved. The ledger remains at 31 unresolved rows. SoW 06 remains `in_progress`.

## Remediation Batch 5: Cross-Document Role Coverage

### Generalisation

This change fixes comparison requests that name distinct document roles but were previously considered covered by generic documentary retrieval. It derives deterministic roles from the question, requires one candidate matching each role before generic diversity backfill, and exposes any unmatched role as a retrieval coverage shortfall. It does not inspect UAT IDs, source identifiers, expected prose, or model confidence.

### Implementation and Validation

- `RetrievalContract` now records requested document roles such as teaching, paper, record, note, assessment, and calendar. `diversify_candidates` selects each named role before ordinary source diversity and reports found/missing roles in retrieval coverage.
- The focused regression proves that a teaching-versus-papers question selects both roles and cannot be marked fully covered by teaching material alone. The retrieval-contract suite passed 17 tests; the combined contract and archive-first suite passed 44 tests; `git diff --check` passed.
- Live representative trace: `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch5_document_roles/ml-triage-v2-20261001T121510Z-74fb6e35/MLT-DOC-06.json`. It completed as `validated_bounded_answer` and reports `partially_satisfied` retrieval coverage with an explicit missing document-role diagnostic rather than silently treating generic documentary material as a full comparison.

### Residual Decision

No row is removed. `MLT-DOC-06` now has a bounded, inspectable cross-document coverage result, but it does not yet satisfy its existing requirement for a documented comparison. The ledger remains at 31 unresolved rows. SoW 06 remains `in_progress`.

## Stop condition

## Residual Triage Before Batch 6

### Scope and decision rule

This is a read-only assessment of the unchanged 31-row residual ledger. It uses the ledger's recorded pipeline statuses plus the canonical traces, including Batch 4's bounded-passage `MLT-HYB-04` trace and Batch 5's document-role `MLT-DOC-06` trace. A `Yes` in **bounded correct** means that the current bounded answer does not make an unsupported historical assertion; it does not mean that the UAT expectation is satisfied.

| Bucket | Count | Meaning |
| --- | ---: | --- |
| A | 20 | A general deterministic defect remains; a candidate Batch 6 rule may address it. |
| B | 10 | Available digitised evidence does not establish the requested result under the current provenance rules. |
| C | 1 | The residual needs a researcher/UAT decision before a software-remediation claim can be made. |

### Per-case classification

| UAT ID | Bucket | Root cause | First failing stage | Evidence upstream | Safe deterministic fix | Bounded correct | Confidence | Recommended action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| MLT-DOC-01 | B | Only a narrow materialised teaching slice supports the requested overview. | Retrieval coverage | Partial | No | Yes | High | Retain the scoped result; enrich/materialise corpus before changing acceptance. |
| MLT-DOC-02 | B | Required scientific-method facets include unavailable or insufficiently documented teaching material. | Retrieval coverage | Partial | No | Yes | High | Retain bounded result; do not infer missing conceptual links. |
| MLT-DOC-03 | B | The teaching-practice versus infrastructure distinction has only one material direct source after quality controls. | Retrieval coverage | Partial | No | Yes | Medium | Treat as corpus insufficiency pending additional materialised course evidence. |
| MLT-DOC-04 | B | Batch 6 preserves activity facets and establishes only simulation; games, modelling, and learning-by-doing have no direct eligible support. | Retrieval evidence availability | Partial | No | Yes | High | Retain the explicit activity gaps; do not substitute theoretical or relation-only material. |
| MLT-DOC-05 | A | Early/late Archer comparison is not bound to dated evidence buckets despite valid material across the span. | Retrieval contract | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-06 | B | Batch 5 finds `teaching` but not required `paper`; the documented comparison cannot be completed. | Retrieval coverage | No | No | Yes | High | Keep Batch 5 partial-coverage diagnostic and bounded result; do not force a second role. |
| MLT-DOC-07 | A | Variant comparison does not require distinct dated document evidence before repeated/adjacent material. | Retrieval diversification | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-08 | A | Institutional collection selection has no requirement for distinct relevant document genres. | Retrieval diversification | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-09 | A | Early/late DEU priorities are not represented as mandatory dated comparison facets. | Retrieval contract | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-10 | A | The named notes and assessment-document roles are not both bound to the analytical comparison. | Retrieval contract | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-11 | A | The explicit oral-history versus contemporary-evidence comparison is not carried as two claim-plan obligations. | Claim-plan coverage | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-12 | B | No subject-matched Reffin-Smith testimony establishes the requested comparison in the eligible corpus. | Retrieval evidence availability | No | No | Yes | High | Retain scoped absence; do not substitute generic oral history. |
| MLT-DOC-13 | A | Valid multi-aspect material is rendered in source order rather than course-content, audience, and framing dimensions. | Narrative planning | Yes | Yes | Yes | High | Schedule as the narrative-shape cluster, not Batch 6's selected class. |
| MLT-DOC-14 | A | Institutional-family and chronological facets are selected but not jointly required. | Retrieval contract | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-DOC-15 | A | Valid dated Rector-report material loses its chronological organising field in the final plan. | Narrative planning | Yes | Yes | Yes | High | Schedule as the narrative-shape cluster, not Batch 6's selected class. |
| MLT-DOC-16 | B | Two required Job 171 assets have no materialised text; surviving reports cannot establish the full expectation. | Corpus representation | Partial | No | Yes | High | Preserve source-specific representation gaps; prioritise corpus remediation separately. |
| MLT-DOC-17 | A | Explicit Job 146/175 boundaries are not retained through final comparison selection, allowing adjacent-job bleed. | Retrieval diversification | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-HYB-01 | A | Person-specific teaching claims do not require a direct person-named documentary passage. | Retrieval contract | Yes | Yes | Yes | Medium | Include in explicit-facet coverage remediation. |
| MLT-HYB-02 | A | Teaching component is not diversified by document identity before repeated evidence is admitted. | Retrieval diversification | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-HYB-03 | B | Available course material does not establish Patrick Purcell's asserted course-note contribution. | Evidence availability | No | No | Yes | High | Retain a person-specific scoped limit; do not convert authority context into authorship. |
| MLT-HYB-04 | B | Post-Batch-4 material is relation-only, unrelated, or documentary-insufficient for an activity claim. | Evidence availability | No | No | Yes | High | Retain the bounded result and strict authority/document separation; do not reinstate weak propositions. |
| MLT-HYB-05 | A | Independent person evidence is not required before assessing the DEU connection for both named people. | Retrieval contract | Yes | Yes | Yes | Medium | Include in explicit-facet coverage remediation. |
| MLT-HYB-07 | B | Job 171 report text does not name Pierre Goumain, so authority employment cannot prove the project connection. | Evidence availability | No | No | Yes | High | Preserve authority/report separation and a scoped limit. |
| MLT-HYB-10 | A | Authority identifiers and report titles are not deterministically reconciled as distinct typed labels. | Claim planning | Yes | Yes | Yes | High | Address in the typed relevance-and-reconciliation cluster. |
| MLT-HYB-11 | A | Authority fields and report feasibility findings are not reliably compiled as separate typed claims. | Claim planning | Yes | Yes | Yes | High | Address in the typed relevance-and-reconciliation cluster. |
| MLT-HYB-12 | A | Documentary attribution is not constrained by the authority employment interval. | Temporal claim validation | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-HYB-13 | A | Controlled period labels are not translated into dated documentary test obligations. | Retrieval/claim-plan coverage | Yes | Yes | Yes | Medium | Include in explicit-facet coverage remediation; qualify unsupported labels rather than infer confirmation. |
| MLT-HYB-14 | C | The baseline has no expected-answer decision, so completeness/significance cannot be determined mechanically. | Evaluation | Partial | No | Yes | High | Obtain researcher review; leave baseline fields unchanged. |
| MLT-LIM-06 | A | Final selection retains a passage irrelevant to the authorship evidence test. | Narrative selection | Yes | Yes | No | High | Address in the typed relevance-and-reconciliation cluster. |
| MLT-LIM-07 | A | Direct Baynes/Roberts relationship evidence exists but generic DEU context outranks it. | Retrieval ranking | Yes | Yes | Yes | High | Include in explicit-facet coverage remediation. |
| MLT-LIM-08 | A | Closure attribution admits contextual name matches that do not bear on the decision under test. | Evidence relevance | Yes | Yes | No | High | Address in the typed relevance-and-reconciliation cluster. |

### Bucket A clusters

| Rank | Cluster | Cases | Defect confidence | Generality | Risk |
| ---: | --- | --- | --- | --- | --- |
| 1 | Explicit query-facet coverage through retrieval and claim planning | DOC-05, DOC-07 to DOC-11, DOC-14, DOC-17, HYB-01, HYB-02, HYB-05, HYB-12, HYB-13, LIM-07 (14) | High | High | Medium |
| 2 | Typed relevance and authority/document reconciliation | HYB-10, HYB-11, LIM-06, LIM-08 (4) | High | High | Low to medium |
| 3 | Narrative organisation of already-supported claims | DOC-13, DOC-15 (2) | High | Medium | Low |

### Proposed Batch 6: explicit query-facet coverage

**General defect class:** the retrieval contract and final claim plan do not consistently preserve every explicit, answer-shaping facet in a multi-surface question. Existing contracts cover some source roles, project families, periods, and evidence types, but not the complete conjunction of requested activity, concept, genre, named-person, relationship, and temporal-attribution facets.

**Proposed deterministic rule:** derive explicit facets from the normalised question and require one directly relevant selected passage or supported claim for each facet before generic diversity backfill. Facets with no eligible direct evidence must remain visible as scoped coverage gaps; they must not be satisfied by authority context, metadata association, a neighbouring project, or a generic collection match.

- Representative UAT cases: `MLT-DOC-05`, `MLT-DOC-07`, `MLT-DOC-10`, `MLT-DOC-11`, `MLT-DOC-14`, `MLT-DOC-17`, `MLT-HYB-01`, `MLT-HYB-02`, `MLT-HYB-12`, `MLT-LIM-07`.
- Nearest nonidentical regression controls: `MLT-DOC-06` must continue to report the missing `paper` role rather than fabricate a comparison; `MLT-HYB-04` must continue to reject relation-only activity claims; `MLT-DOC-18` and `MLT-LIM-01` remain the required SoW controls.
- Expected regression risk: medium. Extra facet obligations can reduce answer breadth or expose legitimate corpus gaps, so selection must remain fail-closed and preserve existing single-document and narrow-question behaviour.
- Anti-memorisation rationale: the rule operates on parsed query facets and source/claim metadata only. It does not inspect UAT IDs, full question literals, known source identifiers, expected answers, or baseline outcomes. It applies equally to an unseen request containing multiple explicit documentary surfaces, and returns a bounded coverage gap when the corpus cannot meet one.

### Remediation Batch 6: Explicit Query-Facet Coverage

#### Implementation and first loss stage

- The earliest safe structured loss point was `RetrievalContract`: it had source, role, project, and temporal fields but no typed obligation able to survive into candidate selection and claim planning.
- `FacetRequirement` now represents deterministic source-role, person, activity, relationship, and temporal obligations. The derivation uses existing structured entity anchors, named document-role patterns, temporal routing, and a constrained activity/relationship vocabulary; it does not call a model or inspect UAT data.
- Candidate diversification selects explicit facet matches before generic backfill and records machine-readable `facets_found` and `facets_missing`. Every selected result carries its required and supported facets through evidence packets, cards, the evidence ledger, and the compact final claim plan.
- The final plan emits a deterministic bounded limit for each missing facet. This preserves the gap rather than completing it with semantically adjacent, metadata-only, or authority evidence.

#### Focused regressions and validation

- New contract regressions cover thematic omission, activity/relationship non-substitution, derived temporal/source-role facets, and a multi-facet request where one person is missing. `tests.test_retrieval_contract_service` passes 21 tests.
- New evidence-pipeline regression proves that required/supported facets persist from an evidence card into final-plan found/missing coverage. The focused test passes.
- Combined focused Batch 1-6 suite ran 176 tests. The only failure is the existing unrelated narrative-telemetry mismatch (`expected skipped`, `actual success`); no Batch 6 test fails. Pylance and workspace diagnostics report no errors in the changed sources/tests.
- Live evidence: `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch6_facet_coverage/ml-triage-v2-20261001T123555Z-0c00c51a/` and `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch6_facet_coverage_remaining/ml-triage-v2-20261001T124136Z-1d459617/`. All six representatives completed as `validated_bounded_answer` with inspectable requested facets, retrieval/card/plan coverage, bounded gaps, and existing citation binding.
- No Bucket A residual meets its full existing UAT expectation solely from this batch, so no residual is removed. `MLT-DOC-04` is reclassified A -> B because the new activity diagnostics show that only simulation is directly supported; games, modelling, and learning-by-doing remain absent.

### Remediation Batch 7: Multi-Source Facet Aggregation

#### Implementation and first loss stage

- The remaining structured loss point was the compact claim plan: retrieval could establish `temporal:multiple_periods` from distinct dated sources, but cards only carried source-local supported facets and the plan therefore reported the aggregate temporal obligation as missing.
- Selected results now carry structured facet contributions. Each contribution retains its facet, component (such as `1970s`), evidence-card ID, source ID, and the card's direct documentary proposition through the evidence packet, card, ledger, and compact plan.
- The only aggregate rule introduced is fail-closed: `temporal:multiple_periods` is found only when at least two distinct temporal components contribute. A single component stays missing. The plan retains the individual propositions and creates no causal, evolutionary, conflict-resolution, or other cross-source bridge claim.

#### Focused regressions and validation

- Focused regressions prove attributable two-source temporal coverage and that a single temporal component remains bounded. Both pass. Workspace diagnostics report no errors in the changed sources or test.
- Live evidence: `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch7_aggregation/ml-triage-v2-20261001T124825Z-39b53f8e/`. All six selected targets and controls completed as `validated_bounded_answer`.
- `MLT-DOC-05` now marks `temporal:multiple_periods` found in the compact plan, with inspectable 1970s/1980s source, card, and proposition contributions. It remains residual because the full requested account of change would require an independently warranted comparative claim, which Batch 7 intentionally does not invent.
- `MLT-DOC-11` continues to report the missing retrospective testimony facet in the compact plan; aggregation does not mask that single-facet source gap. `MLT-DOC-04`, `MLT-HYB-06`, `MLT-DOC-18`, and `MLT-LIM-01` remain bounded controls with no regression in their scoped gaps.

### Post-Batch-7 Re-Cluster

This is a read-only reassessment of the 20 cases that were in Bucket A before Batches 6 and 7. It uses the current contract, ledger, claim-plan, and canonical trace evidence. It does not alter UAT expectations or production behaviour.

| UAT ID | First current failing stage | Upstream evidence and typing | Facet/claim-plan result | Revised bucket | Decision |
| --- | --- | --- | --- | --- | --- |
| MLT-DOC-05 | None requiring remediation | Direct propositions from distinct periods are attributable | Multi-period facet is found; change remains unproved | B | Do not manufacture an account of change. |
| MLT-DOC-07 | Retrieval coverage | Variant comparison has no sufficiently typed balanced direct evidence | Coverage remains bounded | B | Do not treat adjacent or repeated material as a comparison. |
| MLT-DOC-08 | Retrieval coverage | Relevant collection material lacks direct recommendation/outcome genre support | Coverage remains bounded | B | Do not infer document function from collection membership. |
| MLT-DOC-09 | Retrieval coverage | Dated material does not establish the requested early/late priority comparison | Temporal gap remains bounded | B | Distinct dates do not themselves prove comparative priorities. |
| MLT-DOC-10 | Retrieval coverage | Named roles are represented but no direct comparison is independently established | Role facets reach the plan | B | Do not synthesize a comparison beyond individual propositions. |
| MLT-DOC-11 | Retrieval coverage | Contemporary teaching is direct; retrospective testimony remains absent | Retrospective facet is explicitly missing | B | Do not substitute contemporary material for testimony. |
| MLT-DOC-13 | Narrative planning | Typed direct claims are available | Claims reach plan but lack requested analytical organisation | A | Retain as narrative-organisation defect. |
| MLT-DOC-14 | Retrieval coverage | Institutional material is not direct support for all named family/date surfaces | Gaps remain bounded | B | Do not treat generic institutional material as prospectus/calendar evidence. |
| MLT-DOC-15 | Narrative planning | Dated direct claims are available | Claims reach plan but lose chronological organisation | A | Retain as narrative-organisation defect. |
| MLT-DOC-17 | Retrieval coverage | Project material outside requested anchors is not comparison evidence | Project boundary is bounded | B | Do not broaden project identity by lexical Job match. |
| MLT-HYB-01 | Retrieval coverage | Named-person documentary passage is absent for the missing role | Role gap is explicit | B | Preserve subject-specific scoped absence. |
| MLT-HYB-02 | Retrieval coverage | Repeated teaching material lacks independently typed theme support | Diversity gap is bounded | B | Do not count repeated chunks as distinct teaching evidence. |
| MLT-HYB-05 | Evidence availability | Employment overlap does not directly establish a relationship | Relationship remains conditional | B | Do not infer collaboration from overlap. |
| MLT-HYB-10 | Claim planning | Authority identifiers and report labels are separately valid and typed | Typed distinction is not reliably preserved in claims | A | Retain as typed claim-admissibility defect. |
| MLT-HYB-11 | Claim planning | Authority facts and documentary findings are separately valid and typed | Evidence-type separation is not reliably preserved in claims | A | Retain as typed claim-admissibility defect. |
| MLT-HYB-12 | Temporal claim validation | Authority interval is typed; later documentary material is available but incompatible | Incompatible attribution can enter claims | A | Retain as typed claim-admissibility defect. |
| MLT-HYB-13 | Retrieval coverage | Period labels are authority context, not direct documentary confirmation | Label-testing gap is bounded | B | Do not convert labels into historical findings. |
| MLT-LIM-06 | Claim planning | Relation-only status and relevance classification are already available | Irrelevant supervision claim can reach plan | A | Retain as question-scoped relevance defect. |
| MLT-LIM-07 | Retrieval coverage | No direct collaboration proposition is selected as support | Relationship gap is explicit | B | Do not infer collaboration from institutional context. |
| MLT-LIM-08 | Claim planning | Dispositive closure evidence is distinguishable from contextual name matches | Non-dispositive claims can reach plan | A | Retain as question-scoped relevance defect. |

#### Remaining genuine Bucket A clusters

| Cluster | Cases | Count | First failing stage | Assessment |
| --- | --- | ---: | --- | --- |
| Typed claim admissibility and question-scoped relevance | MLT-HYB-10, MLT-HYB-11, MLT-HYB-12, MLT-LIM-06, MLT-LIM-08 | 5 | Evidence/claim planning | Valid, typed upstream evidence is deterministically admitted into claims despite being the wrong evidence type, temporally incompatible, or non-dispositive for the question. |
| Narrative organisation of established claims | MLT-DOC-13, MLT-DOC-15 | 2 | Narrative planning | Direct claims reach the plan but are not organised by the requested analytical dimensions or chronology. |

#### Strongest potential Batch 8 class

**Typed claim admissibility and question-scoped relevance** is the only proposed Batch 8 class. It affects five nonidentical cases and has valid upstream structured evidence: authority/document type, source identity, temporal interval, evidence classification, and question-bearing relevance are available before claim compilation. The deterministic failure is downstream admission of a claim that does not meet the question's required evidential status.

**Proposed deterministic rule:** permit an evidence card to support a rendered claim only when it satisfies both its typed provenance constraint and the question-scoped admissibility constraint. A document outside a person's authority interval cannot support a person-attribution claim; authority context cannot support a documentary finding; and contextual or relation-only evidence cannot support a dispositive evidence-test claim. Preserve such material in the ledger as context or a visible limit, rather than silently dropping provenance or treating it as direct support.

- Representative cases: `MLT-HYB-10`, `MLT-HYB-11`, `MLT-HYB-12`, `MLT-LIM-06`, `MLT-LIM-08`.
- Regression risk: medium. Over-broad filtering could suppress legitimate retrospective discussion or contextual explanation, so the rule must govern claim support and claim rendering, not evidence retention.
- Nearest nonidentical controls: `MLT-HYB-04` (relation-only evidence stays non-attributive), `MLT-LIM-01` (scoped missingness remains visible), `MLT-HYB-08` (available report text survives a personnel gap), and `MLT-DOC-18` (ordinary documentary support remains eligible).
- Anti-memorisation rationale: the rule evaluates structured source type, temporal compatibility, claim relation, and evidence relevance. It does not inspect UAT IDs, expected prose, or fixed source identifiers.

### Remediation Batch 8: Typed Claim Admissibility and Question-Scoped Relevance

#### Generalisation

This change prevents valid but question-inadmissible evidence from becoming direct claim support. It evaluates typed provenance and question-scoped admissibility before compact-plan admission, while retaining excluded material in the evidence ledger with its limit and provenance. It does not inspect UAT IDs, expected prose, or fixed source identifiers.

#### Implementation and validation

- Evidence cards carry structured admissibility decisions; only `DIRECT_SUPPORT` cards can ground direct claims. Contextual and insufficient cards remain inspectable.
- Hybrid authority assembly now converts authority context plus an explicit documentary uncertainty into `deterministic_evidence_limit` / `evidential_limit`, preserving both the authority claim and documentary limit.
- The complete route-path regression covers valid authority context, an explicit-title document, no admissible documentary claim, and an explicit documentary limit. The focused complete-path and projection regressions pass.
- Canonical live validation: `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch8_admissibility_final2/ml-triage-v2-20261001T141558Z-0148a8ac/`. All nine cases completed: five `validated_bounded_answer` and four `scoped_limit`; no synthesis-validation errors occurred.
- Follow-up claim-level validation: `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch8_claim_admissibility_targets/ml-triage-v2-20261001T143813Z-9edfacd9/` returned `scoped_limit` for both `MLT-HYB-12` and `MLT-LIM-08`. The seven-control run at `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch8_claim_admissibility_controls/ml-triage-v2-20261001T144203Z-23032f00/` retained four `scoped_limit` and three `validated_bounded_answer` outcomes.

#### Target decisions

| UAT ID | Batch 8 evidence | Decision |
| --- | --- | --- |
| MLT-HYB-10 | Eight documentary cards are `INSUFFICIENT`; authority context and the explicit documentary limit render together as a scoped limit. | RESOLVED |
| MLT-HYB-11 | Seven documentary cards are `INSUFFICIENT`; authority context remains visible and no unsupported feasibility claim renders. | A -> B evidence insufficiency |
| MLT-HYB-12 | Proposition-specific card admission now applies the matching employment interval before direct claim admission; incompatible material remains contextual and the live result is a scoped limit. | RESOLVED |
| MLT-LIM-06 | The relation-only card is `INSUFFICIENT`; no direct claim renders and the answer is a scoped limit. | RESOLVED |
| MLT-LIM-08 | Proposition-specific relationship matching now prevents non-dispositive bursary and postgraduate material from becoming direct closure support; the live result is a scoped limit. | RESOLVED |

`MLT-HYB-04`, `MLT-HYB-08`, `MLT-LIM-01`, and `MLT-DOC-18` remain healthy controls with visible provenance and bounded results. `MLT-DOC-13` and `MLT-DOC-15` remain the two narrative-organisation cases: direct claims are available, but the requested analytical and chronological organisation is still absent.

### Triage conclusion

Batches 6, 7, and 8 are complete. After the Batch 8 target decisions, the residual ledger contains 27 rows: 2 Bucket A, 24 Bucket B, and 1 Bucket C. UAT expectations, provenance rules, scoped-missingness rules, and bounded-answer semantics remain unchanged. SoW 06 remains `in_progress`.

The remaining Batch 8 A defects are resolved through one general proposition-specific admissibility rule. A final Batch 9 for narrative organisation is now eligible, but has not been started.

### Remediation Batch 9: Narrative Organisation of Established Claims

#### Generalisation

This change carries existing source dates into compact claims, orders temporal moves by those dates, and groups explicit multi-part questions by their requested components. It does not inspect UAT IDs, literal UAT wording, expected source identifiers, or expected answer text. Claim bindings, evidence classes, and bounded limits remain application-owned.

#### Validation and database parity recovery

- Focused regressions cover multi-part claim/limit preservation, chronological move ordering, and provenance binding. Adjacent narrative controls pass. The evidence-pipeline suite remains 118/119, with only the pre-existing telemetry expectation mismatch.
- Live validation initially exposed a dev database parity issue: the legacy `init-db.sql` bootstrap does not apply numbered archive-first migrations or successor-corpus data. The canonical archive schema migrations and persisted snapshot materialisation were verified, then the dev database was cleanly restored from a verified local parity dump using `ON_ERROR_STOP`. The restored dev database contains 490 documents, 54,612 chunks, 136 asset snapshots, 222 authority-graph relations, and all required targeted successor corpora.
- Fresh canonical run: `artifacts/ml_triage_dev_v2/uat_runs/sow06_batch9_validated_post_parity/ml-triage-v2-20261001T160127Z-d4c4a49a/`. All six traces completed without schema or transport errors: five `validated_bounded_answer` and one `scoped_limit`.
- Controls remain bounded and provenance-bearing: `MLT-DOC-18`, `MLT-LIM-01`, and `MLT-HYB-08` completed as `validated_bounded_answer`; `MLT-HYB-10` completed as a scoped limit with authority context and an explicit documentary limit.

#### Target decisions

| UAT ID | Batch 9 evidence | Decision |
| --- | --- | --- |
| MLT-DOC-13 | The fresh bounded answer states the short-course design-method content and its product-design/public-sector framing, with traceable citations and preserved limits. | RESOLVED |
| MLT-DOC-15 | The final renderer preserves July 1968, December 1972, December 1983, and December 1985 as separate claim-bound paragraphs without an unsupported expansion proposition. | RESOLVED |

#### Final Batch 9 closure implementation and validation

- `application_owned_temporal_rendering` deterministically renders already sorted `TEMPORAL_CHANGE` moves with their existing compact-plan claim IDs and limits. The model cannot reorder those moves or introduce a relational proposition absent from the validated plan. Other answer shapes retain the existing narrative-realisation path.
- Focused generic regressions cover chronological plan order despite reverse retrieval input, absence of unsupported progression language, retention of explicitly supported change language, unchanged non-temporal routing, and preserved source bindings.
- Target trace: `artifacts/ml_triage_dev_v2/uat_runs/sow06_final_narrative_order/ml-triage-v2-20261001T181732Z-b562f990/MLT-DOC-15.json`. It completed as `validated_bounded_answer`; rendered claims are ordered `c1`, `c3`, `c2`, `c4`, each with its original supporting source. Both bounded limits remain present and the trace has no errors.
- Control trace: `artifacts/ml_triage_dev_v2/uat_runs/sow06_final_narrative_controls/ml-triage-v2-20261001T181744Z-101d6a35/`. `MLT-DOC-13`, `MLT-DOC-18`, `MLT-LIM-01`, and `MLT-HYB-08` are `validated_bounded_answer`; `MLT-HYB-10` is the expected `scoped_limit`. All controls have empty error lists and retained claim/source bindings and limit states.
- The focused evidence-pipeline suite ran 122 tests: 121 pass. The known unrelated exception is `test_staged_pipeline_records_safe_execution_telemetry`, whose stale expected `narrative_synthesis == skipped` conflicts with the existing `success` status.
- Production code contains no UAT-ID checks, literal UAT-question matching, hard-coded dates, expected source IDs, or special-cased connective words.

#### Final residual decision

`MLT-DOC-13` and `MLT-DOC-15` are removed from the residual ledger. The ledger now contains 25 rows: 0 Bucket A, 24 Bucket B, and 1 Bucket C. The remaining cases are corpus/evidence limitations or researcher/UAT decisions, so no further residual implementation is justified.

### Acceptance record

Human approval was recorded on 2026-10-02. SoW 06 is accepted and closed. Its retrieval, evidence, facet, admissibility, provenance, scoped-missingness, and narrative-rendering behaviour is frozen. Do not create Batch 10 or remediate the remaining Bucket B or Bucket C cases without a new explicitly authorised SoW.

Stop residual remediation when either:

- the build appears ready for the full-50 release gate; or
- remaining failures require a research/design decision rather than a safe implementation change.

Do not force an answer merely to reach a numerical target.

## Acceptance criteria

Proceed to SoW 07 when:

- all known residual fixes are expressed as general rules;
- no critical provenance/capability violation is known in the current build;
- both current PASS regressions remain healthy;
- `MLT-HYB-14` executes to a typed result;
- automated tests pass;
- the codebase contains no UAT-specific production branching.
