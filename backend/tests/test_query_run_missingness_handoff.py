import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.query_runs import QueryRunMissingnessRequest, build_missingness_event_values


class QueryRunMissingnessHandoffTests(unittest.TestCase):
    def test_zero_result_run_creates_scoped_retrieval_event(self):
        run = SimpleNamespace(
            query_id="query-zero",
            prompt="Did the records establish user reception?",
            chunks=[],
            retrieved_chunk_count=0,
            model="qwen",
            failure_reason="No supporting source chunks were returned.",
            caveats=None,
        )
        values = build_missingness_event_values(run, QueryRunMissingnessRequest())
        self.assertEqual(values["type"], "retrieval")
        self.assertEqual(values["query_id"], "query-zero")
        self.assertEqual(values["source_document_ids_json"], [])
        self.assertIn("current digitised corpus and retrieval run only", values["evidence"])

    def test_weak_retrieval_preserves_all_returned_source_provenance(self):
        run = SimpleNamespace(
            query_id="query-weak",
            prompt="Can the surviving digitised records establish how Design in General Education was received by its intended users?",
            chunks=[
                SimpleNamespace(document_id="doc-1", chunk_id="chunk-1"),
                SimpleNamespace(document_id="doc-2", chunk_id="chunk-2"),
            ],
            retrieved_chunk_count=2,
            model="qwen",
            failure_reason=None,
            caveats="The retrieved evidence does not establish reception by intended users.",
        )
        values = build_missingness_event_values(run, QueryRunMissingnessRequest(
            evidence_note="The retained evidence does not directly establish reception by intended users.",
            follow_up_action="Search correspondence and evaluations.",
        ))
        self.assertEqual(values["source_document_ids_json"], ["doc-1", "doc-2"])
        self.assertEqual(values["source_chunk_ids_json"], ["chunk-1", "chunk-2"])
        self.assertEqual(values["follow_up_action"], "Search correspondence and evaluations.")
        self.assertIn("does not directly establish reception", values["evidence"])
