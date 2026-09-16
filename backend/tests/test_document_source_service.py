import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.document_source_service import (
    build_document_annotations_payload,
    build_document_detail_payload,
    build_document_list_payload,
    is_asset_granular_document,
    select_source_documents,
)


class DocumentSourceSelectionTests(unittest.TestCase):
    def test_prefers_asset_granular_rows_when_present(self):
        legacy = SimpleNamespace(
            document_id='doc_pid_014262507600',
            pid='014262507600',
            asset_id=None,
            asset_pid=None,
            asset_id_or_asset_pid=None,
            source_uri=None,
        )
        enriched = SimpleNamespace(
            document_id='doc_287080879712_65e55d098336',
            pid='287080879712',
            archive_record_pid='014262507600',
            asset_id='asset-1',
            asset_pid='942396101474',
            asset_id_or_asset_pid='asset-1',
            source_uri='https://archive.test/asset.pdf',
        )

        self.assertFalse(is_asset_granular_document(legacy))
        self.assertTrue(is_asset_granular_document(enriched))
        self.assertEqual(select_source_documents([legacy, enriched]), [enriched])

    def test_keeps_unrelated_legacy_rows_alongside_asset_rows(self):
        legacy_without_asset = SimpleNamespace(
            document_id='doc_pid_999',
            pid='999',
            metadata_source=None,
            archive_record_pid=None,
            asset_id=None,
            asset_pid=None,
            asset_id_or_asset_pid=None,
            source_uri=None,
        )
        legacy_with_asset = SimpleNamespace(
            document_id='doc_pid_014262507600',
            pid='014262507600',
            metadata_source=None,
            archive_record_pid=None,
            asset_id=None,
            asset_pid=None,
            asset_id_or_asset_pid=None,
            source_uri=None,
        )
        enriched = SimpleNamespace(
            document_id='doc_287080879712_65e55d098336',
            pid='287080879712',
            metadata_source=None,
            archive_record_pid='014262507600',
            asset_id='asset-1',
            asset_pid='942396101474',
            asset_id_or_asset_pid='asset-1',
            source_uri='https://archive.test/asset.pdf',
        )

        self.assertEqual(select_source_documents([legacy_without_asset, legacy_with_asset, enriched]), [legacy_without_asset, enriched])

    def test_prefers_inventory_backed_rows_over_legacy_rows(self):
        legacy = SimpleNamespace(
            document_id='doc_legacy',
            pid='legacy-pid',
            metadata_source=None,
            archive_record_pid=None,
            asset_id=None,
            asset_pid=None,
            asset_id_or_asset_pid=None,
            source_uri=None,
        )
        inventory_row = SimpleNamespace(
            document_id='doc_inventory',
            pid='media-pid',
            metadata_source='archive_graphql.records_v1',
            archive_record_pid='record-pid',
            asset_id='asset-1',
            asset_pid='asset-pid-1',
            asset_id_or_asset_pid='asset-1',
            source_uri='https://archive.test/asset.pdf',
        )

        self.assertEqual(select_source_documents([legacy, inventory_row]), [inventory_row])

    def test_keeps_legacy_rows_when_no_asset_rows_exist(self):
        legacy = SimpleNamespace(
            document_id='doc_pid_014262507600',
            pid='014262507600',
            asset_id=None,
            asset_pid=None,
            asset_id_or_asset_pid=None,
            source_uri=None,
        )

        self.assertEqual(select_source_documents([legacy]), [legacy])


