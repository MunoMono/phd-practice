import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.retrieval_validation_service import (
    QueryExpansion,
    RetrievalValidationRequest,
    RetrievalValidationService,
    build_query_transparency,
    build_retrieval_diagnostics,
)


def make_row(*, chunk_id='chunk-1', document_id='doc-1', score=0.5, resolved=True, text='Design research evidence'):
    return {
        'chunk_id': chunk_id,
        'document_id': document_id,
        'chunk_text': text,
        'chunk_index': 1,
        'chunk_type': 'paragraph',
        'source_page': 2,
        'source_section': 'Methods',
        'chunk_metadata': {},
        'pid': 'media-1',
        'title': 'A design research note',
        'filename': 'note.pdf',
        'authority_id': 'media-id' if resolved else None,
        'authority_data': {'creator_agent_label': 'Ken Baynes'},
        'archive_record_id': 'record-id' if resolved else None,
        'archive_record_pid': 'record-pid' if resolved else None,
        'asset_id': 'asset-id' if resolved else None,
        'asset_pid': 'asset-pid' if resolved else None,
        'asset_id_or_asset_pid': 'asset-id' if resolved else None,
        'source_uri': 'https://archive.example/note.pdf' if resolved else None,
        'archive_metadata_source': 'ddr_graphql.record_v1' if resolved else None,
        'metadata_sync_status': 'current' if resolved else 'error',
        'corpus_version': 'corpus-test-v1',
        'score': score,
    }


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class FakeDatabase:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        return FakeResult(self.rows)


class RetrievalValidationServiceTests(unittest.TestCase):
    def test_retrieval_preserves_rank_order_and_top_k(self):
        database = FakeDatabase([
            make_row(chunk_id='chunk-high', score=0.9),
            make_row(chunk_id='chunk-low', document_id='doc-2', score=0.2),
        ])
        request = RetrievalValidationRequest(query='design research', top_k=2)

        payload = RetrievalValidationService().retrieve(database, request)

        self.assertEqual([result['rank'] for result in payload['results']], [1, 2])
        self.assertEqual([result['score'] for result in payload['results']], [0.9, 0.2])
        self.assertEqual(database.calls[-1][1]['limit'], 2)
        self.assertIn('ORDER BY score DESC, dc.chunk_id ASC', database.calls[-1][0])

    def test_query_transparency_records_controlled_expansion(self):
        request = RetrievalValidationRequest(
            query='  Design   Education Unit ',
            top_k=3,
            expansions=[QueryExpansion(value='DEU', source='researcher_supplied')],
        )

        transparency = build_query_transparency(request)

        self.assertEqual(transparency['normalised_query'], 'Design Education Unit')
        self.assertEqual(transparency['expanded_query'], 'Design Education Unit OR DEU')
        self.assertEqual(transparency['query_expansions'], ['DEU'])
        self.assertEqual(transparency['expansion_sources'][0]['source'], 'researcher_supplied')

    def test_retrieval_filters_to_explicit_corpus_version(self):
        request = RetrievalValidationRequest(query='design research', corpus_version='corpus_turin_pilot')

        RetrievalValidationService().retrieve(FakeDatabase([make_row()]), request)

        database = FakeDatabase([make_row()])
        RetrievalValidationService().retrieve(database, request)
        statement, params = database.calls[-1]
        self.assertIn('dc.corpus_version = :corpus_version', statement)
        self.assertEqual(params['corpus_version'], 'corpus_turin_pilot')

    def test_result_keeps_catalogue_metadata_separate_from_source_text(self):
        result = RetrievalValidationService()._result_from_row(make_row(), 1)

        self.assertEqual(result['text'], 'Design research evidence')
        self.assertEqual(result['catalogue_metadata']['creator'], 'Ken Baynes')
        self.assertNotIn('creator', result['provenance'])
        self.assertEqual(result['archive_resolution_status'], 'archive_resolved_current')
        self.assertEqual(result['archive_record_pid'], 'record-pid')

    def test_unresolved_result_has_no_invented_archive_provenance(self):
        result = RetrievalValidationService()._result_from_row(make_row(resolved=False), 1)

        self.assertEqual(result['archive_resolution_status'], 'unresolved_legacy')
        self.assertIsNone(result['archive_record_pid'])
        self.assertEqual(result['provenance'], {})
        self.assertEqual(result['rights_access'], {})

    def test_zero_result_diagnostics_describe_retrieval_scope_only(self):
        diagnostics = build_retrieval_diagnostics([])

        self.assertEqual(diagnostics['result_count'], 0)
        self.assertTrue(diagnostics['possible_low_recall'])
        self.assertIn('retrieval-scope result', diagnostics['notes'][0])
        self.assertIn('not evidence of historical absence', diagnostics['notes'][0])

    def test_concentrated_results_are_flagged(self):
        service = RetrievalValidationService()
        results = [
            service._result_from_row(make_row(chunk_id='chunk-1'), 1),
            service._result_from_row(make_row(chunk_id='chunk-2'), 2),
            service._result_from_row(make_row(chunk_id='chunk-3'), 3),
            service._result_from_row(make_row(chunk_id='chunk-4', document_id='doc-2'), 4),
        ]

        diagnostics = build_retrieval_diagnostics(results)

        self.assertTrue(diagnostics['evidence_concentration'])
        self.assertTrue(diagnostics['retrieval_redundancy'])

    def test_authority_expansion_requires_complete_explicit_current_identity(self):
        request = RetrievalValidationRequest(
            query='design',
            expansions=[QueryExpansion(value='method', authority_source='DDR', authority_field='label')],
        )

        with self.assertRaisesRegex(ValueError, 'requires source, field, role, and resolved document identity'):
            RetrievalValidationService().retrieve(FakeDatabase([]), request)

    def test_authority_expansion_logs_explicit_source_and_role(self):
        request = RetrievalValidationRequest(
            query='design',
            expansions=[
                QueryExpansion(
                    value='methodology',
                    source='database_authority',
                    authority_source='ref_methodology',
                    authority_field='label',
                    authority_role='controlled_query_expansion',
                    authority_document_id='doc-1',
                )
            ],
        )

        payload = RetrievalValidationService().retrieve(FakeDatabase([make_row()]), request)

        expansion = payload['transparency']['expansion_sources'][0]
        self.assertEqual(expansion['authority_source'], 'ref_methodology')
        self.assertEqual(expansion['authority_role'], 'controlled_query_expansion')

    def test_project_authority_expansion_requires_resolved_project_record(self):
        expansion = QueryExpansion(
            value='METHOD building',
            source='database_authority',
            authority_source='database_authorities.ddr_projects',
            authority_id='97',
            authority_field='title',
            authority_role='controlled_query_expansion',
        )

        RetrievalValidationService()._validate_expansions(FakeDatabase([{'authority_id': '97'}]), [expansion])