import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.analysis import (
    ExploratoryInterrogationRequest,
    _catalogue_response,
    _project_staged_exploratory_response,
)


class ExploratoryComparisonRequestTests(unittest.TestCase):
    def test_comparison_requires_exactly_two_documents(self):
        with self.assertRaises(ValidationError):
            ExploratoryInterrogationRequest(
                query="Compare the selected sources.",
                mode="comparison",
                target_document_ids=["document-a"],
            )

    def test_comparison_accepts_two_documents(self):
        request = ExploratoryInterrogationRequest(
            query="Compare the selected sources.",
            mode="comparison",
            target_document_ids=["document-a", "document-b"],
        )

        self.assertEqual(request.mode, "comparison")
        self.assertEqual(request.target_document_ids, ["document-a", "document-b"])

    def test_catalogue_authority_claims_include_authority_citation_numbers(self):
        response = _catalogue_response(
            "What projects did Pierre Goumain work on?",
            {"results": []},
            [{
                "authority_type": "ddr_projects",
                "authority_id": "171",
                "fields": {"title": "Designer-computer interaction", "project_lead_name": "Pierre Goumain"},
            }],
        )

        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["authority_numbers"], [1])

    def test_catalogue_document_claims_include_source_citation_numbers(self):
        response = _catalogue_response(
            "What documents mention Janet Daley?",
            {"results": [{
                "document_id": "document-1",
                "chunk_id": "chunk-1",
                "title": "RCA yearbook",
                "asset_pid": "asset-1",
                "page_start": 40,
            }]},
            [],
        )

        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1])

    def test_evidence_limit_claim_includes_all_returned_source_citations(self):
        response = _project_staged_exploratory_response(
            {
                "final_synthesis": {
                    "answer": "The DDR documents do not provide direct documentary evidence for this question.",
                    "synthesis_claims": [],
                },
                "cross_source_analysis": {},
                "evidence_map": {
                    "DIRECT_DOCUMENTARY": [],
                    "DATABASE_AUTHORITY": [],
                    "ARCHIVAL_METADATA": [],
                    "CONTEXTUAL": [],
                    "NOT_ESTABLISHED": [],
                    "source_classifications": [],
                },
            },
            {
                "transparency": {"strategy": "semantic", "resolved_entities": [], "query_variants": []},
                "results": [{
                    "document_id": "document-1",
                    "chunk_id": "chunk-1",
                    "title": "RCA yearbook",
                    "asset_pid": "asset-1",
                    "page_start": 5,
                }],
            },
        )

        self.assertEqual(response["answer_origin"], "deterministic_evidence_limit")
        self.assertEqual(response["answer_paragraphs"][0]["claims"][0]["source_numbers"], [1])


if __name__ == "__main__":
    unittest.main()