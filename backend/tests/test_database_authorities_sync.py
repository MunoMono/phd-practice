import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.database_authorities_sync import AUTHORITY_ALLOWED_ROLES, AUTHORITY_DEFINITIONS, get_authority_inventory


class DatabaseAuthorityInventoryTests(unittest.TestCase):
    def test_inventory_covers_all_defined_authority_types(self):
        inventory = get_authority_inventory()
        self.assertEqual(len(inventory), len(AUTHORITY_DEFINITIONS))
        self.assertEqual({item['authority_type'] for item in inventory}, set(AUTHORITY_DEFINITIONS.keys()))

    def test_all_authority_types_have_allowed_roles(self):
        inventory = get_authority_inventory()
        self.assertEqual(set(AUTHORITY_ALLOWED_ROLES.keys()), set(AUTHORITY_DEFINITIONS.keys()))
        self.assertTrue(all(item['allowed_roles'] for item in inventory))
        self.assertIn('controlled_query_expansion', AUTHORITY_ALLOWED_ROLES['ddr_projects'])
        self.assertEqual(AUTHORITY_ALLOWED_ROLES['ref_epistemic_stance'], ['structural_context', 'corroborative_check'])


if __name__ == '__main__':
    unittest.main()