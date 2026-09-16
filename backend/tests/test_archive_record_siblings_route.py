import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.search import find_archive_record_siblings


class FakeResult:
    def __init__(self, *, one=None, many=None):
        self.one = one
        self.many = many or []

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeSession:
    def __init__(self, source, siblings):
        self.source = source
        self.siblings = siblings
        self.statements = []
        self.closed = False

    def execute(self, statement, parameters):
        self.statements.append((str(statement), parameters))
        if len(self.statements) == 1:
            return FakeResult(one=self.source)
        return FakeResult(many=self.siblings)

    def close(self):
        self.closed = True


def sibling(document_id, year, title="Rector's report", asset_pid=None, source_uri=None, used_for_ml=True):
    return SimpleNamespace(
        document_id=document_id,
        title=title,
        publication_year=year,
        attached_media_pid='521129471965',
        archive_record_pid='788065484899',
        asset_pid=asset_pid or f'asset-{document_id}',
        source_uri=source_uri or f'https://archive.test/{document_id}.pdf',
        archive_record_title="RCA Rector's reports | 1967-85",
        use_for_ml=used_for_ml,
        ml_policy_status='eligible_page_restricted' if used_for_ml else 'excluded_use_for_ml_false',
    )


class ArchiveRecordSiblingRouteTests(unittest.TestCase):
    def call_route(self, source, siblings):
        session = FakeSession(source, siblings)
        with patch('app.api.routes.search.LocalSessionLocal', return_value=session):
            response = asyncio.run(find_archive_record_siblings(source.document_id))
        return response, session

    def test_rectors_report_returns_ordered_structural_siblings_without_similarity(self):
        source = SimpleNamespace(document_id='rector-1968', archive_record_pid='788065484899')
        siblings = [sibling(f'rector-{year}', year) for year in range(1969, 1984)]

        response, session = self.call_route(source, siblings)

        self.assertEqual(response['metadata'], {'relationship': 'shared_archive_record', 'count': 15})
        self.assertEqual(response['relatedDocuments'][0]['documentId'], 'rector-1969')
        self.assertEqual(response['relatedDocuments'][-1]['documentId'], 'rector-1983')
        self.assertNotIn('similarity', response['relatedDocuments'][0])
        self.assertEqual(response['relatedDocuments'][0]['archiveRecordPid'], '788065484899')
        self.assertNotIn('rector-1968', [row['documentId'] for row in response['relatedDocuments']])
        sibling_query = session.statements[1][0]
        self.assertIn("metadata_source = 'archive_graphql.records_v1'", sibling_query)
        self.assertIn('document_id <> :document_id', sibling_query)
        self.assertIn('PARTITION BY COALESCE', sibling_query)
        self.assertIn('ORDER BY publication_year ASC NULLS LAST, title ASC NULLS LAST, document_id ASC', sibling_query)
        self.assertNotIn('document_similarities', sibling_query)
        self.assertNotIn('embedding', sibling_query.lower())

    def test_calendar_record_keeps_heterogeneous_structural_siblings(self):
        source = SimpleNamespace(document_id='calendar-1965', archive_record_pid='880612075513')
        siblings = [
            sibling('calendar-1966', 1966, 'RCA calendar'),
            sibling('yearbook-1976', 1976, 'RCA yearbook'),
            sibling('prospectus-1983', 1983, 'RCA prospectus', used_for_ml=False),
        ]

        response, _ = self.call_route(source, siblings)

        self.assertEqual([row['title'] for row in response['relatedDocuments']], ['RCA calendar', 'RCA yearbook', 'RCA prospectus'])
        self.assertFalse(response['relatedDocuments'][-1]['usedForMl'])

    def test_no_archive_record_returns_an_explicit_empty_relationship(self):
        source = SimpleNamespace(document_id='unrelated-source', archive_record_pid=None)

        response, session = self.call_route(source, [])

        self.assertEqual(response['relatedDocuments'], [])
        self.assertEqual(response['metadata']['relationship'], 'shared_archive_record')
        self.assertEqual(len(session.statements), 1)