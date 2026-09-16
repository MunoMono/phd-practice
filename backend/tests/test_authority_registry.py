import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.authority_registry import AUTHORITY_SPECS, AuthorityRegistry


class Rows:
    def __init__(self, values):
        self.values = values

    def mappings(self):
        return self

    def all(self):
        return self.values


class AuthorityDatabase:
    def execute(self, _, params):
        authority_type = params["authority_type"]
        return Rows([{
            "authority_id": "1965-71" if authority_type == "ref_ddr_period" else f"{authority_type}-1",
            "code": "CODE",
            "label": "Known Student" if authority_type == "ref_students" else f"Known {authority_type}",
            "description": "Controlled authority description",
            "metadata": {"year": 1971} if authority_type == "ref_students" else {},
        }])


class AuthorityRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = AuthorityRegistry()
        self.database = AuthorityDatabase()

    def test_inventory_includes_every_live_database_authority_type(self):
        inventory = self.registry.inventory()
        self.assertEqual({item["authority_type"] for item in inventory}, set(AUTHORITY_SPECS))
        self.assertEqual(len(inventory), 11)
        self.assertEqual(next(item for item in inventory if item["authority_type"] == "ref_methodology")["epistemic_type"], "interpretative_analytical")

    def test_natural_language_selection_covers_every_registered_non_staff_project_authority(self):
        cases = {
            "What role did Known agent_employment hold?": "agent_employment",
            "When did Known agent_employment work at DDR?": "agent_employment",
            "What was Known agent_employment's involvement at DDR?": "agent_employment",
            "Which students are recorded?": "ref_students",
            "What fonds are represented?": "ref_fonds",
            "Show reports relating to hospital equipment": "ref_publication_type",
            "What period does 1973 belong to?": "ref_ddr_period",
            "Which methodology classifications are available?": "ref_methodology",
            "Find projects concerned with disability": "ref_project_theme",
            "Which outcomes are classified?": "ref_project_outcome",
            "Which beneficiary audience is classified?": "ref_beneficiary_audience",
            "Which epistemic stance is classified?": "ref_epistemic_stance",
        }
        for question, authority_type in cases.items():
            with self.subTest(authority_type=authority_type):
                self.assertIn(authority_type, self.registry.selected_types(question))

    def test_period_uses_explicit_controlled_identifier_range(self):
        contexts = self.registry.resolve(self.database, "What period does 1970 belong to?", ["ref_ddr_period"])
        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0].authority_id, "1965-71")
        self.assertEqual(contexts[0].fields["epistemic_type"], "administrative_structural")

    def test_named_student_miss_does_not_become_historical_absence_or_full_list(self):
        contexts = self.registry.resolve(self.database, "Was Unknown Person a student?", ["ref_students"])
        self.assertEqual(contexts, [])

    def test_interpretative_authority_is_labelled_as_database_classification(self):
        contexts = self.registry.resolve(self.database, "Which methodology classifications are available?", ["ref_methodology"])
        self.assertEqual(contexts[0].fields["authority_classification"], "database authority classification")


if __name__ == "__main__":
    unittest.main()