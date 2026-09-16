import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer


class QuestionAnalyzerTests(unittest.TestCase):
    def test_person_role_analysis_is_deterministic_and_inspectable(self):
        question = "What teaching role did Example Person have in 1974?"
        first = TurinRetrievalV3QuestionAnalyzer().analyze(question)
        self.assertEqual(first, TurinRetrievalV3QuestionAnalyzer().analyze(question))
        self.assertEqual(first.template, "PERSON_ROLE")
        self.assertEqual(first.terms["ENTITY"], ["Example Person"])
        self.assertIn("teaching", first.terms["ACTIVITY"])
        self.assertIn("PERSON_A", first.required_facets)
        self.assertIn("entity", first.lane_queries)
        self.assertNotIn("semantic", first.lane_queries)

    def test_two_people_prefer_relationship_template(self):
        result = TurinRetrievalV3QuestionAnalyzer().analyze("How did Example Person work with Other Person in the department?")
        self.assertEqual(result.template, "PERSON_PERSON_RELATIONSHIP")
        self.assertEqual(result.required_facets[:2], ["PERSON_A", "PERSON_B"])

    def test_event_and_project_templates_are_generic(self):
        analyzer = TurinRetrievalV3QuestionAnalyzer()
        self.assertEqual(analyzer.analyze("Why did the department close in 1978?").template, "EVENT_CAUSATION")
        self.assertEqual(analyzer.analyze("What traces survive for Job 171?").template, "PROJECT_TRACES")


if __name__ == "__main__":
    unittest.main()