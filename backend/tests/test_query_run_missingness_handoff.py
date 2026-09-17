import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.query_runs import (
    QueryRunMissingnessRequest,
    build_missingness_event_values,
    export_query_run_json,
    export_query_run_markdown,
)


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


class QueryRunExportTests(unittest.TestCase):
    def setUp(self):
        self.db = Mock()
        self.run = SimpleNamespace(
            query_id="query-export",
            prompt="What does the evidence establish?",
            mode="exploratory",
            model="qwen",
            response="A source-grounded response.",
            caveats=None,
            failed_or_partial=False,
            failure_reason=None,
            retrieved_chunk_count=0,
            export_status=None,
            created_at=None,
            updated_at=None,
            chunks=[],
        )

    def test_json_export_does_not_persist_export_history(self):
        with patch("app.api.routes.query_runs.LocalSessionLocal", return_value=self.db), patch(
            "app.api.routes.query_runs.get_query_run_or_404", return_value=self.run
        ):
            response = asyncio.run(export_query_run_json("query-export"))

        self.assertEqual(response.media_type, "application/json")
        self.assertIn(b'"query_id": "query-export"', response.body)
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

    def test_markdown_export_does_not_persist_export_history(self):
        with patch("app.api.routes.query_runs.LocalSessionLocal", return_value=self.db), patch(
            "app.api.routes.query_runs.get_query_run_or_404", return_value=self.run
        ):
            response = asyncio.run(export_query_run_markdown("query-export"))

        self.assertEqual(response.media_type, "text/markdown")
        self.assertIn(b"# Retrieval trail memo", response.body)
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()
