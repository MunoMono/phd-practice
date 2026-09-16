import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.corpus_status_service import (
    ARCHIVE_RESOLUTION_RESOLVED_CURRENT,
    ARCHIVE_RESOLUTION_UNRESOLVED_LEGACY,
    archive_resolution_status,
    build_corpus_status,
)
from app.services.provenance_service import ProvenanceService


class CorpusStatusContractTests(unittest.TestCase):
    def test_accepted_baseline_satisfies_corpus_invariant(self):
        status = build_corpus_status(138, 109)

        self.assertEqual(status['persistedDocumentCount'], 138)
        self.assertEqual(status['archiveResolvedDocumentCount'], 109)
        self.assertEqual(status['unresolvedLegacyDocumentCount'], 29)
        self.assertTrue(status['invariantSatisfied'])

    def test_archive_resolution_requires_current_explicit_identity(self):
        resolved = SimpleNamespace(
            archive_metadata_source='ddr_graphql.record_v1',
            metadata_sync_status='current',
            archive_record_id='record-1',
            archive_record_pid='record-pid-1',
            asset_id='asset-1',
            asset_pid=None,
            source_uri='https://archive.example/asset.pdf',
        )
        unresolved_legacy = SimpleNamespace(
            archive_metadata_source=None,
            metadata_sync_status='error',
            archive_record_id=None,
            archive_record_pid=None,
            asset_id=None,
            asset_pid=None,
            source_uri=None,
        )

        self.assertEqual(archive_resolution_status(resolved), ARCHIVE_RESOLUTION_RESOLVED_CURRENT)
        self.assertEqual(archive_resolution_status(unresolved_legacy), ARCHIVE_RESOLUTION_UNRESOLVED_LEGACY)

    def test_invalid_corpus_counts_are_rejected(self):
        with self.assertRaises(ValueError):
            build_corpus_status(109, 138)

    def test_legacy_citation_does_not_invent_archive_record_url(self):
        service = ProvenanceService()
        document = SimpleNamespace(
            document_id='doc_legacy',
            pid='legacy-local-pid',
            title='Legacy document',
            publication_year=1975,
            authority_data={},
        )
        chunk = {
            'chunk_id': 'chunk_legacy',
            'chunk_text': 'A retained locally persisted experimental text.',
            'source_page': 3,
            'source_section': None,
            'extraction_timestamp': None,
        }

        service._get_chunk_record = lambda db, chunk_id: chunk
        service._find_document_for_chunk = lambda db, source_chunk: document
        citation = service.build_chunk_citation('chunk_legacy', db=object())

        self.assertIsNone(citation['public_url'])