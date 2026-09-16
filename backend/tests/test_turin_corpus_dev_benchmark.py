import json
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_evidence_pipeline_service import SourceEvidencePacket, score_benchmark_case


class CorpusDevelopmentBenchmarkTests(unittest.TestCase):
    def test_benchmark_excludes_registered_question_ids(self):
        payload = json.loads((BACKEND_ROOT / "fixtures" / "turin-corpus-dev-benchmark-v1.json").read_text())
        self.assertEqual(payload["benchmark_version"], "turin-corpus-dev-benchmark-v1")
        self.assertEqual(len(payload["cases"]), 12)
        self.assertTrue(all(not case["case_id"].startswith(("KR", "CI", "SM", "Q")) for case in payload["cases"]))

    def test_benchmark_uses_only_neutral_case_identifiers(self):
        payload = json.loads((BACKEND_ROOT / "fixtures" / "turin-corpus-dev-benchmark-v1.json").read_text())
        self.assertEqual({case["case_id"] for case in payload["cases"]}, {f"DEV-{index:03}" for index in range(1, 13)})

    def test_scorecard_flags_unused_source_and_forbidden_claim(self):
        packet = SourceEvidencePacket(source_id="source-1", document={}, retrieval_match={}, document_context={"ordered_chunks": []}, source_status={}, field_provenance={})
        score = score_benchmark_case({"expected_direct_facts": ["Report 108"], "must_not_claim": ["collaboration"]}, {"final_synthesis": {"direct_documentary_claims": [{"claim": "Report 108", "evidence": []}], "cross_source_inferences": ["collaboration"], "answer": ""}, "source_analyses": [], "provenance": {}}, [packet])
        self.assertEqual(score["expected_direct_facts_recovered"]["count"], 1)
        self.assertEqual(score["unsupported_claims"], ["collaboration"])
        self.assertEqual(score["selected_sources_accounted_for"]["unused"], ["source-1"])

    def test_scorecard_accounts_for_source_artifact_packet(self):
        packet = SourceEvidencePacket(source_id="source-1", document={}, retrieval_match={}, document_context={"ordered_chunks": []}, source_status={}, field_provenance={})
        score = score_benchmark_case({}, {"source_analyses": [{"packet": {"source_id": "source-1"}}]}, [packet])
        self.assertEqual(score["selected_sources_accounted_for"]["unused"], [])


if __name__ == "__main__":
    unittest.main()