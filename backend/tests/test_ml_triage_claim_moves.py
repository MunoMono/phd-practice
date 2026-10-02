import unittest

from app.services.ml_triage_claim_moves import evaluate_required_claim_moves


class MlTriageClaimMoveTests(unittest.TestCase):
    def test_persists_explicit_move_ids_without_keyword_scoring(self):
        evaluation = evaluate_required_claim_moves(
            {"required_claim_moves": "Recorded employment role; Controlled period", "question_class": "AUTHORITY_ONLY"},
            {"retrieval": {"route_family": "AUTHORITY_ONLY"}, "answer_paragraphs": [{"claims": [{"claim_ids": ["c1"]}]}], "final_claim_plan": {"claims": [{"claim_id": "c1", "claim_type": "DATABASE_AUTHORITY", "supporting_authority_ids": ["AUTH-1"]}]}},
        )
        self.assertTrue(evaluation["machine_evaluable"])
        self.assertEqual(evaluation["coverage"]["covered"], 2)
        self.assertTrue(all(item["required_claim_move_id"].startswith("move:") for item in evaluation["statuses"]))

    def test_documentary_move_requires_explicit_final_claim_support(self):
        evaluation = evaluate_required_claim_moves(
            {"required_claim_moves": "Compare dated teaching approaches", "question_class": "DOCUMENTARY"},
            {
                "retrieval": {"route_family": "DOCUMENTARY"},
                "answer_paragraphs": [{"claims": [{"claim_ids": ["c1"]}]}],
                "final_claim_plan": {"claims": [{
                    "claim_id": "c1", "claim_type": "DIRECT_DOCUMENTARY",
                    "text": "The course notes describe an ergonomics exercise.",
                    "supporting_evidence_card_ids": ["ev-1"],
                }]},
            },
        )

        self.assertEqual(evaluation["statuses"][0]["status"], "NOT_COVERED")
        self.assertIn("do not explicitly support", evaluation["statuses"][0]["reason"])
