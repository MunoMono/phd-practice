import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "scripts" / "uat_research_query.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("uat_research_query", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DocumentGroundedUatRunnerTests(unittest.TestCase):
    def test_document_grounded_mode_targets_document_and_records_full_result(self):
        runner = load_runner()
        captured = {}

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({
                    "query_id": "run-123",
                    "answer": "A complete source-bound answer.",
                    "stage_execution": {"call_count": 3},
                    "retrieved_evidence": [{"document_id": "doc-selected"}],
                    "provenance_validation": {"valid": True, "source_count": 1},
                    "missingness": ["A scoped limit"],
                }).encode()

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode())
            return Response()

        runner.urllib.request.urlopen = fake_urlopen
        original_argv = sys.argv
        sys.argv = [str(RUNNER_PATH), "http://example.test", "--document-grounded", "1", "1"]
        try:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(runner.main(), 0)
        finally:
            sys.argv = original_argv

        record = json.loads(output.getvalue())
        self.assertEqual(record["question_id"], "DG01")
        self.assertEqual(record["expected_document_id"], "doc_338541406157_72774d03522b")
        self.assertEqual(record["query_id"], "run-123")
        self.assertEqual(record["answer"], "A complete source-bound answer.")
        self.assertEqual(record["returned_document_ids"], ["doc-selected"])
        self.assertTrue(record["provenance_valid"])
        self.assertEqual(record["provenance_source_count"], 1)
        self.assertEqual(record["missingness_count"], 1)
        self.assertEqual(
            captured["payload"]["target_document_ids"],
            ["doc_338541406157_72774d03522b"],
        )


if __name__ == "__main__":
    unittest.main()