import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.query_execution_trace import build_query_execution_trace


RUNNER_PATH = BACKEND_ROOT / "scripts" / "run_ml_triage_dev_v2.py"
CSV_PATH = REPO_ROOT / "docs" / "ml_triage_dev_v2" / "clean_ml_triage_dev_UAT_50_v2.csv"


def load_runner():
    spec = importlib.util.spec_from_file_location("run_ml_triage_dev_v2", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class Response:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class MLTriageDevV2HarnessTests(unittest.TestCase):
    def test_blank_answer_without_evidence_is_a_typed_retrieval_error(self):
        trace = build_query_execution_trace(
            {
                "query_id": "query-1",
                "answer": "",
                "stage_execution": {},
                "retrieval_diagnostics": {"retrieved_documentary_source_count": 0},
            },
            external_test_id="external-1",
            question_text="A neutral test question?",
        )

        self.assertEqual(trace["execution_outcome"], "retrieval_coverage_error")
        self.assertEqual(trace["errors"][0]["stage"], "response")
        self.assertEqual(trace["retrieval_diagnostics"]["retrieved_documentary_source_count"], 0)

    def test_trace_preserves_typed_evidence_ledger(self):
        trace = build_query_execution_trace(
            {
                "query_id": "query-typed",
                "answer": "A bounded answer.",
                "evidence_ledger": [{
                    "evidence_id": "authority:job-181",
                    "evidence_type": "DATABASE_AUTHORITY",
                    "source_pid_or_authority_key": "job-181",
                }],
            },
            external_test_id="external-typed",
            question_text="A neutral authority question?",
        )

        self.assertEqual(trace["evidence_type_per_item"][0]["evidence_type"], "DATABASE_AUTHORITY")

    def test_executes_all_50_without_sending_evaluation_fields(self):
        runner = load_runner()
        requests = []

        def fake_urlopen(request, timeout):
            payload = json.loads(request.data.decode("utf-8"))
            requests.append(payload)
            if payload["question_id"] == "MLT-LIM-01":
                return Response({
                    "query_id": "limit-run",
                    "answer": "The bounded evidence does not establish the requested cause.",
                    "answer_state": "evidential_limit",
                    "answer_origin": "scoped_limit",
                    "missingness": [{"scope": "current digitised corpus"}],
                })
            return Response({
                "query_id": f"run-{len(requests)}",
                "answer": "A source-grounded response.",
                "answer_state": "synthesis_valid",
                "retrieved_evidence": [{"chunk_id": "chunk-1", "pid": "pid-1"}],
                "provenance_validation": {"valid": True},
            })

        with tempfile.TemporaryDirectory() as temporary_directory, patch.object(
            runner.urllib.request, "urlopen", side_effect=fake_urlopen
        ):
            output_root = Path(temporary_directory)
            exit_code = runner.main(["--csv", str(CSV_PATH), "--output-root", str(output_root)])
            run_dir = next(output_root.iterdir())
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(requests), 50)
            self.assertEqual(len(manifest["cases"]), 50)
            self.assertEqual(manifest["baseline"], {"total": 50, "pass": 2, "fail": 47, "unresolved_blank": 1})
            self.assertFalse({"uat_pass_fail", "graham_newman_subjective_comments"} & set(requests[0]))
            document_trace = json.loads((run_dir / "MLT-DOC-18.json").read_text(encoding="utf-8"))
            limit_trace = json.loads((run_dir / "MLT-LIM-01.json").read_text(encoding="utf-8"))
            self.assertEqual(document_trace["execution_outcome"], "success")
            self.assertEqual(document_trace["source_details"][0]["source_pid"], "pid-1")
            self.assertEqual(limit_trace["execution_outcome"], "scoped_limit")
            self.assertTrue(limit_trace["final_answer"])

    def test_unresolved_case_execution_failure_persists_typed_trace(self):
        runner = load_runner()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            exit_code = runner.main([
                "--csv", str(CSV_PATH),
                "--output-root", str(root / "runs"),
                "--replay-dir", str(root / "missing-replays"),
                "--case", "MLT-HYB-14",
            ])
            run_dir = next((root / "runs").iterdir())
            trace = json.loads((run_dir / "MLT-HYB-14.json").read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 1)
            self.assertEqual(trace["execution_outcome"], "explicit_synthesis_validation_error")
            self.assertIn("No replay response found", trace["errors"][0]["error"])


if __name__ == "__main__":
    unittest.main()