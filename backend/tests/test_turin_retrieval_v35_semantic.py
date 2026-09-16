import sys
import unittest
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v35_semantic_reranker import TurinRetrievalV35SemanticReranker


class FakeEmbeddingModel:
    def encode(self, values, **kwargs):
        if isinstance(values, str):
            return np.asarray([1.0, 0.0] if "exact" in values.lower() else [0.0, 1.0], dtype=np.float32)
        return np.asarray([[1.0, 0.0] if "exact" in value.lower() else [0.0, 1.0] for value in values], dtype=np.float32)


class TurinV35SemanticTests(unittest.TestCase):
    def setUp(self):
        self.reranker = TurinRetrievalV35SemanticReranker()
        self.reranker._model = FakeEmbeddingModel()
        self.reranker.configuration["embedding_dimension"] = 2
        self.reranker._cache = {}

    @staticmethod
    def candidate(chunk_id, text, asset_id=None, adequacy="PASSAGE_STRONG", **extra):
        return {"chunk_id": chunk_id, "document_id": chunk_id, "canonical_asset_id": asset_id or chunk_id, "chunk_index": 0, "chunk_text": text, "passage_score": 1.0, "passage_adequacy": adequacy, **extra}

    def test_metadata_cannot_change_documentary_embedding_score(self):
        first = self.candidate("first", "Exact documentary relationship text with enough provenance-preserving content for scoring.", title="Unrelated title", authority_graph_signals={"authority_edge_count": 0})
        second = self.candidate("second", "Exact documentary relationship text with enough provenance-preserving content for scoring.", title="Misleading graph title", authority_graph_signals={"authority_edge_count": 99})
        result = self.reranker.rerank("exact question", [first, second])
        scores = {item["chunk_id"]: item["semantic_similarity"] for item in result["candidate_pool"]}
        self.assertEqual(scores["first"], scores["second"])

    def test_empty_fts_documentary_chunk_is_semantically_scored(self):
        candidate = self.candidate("empty", "Exact documentary relationship text with enough provenance-preserving content for scoring.", search_tsv="")
        result = self.reranker.rerank("exact question", [candidate])
        self.assertEqual(result["candidate_pool"][0]["chunk_id"], "empty")

    def test_same_canonical_source_cannot_flood_final_set(self):
        first = self.candidate("first", "Exact documentary relationship text with enough provenance-preserving content for scoring.", asset_id="asset")
        second = self.candidate("second", "Exact documentary relationship text with enough provenance-preserving content for scoring.", asset_id="asset")
        third = self.candidate("third", "Generic documentary relationship text with enough provenance-preserving content for scoring.", asset_id="other")
        self.assertEqual(len(self.reranker.rerank("exact question", [first, second, third])["semantic_only"]), 2)

    def test_irrelevant_passage_is_not_final_padding(self):
        relevant = self.candidate("relevant", "Exact documentary relationship text with enough provenance-preserving content for scoring.")
        irrelevant = self.candidate("irrelevant", "Image marker only.", adequacy="PASSAGE_IRRELEVANT")
        final = self.reranker.rerank("exact question", [relevant, irrelevant])["rrf"]
        self.assertEqual([item["chunk_id"] for item in final], ["relevant"])


if __name__ == "__main__":
    unittest.main()
