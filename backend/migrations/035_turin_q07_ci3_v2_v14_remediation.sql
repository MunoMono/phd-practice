-- Append-only CI3 comparative-retrieval and structured-output-capacity remediation.
BEGIN;

INSERT INTO turin_retrieval_protocol_amendments (protocol_version, supersedes_protocol_version, amendment_scope, amendment_json)
VALUES (
    'turin-retrieval-protocol-v1.4',
    'turin-retrieval-protocol-v1.3',
    'structured_output_capacity',
    '{"structured_output_max_tokens":1500,"temperature":0.0,"top_p":1.0,"do_sample":false,"response_schema_version":"turin-archival-analysis-response-v1","input_budget_chars":6000,"context_selection":"deterministic_max_min_fair_all_top_k","documentary_evidence_priority":true,"retrieval_changed":false,"corpus_changed":false,"model_changed":false,"governance_note":"Retrieval Protocol v1.4 increases only the structured-output capacity from 1000 to 1500 tokens after Q07 exhausted the v1.3 ceiling before completing the governed response schema. Retrieval, corpus, model, prompt substance, schema, sampling, context representation, repair semantics, write-ahead persistence, raw-before-parse persistence, and provenance rules remain unchanged."}'::jsonb
)
ON CONFLICT (protocol_version) DO NOTHING;

INSERT INTO turin_retrieval_plans (
    plan_id, question_id, protocol_version, plan_version, researcher_approval_state,
    researcher_approved_at, run_classification, supersedes_plan_id, plan_json
)
SELECT
    'CI3-v2', 'CI3', 'turin-retrieval-protocol-v1.0', '2.0', 'approved', CURRENT_TIMESTAMP,
    'primary', 'CI3-v1',
    jsonb_set(
        jsonb_set(
            jsonb_set(plan_json, '{plan_id}', '"CI3-v2"'::jsonb),
            '{plan_version}', '"2.0"'::jsonb
        ),
        '{run_classification}', '"primary"'::jsonb
    ) || jsonb_build_object(
        'supersedes_plan_id', 'CI3-v1',
        'top_k', 6,
        'temporal_strata', '[{"stratum_id":"contemporary","classification":"contemporary DDR document","top_k":4,"year_to":1985,"source_type":"any"},{"stratum_id":"retrospective","classification":"later retrospective account","top_k":2,"year_from":1986,"source_type":"oral_history"}]'::jsonb,
        'rationale', 'CI3-v2 corrects evidence-class coverage for a question whose wording explicitly requires comparison between contemporary and retrospective sources. It does not alter the lexical identity, corpus, scoring function or expected historical answer.',
        'notes', 'CI3-v2 uses unchanged lexical FTS independently within metadata-defined contemporary and later-retrospective strata. It preserves corpus, scoring, archive resolution, source provenance, and the rejected-term list: account, history, retrospective, recollection, memoir. Persist stratum, within-stratum rank, presentation rank, original score, and classification basis.'
    )
FROM turin_retrieval_plans
WHERE plan_id = 'CI3-v1'
  AND question_id = 'CI3'
  AND NOT EXISTS (SELECT 1 FROM turin_retrieval_plans WHERE plan_id = 'CI3-v2');

INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT
    'turin-q07-ci3-v2-v14-remediation-pending',
    'CI3',
    'PENDING EVALUABLE RESULT — CI3-v2 COMPARATIVE RETRIEVAL + v1.4 CAPACITY REMEDIATION',
    'CI3-v1 remains non-evaluable: it has a comparative retrieval coverage failure and a structured-output capacity limitation. CI3-v2 preserves lexical identity and scores while requiring metadata-defined contemporary and later-retrospective strata; v1.4 raises only the structured-output ceiling.'
WHERE NOT EXISTS (
    SELECT 1 FROM turin_question_governance_notes WHERE note_id = 'turin-q07-ci3-v2-v14-remediation-pending'
);

COMMIT;