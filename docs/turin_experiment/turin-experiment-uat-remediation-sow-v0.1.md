# Turin Experiment — UAT Remediation Statement of Work v0.1

**Project:** Retrieval-Augmented Archival Interrogation Experiment  
**Date:** 17 August 2026  
**Status:** Working remediation specification  
**Evidence baseline:** `turin-experiment-uat-v0.1.csv`  
**UAT result:** 135 tests; 79 PASS; 56 FAIL

## 1. Purpose

This Statement of Work converts the first manual User Acceptance Test into a controlled remediation programme for the Turin Experiment research instrument.

The original UAT CSV is evidence and must remain unchanged. This document does not retrospectively rewrite a failed test as a pass. Where investigation shows that a UAT expectation was incorrect, the implementation record must state that explicitly and the later UAT version must record the revised acceptance behaviour.

The remediation will proceed **page by page and function by function**. Copilot must investigate each item before changing code, make the smallest justified change, add machine-verifiable regression coverage where practical, and stop for human UAT confirmation before a page is considered accepted.

## 2. Controlling methodological constraints

UAT remediation must not alter the research method merely to make red cells green.

- PostgreSQL full-text search remains the principal retrieval method for the Turin experiment.
- pgvector/embedding retrieval must not silently replace or augment FTS.
- Semantic-atlas embeddings and UMAP are a separate visual-analytical capability. Their activation requires an explicit implementation decision and must not change the retrieval contract.
- Source-document evidence, archive/catalogue metadata, database-authority assertions, corpus-control/provenance metadata, generated inference and researcher assessment must remain distinguishable.
- Authority context remains optional and must never be presented as source-document evidence.
- No retrieval result, no authority record or no atlas point must never be converted into a claim of historical absence.
- Do not fabricate seed data, testimony passages, claims, embeddings, experiment runs or model responses simply to satisfy UAT.
- Do not hard-code record/PID mappings to make navigation tests pass.
- Preserve corpus version, provenance, page scope, rights/access controls and immutable experiment-run records.
- Passing behaviour already established by UAT v0.1 must not regress.

## 3. Remediation classifications

| Classification | Meaning |
|---|---|
| **DEFECT** | A currently implemented function does not behave as its intended user-facing contract requires. |
| **FUNCTIONAL GAP** | The UAT identifies a legitimate required function that is absent from the current interface/workflow. Confirm against the controlling SoW before implementation. |
| **BLOCKED / NOT YET ACTIVATED** | The UI cannot yet be meaningfully tested because required data, persisted records or an analytical prerequisite does not exist. Do not manufacture data to force a pass. |
| **SPECIFICATION / UX ISSUE** | Behaviour, labelling, scope or expected acceptance is ambiguous and must be clarified before code changes. |

## 4. Delivery sequence

1. Workbench
2. Sources
3. Source interrogation
4. Absences
5. Research runs
6. Cross-readings
7. Semantic atlas
8. Claims and evidence
9. Documentation
10. Full regression and human UAT v0.2

Global and Provenance behaviours that passed UAT v0.1 are frozen unless a justified remediation requires touching them.

## 5. Page-level operating procedure

For each page:

1. Inspect the current implementation and relevant API/database contracts.
2. Reproduce every failed UAT item without changing code.
3. Classify root cause; do not assume the UAT note identifies it.
4. Confirm intended behaviour against the technical SoW and current research method.
5. Implement only the smallest justified remediation.
6. Add/update unit or integration/browser regression coverage where appropriate.
7. Run relevant existing tests and build checks.
8. Record files changed, commands run, results and known limitations.
9. Stop and report.
10. Researcher manually reruns the affected UAT rows in production.
11. Only after human acceptance proceed to the next page.

## 6. UAT remediation register

# Workbench /workbench

**Failed UAT items:** 3

## UAT-018 — Archive resolution output

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Corpus status

### Manual test action
Inspect archive-resolved and unresolved-record metrics

### Expected behaviour
The two distinct counts are visible and not conflated.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Corpus metrics are individually plausible but semantically ambiguous. Dashboard mixes frozen experimental-corpus metrics with legacy database-record metrics without distinguishing their populations.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-018** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-018** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-019 — Embedding and PDF coverage

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Corpus status

### Manual test action
Inspect embedding and archive-linked PDF metrics

