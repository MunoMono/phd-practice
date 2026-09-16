-- Correct the unexecuted CI3-v2 record to its approved primary run classification.
BEGIN;

UPDATE turin_retrieval_plans
SET run_classification = 'primary',
    plan_json = jsonb_set(plan_json, '{run_classification}', '"primary"'::jsonb)
WHERE plan_id = 'CI3-v2'
  AND question_id = 'CI3'
  AND run_classification = 'protocol_revision'
  AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE retrieval_plan_id = 'CI3-v2')
  AND NOT EXISTS (SELECT 1 FROM turin_formal_protocol_authorizations WHERE plan_id = 'CI3-v2');

INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT
    'turin-q07-ci3-v2-primary-classification-correction',
    'CI3',
    'PENDING EVALUABLE RESULT — CI3-v2 COMPARATIVE RETRIEVAL + v1.4 CAPACITY REMEDIATION',
    'Before any CI3-v2 authorization or execution, the unexecuted CI3-v2 registration was corrected from protocol_revision to primary to match the approved Q07 formal classification. CI3-v1 and its failed run remain unchanged.'
WHERE EXISTS (SELECT 1 FROM turin_retrieval_plans WHERE plan_id = 'CI3-v2' AND run_classification = 'primary')
  AND NOT EXISTS (SELECT 1 FROM turin_question_governance_notes WHERE note_id = 'turin-q07-ci3-v2-primary-classification-correction');

COMMIT;