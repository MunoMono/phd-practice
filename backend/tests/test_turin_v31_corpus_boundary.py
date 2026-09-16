import os
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v3_service import (
    DOCUMENTARY_CHUNK_CORPUS_PREDICATE,
    SOURCE_NOMINATION_CORPUS_PREDICATE,
    TurinRetrievalV3Service,
)


class _Result:
    def mappings(self):
        return self

    def all(self):
        return []


class _CapturingDatabase:
    def __init__(self):
        self.queries = []

    def execute(self, statement, parameters):
        self.queries.append(str(statement))
        return _Result()


class TurinV31CorpusBoundaryTests(unittest.TestCase):
    def test_source_nomination_requires_represented_document_not_nonempty_fts(self):
        self.assertIn("EXISTS", SOURCE_NOMINATION_CORPUS_PREDICATE)
        self.assertIn("nomination_chunk.document_id = d.document_id", SOURCE_NOMINATION_CORPUS_PREDICATE)
        self.assertNotIn("search_tsv", SOURCE_NOMINATION_CORPUS_PREDICATE)

    def test_documentary_chunk_surface_never_filters_empty_tsvectors(self):
        self.assertIn("dc.corpus_version = :corpus_version", DOCUMENTARY_CHUNK_CORPUS_PREDICATE)
        self.assertNotIn("search_tsv", DOCUMENTARY_CHUNK_CORPUS_PREDICATE)
        database = _CapturingDatabase()
        TurinRetrievalV3Service()._source_rows(database, "governed-document", "corpus_f40d78dbce52")
        self.assertNotIn("search_tsv <> ''::tsvector", database.queries[0])

    def test_metadata_nomination_excludes_zero_chunk_assets_by_exists_only(self):
        database = _CapturingDatabase()
        TurinRetrievalV3Service()._metadata_lane(database, ["Design Education Unit"], "corpus_f40d78dbce52")
        query = database.queries[0]
        self.assertIn("FROM document_chunks nomination_chunk", query)
        self.assertNotIn("nomination_chunk.search_tsv", query)

    @unittest.skipUnless(os.getenv("TURIN_PRODUCTION_DATABASE_URL"), "requires explicit production audit database URL")
    def test_production_frozen_boundary(self):
        engine = create_engine(os.environ["TURIN_PRODUCTION_DATABASE_URL"])
        with engine.connect() as connection:
            result = connection.execute(text("""
                WITH nominated_documents AS (
                    SELECT d.document_id
                    FROM documents d
                    WHERE d.corpus_version = 'corpus_f40d78dbce52'
                      AND d.use_for_ml = 1
                      AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                      AND EXISTS (
                          SELECT 1 FROM document_chunks nomination_chunk
                          WHERE nomination_chunk.document_id = d.document_id
                            AND nomination_chunk.corpus_version = d.corpus_version
                      )
                )
                SELECT
                    (SELECT count(*) FROM nominated_documents) AS formal_documents,
                    (SELECT count(*) FROM document_chunks dc JOIN nominated_documents d USING (document_id)
                     WHERE dc.corpus_version = 'corpus_f40d78dbce52') AS formal_chunks,
                    (SELECT count(*) FROM document_chunks dc JOIN nominated_documents d USING (document_id)
                     WHERE dc.corpus_version = 'corpus_f40d78dbce52' AND dc.search_tsv IS NULL) AS null_fts_vectors,
                    (SELECT count(*) FROM document_chunks dc LEFT JOIN documents d
                     ON d.document_id = dc.document_id AND d.corpus_version = dc.corpus_version
                     WHERE dc.corpus_version = 'corpus_f40d78dbce52' AND d.document_id IS NULL) AS orphans,
                    (SELECT count(*) FROM documents d
                     WHERE d.corpus_version = 'corpus_f40d78dbce52'
                       AND d.use_for_ml = 1
                       AND d.ml_policy_status IN ('eligible_unrestricted', 'eligible_page_restricted')
                       AND NOT EXISTS (SELECT 1 FROM document_chunks dc WHERE dc.document_id = d.document_id
                                       AND dc.corpus_version = d.corpus_version)) AS zero_chunk_eligible_assets
            """)).mappings().one()
        self.assertEqual(result["formal_documents"], 95)
        self.assertEqual(result["formal_chunks"], 12884)
        self.assertEqual(result["null_fts_vectors"], 0)
        self.assertEqual(result["orphans"], 0)
        self.assertEqual(result["zero_chunk_eligible_assets"], 2)


if __name__ == "__main__":
    unittest.main()