### Expected behaviour
The visible values identify separate corpus coverage measures.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Corpus metrics are individually plausible but semantically ambiguous. Dashboard mixes frozen experimental-corpus metrics with legacy database-record metrics without distinguishing their populations.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-019** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-019** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-022 — Dashboard charts

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Analytical surface

### Manual test action
Inspect analytical-surface panels

### Expected behaviour
Charts or their explicit no-data/error states render without overlap.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Need a tooltip on rollover/hover. Evidence density text description is clipped off.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-022** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-022** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Sources /sources

**Failed UAT items:** 2

## UAT-037 — Similar documents

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Source detail

### Manual test action
Inspect Similar documents

### Expected behaviour
Similar records or the explicit no-similar-documents state is shown.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Not really working for example if I am looking at RCA calendar or Rector's reports they should appear. Actually the similar documents could be pulled from the parent PID in ddrarchive.org

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-037** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-037** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-042 — Open DDR source

**UAT status:** FAIL  
**Classification:** DEFECT  
**Area:** Source actions

### Manual test action
For an enabled record select Open DDR source

### Expected behaviour
Configured archive source opens in a new tab; unavailable records keep control disabled.

### Observed UAT evidence
**Actual result:** 404 Not Found

**Researcher note:** example: https://ddrarchive.org/id/record/873981573030 equals Unexpected Application Error!

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-042** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-042** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Source interrogation /source-interrogation

**Failed UAT items:** 8

## UAT-051 — Scoped missingness

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Answer

### Manual test action
Run a query with a known evidence gap

### Expected behaviour
Scoped missingness is explicit and does not claim archive-wide absence.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** We need to work on this.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-051** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-051** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-053 — Overall claim status

**UAT status:** FAIL  
**Classification:** DEFECT  
**Area:** Answer

### Manual test action
Change Overall claim status

### Expected behaviour
Selected status visibly changes for the current view.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Nothing happens when I click the validation status dropdown.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-053** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-053** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-054 — Copy retrieval memo

**UAT status:** FAIL  
**Classification:** FUNCTIONAL GAP  
**Area:** Answer

### Manual test action
Select Copy retrieval memo and paste

### Expected behaviour
A memo for the current retrieval trail is copied.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** We just have a copy citation button, no memo.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-054** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-054** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-055 — Download retrieval memo

**UAT status:** FAIL  
**Classification:** FUNCTIONAL GAP  
**Area:** Answer

### Manual test action
Select Download retrieval memo

### Expected behaviour
A Markdown memo downloads for the current result.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** No markdown memo button.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-055** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-055** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-056 — Export retrieval trail

**UAT status:** FAIL  
**Classification:** FUNCTIONAL GAP  
**Area:** Answer

### Manual test action
Select Export retrieval trail

### Expected behaviour
A JSON retrieval trail downloads; persistence failure is visible if it occurs.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** No Export retrieval trail button. Currently we have Copy citation, open in sources, locate in semantic atlas and vire provenance buttons. These go to separate pages, when I clisk back to the source interrogation answer, it is blank and the query return is lost!

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-056** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-056** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-058 — Per-source evidence status

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Evidence chain

### Manual test action
Change a source Evidence status

### Expected behaviour
Selected source status changes independently for the current view.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I really don't know what this function should do!

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-058** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-058** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-060 — Open in sources

**UAT status:** FAIL  
**Classification:** DEFECT  
**Area:** Evidence chain

### Manual test action
Select Open in sources

### Expected behaviour
Sources opens with document/PID handoff parameters.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I am not sure if this is working. We need to test this  with co-pilot's help.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-060** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-060** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-061 — Locate in semantic atlas

**UAT status:** FAIL  
**Classification:** DEFECT  
**Area:** Evidence chain

### Manual test action
Select Locate in semantic atlas

### Expected behaviour
Semantic atlas opens with chunk/PID handoff parameters.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** No handoff. Alert on semantic atlas says No visual point is currently available for this trace. The handoff parameters were received, but the current projection does not contain a matching chunk, document, or PID.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-061** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-061** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

### Approved remediation closeout (17 August 2026)
**Final classification:** **BLOCKED / NOT YET ACTIVATED**

