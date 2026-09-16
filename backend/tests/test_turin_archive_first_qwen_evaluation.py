import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT / "scripts"))

from run_turin_archive_first_qwen_evaluation import CitedStatement, QwenEvidenceResponse, _validate_response


class ArchiveFirstQwenEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {"source_id": "S1", "evidence_classification": "DIRECT_SUPPORT", "archive_identity": {"asset_pid": "123456789012", "asset_id": "asset-1"}},
            {"source_id": "S2", "evidence_classification": "CONTEXTUAL", "archive_identity": {"asset_pid": "234567890123", "asset_id": "asset-2"}},
        ]

    def test_validates_supplied_direct_evidence_and_labelled_inference(self):
        response = QwenEvidenceResponse(
            direct_documentary_evidence=[CitedStatement(statement="The passage records a tutorial.", sources=["S1"])],
            cross_source_interpretation=[CitedStatement(statement="Inference: the two records can be read together.", sources=["S1", "S2"])],
            what_the_evidence_does_not_establish=[CitedStatement(statement="The evidence does not establish outcomes.", sources=["S1"])],
        )

        validation = _validate_response(response, self.sources, "known_relationship")

        self.assertTrue(validation["provenance_valid"])
        self.assertTrue(validation["cross_source_inference_explicitly_labelled"])

    def test_exposes_unknown_and_contextual_direct_citations(self):
        response = QwenEvidenceResponse(
            direct_documentary_evidence=[CitedStatement(statement="Unsupported direct statement.", sources=["S2", "S99"])],
        )

        validation = _validate_response(response, self.sources, "known_relationship")

        self.assertFalse(validation["provenance_valid"])
        self.assertTrue(validation["fabricated_source_identity"])
        self.assertTrue(validation["contextual_evidence_promoted_to_direct_fact"])


if __name__ == "__main__":
    unittest.main()