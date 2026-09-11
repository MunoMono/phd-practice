import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.analysis import ExploratoryInterrogationRequest, _catalogue_response


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


if __name__ == "__main__":
    unittest.main()