import sys
import unittest
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v36_semantic_reranker import TurinRetrievalV36SemanticReranker


class FakeEmbeddingModel:
    def encode(self, values, **kwargs):
        if isinstance(values, str):
            return np.asarray([1.0, 0.0], dtype=np.float32)
        return np.asarray([[1.0, 0.0] for _ in values], dtype=np.float32)


class TurinV36SemanticTests(unittest.TestCase):
    def setUp(self):
        self.reranker = TurinRetrievalV36SemanticReranker()
        self.reranker._model = FakeEmbeddingModel()
        self.reranker.cache = {}

    @staticmethod
    def candidate(index, chunk_id=None, asset_id=None, adequacy="PASSAGE_STRONG"):
        return {"chunk_id": chunk_id or f"chunk-{index}", "document_id": f"document-{index}", "canonical_asset_id": asset_id or f"asset-{index}", "chunk_index": index, "chunk_text": f"Documentary text {index} provides adequate provenance-valid evidence for semantic scoring.", "passage_score": float(index), "passage_adequacy": adequacy}

    def test_complete_v32_top_three_union_is_not_capped(self):
        candidates = [self.candidate(index) for index in range(180)]
        result = self.reranker.rerank("research question", candidates)
        self.assertEqual(result["candidate_count_before_deduplication"], 180)
        self.assertEqual(result["candidate_count_after_deduplication"], 180)

    def test_final_evidence_preserves_canonical_source_uniqueness(self):
        candidates = [self.candidate(1, "first", "asset"), self.candidate(2, "second", "asset"), self.candidate(3, "third", "other")]
        result = self.reranker.rerank("research question", candidates)
        self.assertEqual(len(result["final"]), 2)

    def test_duplicate_chunk_ids_are_deduplicated_before_scoring(self):
        result = self.reranker.rerank("research question", [self.candidate(1, "same"), self.candidate(2, "same")])
        self.assertEqual(result["candidate_count_before_deduplication"], 2)
        self.assertEqual(result["candidate_count_after_deduplication"], 1)


if __name__ == "__main__":
    unittest.main()
