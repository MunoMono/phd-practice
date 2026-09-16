-- Append-only SM1 evidence-class retrieval remediation; this migration authorizes no inference.
BEGIN;

INSERT INTO turin_retrieval_plans (
    plan_id, question_id, protocol_version, plan_version, researcher_approval_state,
    researcher_approved_at, run_classification, supersedes_plan_id, plan_json
)
SELECT
    'SM1-v2', 'SM1', 'turin-retrieval-protocol-v1.0', '2.0', 'approved', CURRENT_TIMESTAMP,
    'primary', 'SM1-v1',
    jsonb_set(
        jsonb_set(
            jsonb_set(plan_json, '{plan_id}', '"SM1-v2"'::jsonb),
            '{plan_version}', '"2.0"'::jsonb
        ),
        '{run_classification}', '"primary"'::jsonb
    ) || jsonb_build_object(
        'supersedes_plan_id', 'SM1-v1',
        'top_k', 6,
        'temporal_strata', '[
          {"stratum_id":"contemporary","classification":"contemporary DDR document","top_k":3,"year_to":1985,"source_type":"any"},
          {"stratum_id":"retrospective","classification":"later retrospective account","top_k":3,"year_from":1986,"source_type":"oral_history","lexical_facets":[{"facet_id":"retrospective_institutional_fate","alternatives":["\\\"future of design research\\\"","\\\"close the DDR\\\"","\\\"DDR closing\\\""]}]}
        ]'::jsonb,
        'rationale', 'SM1-v2 corrects retrieval-plan evidence-class coverage. It retains SM1-v1’s approved contemporary decision/process FTS identity and independently retrieves archive-resolved, later oral-history accounts using source-backed institutional-fate phrases. It introduces no causal-loading terms, document/PID restriction, corpus change, or cross-stratum rescoring.',
        'notes', '{"display_question_id":"Q09","remediation_status":"PENDING EVALUABLE RESULT — SM1-v2 CAUSAL EVIDENCE-CLASS RETRIEVAL REMEDIATION","intended_execution_protocol":"turin-retrieval-protocol-v1.5","intended_corpus_version":"corpus_f40d78dbce52","contemporary_stratum":"Unchanged SM1-v1 lexical FTS, top 3, source date through 1985.","retrospective_stratum":"Archive-resolved current oral-history metadata, source date from 1986, top 3, independently ranked using quoted source-backed institutional-fate phrases.","rejected_terms":["because","cause","reason","why"],"no_hand_picked_document_or_pid":true}'
    )
FROM turin_retrieval_plans
WHERE plan_id = 'SM1-v1'
  AND question_id = 'SM1'
  AND NOT EXISTS (SELECT 1 FROM turin_retrieval_plans WHERE plan_id = 'SM1-v2');

INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT
    'turin-q09-sm1-v2-causal-evidence-class-retrieval-remediation',
    'SM1',
    'PENDING EVALUABLE RESULT — SM1-v2 CAUSAL EVIDENCE-CLASS RETRIEVAL REMEDIATION',
    'The prior SM1-v1 corpus-wide search reached all 12,884 frozen chunks but ranked known retrospective participant testimony below top-k. SM1-v2 introduces evidence-class stratification to represent contemporary decision/process records and later participant testimony without hand-picking sources or changing the corpus. SM1-v1 and experiment-fd6db9dfa85f remain immutable evidence of causal overreach under incomplete evidence-class coverage.'
WHERE NOT EXISTS (
    SELECT 1 FROM turin_question_governance_notes
    WHERE note_id = 'turin-q09-sm1-v2-causal-evidence-class-retrieval-remediation'
);

COMMIT;