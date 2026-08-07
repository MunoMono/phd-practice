import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.corpus_identity import build_corpus_version, build_stable_document_id, compute_sha256
from app.services.corpus_inventory_service import CorpusInventoryService
from app.services.ml_policy import evaluate_ml_policy, parse_ml_pages


class CorpusIdentityTests(unittest.TestCase):
    def test_checksum_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / 'sample.pdf'
            file_path.write_bytes(b'archive-pdf-bytes')
            self.assertEqual(
                compute_sha256(file_path),
                'dbe376175a827065dd16f00b4343e3bcc4bcd6d2cb531e3708d03958e8350a1a',
            )

    def test_stable_document_id(self):
        first = build_stable_document_id(
            '287080879712',
            'sample.pdf',
            'https://example.test/sample.pdf',
            archive_record_pid='014262507600',
            asset_identifier='asset-1',
        )
        second = build_stable_document_id(
            '287080879712',
            'sample.pdf',
            'https://example.test/sample.pdf',
            archive_record_pid='014262507600',
            asset_identifier='asset-1',
        )
        third = build_stable_document_id(
            '287080879712',
            'sample.pdf',
            'https://example.test/sample.pdf',
            archive_record_pid='014262507600',
            asset_identifier='asset-2',
        )
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_corpus_version_is_deterministic(self):
        rows = [
            {'pid': '2', 'source_filename': 'b.pdf', 'source_uri': 'https://example.test/b.pdf'},
            {'pid': '1', 'source_filename': 'a.pdf', 'source_uri': 'https://example.test/a.pdf'},
        ]
        first = build_corpus_version(rows)
        second = build_corpus_version(list(reversed(rows)))
        self.assertEqual(first, second)


class CorpusInventoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = CorpusInventoryService(authority_service=None)

    def test_flatten_record_maps_metadata(self):
        self.service.authority_service = type('StubAuthorityService', (), {
            'fetch_published_records': lambda self, status='published': [
                {
                    'id': '155',
                    'pid': '014262507600',
                    'title': 'Design Education Unit | DEU',
                    'public_uri': 'https://ddrarchive.org/id/record/014262507600',
                    'location_repository': 'RCA',
                    'language_codes': 'en-GB',
                    'attached_media': [
                        {
                            'id': '149',
                            'pid': '287080879712',
                            'title': 'Design Education Unit',
                            'creator_agent_label': 'Ken Baynes',
                            'date_begin': '197806',
                            'date_end': '197806',
                            'category': 'report',
                            'reference_code': 'DEU/2',
                            'access_level': 'Internal',
                            'location_repository': 'RCA',
                            'copyright_holder': 'Copyright © Royal College of Art',
                            'rights_holders': 'V&A',
                            'used_for_ml': True,
                            'ml_annotation': '',
                            'pdf_files': [
                                {
                                    'filename': 'a3.pdf',
                                    'role': 'pdf_master',
                                    'url': 'https://archive.test/a3.pdf',
                                    'label': 'A five year programme',
                                }
                            ],
                            'digital_assets': [
                                {
                                    'role': 'pdf_master',
                                    'filename': 'a3.pdf',
                                    'assetId': 'asset-149',
                                    'pid': 'asset-pid-149',
                                    'use_for_ml': True,
                                    'ml_pages': '1-5',
                                    'ml_annotation': 'sample',
                                    'mime': 'application/pdf',
                                    'display_date': 'June 1978',
                                    'date_qualifier': 'Month known',
                                    'location_repository': 'VAE',
                                    'location_accession': 'AU.AAD.20718',
                                    'location_note': 'AAD/1989/9 Part 2 of 3',
                                    'data_rights': 'Royal College of Art',
                                    'data_rights_holder': 'Royal College of Art',
                                    'image_rights': 'Royal College of Art',
                                    'image_rights_holder': 'Royal College of Art',
                                    'copyright_holder': 'Copyright © Royal College of Art',
                                    'extent_unit': 'ITEM',
                                    'language_codes': 'en-GB',
                                    'keywords': [{'label': 'Bruce Archer'}, {'label': 'Design methods'}],
                                }
                            ],
                        }
                    ],
                }
            ]
        })()

        rows = self.service.flatten_published_pdf_sources()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['pid'], '287080879712')
        self.assertEqual(row['title'], 'A five year programme')
        self.assertEqual(row['creator'], 'Ken Baynes')
        self.assertEqual(row['archive_record_pid'], '014262507600')
        self.assertEqual(row['ml_pages'], '1-5')
        self.assertEqual(row['ml_page_scope'], '1-5')
        self.assertEqual(row['asset_id_or_asset_pid'], 'asset-149')
        self.assertEqual(row['ml_policy_status'], 'eligible_page_restricted')
        self.assertEqual(row['metadata_source'], 'archive_graphql.records_v1')
        self.assertEqual(row['location_repository'], 'VAE')
        self.assertEqual(row['location_accession'], 'AU.AAD.20718')
        self.assertEqual(row['location_note'], 'AAD/1989/9 Part 2 of 3')
        self.assertEqual(row['date_text'], 'June 1978')
        self.assertEqual(row['date_qualifier'], 'Month known')
        self.assertEqual(row['keywords'], ['Bruce Archer', 'Design methods'])
        self.assertEqual(row['language_codes'], 'en-GB')
        self.assertEqual(row['data_rights'], 'Royal College of Art')

    def test_flatten_record_with_multiple_assets_keeps_one_row_per_pdf_master(self):
        record = {
            'id': '155',
            'pid': '014262507600',
            'title': 'Design Education Unit | DEU',
            'public_uri': 'https://ddrarchive.org/id/record/014262507600',
            'attached_media': [
                {
                    'id': '149',
                    'pid': '287080879712',
                    'title': 'Design Education Unit',
                    'pdf_files': [
                        {'filename': 'excluded.pdf', 'role': 'pdf_master', 'url': 'https://archive.test/excluded.pdf', 'label': 'Excluded'},
                        {'filename': 'restricted.pdf', 'role': 'pdf_master', 'url': 'https://archive.test/restricted.pdf', 'label': 'Restricted'},
                    ],
                    'digital_assets': [
                        {'role': 'pdf_master', 'filename': 'excluded.pdf', 'assetId': 'asset-excluded', 'pid': 'pid-excluded', 'use_for_ml': False, 'ml_pages': None, 'mime': 'application/pdf'},
                        {'role': 'pdf_master', 'filename': 'restricted.pdf', 'assetId': 'asset-restricted', 'pid': 'pid-restricted', 'use_for_ml': True, 'ml_pages': '3-5', 'mime': 'application/pdf'},
                    ],
                }
            ],
        }

        rows = self.service.flatten_records_pdf_sources([record])
        self.assertEqual(len(rows), 2)
        self.assertEqual({row['asset_pid'] for row in rows}, {'pid-excluded', 'pid-restricted'})
        self.assertEqual({row['ml_policy_status'] for row in rows}, {'excluded_use_for_ml_false', 'eligible_page_restricted'})

    def test_missing_metadata_is_preserved(self):
        self.service.authority_service = type('StubAuthorityService', (), {
            'fetch_published_records': lambda self, status='published': [
                {
                    'id': '1',
                    'pid': '10',
                    'title': 'Parent',
                    'public_uri': 'https://ddrarchive.org/id/record/10',
                    'attached_media': [
                        {
                            'id': '2',
                            'pid': '20',
                            'title': None,
                            'pdf_files': [
                                {
                                    'filename': 'sample.pdf',
                                    'role': 'pdf_master',
                                    'url': 'https://archive.test/sample.pdf',
                                    'label': None,
                                }
                            ],
                            'digital_assets': [
                                {
                                    'role': 'pdf_master',
                                    'filename': 'sample.pdf',
                                    'use_for_ml': True,
                                    'ml_pages': None,
                                    'ml_annotation': None,
                                    'mime': 'application/pdf',
                                }
                            ],
                        }
                    ],
                }
            ]
        })()
        row = self.service.flatten_published_pdf_sources()[0]
        self.assertIsNone(row['creator'])
        self.assertIsNone(row['document_type'])
        self.assertEqual(row['title'], 'Parent')

    def test_ineligible_rows_remain_in_manifest_with_reason(self):
        self.service.authority_service = type('StubAuthorityService', (), {
            'fetch_published_records': lambda self, status='published': [
                {
                    'id': '1',
                    'pid': '10',
                    'title': 'Parent',
                    'public_uri': 'https://ddrarchive.org/id/record/10',
                    'attached_media': [
                        {
                            'id': '2',
                            'pid': '20',
                            'title': 'Restricted item',
                            'used_for_ml': True,
                            'pdf_files': [
                                {
                                    'filename': 'sample.pdf',
                                    'role': 'pdf_master',
                                    'url': 'https://archive.test/sample.pdf',
                                    'label': None,
                                }
                            ],
                            'digital_assets': [
                                {
                                    'role': 'pdf_master',
                                    'filename': 'sample.pdf',
                                    'assetId': 'asset-20',
                                    'use_for_ml': False,
                                    'ml_pages': None,
                                    'ml_annotation': None,
                                    'mime': 'application/pdf',
                                }
                            ],
                        }
                    ],
                }
            ]
        })()
        row = self.service.flatten_published_pdf_sources()[0]
        self.assertEqual(row['ml_policy_status'], 'excluded_use_for_ml_false')
        self.assertEqual(row['ml_exclusion_reason'], 'asset_marked_use_for_ml_false')
        self.assertFalse(row['use_for_ml'])

    def test_invalid_ml_pages_is_unresolved(self):
        self.service.authority_service = type('StubAuthorityService', (), {
            'fetch_published_records': lambda self, status='published': [
                {
                    'id': '1',
                    'pid': '10',
                    'title': 'Parent',
                    'public_uri': 'https://ddrarchive.org/id/record/10',
                    'attached_media': [
                        {
                            'id': '2',
                            'pid': '20',
                            'title': 'Odd pages',
                            'used_for_ml': True,
                            'pdf_files': [
                                {
                                    'filename': 'sample.pdf',
                                    'role': 'pdf_master',
                                    'url': 'https://archive.test/sample.pdf',
                                    'label': None,
                                }
                            ],
                            'digital_assets': [
                                {
                                    'role': 'pdf_master',
                                    'filename': 'sample.pdf',
                                    'assetId': 'asset-20',
                                    'use_for_ml': True,
                                    'ml_pages': 'all except 10-12',
                                    'ml_annotation': None,
                                    'mime': 'application/pdf',
                                }
                            ],
                        }
                    ],
                }
            ]
        })()
        row = self.service.flatten_published_pdf_sources()[0]
        self.assertEqual(row['ml_policy_status'], 'policy_unresolved')
        self.assertEqual(row['ml_exclusion_reason'], 'invalid_ml_pages:unsupported_page_token')

    def test_duplicate_checksum_detection(self):
        duplicates = self.service.find_duplicate_checksums([
            {'source_filename': 'a.pdf', 'checksum_sha256': 'abc'},
            {'source_filename': 'b.pdf', 'checksum_sha256': 'abc'},
            {'source_filename': 'c.pdf', 'checksum_sha256': 'def'},
        ])
        self.assertEqual(duplicates, {'abc': ['a.pdf', 'b.pdf']})

    def test_pdf_to_record_mapping_failure(self):
        rows = [{'pid': '123', 'source_filename': 'a.pdf'}]
        self.assertIsNone(self.service.find_source_record(rows, '999', 'missing.pdf'))

    def test_manifest_serialization(self):
        rows = [{
            'document_id': 'doc_1',
            'pid': '123',
            'source_filename': 'a.pdf',
            'checksum_sha256': 'abc',
            'title': 'Title',
            'creator': None,
            'date_text': None,
            'document_type': None,
            'archive_reference': None,
            'page_count': 5,
            'ocr_status': 'text_layer_present',
            'ingestion_status': 'inventory_ready',
            'ingestion_error': None,
            'chunk_count': None,
            'ingestion_version': 'v1',
            'corpus_version': 'corpus_123',
            'source_uri': 'https://archive.test/a.pdf',
            'source_path': '/tmp/a.pdf',
            'authority_id': '149',
            'archive_record_id': '155',
            'archive_record_pid': '014262507600',
            'asset_id': 'asset-149',
            'asset_pid': 'asset-pid-149',
            'asset_id_or_asset_pid': 'asset-149',
            'metadata_source': 'archive_graphql.records_v1',
            'access_level': 'Internal',
            'rights_note': 'RCA',
            'media_used_for_ml': True,
            'use_for_ml': True,
            'ml_pages': '1-2',
            'ml_page_scope': '1-2',
            'ml_annotation': None,
            'ml_policy_status': 'eligible_page_restricted',
            'ml_exclusion_reason': None,
            'record_title': 'Parent',
            'record_public_uri': 'https://ddrarchive.org/id/record/014262507600',
        }]

        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / 'manifest.csv'
            json_path = Path(tmp_dir) / 'manifest.json'
            self.service.write_manifest_csv(rows, csv_path)
            self.service.write_manifest_json(rows, json_path)

            with csv_path.open(newline='', encoding='utf-8') as handle:
                csv_rows = list(csv.DictReader(handle))
            with json_path.open(encoding='utf-8') as handle:
                json_rows = json.load(handle)

            self.assertEqual(len(csv_rows), 1)
            self.assertEqual(csv_rows[0]['pid'], '123')
            self.assertEqual(csv_rows[0]['ml_policy_status'], 'eligible_page_restricted')
            self.assertEqual(len(json_rows), 1)
            self.assertEqual(json_rows[0]['source_filename'], 'a.pdf')


