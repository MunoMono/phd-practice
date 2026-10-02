import unittest

from app.services.turin_question_route import classify_question_route, decompose_hybrid_question
from tests.ml_triage_uat_fixture import load_ml_triage_uat_cases


class TurinQuestionRouteTests(unittest.TestCase):
    def test_canonical_manifest_routes_by_intent(self):
        for case in load_ml_triage_uat_cases():
            with self.subTest(case_id=case["uat_id"]):
                self.assertEqual(classify_question_route(case["question"]).family, case["question_class"])

    def test_person_entity_does_not_override_documentary_intent(self):
        decision = classify_question_route("What do Archer's lecture notes say about design research?")
        self.assertEqual(decision.family, "DOCUMENTARY")

    def test_evidence_test_outranks_person_authority_context(self):
        decision = classify_question_route("Does the current corpus establish that Archer caused the closure?")
        self.assertEqual(decision.family, "SCOPED_MISSINGNESS")

    def test_natural_language_ddr_closure_rationale_is_scoped_missingness(self):
        decision = classify_question_route("Why did the Department of Design Research close?")
        self.assertEqual(decision.family, "SCOPED_MISSINGNESS")

    def test_hybrid_decomposition_separates_documentary_proposition_and_explicit_anchor(self):
        question = (
            "According to the database record, who is recorded as leading Job 171, "
            "and what do the surviving Job 171 reports establish about research needs?"
        )

        decomposition = decompose_hybrid_question(question)

        self.assertIsNotNone(decomposition)
        self.assertEqual(
            decomposition.documentary_query,
            "what do the surviving Job 171 reports establish about research needs?",
        )
        self.assertEqual(decomposition.documentary_anchors, ["Job 171"])
        self.assertNotIn("database record", decomposition.documentary_query.lower())
        self.assertNotIn("leading", decomposition.documentary_query.lower())

    def test_non_hybrid_routes_do_not_manufacture_documentary_decomposition(self):
        self.assertIsNone(decompose_hybrid_question("What do Job 171 reports establish about research needs?"))
        self.assertIsNone(decompose_hybrid_question("Who is recorded as leading Job 171?"))

    def test_hybrid_without_a_deterministic_documentary_proposition_fails_closed(self):
        self.assertIsNone(decompose_hybrid_question(
            "According to the database record, who is recorded as leading Job 171 alongside archival context?"
        ))
