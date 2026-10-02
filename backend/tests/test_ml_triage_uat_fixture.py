import unittest

from tests.ml_triage_uat_fixture import REQUIRED_COLUMNS, load_ml_triage_uat_cases


class MlTriageUatFixtureTests(unittest.TestCase):
    def test_frozen_uat_fixture_has_all_required_fields_and_unique_ids(self):
        cases = load_ml_triage_uat_cases()

        self.assertEqual(len(cases), 50)
        self.assertEqual(len({case["uat_id"] for case in cases}), 50)
        for case in cases:
            self.assertTrue(REQUIRED_COLUMNS.issubset(case))
            self.assertTrue(case["expected_retrieval_mode"])
            self.assertTrue(case["prohibited_overclaim"])
            self.assertTrue(case["pass_criteria"])


if __name__ == "__main__":
    unittest.main()