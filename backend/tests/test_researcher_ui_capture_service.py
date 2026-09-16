import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.researcher_ui_capture_service import parse_one_shot_output, project_claim_provenance


class ResearcherUiCaptureServiceTests(unittest.TestCase):
    def test_claim_provenance_and_complete_source_classification(self):
        raw = """DIRECT DOCUMENTARY EVIDENCE
S1 [DIRECT_SUPPORT]: A directly evidenced claim.
S9 [CONTEXTUAL]: An invalid citation.

CROSS-SOURCE INFERENCE
S2 [PARTIAL_SUPPORT]: An inference across sources.
An uncited generated claim.

CONTESTED / QUALIFIED EVIDENCE
None.

WHAT THE EVIDENCE DOES NOT ESTABLISH
S3 [NO_RELEVANT_PASSAGE]: A scoped limit.
"""
        claims, classifications = parse_one_shot_output(raw, {"S1", "S2", "S3"})
        self.assertEqual([claim["provenance_status"] for claim in claims], ["PROVENANCE_PASS", "INVALID_SOURCE_ID", "PROVENANCE_PASS", "UNCITED_CLAIM", "PROVENANCE_PASS"])
        self.assertEqual(claims[-1]["section"], "WHAT THE EVIDENCE DOES NOT ESTABLISH")
        self.assertEqual({item["source_id"]: item["classification"] for item in classifications}, {"S1": "DIRECT_SUPPORT", "S2": "PARTIAL_SUPPORT", "S3": "NO_RELEVANT_PASSAGE"})

    def test_explicit_question_echo_is_a_format_violation_but_uncited_claim_remains_uncited(self):
        claims = [
            {"claim_text": "No relevant passage provides contested evidence.", "provenance_status": "UNCITED_CLAIM"},
            {"claim_text": "EXACT REGISTERED QUESTION", "provenance_status": "UNCITED_CLAIM"},
            {"claim_text": "What does Job 171 establish?", "provenance_status": "UNCITED_CLAIM"},
        ]
        projected = project_claim_provenance(claims)
        self.assertEqual([claim["provenance_status"] for claim in projected], ["UNCITED_CLAIM", "FORMAT_VIOLATION", "FORMAT_VIOLATION"])
        self.assertEqual(claims[1]["provenance_status"], "UNCITED_CLAIM")