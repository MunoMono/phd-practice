# Research Query UAT Completion Statement of Work v0.2

**Project:** Testamentary Traces, Turin research instrument

**Area:** Source interrogation / Research Query

**Date:** 9 September 2026

**Status:** Active remediation and acceptance specification

**Evidence baseline:** `artifacts/uat_research_query_*.jsonl`; `scripts/uat_research_query.py`

## 1. Purpose

This Statement of Work defines the work required to achieve a defensible pass on a 23-question production UAT for Research Query. The questions were derived from the DDR Archive database-authority and archive-record surfaces, then executed through the production Innovation Design endpoint.

The purpose is not to make every question produce a positive historical claim. A pass means the instrument selects the correct response path, makes the source type inspectable, gives a useful answer within the available evidence, and states an evidence limit plainly where the corpus does not support an answer.

This SoW supplements, and is governed by, `turin-experiment-uat-remediation-sow-v0.1.md`.

## 2. Non-Negotiable Constraints

1. PostgreSQL FTS remains the principal selection mechanism for documentary-source interrogation.
2. Database authorities are administrative or catalogue records, not documentary quotations. They must remain separately labelled in the API and interface.
3. A direct authority answer must not claim a relationship stronger than the recorded field. A project `project_lead_name`, for example, supports “named as project lead”, not “worked on”.
4. Qwen is not used for direct register or catalogue facts when a bounded deterministic result is available.
5. Qwen may produce an evidence limit for an interpretative question, but it must not invent a historical statement to avoid that limit.
6. A retrieval failure, empty authority lookup, or missing document chunk does not establish historical absence.
7. No hard-coded PID, person, project, student, or period mappings may be introduced to make an individual UAT row pass.
8. The active corpus version, PID/page identity, rights/access controls, and existing immutable records remain intact.

## 3. UAT Outcome Classes

| Class | Required response path | Pass condition |
|---|---|---|
| Documentary catalogue | Deterministic retrieval display, zero Qwen calls | Returns up to five relevant document records with Asset PID and page; does not claim authorship from a mention result. |
| Direct authority fact | Deterministic authority-register display, zero Qwen calls | Returns the matching authority type, ID/range, exact recorded fields, and the label “not documentary quotations”. |
| Mixed authority/document | Deterministic display, zero Qwen calls | Shows authority result first when it answers the factual question; documentary records are only included when relevant and are visibly separate. |
| Interpretative documentary question | Staged Qwen pipeline | Uses supplied document chunks, identifies direct support where present, and otherwise gives a bounded limitation tied to the selected sources. |

## 4. Current Baseline

The September production run completed all 23 requests.

- Questions 1-22 reached the deterministic path with HTTP 200 and zero Qwen calls after routing and authority matching remediation.
- Question 23 reached the staged pipeline with five retrieved chunks and three Qwen calls. It returned `NOT_ESTABLISHED` rather than a useful synthesis.
- The current direct-answer work is a valid machine baseline, but full UAT acceptance is not yet granted: all 23 need explicit acceptance records, and Question 23 needs evidence/prompt diagnosis.

## 5. Acceptance Dataset

| # | Question | Class | Required acceptance evidence |
|---|---|---|---|
| 1 | What documents mention Janet Daley? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 2 | What documents mention Richard Langdon? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 3 | What documents mention Pierre Gourmain? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 4 | What documents mention Bruce Archer? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 5 | What documents mention Eileen Adams? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 6 | What documents mention Ken Baynes? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 7 | What projects did Bruce Archer work on? | Direct authority fact | Records explicitly say Bruce Archer is project lead; wording does not claim broader participation. |
| 8 | What projects did Kenneth Agnew work on? | Direct authority fact | Records explicitly say Kenneth Agnew is project lead; bounded result list. |
| 9 | What projects did Richard Langdon work on? | Direct authority fact | Records explicitly say Richard Langdon is project lead; bounded result list. |
| 10 | What documents by Richard Langdon are available? | Documentary catalogue | Results labelled as records mentioning/associated with the name unless authorship metadata is verified. |
| 11 | What documents by Bruce Archer are available? | Documentary catalogue | Results labelled as records mentioning/associated with the name unless authorship metadata is verified. |
| 12 | When did DEU take in its first students? | Mixed authority/document | Direct register context and relevant documentary records remain separate. |
| 13 | When was the DDR formally constituted? | Direct authority fact | `1972-73`, “Formal constitution of DDR”, and registered description displayed. |
| 14 | Which students are recorded in the DDR register? | Direct authority fact | Bounded student list, count/limit clarity, and authority label. |
| 15 | What was Eileen Adams's degree? | Direct authority fact | `Adams, Eileen`, `1983`, `MA`; zero model calls. |
| 16 | What was Kenneth Agnew's thesis title? | Direct authority fact | `Agnew, Kenneth Malcom`, `1969`, `By project`; zero model calls. |
| 17 | Who led the Design of battery operated appliances project? | Direct authority fact | Job 21 and `Dario di Diana` as project lead. |
| 18 | What is Job 31? | Direct authority fact | Job 31 title and Anthony Smallhorn as project lead; no unrelated document list. |
| 19 | What did the Peak productivity period cover? | Direct authority fact | `1973-79`, period label, and register description; explicit statement when no documentary record was retrieved. |
| 20 | What projects were funded by the National Council for Educational Technology? | Direct authority fact | Only funding-matched projects; never labelled as project-lead results. |
| 21 | What documents mention hospital bedstead? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 22 | What records mention design research courses? | Documentary catalogue | Relevant PID/page records; zero model calls. |
| 23 | How did DDR documents describe design research? | Interpretative documentary question | A bounded synthesis with source-linked direct support, or a precise source-specific limit after researcher review of all five selected passages. |