The original UAT v0.1 failure remains immutable evidence. The current frozen corpus `corpus_f40d78dbce52` has zero embedded chunks, zero documents with embeddings, zero projection candidates and points, `projection_method: none`, no embedding or UMAP model, and no demo dataset. `Locate in semantic atlas` carries the exact source `chunkId` and PID to `/semantic-atlas`; the atlas truthfully reports that no projection and no visual point are available, without selecting a default or fabricated point. Browser Back restores the originating persisted Source interrogation `runId`.

**Revised UAT v0.2 acceptance:** when the Semantic Atlas is inactive for the current frozen corpus, the action may navigate to the atlas if the route retains the trace identity and the interface clearly reports unavailable projection, no visual point for the trace, and zero visible points. This is a capability state, not evidence of archival absence.

No application code, embeddings, pgvector retrieval, UMAP projection, atlas points, source/provenance data, corpus membership, FTS retrieval, or immutable experiment evidence were changed for this closeout.

# Absences /absences

**Failed UAT items:** 4

## UAT-068 — Completeness cards

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Completeness

### Manual test action
Inspect completeness cards

### Expected behaviour
Metadata retrieval entity and institutional gap outputs are distinct where data exists.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I am not sure if this is working. We need to test this  with co-pilot's help.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-068** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-068** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-070 — Select missingness event

**UAT status:** FAIL  
**Classification:** DEFECT  
**Area:** Events table

### Manual test action
Select a Missingness events table row

### Expected behaviour
Selected event opens in Selected event review.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Nothing happens when I click a row.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-070** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-070** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-072 — Reviewer note

**UAT status:** FAIL  
**Classification:** FUNCTIONAL GAP  
**Area:** Selected event review

### Manual test action
Enter a reviewer note

### Expected behaviour
Text remains visible before saving.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** No reviewer note field to test.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-072** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-072** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-073 — Save review state

**UAT status:** FAIL  
**Classification:** FUNCTIONAL GAP  
**Area:** Selected event review

### Manual test action
Save a changed review

### Expected behaviour
Saved confirmation appears and event reflects review state.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** No reviewer note field to test.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-073** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-073** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Research runs /research-runs

**Failed UAT items:** 3

## UAT-111 — Saved experiment-run selector

**UAT status:** FAIL  
**Classification:** DEFECT  
**Area:** Saved runs

### Manual test action
Select a saved run

### Expected behaviour
Immutable run loads with status creation time corpus version model and assessment state.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** ui alert says "Model: not invoked Assessment: not assessed Run failure: granite_failure TimeoutError:"

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-111** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-111** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-114 — Authority context separation

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Run record

### Manual test action
Inspect Archive and authority context

### Expected behaviour
Authority context is explicitly not source-document evidence.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** UI alert says: "No authority context supplied
This run used document evidence only."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-114** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-114** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-118 — Five scores

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Researcher assessment

### Manual test action
Change each assessment selector

### Expected behaviour
All five scores accept 0-3 or Not assessed.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** UI just defauts to "Not assessed"

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-118** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-118** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Cross-readings /cross-readings

**Failed UAT items:** 10
> **Workstream note:** The UAT reports no persisted testimony passages. Determine the legitimate ingestion/creation route and whether Cross-readings is required for the Turin release before treating the ten rows as software defects.

## UAT-076 — Passage list

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Passage input

### Manual test action
Select a persisted passage

### Expected behaviour
Selected passage fields and retrieval mappings load.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-076** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-076** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-077 — Empty passage validation

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Passage input

### Manual test action
Attempt Create passage with no Passage text

### Expected behaviour
Passage is not created and required-text error is clear.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-077** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-077** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-078 — Create passage

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Passage input

### Manual test action
Enter non-sensitive test passage and select Create passage

### Expected behaviour
Persisted passage is created selected and confirmed.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-078** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-078** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-079 — Passage fields

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Passage input

### Manual test action
Edit label speaker/source type status and memory-position note

### Expected behaviour
Each field accepts its designed value.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-079** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-079** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-080 — Save passage

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Passage input

### Manual test action
Modify selected test passage then Save passage

### Expected behaviour
Update confirmation appears and values remain visible.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-080** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-080** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-081 — Run passage as retrieval probe

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Passage input

### Manual test action
Select Run passage as retrieval probe

