import sys
import unittest
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v37_cross_encoder_reranker import TurinRetrievalV37CrossEncoderReranker


class FakeTokenizer:
    def __call__(self, *values, **kwargs):
        return {"input_ids": list(range(sum(len(value.split()) for value in values)))}


class FakeCrossEncoder:
    def __init__(self):
        self.tokenizer = FakeTokenizer()
        self.pairs = []

    def predict(self, pairs, **kwargs):
        self.pairs = pairs
        return np.asarray([float(index) for index, _ in enumerate(pairs)], dtype=np.float32)


class TurinV37CrossEncoderTests(unittest.TestCase):
    def setUp(self):
        self.reranker = TurinRetrievalV37CrossEncoderReranker()
        self.fake_model = FakeCrossEncoder()
        self.reranker.model = self.fake_model

    @staticmethod
    def candidate(index, asset_id=None, text=None, adequacy="PASSAGE_STRONG"):
        return {"chunk_id": f"chunk-{index}", "document_id": f"document-{index}", "canonical_asset_id": asset_id or f"asset-{index}", "chunk_index": index, "chunk_text": text or f"Documentary passage {index} with provenance-valid content.", "passage_score": float(index), "passage_adequacy": adequacy, "title": "Excluded title", "authority_graph_signals": {"authority_edge_count": 99}}

    def test_cross_encoder_input_is_question_and_documentary_text_only(self):
        candidate = self.candidate(1)
        self.reranker.rerank("Original research question", [candidate])
        self.assertEqual(self.fake_model.pairs, [("Original research question", candidate["chunk_text"])])

    def test_complete_candidate_union_is_not_capped(self):
        result = self.reranker.rerank("Question", [self.candidate(index) for index in range(180)])
        self.assertEqual(result["candidate_count_after_deduplication"], 180)

    def test_final_evidence_is_canonical_source_unique_and_ignores_irrelevant(self):
        candidates = [self.candidate(1, "asset"), self.candidate(2, "asset"), self.candidate(3, "other", adequacy="PASSAGE_IRRELEVANT")]
        final = self.reranker.rerank("Question", candidates)["cross_encoder_final"]
        self.assertEqual([item["chunk_id"] for item in final], ["chunk-1"])

    def test_truncation_is_inspectable(self):
        long_text = "term " * 600
        result = self.reranker.rerank("Question", [self.candidate(1, text=long_text)])
        self.assertTrue(result["candidate_pool"][0]["truncated"])
        self.assertEqual(result["candidate_pool"][0]["original_passage_token_count"], 600)


if __name__ == "__main__":
    unittest.main()
