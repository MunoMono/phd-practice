import sys
import json
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.benchmark_evaluation_service import evaluate_benchmark_artifact, render_evaluation_matrix
from app.services.archival_benchmark_policy import load_question_policies
from app.services.turin_question_policy import TURIN_QUESTION_POLICIES, validate_turin_question_policies
from app.services.turin_evidence_pipeline_service import CrossSourceAnalysis, FinalSynthesis, SourceEvidencePacket, apply_configured_synthesis_guard


class BenchmarkEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy = next(policy for policy in TURIN_QUESTION_POLICIES if policy.policy_id == "SM2")
        self.artifact = {
            "evidence_map": {
                "DIRECT_DOCUMENTARY": [{"source_id": "source-1", "document_id": "document-1"}],
                "source_classifications": [{"source_id": "source-1", "relationship_to_question": "DIRECT_SUPPORT"}],
                "NOT_ESTABLISHED": ["A unique initiator and the decision process are not established."],
            },
            "final_synthesis": {"direct_documentary_claims": [{"source_id": "source-1"}], "cross_source_inferences": [], "answer": ""},
            "cross_source_analysis": {"cross_source_inferences": []},
            "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True, "checked_references": 1}},
        }

    def test_loaded_policies_cover_the_full_turin_register(self):
        validate_turin_question_policies()
        self.assertEqual(len(TURIN_QUESTION_POLICIES), 12)

    def test_collection_neutral_loader_accepts_a_non_turin_configuration(self):
        specification = {
            "schema_version": "archival-evidence-benchmark-v1",
            "collection_id": "fixture-archive",
            "corpus_version": "fixture-v1",
            "questions": [{
                "id": "FIX1",
                "research_case": "scoped_missingness",
                "question": "What does the fixture establish?",
                "triggers": ["fixture", "establish"],
                "reservation": {"type": "SCOPED_MISSINGNESS", "chunk_ids": ["fixture-chunk-1"]},
                "prohibited_inference_classes": ["causation"],
                "expected_missingness": ["decision rationale"],
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture-v1.json"
            path.write_text(json.dumps(specification))
            policies = load_question_policies(path)

        self.assertEqual(policies[0].policy_id, "FIX1")
        self.assertTrue(policies[0].matches("What does this fixture establish?"))

    def test_harbor_fixture_runs_its_configured_missingness_guard(self):
        policy = next(policy for policy in load_question_policies(BACKEND_ROOT / "config" / "benchmark_questions" / "harbor-notes-v1.json") if policy.policy_id == "HM1")
        packets = [
            SourceEvidencePacket(source_id="minute:7", document={"document_id": "harbor-minute"}, retrieval_match={"chunk_id": "harbor-minute-7", "page": 7}, document_context={"ordered_chunks": [{"chunk_id": "harbor-minute-7", "page": 7, "text": "The pier proposal was withdrawn."}]}, source_status={}, field_provenance={}),
            SourceEvidencePacket(source_id="interview:4", document={"document_id": "harbor-interview"}, retrieval_match={"chunk_id": "harbor-interview-4", "page": 4}, document_context={"ordered_chunks": [{"chunk_id": "harbor-interview-4", "page": 4, "text": "I remember budget pressure."}]}, source_status={}, field_provenance={}),
        ]
        evidence_map = {"DIRECT_DOCUMENTARY": [], "CONTEXTUAL": [], "CROSS_SOURCE_INFERENCE": [], "NOT_ESTABLISHED": [], "source_classifications": [{"source_id": packet.source_id, "subject_named": False, "relationship_to_question": "CONTEXTUAL_ONLY"} for packet in packets]}
        final = FinalSynthesis(direct_documentary_claims=[], cross_source_inferences=["The withdrawal was caused by budget pressure."], authority_context=[], missing_or_not_established=[], answer="")
        cross_source = CrossSourceAnalysis(supported_by_multiple_sources=[], supported_by_one_source=[], differences_or_contradictions=[], cross_source_inferences=["The withdrawal was caused by budget pressure."], not_established=[])

        self.assertTrue(apply_configured_synthesis_guard("Does the digitised Harbour Survey corpus establish why the pier proposal was withdrawn?", final, evidence_map, packets, cross_source, policy=policy))
        self.assertEqual(len(final.direct_documentary_claims), 2)
        self.assertIn("does not establish why", final.answer)
        self.assertEqual(final.cross_source_inferences, [])
        self.assertTrue(all(item["relationship_to_question"] == "DIRECT_SUPPORT" for item in evidence_map["source_classifications"]))
        result = evaluate_benchmark_artifact(policy, {
            "evidence_map": evidence_map,
            "final_synthesis": final.model_dump(),
            "cross_source_analysis": cross_source.model_dump(),
            "provenance": {"source_analyses": {"valid": True}, "final_synthesis": {"valid": True, "checked_references": 2}},
        })
        self.assertTrue(result["valid"])
        self.assertEqual(result["expected_missingness"]["recovered"], ["decision rationale", "contemporaneous explanation"])

    def test_evaluator_reports_typed_counts_and_expected_missingness(self):
        result = evaluate_benchmark_artifact(self.policy, self.artifact)

        self.assertTrue(result["valid"])
        self.assertEqual(result["retained_source_count"], 1)
        self.assertEqual(result["final_direct_claim_count"], 1)
        self.assertEqual(result["expected_missingness"]["total"], 2)
        self.assertEqual(len(result["expected_missingness"]["recovered"]), 2)

    def test_evaluator_rejects_prohibited_inference_marker(self):
        self.artifact["final_synthesis"]["answer"] = "This establishes a sole initiator."

        result = evaluate_benchmark_artifact(self.policy, self.artifact)

        self.assertFalse(result["valid"])
        self.assertEqual(result["prohibited_inference_matches"], ["sole_initiator"])

    def test_evaluator_accepts_an_explicit_negated_prohibited_inference(self):
        policy = next(policy for policy in TURIN_QUESTION_POLICIES if policy.policy_id == "KR3")
        self.artifact["final_synthesis"]["answer"] = "This establishes a shared listing, not collaboration."

        result = evaluate_benchmark_artifact(policy, self.artifact)

        self.assertTrue(result["valid"])
        self.assertEqual(result["prohibited_inference_matches"], [])

    def test_evaluator_reports_source_family_temporal_and_fallback_failures(self):
        policy = next(policy for policy in TURIN_QUESTION_POLICIES if policy.policy_id == "SM2")
        policy = policy.__class__(**{**policy.__dict__, "source_selection": {"required_source_families": ["documentary", "oral_history"]}})
        artifact = {
            **self.artifact,
            "final_synthesis": {"direct_documentary_claims": [{"source_id": "source-1"}], "cross_source_inferences": [], "answer": "This establishes 1986 activity."},
            "retrieval_diagnostics": {"source_family_diversity": {"selected": ["documentary"]}},
            "final_artifact": {"parse_error": "invalid schema"},
        }

        result = evaluate_benchmark_artifact(policy, artifact)

        self.assertFalse(result["valid"])
        self.assertEqual(result["source_family_policy"]["unmet"], ["oral_history"])
        self.assertEqual(result["stage_fallback"]["malformed_without_fallback"], ["invalid schema"])

    def test_matrix_is_researcher_readable(self):
        matrix = render_evaluation_matrix([evaluate_benchmark_artifact(self.policy, self.artifact)])

        self.assertIn("| SM2 | PASS |", matrix)


if __name__ == "__main__":
    unittest.main()