### Expected behaviour
Running state then persisted query ID or clear error appears.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-081** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-081** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-082 — Mapping selection

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Retrieval results

### Manual test action
Select a candidate mapping

### Expected behaviour
Mapping becomes selected for annotation.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-082** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-082** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-083 — Relation type

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Relation annotation

### Manual test action
Change Relation type

### Expected behaviour
Value changes among supports complicates contradicts and no-documentary-trace.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-083** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-083** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-084 — Confidence/status and note

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Relation annotation

### Manual test action
Edit Confidence / status and Reviewer / interpretive note

### Expected behaviour
Values remain visible before saving.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-084** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-084** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-085 — Save mapping annotation

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Relation annotation

### Manual test action
Save a changed mapping annotation

### Expected behaviour
Update confirmation appears and relationship remains visible.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "No passages yet No persisted testimony passages are available yet. This surface remains intentionally empty until passages are created or ingested."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-085** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-085** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Semantic atlas /semantic-atlas

**Failed UAT items:** 18
> **Workstream note:** All 18 failures share the stated prerequisite that embeddings have not yet been generated and therefore no UMAP projection exists. Treat this first as one capability-readiness decision, then rerun the individual controls only if the atlas is explicitly activated. Do not activate embedding-based retrieval.

## UAT-086 — Projection loading and availability

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Atlas state

### Manual test action
Open Semantic atlas

### Expected behaviour
Loading resolves to projection or explicit no-embeddings/endpoint-unavailable state.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-086** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-086** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-087 — Point type

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Filters

### Manual test action
Change Point type between Chunks and Documents

### Expected behaviour
Projection reloads using selected point type.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-087** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-087** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-088 — Colour by

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Filters

### Manual test action
Change Colour by

### Expected behaviour
Visible point colouring updates for selected dimension.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-088** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-088** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-089 — Year range

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Filters

### Manual test action
Enter Year min and Year max

### Expected behaviour
Projection refreshes and nonnumeric input is not retained.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-089** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-089** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-090 — Theme and source type

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Filters

### Manual test action
Enter Theme filter and Source type filter

### Expected behaviour
Projection refreshes using each supplied constraint.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-090** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-090** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-091 — Refresh and reset

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Filters

### Manual test action
Refresh then set filters/select point and Reset view

### Expected behaviour
Refresh reloads; reset restores default filters and clears selection.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-091** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-091** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-092 — Atlas coordinate/cluster summary

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Export

### Manual test action
Select Export atlas coordinates / cluster summary

### Expected behaviour
A visual-analytics Markdown memo downloads.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-092** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-092** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-093 — Metadata overlays and corpus scope

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Scope

### Manual test action
Inspect Metadata overlays and evidence surface scope

### Expected behaviour
Returned points embedding/text/PDF and missingness coverage are presented as scoped output.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-093** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-093** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-094 — Point hover and selection

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Projection

### Manual test action
Hover then select a visible UMAP point

### Expected behaviour
Tooltip shows available metadata; selected point highlights and detail renders.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-094** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-094** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-095 — Zoom and pan

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Projection

### Manual test action
Use mouse/trackpad controls on UMAP

### Expected behaviour
Projection responds without losing points or breaking layout.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-095** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-095** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-096 — Evidence surface and missingness

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Point detail

### Manual test action
Inspect selected point

### Expected behaviour
PID cluster metadata evidence flags scoped missingness and excerpt are visible where supplied.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-096** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-096** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-097 — Open in sources

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Point detail

### Manual test action
Select Open in sources

### Expected behaviour
Sources opens with document/PID handoff parameter.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-097** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-097** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-098 — Open in source interrogation

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Point detail

### Manual test action
Select Open in source interrogation

### Expected behaviour
Interrogation opens with chunk/PID handoff parameter.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-098** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-098** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-099 — Copy PID and excerpt

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Point detail

### Manual test action
Copy PID then Copy excerpt and paste each

### Expected behaviour
Selected PID and excerpt are copied.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-099** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-099** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-100 — Add to research memo

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Point detail

### Manual test action
Select Add to research memo

### Expected behaviour
Local memo queue count increases and duplicate point is not duplicated.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-100** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-100** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-101 — Cluster selection

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Clusters

### Manual test action
Select a cluster then select it again

