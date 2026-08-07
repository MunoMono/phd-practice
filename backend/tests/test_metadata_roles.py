import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.metadata_roles import attach_metadata_roles, format_granite_source_block


class MetadataRoleTests(unittest.TestCase):
    def test_attach_metadata_roles_partitions_control_rights_provenance_and_catalogue(self):
        payload = attach_metadata_roles(
            {
                'authority_id': '149',
                'record_pid': '014262507600',
                'asset_pid': '942396101474',
                'asset_id': 'asset-149',
                'title': 'Memorandum',
                'source_filename': 'memo.pdf',
                'source_uri': 'https://archive.test/memo.pdf',
                'archive_reference': 'DEU/2',
                'record_title': 'Design Education Unit | DEU',
                'location_repository': 'V&A Archive',
                'location_accession': 'AU.AAD.20718',
                'location_note': 'AAD/1989/9 Part 2 of 3',
                'date_text': 'June 1978',
                'date_qualifier': 'Estimated from context',
                'creator': 'Ken Baynes',
                'caption': 'Signed motion',
                'keywords': ['Bruce Archer', 'Design methods'],
                'scope_and_content': 'Institutional policy correspondence.',
                'subjects': ['academic governance', 'institutional policy'],
                'document_type': 'report',
                'use_for_ml': False,
                'ml_page_scope': '19-20',
                'ml_policy_status': 'excluded_use_for_ml_false',
                'rights_note': 'V&A',
                'data_rights': 'Royal College of Art',
                'copyright_holder': 'Copyright © Royal College of Art',
            }
        )
        self.assertEqual(payload['corpus_control']['ml_policy_status'], 'excluded_use_for_ml_false')
        self.assertEqual(payload['rights_access']['data_rights'], 'Royal College of Art')
        self.assertEqual(payload['retrieval_provenance']['archive_record_pid'], '014262507600')
        self.assertEqual(payload['retrieval_provenance']['accession_shelfmark'], 'AU.AAD.20718')
        self.assertEqual(payload['retrieval_provenance']['location_note'], 'AAD/1989/9 Part 2 of 3')
        self.assertEqual(payload['catalogue_metadata']['caption'], 'Signed motion')
        self.assertEqual(payload['catalogue_metadata']['keywords'], ['Bruce Archer', 'Design methods'])
        self.assertEqual(payload['catalogue_metadata']['date_qualifier'], 'Estimated from context')
        self.assertNotIn('caption', payload['corpus_control'])
        self.assertNotIn('rights_note', payload['corpus_control'])

    def test_format_granite_source_block_separates_catalogue_metadata(self):
        block = format_granite_source_block(
            1,
            {
                'text': 'The memorandum records a policy dispute.',
                'provenance': {
                    'archive_record_pid': '014262507600',
                    'asset_pid': '942396101474',
                    'title': 'Memorandum',
                    'document_date': 'June 1978',
                    'creator': 'Ken Baynes',
                    'page': 19,
                    'chunk_id': 'chunk_1',
                },
                'catalogue_metadata': {
                    'caption': 'Signed motion',
                    'subjects': ['academic governance', 'institutional policy'],
                },
            },
        )
        self.assertIn('ARCHIVE RECORD PID: 014262507600', block)
        self.assertIn('ARCHIVE / CATALOGUE METADATA:', block)
        self.assertIn('CAPTION: Signed motion', block)
        self.assertIn('SOURCE TEXT:\nThe memorandum records a policy dispute.', block)
        self.assertNotIn('use_for_ml', block)


if __name__ == '__main__':
    unittest.main()