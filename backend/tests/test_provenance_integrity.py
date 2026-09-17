import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.provenance_integrity import (
    claim_evidence_digest,
    experiment_evidence_digest,
    experiment_run_digest,
    query_run_chunk_digest,
    query_run_digest,
)


class ProvenanceIntegrityTests(unittest.TestCase):
    def test_chunk_digest_is_deterministic_across_json_key_order(self):
        first = {
            "chunk_id": "chunk-1", "document_id": "doc-1", "page_range": "4",
            "rank": 1, "score": 0.9, "citation_text": "Citation",
            "provenance_json": {"pid": "pid-1", "title": "Document"},
            "source_metadata_json": {"title": "Document", "pid": "pid-1"},
        }
        second = {**first, "provenance_json": {"title": "Document", "pid": "pid-1"}}
        self.assertEqual(query_run_chunk_digest(first), query_run_chunk_digest(second))

    def test_run_digest_changes_when_the_retrieval_stack_changes(self):
        run = {"query_id": "query-1", "prompt": "Question", "failed_or_partial": False}
        self.assertNotEqual(query_run_digest(run, ["a" * 64]), query_run_digest(run, ["b" * 64]))

    def test_claim_evidence_digest_binds_claim_and_citation(self):
        evidence = {"claim_id": "claim-1", "chunk_id": "chunk-1", "citation_text": "Citation"}
        changed = {**evidence, "citation_text": "Different citation"}
        self.assertNotEqual(claim_evidence_digest(evidence), claim_evidence_digest(changed))

    def test_experiment_run_digest_binds_output_and_evidence(self):
        run = {"run_id": "experiment-1", "research_question": "Question", "status": "completed"}
        self.assertNotEqual(
            experiment_run_digest(run, ["a" * 64]),
            experiment_run_digest({**run, "status": "failed"}, ["a" * 64]),
        )
        self.assertNotEqual(
            experiment_evidence_digest({"run_id": "experiment-1", "rank": 1, "chunk_id": "chunk-1", "document_id": "doc-1", "snapshot_json": {}}),
            experiment_evidence_digest({"run_id": "experiment-1", "rank": 1, "chunk_id": "chunk-1", "document_id": "doc-1", "snapshot_json": {"text": "changed"}}),
        )