import unittest
from pathlib import Path


MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "045_turin_q09_sm1_v2_plan_identity_primary_uniqueness.sql"


class TurinQ09PlanIdentityGovernanceTests(unittest.TestCase):
    def test_primary_uniqueness_includes_immutable_plan_identity(self):
        sql = MIGRATION.read_text()
        self.assertIn("idx_experiment_runs_primary_question_protocol_plan", sql)
        self.assertIn("question_id, retrieval_protocol_version, retrieval_plan_id, retrieval_plan_version", sql)

    def test_primary_evaluability_predicate_remains_unchanged(self):
        sql = MIGRATION.read_text()
        self.assertIn("status IN ('completed', 'completed_with_missingness')", sql)
        self.assertIn("OR raw_model_response IS NOT NULL", sql)
        self.assertIn("retrieval_run_classification = 'primary'", sql)
        self.assertIn("retrieval_scope = 'corpus_wide'", sql)
        self.assertIn("formal_authorization_id IS NOT NULL", sql)

    def test_migration_does_not_create_authorizations_or_runs(self):
        sql = MIGRATION.read_text()
        self.assertNotIn("INSERT INTO", sql)
        self.assertNotIn("UPDATE experiment_runs", sql)

    def test_raw_recovery_transition_is_limited_to_the_existing_authorized_run(self):
        sql = MIGRATION.read_text()
        self.assertIn("OLD.run_id = 'experiment-381bc274183b'", sql)
        self.assertIn("OLD.error_code = 'persistence_failure'", sql)
        self.assertIn("NEW.status = 'completed'", sql)
        self.assertIn("NEW.raw_model_response = OLD.raw_model_response", sql)


if __name__ == "__main__":
    unittest.main()