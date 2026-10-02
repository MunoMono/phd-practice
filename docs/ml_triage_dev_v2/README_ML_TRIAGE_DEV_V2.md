---
document_type: remediation_programme
programme_id: ML_TRIAGE_DEV_V2
status: ready_for_implementation
repo_path: /docs/ml_triage_dev_v2/
baseline_csv: /docs/ml_triage_dev_v2/clean_ml_triage_dev_UAT_50_v2.csv
baseline_total_cases: 50
baseline_pass: 2
baseline_fail: 47
baseline_unresolved_blank: 1
operational_unresolved: 48
release_threshold_pass_count: 40
release_threshold_pass_rate: 0.80
holdout_phase: questions_51_100_after_release_gate
---

# ML Triage Dev V2 - Remediation Programme

## 1. Purpose

Remediate the 48 operationally unresolved cases in `clean_ml_triage_dev_UAT_50_v2.csv` without memorising the first 50 UAT questions.

The current baseline is:

- 50 total UAT cases.
- 2 PASS: `MLT-DOC-18`, `MLT-LIM-01`.
- 47 explicit FAIL.
- 1 unresolved blank result: `MLT-HYB-14`.
- 48 operationally unresolved cases.

The release target for this phase is at least 40/50 PASS in a full human-in-the-loop UI rerun, with no critical provenance or capability violations.

After this release gate is passed, Questions 51-100 will be introduced as a holdout/generalisation set containing new entities, evidence combinations and harder edge cases. Do not use or anticipate those holdout questions during this remediation programme.

## 2. Non-negotiable programme rules

These rules apply to every SoW in this directory.

1. The CSV is diagnostic evidence, not a set of labels to reproduce.
2. Do not special-case any `uat_id` in production code.
3. Do not branch on the literal wording of any UAT question.
4. Do not hard-code expected answer text, known source stacks, PASS/FAIL values, Graham Newman comments, or expected source identifiers into production answer logic.
5. Do not inject manual answers for failing cases.
6. Fix general retrieval, evidence, validation or rendering behaviour that can apply to unseen questions.
7. Preserve the two existing PASS cases as must-not-regress tests.
8. Do not change the underlying archival corpus, authority records, source text, UAT CSV or UAT pass criteria merely to make tests pass.
9. Preserve the research evidence hierarchy. Database authority, archival metadata, documentary text, retrospective testimony and model synthesis are not interchangeable.
10. A missingness conclusion may only be produced after an adequate bounded retrieval attempt for the claim being tested.
11. A capability the system does not possess must not be simulated in prose. In particular, do not infer visual content from non-ML photographs.
12. Every code change must have automated tests appropriate to the layer changed.
13. Every SoW must pass its automated checks and targeted UI sentinel UAT before proceeding to the next SoW.
14. Prefer deterministic guardrails for evidence typing, coverage and validation. Do not rely on prompt wording alone for critical provenance rules.
15. Keep changes inspectable. Small, bounded commits are preferred to repo-wide rewrites.

## 3. Target architecture

The target flow is:

```text
user question
  -> question classification
  -> retrieval/evidence contract
  -> bounded candidate retrieval
  -> source diversification and coverage checks
  -> typed evidence ledger
  -> claim plan
  -> synthesis
  -> claim/evidence validation
  -> scoped missingness/capability validation
  -> provenance-aware UI rendering
```

Do not retain the effective pattern:

```text
retrieve top chunks -> send untyped chunks to model -> render prose
```

## 4. Evidence classes

Use the following conceptual evidence classes consistently. Reuse existing enums/types where they already exist rather than duplicating them.

- `DATABASE_AUTHORITY`: controlled database facts such as employment, project authority, period or methodology authority.
- `ARCHIVAL_METADATA`: catalogue metadata, derived source-person relations, keywords, collection associations and other descriptive metadata.
- `DIRECT_DOCUMENTARY`: contemporary documentary text from ML-enabled source assets.
- `RETROSPECTIVE_TESTIMONY`: later testimony such as oral-history transcripts.
- `QUALIFIED_SYNTHESIS`: model-generated interpretation explicitly grounded in typed evidence.
- `SCOPED_LIMIT`: a bounded statement about what the searched evidence surface can and cannot establish.

Core evidence hierarchy:

