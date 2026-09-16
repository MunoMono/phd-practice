-- Append-only SM4 sparse-personal-visibility retrieval revision; this migration authorizes no inference.
BEGIN;

INSERT INTO turin_retrieval_plans (
    plan_id, question_id, protocol_version, plan_version, researcher_approval_state,
    researcher_approved_at, run_classification, supersedes_plan_id, plan_json
)
SELECT
    'SM4-v2', 'SM4', 'turin-retrieval-protocol-v1.0', '2.0', 'approved', CURRENT_TIMESTAMP,
    'primary', 'SM4-v1',
    jsonb_set(
        jsonb_set(
            jsonb_set(plan_json, '{plan_id}', '"SM4-v2"'::jsonb),
            '{plan_version}', '"2.0"'::jsonb
        ),
        '{run_classification}', '"primary"'::jsonb
    ) || jsonb_build_object(
        'supersedes_plan_id', 'SM4-v1',
        'top_k', 5,
        'temporal_strata', '[
          {"stratum_id":"contemporary","classification":"contemporary DDR document","top_k":3,"year_from":1973,"year_to":1977,"source_type":"any","lexical_facets":[{"facet_id":"person","alternatives":["Henrietta Ryott"]},{"facet_id":"institution","alternatives":["Department of Design Research","DDR"]}]},
          {"stratum_id":"retrospective","classification":"later retrospective account","top_k":2,"year_from":1978,"source_type":"any","lexical_facets":[{"facet_id":"person","alternatives":["Henrietta Ryott"]},{"facet_id":"institution","alternatives":["Department of Design Research","DDR"]}]}
        ]'::jsonb,
        'rationale', 'SM4-v1 returned zero documentary results and lacked temporal handling for a question bounded to 1973–1977. SM4-v2 introduces explicit temporal and evidential-status handling while keeping authority context separate from documentary evidence. The contemporary stratum retrieves only 1973–1977 direct name evidence; later material is independently ranked and remains a distinct retrospective-attribution class. Zero documentary results remain a valid scoped-missingness outcome.',
        'notes', to_jsonb('{"display_question_id":"Q12","remediation_status":"PENDING RETRIEVAL-ONLY VALIDATION — SM4-v2 SPARSE PERSONAL VISIBILITY REMEDIATION","intended_execution_protocol":"turin-retrieval-protocol-v1.5","intended_corpus_version":"corpus_f40d78dbce52","contemporary_stratum":"1973–1977, top 3, exact approved canonical-name and DDR formulation. Undated material is excluded.","retrospective_stratum":"1978 onward, top 2, independently ranked exact approved canonical-name and DDR formulation. Later evidence is never treated as direct proof of the 1973–1977 role.","authority_context":"AUTHORITY CONTEXT — NOT DOCUMENTARY EVIDENCE. The employment record provides name, dates, and title only; no authority-document link exists.","rejected_terms":["Ryott","Design Research Department","led","headed","directed","managed","founded","coordinator","administrator","researcher"],"no_hand_picked_document_or_pid":true,"zero_documentary_result_is_valid_scoped_missingness":true}'::text)
    )
FROM turin_retrieval_plans
WHERE plan_id = 'SM4-v1'
  AND question_id = 'SM4'
  AND plan_version = '1.0'
  AND researcher_approval_state = 'approved'
  AND run_classification = 'primary'
  AND NOT EXISTS (SELECT 1 FROM turin_retrieval_plans WHERE plan_id = 'SM4-v2');

INSERT INTO turin_question_governance_notes (note_id, question_id, governance_status, note_text)
SELECT
    'turin-q12-sm4-v2-sparse-personal-visibility-retrieval-remediation',
    'SM4',
    'PENDING RETRIEVAL-ONLY VALIDATION — SM4-v2 SPARSE PERSONAL VISIBILITY REMEDIATION',
    'SM4-v1 reached the frozen eligible corpus but returned zero documentary results for Henrietta Ryott. The only matching authority record supplies employment dates and title, with no authority-document link or documentary corroboration. SM4-v2 introduces explicit 1973–1977 and 1978+ strata using only the approved canonical name and DDR formulation. Authority context remains structurally separate. Zero documentary retrieval is a valid scoped-missingness result, not grounds to invent a role narrative.'
WHERE NOT EXISTS (
    SELECT 1 FROM turin_question_governance_notes
    WHERE note_id = 'turin-q12-sm4-v2-sparse-personal-visibility-retrieval-remediation'
);

COMMIT;