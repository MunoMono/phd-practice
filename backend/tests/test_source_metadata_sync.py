import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.source_metadata_sync import SourceMetadataSyncService, _snapshot_hash


class FakeQuery:
    def __init__(self, document):
        self.document = document

    def filter(self, *_args):
        return self

    def first(self):
        return self.document


class FakeSession:
    def __init__(self, document):
        self.document = document
        self.commits = 0
        self.rollbacks = 0

    def query(self, *_args):
        return FakeQuery(self.document)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        pass


class FakeAuthorityService:
    def __init__(self, record=None):
        self.record = record

    def fetch_record_by_pid(self, _pid):
        return self.record


def make_record(title='Title B', use_for_ml=True, ml_pages='', asset_id='asset-1', asset_pid='asset-pid-1'):
    return {
        'id': 'record-id',
        'pid': 'record-pid',
        'title': 'Record title',
        'public_uri': 'https://ddr.test/record',
        'attached_media': [{
            'id': 'media-id',
            'pid': 'media-pid',
            'title': title,
            'data_rights': 'DDR rights',
            'pdf_files': [{
                'role': 'pdf_master',
                'filename': 'source.pdf',
                'url': 'https://ddr.test/source.pdf',
            }],
            'digital_assets': [{
                'role': 'pdf_master',
                'filename': 'source.pdf',
                'url': 'https://ddr.test/source.pdf',
                'assetId': asset_id,
                'pid': asset_pid,
                'use_for_ml': use_for_ml,
                'ml_pages': ml_pages,
            }],
        }],
    }


def make_document():
    return SimpleNamespace(
        document_id='doc-1', pid='media-pid', authority_id='media-id',
        archive_record_id='record-id', archive_record_pid='record-pid',
        asset_id='asset-1', asset_pid='asset-pid-1', source_uri='https://ddr.test/source.pdf',
        filename='source.pdf', file_type='application/pdf', title='Title A',
        authority_data={'title': 'Title A', 'data_rights': 'Old rights'},
        extracted_text='Evidence must not be changed', processing_status='completed',
        use_for_ml=1, ml_page_scope='all_pages', ml_policy_status='eligible_unrestricted',
        ml_exclusion_reason=None, archive_metadata_snapshot_hash=None,
        source_asset_identity_hash=None, source_asset_changed=0, reingestion_required=0,
    )


class SourceMetadataSyncTests(unittest.TestCase):
    def sync(self, document, record):
        session = FakeSession(document)
        service = SourceMetadataSyncService(FakeAuthorityService(record), session_factory=lambda: session)
        return service.sync_archive_metadata(document.document_id), session

    def test_metadata_only_change_updates_snapshot_without_touching_extraction(self):
        document = make_document()

        result, _session = self.sync(document, make_record())

        self.assertEqual(result['sync_status'], 'updated')
        self.assertIn('title', result['changed_fields'])
        self.assertIn('data_rights', result['changed_fields'])
        self.assertEqual(document.title, 'Title B')
        self.assertEqual(document.extracted_text, 'Evidence must not be changed')
        self.assertEqual(document.processing_status, 'completed')
        self.assertFalse(result['reingestion_required'])

    def test_rights_change_records_snapshot_provenance_without_mutating_evidence(self):
        document = make_document()

        result, _session = self.sync(document, make_record(title='Title A'))

        self.assertTrue(result['metadata_changed'])
        self.assertIn('data_rights', result['changed_fields'])
        self.assertIsNotNone(document.archive_metadata_fetched_at)
        self.assertIsNotNone(document.archive_metadata_snapshot_hash)
        self.assertEqual(document.extracted_text, 'Evidence must not be changed')

    def test_policy_change_reconciles_eligibility_without_reingestion(self):
        document = make_document()

        result, _session = self.sync(document, make_record(title='Title A', use_for_ml=False))

        self.assertTrue(result['policy_changed'])
        self.assertEqual(document.ml_policy_status, 'excluded_use_for_ml_false')
        self.assertEqual(document.use_for_ml, False)
        self.assertFalse(result['reingestion_required'])
        self.assertEqual(document.extracted_text, 'Evidence must not be changed')

    def test_no_upstream_change_is_current_except_for_sync_provenance(self):
        document = make_document()
        record = make_record()
        snapshot = SourceMetadataSyncService._build_snapshot(
            record,
            record['attached_media'][0],
            record['attached_media'][0]['digital_assets'][0],
            {'use_for_ml': True, 'ml_page_scope': 'all_pages', 'ml_policy_status': 'eligible_unrestricted', 'ml_exclusion_reason': None},
        )
        document.authority_data = snapshot
        document.title = 'Title B'
        document.archive_metadata_snapshot_hash = _snapshot_hash(snapshot)

        result, _session = self.sync(document, record)

        self.assertEqual(result['sync_status'], 'current')
        self.assertFalse(result['metadata_changed'])
        self.assertEqual(result['changed_fields'], [])

    def test_asset_change_requires_reingestion_without_running_extraction(self):
        document = make_document()

        result, _session = self.sync(document, make_record(asset_id='asset-2', asset_pid='asset-pid-2'))

        self.assertEqual(result['sync_status'], 'source_asset_changed')
        self.assertTrue(result['source_asset_changed'])
        self.assertTrue(result['reingestion_required'])
        self.assertEqual(document.extracted_text, 'Evidence must not be changed')

    def test_graphql_failure_preserves_existing_metadata(self):
        document = make_document()
        original_metadata = dict(document.authority_data)

        result, _session = self.sync(document, None)

        self.assertEqual(result['sync_status'], 'error')
        self.assertEqual(document.authority_data, original_metadata)
        self.assertIsNotNone(document.metadata_sync_error)


if __name__ == '__main__':
    unittest.main()