### Expected behaviour
First action filters/highlights matching points; second clears cluster focus.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-101** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-101** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-102 — Copy cluster interpretation

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Clusters

### Manual test action
Select a cluster then Copy cluster interpretation note and paste

### Expected behaviour
Memo describing selected cluster is copied.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-102** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-102** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-103 — Find resonances

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Cluster interpretation

### Manual test action
Enter a term and select Find resonances

### Expected behaviour
Visible resonance result or meaningful empty/error state appears.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Analytical output This view produces atlas coordinates / cluster summaries, point detail, metadata overlays, and cluster interpretation notes over the locally ingested / embedded evidence surface. Clusters are hypotheses, not findings This projection represents the current ML-ingested evidence surface, not the total DDR archive. Atlas not yet generated. No embeddings are currently available for projection. The next backend job is embedding generation followed by UMAP projection."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-103** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-103** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Claims and evidence /claims-evidence

**Failed UAT items:** 7
> **Workstream note:** The surface identifies itself as a development seed requiring more archival records. Confirm release scope and legitimate data provenance before implementing or populating anything.

## UAT-104 — Loading empty and selection

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Claim table

### Manual test action
Open page then select a claim

### Expected behaviour
Loading/empty state is clear; detail loads with claim support evidence count and reviewer status.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-104** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-104** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-105 — Evidence chunk output

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Claim detail

### Manual test action
Inspect attached evidence

### Expected behaviour
Chunk IDs citation text and page ranges render or explicit missing values are shown.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-105** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-105** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-106 — Support level

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Claim detail

### Manual test action
Change Support level

### Expected behaviour
Selected support level changes before save.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-106** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-106** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-107 — Caveats and reviewer status

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Claim detail

### Manual test action
Edit Caveats and Reviewer status

### Expected behaviour
Values remain visible before save.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-107** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-107** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-108 — Save claim updates

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Claim detail

### Manual test action
Save modified claim fields

### Expected behaviour
Saved appears and claim retains updated values.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-108** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-108** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-109 — Unsupported supported-claim warning

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Evidence gating

### Manual test action
Inspect supported claim with no evidence if present

### Expected behaviour
Warning states export will downgrade it to unresolved.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-109** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-109** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

## UAT-110 — Claim-evidence exports

**UAT status:** FAIL  
**Classification:** BLOCKED / NOT YET ACTIVATED  
**Area:** Export

### Manual test action
Select Export claim-evidence CSV and Markdown

### Expected behaviour
Each control downloads correctly named claim-evidence file.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** I can not test this. UI alert reads "Development seed only. Requires more archival records before generalising."

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-110** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-110** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# Documentation /documentation

**Failed UAT items:** 1

## UAT-135 — Return to expanded abstract

**UAT status:** FAIL  
**Classification:** SPECIFICATION / UX ISSUE  
**Area:** Related navigation

### Manual test action
Select Return to the expanded abstract

### Expected behaviour
Foundational documentation record opens and becomes selected.

### Observed UAT evidence
**Actual result:** Not recorded in UAT.

**Researcher note:** Naviation bar on left hand side has "Expanded asbstract" and Tevhnology Statement of Word" only.

### Investigation required
1. Reproduce this exact UAT condition against the current deployed/local-equivalent build.
2. Trace the UI control through its component, route/state handoff, API/GraphQL call and persistence layer as applicable.
3. Establish whether the failure is implementation, data readiness, unavailable prerequisite, ambiguous specification or an incorrect UAT expectation.
4. Compare the behaviour with the controlling Turin Technology SoW and Copilot Work Instruction before changing code.
5. Record the root cause with file/function/API references and any relevant corpus/run identifiers.

### Required remediation
- For **DEFECT**: correct the underlying behaviour without hard-coding the UAT example.
- For **FUNCTIONAL GAP**: confirm that the function belongs to the agreed research-instrument scope, then implement the smallest complete workflow.
- For **BLOCKED / NOT YET ACTIVATED**: resolve or explicitly defer the legitimate prerequisite; do not fabricate data or alter the research method merely to obtain a PASS.
- For **SPECIFICATION / UX ISSUE**: resolve the intended user/research contract first; then change labels, interaction or implementation only where justified.
- Preserve an explicit, intelligible empty/error state whenever the required evidence or capability is unavailable.