class DocumentPayloadTests(unittest.TestCase):
    def test_annotations_preserve_asset_policy_and_roles(self):
        document = SimpleNamespace(
            document_id='doc_287080879712_65e55d098336',
            pid='287080879712',
            authority_id='149',
            archive_record_id='155',
            archive_record_pid='014262507600',
            asset_id='1b843',
            asset_pid='942396101474',
            asset_id_or_asset_pid='1b843',
            title='Ken Baynes memorandum',
            publication_year=1978,
            filename='1b843.pdf',
            source_uri='https://archive.test/1b843.pdf',
            page_count=23,
            ingestion_version='turin-phase2a-archive-inventory-v1',
            corpus_version='corpus_123',
            archive_metadata_source='ddr_graphql.record_v1',
            metadata_sync_status='current',
            processing_status='excluded_use_for_ml_false',
            ml_policy_status='excluded_use_for_ml_false',
            ml_exclusion_reason='asset_marked_use_for_ml_false',
            use_for_ml=0,
            ml_page_scope=None,
            ml_processed_at=None,
            has_diagrams=0,
            created_at=SimpleNamespace(isoformat=lambda: '2026-08-07T00:00:00Z'),
            authority_data={
                'pid': '287080879712',
                'record_pid': '014262507600',
                'asset_id': '1b843',
                'asset_pid': '942396101474',
                'asset_id_or_asset_pid': '1b843',
                'title': 'Ken Baynes memorandum',
                'source_filename': '1b843.pdf',
                'source_uri': 'https://archive.test/1b843.pdf',
                'archive_reference': 'DEU/2',
                'location_accession': 'AU.AAD.20718',
                'location_note': 'AAD/1989/9 Part 2 of 3',
                'location_repository': 'VAE',
                'data_rights': 'Royal College of Art',
                'data_rights_holder': 'Royal College of Art',
                'image_rights': 'Royal College of Art',
                'image_rights_holder': 'Royal College of Art',
                'copyright_holder': 'Copyright © Royal College of Art',
                'keywords': ['Bruce Archer', 'Product development'],
                'date_qualifier': 'Circa',
                'language_codes': 'en-GB',
                'extent_unit': 'ITEM',
                'caption': 'Signed memo',
                'use_for_ml': False,
                'ml_policy_status': 'excluded_use_for_ml_false',
                'ml_exclusion_reason': 'asset_marked_use_for_ml_false',
                'metadata_roles_version': 'turin-phase2-metadata-v1',
                'record_public_uri': 'https://ddrarchive.org/id/record/014262507600',
            },
        )

        annotations = build_document_annotations_payload(document)
        detail = build_document_detail_payload(document)
        list_item = build_document_list_payload(document)

        self.assertEqual(annotations['attached_media_pid'], '287080879712')
        self.assertEqual(annotations['archive_resolution_status'], 'archive_resolved_current')
        self.assertEqual(annotations['asset_pid'], '942396101474')
        self.assertEqual(annotations['ml_policy_status'], 'excluded_use_for_ml_false')
        self.assertEqual(annotations['corpus_control']['ml_exclusion_reason'], 'asset_marked_use_for_ml_false')
        self.assertEqual(annotations['rights_access']['data_rights'], 'Royal College of Art')
        self.assertEqual(annotations['rights_access']['copyright_holder'], 'Copyright © Royal College of Art')
        self.assertEqual(annotations['retrieval_provenance']['accession_shelfmark'], 'AU.AAD.20718')
        self.assertEqual(annotations['retrieval_provenance']['location_note'], 'AAD/1989/9 Part 2 of 3')
        self.assertEqual(annotations['catalogue_metadata']['keywords'], ['Bruce Archer', 'Product development'])
        self.assertEqual(annotations['catalogue_metadata']['date_qualifier'], 'Circa')
        self.assertEqual(annotations['catalogue_metadata']['language'], 'en-GB')
        self.assertEqual(annotations['catalogue_metadata']['caption'], 'Signed memo')
        self.assertEqual(annotations['persistence']['metadata_roles_version'], 'turin-phase2-metadata-v1')
        self.assertEqual(detail['attached_media_pid'], '287080879712')
        self.assertEqual(detail['archive_resolution_status'], 'archive_resolved_current')
        self.assertEqual(detail['rights_access'], annotations['rights_access'])
        self.assertEqual(detail['retrieval_provenance'], annotations['retrieval_provenance'])
        self.assertEqual(detail['catalogue_metadata'], annotations['catalogue_metadata'])
        self.assertEqual(detail['corpus_control'], annotations['corpus_control'])
        self.assertEqual(detail['page_count_source'], 'persisted_document')
        self.assertEqual(list_item['used_for_ml'], False)
        self.assertEqual(list_item['archive_resolution_status'], 'archive_resolved_current')
        self.assertEqual(list_item['metadata_roles_version'], 'turin-phase2-metadata-v1')

    def test_detail_preserves_accession_box_null_semantics(self):
        document = SimpleNamespace(
            document_id='doc_loc_1',
            pid='287080879712',
            authority_id='149',
            archive_record_id='155',
            archive_record_pid='014262507600',
            asset_id='1b843',
            asset_pid='942396101474',
            asset_id_or_asset_pid='1b843',
            title='Ken Baynes memorandum',
            publication_year=1978,
            filename='1b843.pdf',
            source_uri='https://archive.test/1b843.pdf',
            page_count=None,
            ingestion_version='turin-phase2a-archive-inventory-v1',
            corpus_version='corpus_123',
            processing_status='completed',
            ml_policy_status='eligible_unrestricted',
            ml_exclusion_reason=None,
            use_for_ml=1,
            ml_page_scope='all_pages',
            ml_processed_at=None,
            has_diagrams=0,
            created_at=SimpleNamespace(isoformat=lambda: '2026-08-07T00:00:00Z'),
            authority_data={
                'pid': '287080879712',
                'record_pid': '014262507600',
                'asset_id': '1b843',
                'asset_pid': '942396101474',
                'asset_id_or_asset_pid': '1b843',
                'title': 'Ken Baynes memorandum',
                'location_repository': 'V&A East Storehouse Art and Design Archives',
                'location_accession': 'AU.AAD.20718',
                'location_box': None,
                'location_note': 'AAD/1989/9 Part 2 of 3',
                'use_for_ml': True,
                'ml_page_scope': 'all_pages',
                'metadata_roles_version': 'turin-phase2-metadata-v2',
            },
        )

        detail = build_document_detail_payload(document)
        self.assertEqual(detail['retrieval_provenance']['repository'], 'V&A East Storehouse Art and Design Archives')
        self.assertEqual(detail['retrieval_provenance']['accession_shelfmark'], 'AU.AAD.20718')
        self.assertNotIn('box_number', detail['retrieval_provenance'])

    def test_detail_and_annotations_match_relevant_metadata_fields(self):
        document = SimpleNamespace(
            document_id='doc_338541406157_72774d03522b',
            pid='338541406157',
            authority_id='120',
            archive_record_id='127',
            archive_record_pid='873981573030',
            asset_id='cf66faa2e693ca4c11712fcfeca4544a8b1922f5e1f1841ce7d5afeb5df94e4a',
            asset_pid='987235129265',
            asset_id_or_asset_pid='cf66faa2e693ca4c11712fcfeca4544a8b1922f5e1f1841ce7d5afeb5df94e4a',
            title="Overhead transparency of Bruce Archer’s Fig. 5 taxonomy diagram for 'Time for a revolution in art and design education'",
            publication_year=1978,
            filename='cf66faa2e693ca4c11712fcfeca4544a8b1922f5e1f1841ce7d5afeb5df94e4a.pdf',
            source_uri='https://archive.test/cf66faa2.pdf',
            page_count=None,
            ingestion_version='turin-phase2a-archive-inventory-v1',
            corpus_version='corpus_123',
            processing_status='completed',
            ml_policy_status='eligible_unrestricted',
            ml_exclusion_reason=None,
            use_for_ml=1,
            ml_page_scope='all_pages',
            ml_processed_at=None,
            has_diagrams=0,
            created_at=SimpleNamespace(isoformat=lambda: '2026-08-07T00:00:00Z'),
            authority_data={
                'pid': '338541406157',
                'record_pid': '873981573030',
                'record_id': '127',
                'asset_id': 'cf66faa2e693ca4c11712fcfeca4544a8b1922f5e1f1841ce7d5afeb5df94e4a',
                'asset_pid': '987235129265',
                'asset_id_or_asset_pid': 'cf66faa2e693ca4c11712fcfeca4544a8b1922f5e1f1841ce7d5afeb5df94e4a',
                'title': "Overhead transparency of Bruce Archer’s Fig. 5 taxonomy diagram for 'Time for a revolution in art and design education'",
                'caption': "Overhead transparency of Bruce Archer’s Fig. 5 taxonomy diagram for 'Time for a revolution in art and design education'",
                'location_repository': 'V&A East Storehouse Art and Design Archives',
                'location_accession': None,
                'location_box': 'AU.AAD.20718',
                'location_note': "AAD/1989/9 Part 2 of 3 Incomplete collection of students' theses, conference proceedings, policy papers & Bruce Archer's Lecture Notes (1961-1982)",
                'rights_owner': 'RCA',
                'copyright_holder': 'Copyright © Royal College of Art',
                'data_rights': 'Royal College of Art',
                'image_rights': 'Royal College of Art',
                'rights_statement_uri': 'https://rightsstatements.org/vocab/InC-EDU/1.0/',
                'takedown_contact': 'graham.newman@network.rca.ac.uk',
                'keywords': ['Overhead transparency', 'Taxonomy diagram'],
                'date_text': 'Unknown',
                'date_qualifier': 'Unknown',
                'date_unknown': True,
                'language_codes': 'en-GB',
                'extent_unit': 'Item',
                'use_for_ml': True,
                'ml_pages': '',
                'ml_page_scope': 'all_pages',
                'record_public_uri': 'https://ddrarchive.org/id/record/873981573030',
                'metadata_roles_version': 'turin-phase2-metadata-v2',
            },
        )

        detail = build_document_detail_payload(document)
        annotations = build_document_annotations_payload(document)

        self.assertEqual(detail['archive_record_pid'], annotations['archive_record_pid'])
        self.assertEqual(detail['attached_media_pid'], annotations['attached_media_pid'])
        self.assertEqual(detail['asset_pid'], annotations['asset_pid'])
        self.assertEqual(detail['asset_id'], annotations['asset_id'])
        self.assertEqual(detail['ml_policy_status'], annotations['ml_policy_status'])
        self.assertEqual(detail['ml_page_scope'], annotations['ml_page_scope'])
        self.assertEqual(detail['retrieval_provenance'], annotations['retrieval_provenance'])
        self.assertEqual(detail['rights_access'], annotations['rights_access'])
        self.assertEqual(detail['catalogue_metadata'], annotations['catalogue_metadata'])
        self.assertEqual(detail['page_count'], annotations['page_count'])
        self.assertEqual(detail['page_count_source'], annotations['page_count_source'])


    def test_annotations_are_null_safe_for_legacy_rows(self):
        legacy = SimpleNamespace(
            document_id='doc_pid_014262507600',
            pid='014262507600',
            authority_id=None,
            archive_record_id=None,
            archive_record_pid=None,
            asset_id=None,
            asset_pid=None,
            asset_id_or_asset_pid=None,
            title='Design Education Unit | DEU',
            publication_year=1970,
            filename='014262507600.pdf',
            source_uri=None,
            page_count=None,
            ingestion_version=None,
            corpus_version=None,
            processing_status='pending',
            ml_policy_status=None,
            ml_exclusion_reason=None,
            use_for_ml=None,
            ml_page_scope=None,
            ml_processed_at=None,
            has_diagrams=0,
            created_at=SimpleNamespace(isoformat=lambda: '2026-08-07T00:00:00Z'),
            authority_data={},
        )

        annotations = build_document_annotations_payload(legacy)
        self.assertIsNone(annotations['asset_pid'])
        self.assertEqual(annotations['rights_access'], {})
        self.assertEqual(annotations['retrieval_provenance'], {})
        self.assertEqual(annotations['catalogue_metadata'], {})
        self.assertIsNone(annotations['persistence']['metadata_roles_version'])
        detail = build_document_detail_payload(legacy)
        self.assertEqual(detail['rights_access'], {})
        self.assertEqual(detail['retrieval_provenance'], {})
        self.assertEqual(detail['catalogue_metadata'], {})


if __name__ == '__main__':
    unittest.main()