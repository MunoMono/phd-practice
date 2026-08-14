import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_pilot_ingestion import chunks_for_page, deterministic_chunk_id, permitted_pages


class TurinPilotIngestionTests(unittest.TestCase):
    def test_restricted_page_scope_excludes_other_pages(self):
        self.assertEqual(
            permitted_pages(12, "eligible_page_restricted", "3-4, 9"),
            [3, 4, 9],
        )

    def test_ineligible_document_cannot_be_processed(self):
        with self.assertRaisesRegex(ValueError, "not eligible"):
            permitted_pages(12, "excluded_use_for_ml_false", None)

    def test_page_chunks_keep_heading_and_page_provenance(self):
        chunks = chunks_for_page("# Methods\n\nEvidence paragraph one.\n\nEvidence paragraph two.", 7)
        self.assertEqual([chunk["page_start"] for chunk in chunks], [7, 7])
        self.assertEqual([chunk["page_end"] for chunk in chunks], [7, 7])
        self.assertEqual([chunk["heading_path"] for chunk in chunks], ["Methods", "Methods"])

    def test_chunk_identity_is_deterministic(self):
        chunks = chunks_for_page("# Evidence\n\nStable source text.", 3)
        chunk = chunks[0]
        first = deterministic_chunk_id("doc_test", "corpus_test", chunk["page_start"], chunk["sequence_number"], chunk["heading_path"], chunk["chunk_text"])
        second = deterministic_chunk_id("doc_test", "corpus_test", chunk["page_start"], chunk["sequence_number"], chunk["heading_path"], chunk["chunk_text"])
        self.assertEqual(first, second)