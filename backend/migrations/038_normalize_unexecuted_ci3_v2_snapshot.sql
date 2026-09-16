-- Normalize nullable stratum fields before the first CI3-v2 execution snapshot.
BEGIN;

UPDATE turin_retrieval_plans
SET plan_json = jsonb_set(
    jsonb_set(
        plan_json,
        '{temporal_strata,0,year_from}', 'null'::jsonb,
        true
    ),
    '{temporal_strata,1,year_to}', 'null'::jsonb,
    true
)
WHERE plan_id = 'CI3-v2'
  AND question_id = 'CI3'
  AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE retrieval_plan_id = 'CI3-v2')
  AND NOT EXISTS (SELECT 1 FROM experiment_runs WHERE formal_authorization_id = 'turin-q07-ci3-v2-v14-primary-authorization');

COMMIT;