### Constraints
- Preserve provenance and corpus-control semantics.
- Preserve the distinction between retrieved evidence and generated inference.
- Preserve authority/source-evidence separation.
- Do not equate system absence with historical absence.
- Do not introduce hidden external services or paid APIs.
- Do not change FTS retrieval methodology as a side effect of remediation.
- Do not regress UAT rows that already pass.

### Machine acceptance
- Add or update the narrowest appropriate regression test for the diagnosed root cause.
- Relevant backend/frontend tests pass.
- Frontend production build passes where frontend code changes.
- API/route/persistence errors are controlled and user-visible rather than uncaught.
- Any navigation handoff is verified with representative identifiers rather than one hard-coded PID.
- Record exact commands and results in the phase closeout.

### Human acceptance
The researcher repeats **UAT-135** against the deployed production instrument using the original UAT action and records the result in the next UAT dataset.

### Definition of done
- Root cause documented.
- Required remediation or justified deferral documented.
- Machine acceptance evidence recorded.
- No methodological constraint violated.
- **UAT-135** is either manually marked PASS in UAT v0.2 or explicitly re-specified/deferred with rationale; it is never silently removed.

# 7. Special workstream decisions

## 7.1 Workbench corpus semantics

The Workbench must distinguish populations rather than visually imply that every metric describes the same denominator. In particular, frozen experimental-corpus measures, archive-linked asset counts and unresolved legacy database records must be labelled so a researcher can understand what each number counts. Do not change counts merely to make them appear internally consistent.

## 7.2 Source interrogation state preservation

UAT-056 records a research-critical usability problem: leaving a generated interrogation through a handoff and returning can result in the query/output being lost. Investigation must determine the intended persistence model. Saved experimental runs remain immutable; transient UI state must not be confused with persisted research evidence.

## 7.3 Source interrogation query boundaries and routing

Source Interrogation is a bounded, evidence-backed research-question workflow. It retrieves a ranked and explicitly limited selection of passages, then synthesises what that selected evidence establishes. It is not an exhaustive catalogue, record-association or biographical-authority service.

The interface and response contract must classify or clearly qualify these query types:

| Query need | Required product behaviour | Evidence rule |
|---|---|---|
| Exhaustive document inventory, for example “List all documents Richard Langdon was involved with” | Route to, or require use of, Sources/authority search for record associations and catalogue results. Source Interrogation may answer only as a bounded retrieved-evidence result and must state that it is not a complete inventory. | A name in metadata or a passage alone does not establish that a person was involved with a document. |
| Biographical or role question, for example “What did Janet Daley do at the DDR?” | Route to, or require use of, a separately typed authority record and dated role/employment data, with documentary corroboration where the response asserts a role. Source Interrogation must state when those records were not retrieved or are unavailable. | A name mention is not a verified role. Authority assertions remain visibly distinct from source-document evidence and generated inference. |
| Bounded documentary research question | Permit Source Interrogation to answer what the selected documents establish, with passages, page/chunk provenance, limits and scoped missingness visible. | Do not generalise the ranked maximum retrieval set into archive-wide completeness, historical absence or a complete biography. |

For the current Source Interrogation implementation, a response to either example query may be run, but its opening limitation must make clear that it reports only what the retrieved evidence establishes. It must not promise a complete document list, assert that all relevant records have been retrieved, or convert a mention into involvement, employment or a verified role.

### Acceptance criteria

1. A request for “all documents” or equivalent exhaustive language receives a visible bounded-retrieval limitation and a usable Sources/authority-search route or instruction.
2. A person-role query identifies the required evidence types: person authority, dated role/employment data and documentary corroboration for role assertions.
3. When any required evidence type is absent, the response states the specific limitation and does not infer a role from a mention.
4. The response preserves the distinction among catalogue metadata/record association, authority assertion, direct documentary evidence and model synthesis.
5. Regression coverage verifies both example query classes without hard-coding person-specific historical claims.

## 7.4 Research-run authority context

UAT-114 must be investigated as a likely UAT/specification issue rather than automatically treated as a defect. A message stating that a run used document evidence only and supplied no authority context can be correct behaviour because authority context is optional. Acceptance should test that the distinction is explicit and truthful.

## 7.5 Researcher assessment