class MLPolicyTests(unittest.TestCase):
    def test_parse_ml_pages_supports_observed_ranges(self):
        parsed = parse_ml_pages('10, 23-24')
        self.assertEqual(parsed['normalized_scope'], '10, 23-24')
        self.assertEqual(parsed['allowed_pages'], [10, 23, 24])

    def test_parse_ml_pages_blank_is_unrestricted(self):
        parsed = parse_ml_pages('   ')
        self.assertFalse(parsed['is_restricted'])
        self.assertIsNone(parsed['allowed_pages'])

    def test_evaluate_ml_policy_unrestricted(self):
        policy = evaluate_ml_policy(asset_present=True, asset_use_for_ml=True, ml_pages='')
        self.assertEqual(policy['ml_policy_status'], 'eligible_unrestricted')
        self.assertEqual(policy['ml_page_scope'], 'all_pages')

    def test_evaluate_ml_policy_missing_asset_is_unresolved(self):
        policy = evaluate_ml_policy(asset_present=False, asset_use_for_ml=None, ml_pages=None)
        self.assertEqual(policy['ml_policy_status'], 'policy_unresolved')
        self.assertEqual(policy['ml_exclusion_reason'], 'missing_matching_pdf_master_asset')


if __name__ == '__main__':
    unittest.main()