## 6. Work Packages

### WP1: Freeze and Record the Baseline

1. Retain the existing JSONL outputs unchanged as v0.1 machine evidence.
2. Add a structured v0.2 result record with question number, timestamp, corpus version, HTTP status, response class, Qwen call count, retrieved PID/page identities, authority type/ID, output summary, machine status, and researcher status.
3. Add a single command that runs the complete suite in bounded groups and writes a timestamped result file without modifying application data.

**Machine acceptance:** all 23 rows are captured; result files parse; no UAT request persists a research run, annotation, or claim.

### WP2: Complete Direct-Answer Acceptance

1. Add regression tests for each direct response grammar: person-document listing, project lead, student degree, student thesis, exact job, funding, period label, and authority-only period result.
2. Add an explicit list summary for collection questions: total matched count, displayed count, and a statement that the list is bounded.
3. Require exact-match ranking for person, project, and funder results; inspect false positive candidates rather than suppressing them invisibly.
4. Update the Source interrogation UI so authority-only and mixed results visually distinguish authority records from retrieved documents.

**Machine acceptance:** Questions 1-22 return HTTP 200, correct class, zero Qwen calls, bounded output, and required provenance fields. Tests cover no-source authority responses and prevent unrelated exact-Job documents being shown.

**Human acceptance:** researcher verifies at least one result from each direct class in production and confirms wording does not overclaim authorship, participation, or historical absence.

### WP3: Diagnose and Remediate Question 23

1. Capture the exact five selected chunks for Question 23, including PID, page, title, text excerpt, query variant, nomination reason, and source classification.
2. Ask the researcher to review whether those chunks contain a usable documentary formulation of “design research”.
3. If the selection is inadequate, improve lexical planning/FTS ranking using general documentary terms and source metadata. Do not add vector retrieval or hard-code an answer.
4. If the selection is adequate but Qwen classifies all passages as irrelevant, revise the evidence-classification instruction so it can distinguish direct terminology, contextual terminology, and an honest limit.
5. Add a regression fixture containing only rights-permitted existing text or an existing controlled test fixture. The test must assert classification/provenance, never a fabricated historical conclusion.
6. If the selected evidence genuinely provides no description, change the expected output from generic `NOT_ESTABLISHED` to a source-specific statement naming the documents examined and the exact limitation.

**Machine acceptance:** Question 23 returns either (a) at least one source-linked direct documentary formulation and a bounded synthesis, or (b) a source-specific limitation naming the selected records and why they do not answer the question. It must retain five-or-fewer cited source identities and three staged calls at most.

**Human acceptance:** researcher reviews the selected passages and accepts the synthesis or the narrower limitation.

### WP4: Final Regression and Production Acceptance

1. Run focused backend tests, Python compilation, and frontend production build.
2. Deploy only the Innovation Design application.
3. Wait for `/health` before UAT execution.
4. Run the 23-question suite and preserve its output as a new immutable acceptance artifact.
5. Conduct browser UAT in Source interrogation for desktop and mobile layouts, including authority labels, PID/page visibility, empty states, and model-use labels.

## 7. Definition of Pass

The 23-question UAT passes only when:

1. Every question has a recorded production result and researcher status.
2. Questions 1-22 meet their response-class acceptance criteria without Qwen inference.
3. Question 23 meets either the bounded-synthesis or source-specific-limit criterion after researcher review.
4. No answer presents an authority record as a document quotation or turns a retrieval result into an unsupported claim.
5. No current passing behaviour regresses, and the production health check succeeds after deployment.

## 8. Out of Scope

- Replacing FTS with embedding retrieval.
- Re-running BGE-M3 embedding or UMAP jobs.
- Changing the DDR Archive source data to suit the test questions.
- Creating synthetic archive text, source records, authority rows, or model outputs.
- Altering wealth-management containers, volumes, databases, backups, or schedules.