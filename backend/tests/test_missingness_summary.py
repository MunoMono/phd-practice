import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.missingness import calculate_metadata_coverage


class MissingnessSummaryTests(unittest.TestCase):
    def test_metadata_coverage_counts_publication_year_as_a_measured_field(self):
        coverage = calculate_metadata_coverage(
            total_documents=2,
            documents_with_title=2,
            documents_with_pid=2,
            documents_with_filename=2,
            documents_with_publication_year=1,
        )

        self.assertEqual(coverage, 88)

    def test_metadata_coverage_is_zero_without_local_documents(self):
        self.assertEqual(calculate_metadata_coverage(0, 0, 0, 0, 0), 0)