- Catalogue/source association does not establish action.
- Recorded action does not establish intent.
- Employment overlap does not establish collaboration.
- `PERSON_ASSOCIATED_WITH_SOURCE` does not establish authorship or leadership.
- Later recollection does not become contemporary evidence.
- Project authority does not automatically equal report authorship, group leadership or the wording of a report front matter field.

## 5. SoW execution order

Run in this order. Do not skip ahead unless the dependency is explicitly satisfied.

1. `SOW_00_BASELINE_REGRESSION_HARNESS.md`
2. `SOW_01_RETRIEVAL_CONTRACTS_SOURCE_DIVERSITY.md`
3. `SOW_02_EVIDENCE_TYPING_PROVENANCE_GUARDRAILS.md`
4. `SOW_03_CLAIM_PLANNING_SYNTHESIS_VALIDATION.md`
5. `SOW_04_SCOPED_MISSINGNESS_CAPABILITY_GUARDRAILS.md`
6. `SOW_05_AUTHORITY_HYBRID_RECONCILIATION_PROVENANCE_UI.md`
7. `SOW_06_RESIDUAL_CASE_REMEDIATION.md`
8. `SOW_07_FULL_50_RELEASE_GATE.md`

## 6. Primary failure-family routing

This routing is diagnostic, not a production rule. A UAT case may exercise more than one SoW.

### Retrieval/source coverage primary

`MLT-DOC-01`, `MLT-DOC-02`, `MLT-DOC-03`, `MLT-DOC-04`, `MLT-DOC-05`, `MLT-DOC-06`, `MLT-DOC-08`, `MLT-DOC-09`, `MLT-DOC-11`, `MLT-DOC-12`, `MLT-DOC-14`, `MLT-DOC-15`, `MLT-DOC-17`, `MLT-HYB-03`, `MLT-HYB-04`, `MLT-HYB-10`, `MLT-HYB-12`, `MLT-HYB-13`.

### Evidence typing/provenance primary

`MLT-DOC-11`, `MLT-DOC-12`, `MLT-DOC-16`, `MLT-HYB-01` through `MLT-HYB-14`, `MLT-LIM-04`, `MLT-LIM-06`, `MLT-LIM-07`.

### Synthesis/claim planning primary

`MLT-DOC-07`, `MLT-DOC-10`, `MLT-DOC-13`, `MLT-DOC-15`, `MLT-DOC-16`, `MLT-HYB-01`, `MLT-HYB-02`, `MLT-HYB-05`, `MLT-HYB-07`, `MLT-LIM-08`.

### Scoped missingness/capability primary

`MLT-LIM-02` through `MLT-LIM-08`.

### Authority/UI primary

`MLT-AUTH-01` through `MLT-AUTH-10`, plus all hybrid cases where authority and documentary evidence must remain visibly separate.

## 7. Human-in-the-loop development model

Do not require a full manual rerun of all 50 after every SoW.

For each SoW:

1. Run automated unit/integration/regression tests.
2. Run the SoW sentinel set through the real UI.
3. Inspect the source/evidence trace in the UI.
4. Record PASS/FAIL and defect notes.
5. Do not proceed if a critical provenance violation remains in a sentinel case.

After SoW 06, run the full 50 manually under SoW 07.

## 8. Critical violation definition

Any of the following is a release blocker regardless of numerical pass rate:

- Attributing testimony to a source that was not retrieved.
- Attributing documentary claims to database authority records.
- Treating metadata association as authorship, leadership, collaboration or action without documentary support.
- Inventing visual interpretation where no ML-enabled image evidence exists.
- Producing a causal historical claim where the evidence supports only sequence, association or context.
- Producing a scoped-missingness statement about a different claim from the one asked.
- Contradicting displayed authority data in the generated prose.
- Hard-coded UAT-specific production logic.

## 9. Release rule

Candidate release requires all of the following:

- At least 40/50 manual UI UAT cases PASS.
- `MLT-DOC-18` remains PASS.
- `MLT-LIM-01` remains PASS.
- Zero critical provenance/capability violations.
- `MLT-HYB-14` produces a complete auditable result rather than a blank execution state.
- No UAT-ID/literal-question/expected-answer hard coding in production logic.
- Source provenance is human-inspectable in the UI.

Only after this gate passes should the project create Questions 51-100 and run the later 100-question audit.
