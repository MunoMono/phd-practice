import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.analysis import ExploratoryInterrogationRequest, _persist_comparison_snapshot


class Database:
    def __init__(self):
        self.added = []
        self.committed = False

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.committed = True


class ComparisonPersistenceTests(unittest.TestCase):
    def test_snapshot_records_selected_documents_and_passage(self):
        database = Database()
        source = {
            "document_id": "document-a",
            "chunk_id": "chunk-a",
            "text": "Selected passage.",
            "rank": 1,
            "score": 0.9,
            "archive_resolution_status": "archive_resolved_current",
        }

        run_id = _persist_comparison_snapshot(
            database,
            ExploratoryInterrogationRequest(
                query="Compare the selected sources.",
                mode="comparison",
                target_document_ids=["document-a", "document-b"],
            ),
            [source],
            {"transparency": {"strategy": "explicit_document_selection_v1"}, "diagnostics": {}},
            {"model": "fixture", "runtime": "fixture"},
            "Bounded answer.",
            {"schema": "turin-document-comparison-v1"},
            {"valid": True},
            [{"stage": "final_synthesis", "count": 1}],
        )

        run = database.added[0]
        evidence = database.added[1]
        self.assertTrue(run_id.startswith("comparison-"))
        self.assertEqual(run.retrieval_config_json["selected_document_ids"], ["document-a", "document-b"])
        self.assertEqual(evidence.chunk_id, "chunk-a")
        self.assertTrue(database.committed)


if __name__ == "__main__":
    unittest.main()