UAT-118 reports that scores default to “Not assessed”. That may be a valid initial state. The required acceptance behaviour is that each of the five rubric scores can be deliberately changed to an allowed 0–3 value or left Not assessed, persisted where the workflow requires persistence, and reloaded accurately.

## 7.6 Cross-readings

Do not create dummy testimony passages in production. Establish whether passages should be created manually, ingested from an authorised corpus, or remain unavailable for the Turin release. Only then can the interaction tests be meaningfully rerun.

## 7.7 Semantic atlas

The current UAT evidence explicitly states that no embeddings are available and that embedding generation followed by UMAP projection is the next backend prerequisite. Before implementation:

1. confirm that atlas generation is required for the Turin conference/research release;
2. define the embedding model, version, deterministic corpus namespace and storage;
3. preserve the frozen FTS corpus and retrieval contract;
4. ensure embeddings are used for visual analytics, not silently substituted for FTS retrieval;
5. record projection parameters and corpus scope;
6. make the UI state clear when no projection exists.

The 18 atlas UAT rows must then be rerun individually.

### Future activation TODO (not authorised by UAT-061)

Before any activation, establish and persist the embedding model/version/reproducibility identifier, dimensionality, frozen corpus binding, eligible chunk/document scope, namespace/storage, deterministic generation process, exclusions, coverage diagnostics, chunk strategy, projection method/library version, seed, distance metric, neighbour count, minimum distance, projection version, point-to-source identity mapping, and exportable projection provenance.

For a chunk-level projection, a supplied `chunkId` must be the exclusive exact point identity; do not fall back to PID, archive-record PID, title, or a sibling source. For an explicitly document-level projection, `documentId` is the exact identity. Atlas activation remains separate from PostgreSQL FTS retrieval, and pgvector must remain inactive for Turin retrieval.

## 7.8 Claims and evidence

Do not convert a development seed into apparent research evidence by synthetic population. Confirm the legitimate source of claims/evidence records and whether this surface is required in the current release. If deferred, label the interface and UAT status explicitly.

# 8. Phase closeout format

After each page, Copilot must report:

```markdown
## UAT remediation phase completed

### Page
- ...

### UAT items addressed
- ...

### Root causes
- ...

### Changes made
- ...

### Files changed
- ...

### Tests added or updated
- ...

### Commands run
- ...

### Results
- ...

### Deferred / re-specified items
- ...

### Known limitations
- ...

### Human UAT rows to rerun
- ...

### Stop point
Do not proceed to the next page until the researcher confirms.
```

# 9. Final regression and UAT v0.2

After all approved page phases:

- run the complete automated test suite relevant to the instrument;
- run the production frontend build;
- verify backend health and retrieval endpoints;
- verify the frozen corpus/version and provenance invariants have not drifted;
- verify no active vector retrieval has been introduced;
- verify authority context remains inspectable and optional;
- verify saved-run immutability;
- verify all previously passing Global and Provenance behaviours;
- retain UAT v0.1 unchanged;
- create a new UAT v0.2 result dataset from a fresh manual production pass;
- produce a reconciliation table mapping every original FAIL to PASS, DEFERRED or RE-SPECIFIED with rationale.

# 10. Definition of done

The remediation programme is complete when:

1. every one of the 56 original failed UAT rows has an explicit disposition;
2. genuine defects and approved functional gaps have machine-verifiable remediation evidence;
3. blocked capabilities are either legitimately activated and tested or explicitly deferred;
4. specification/UX issues have a documented acceptance contract;
5. no failure is hidden by fabricated data, hard-coded examples or methodological drift;
6. the original UAT v0.1 remains preserved as evidence;
7. a fresh human UAT v0.2 has been completed against production;
8. the final report records remaining limitations as part of the research instrument rather than silently treating them as successes.

# 11. Initial Copilot instruction

```text
Read this UAT Remediation Statement of Work, the original UAT v0.1 CSV, the current Technology Statement of Work and the current Copilot Work Instruction.

Begin with Workbench only.

Do not change code yet.

Reproduce and investigate UAT-018, UAT-019 and UAT-022. Map each observed failure to the current components, data sources and API/database calculations. Determine the root cause and classify whether each requires code, copy/label changes, data correction or UAT re-specification.

Report your findings, proposed acceptance contract and exact files likely to change.

Stop for researcher approval before implementation.
```
