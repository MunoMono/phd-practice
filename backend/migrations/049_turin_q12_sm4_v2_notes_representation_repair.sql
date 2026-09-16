-- Representation-only repair for the unexecuted SM4-v2 plan; this migration authorizes no inference.
BEGIN;

UPDATE turin_retrieval_plans
SET plan_json = jsonb_set(plan_json, '{notes}', to_jsonb(plan_json->>'notes'))
WHERE plan_id = 'SM4-v2'
  AND question_id = 'SM4'
  AND plan_version = '2.0'
  AND jsonb_typeof(plan_json->'notes') = 'object'
  AND NOT EXISTS (
      SELECT 1 FROM experiment_runs
      WHERE retrieval_plan_id = 'SM4-v2'
         OR formal_authorization_id LIKE 'turin-q12-sm4-v2%'
  );

COMMIT;