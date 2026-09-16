import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker


class TurinV32PassageTests(unittest.TestCase):
    def setUp(self):
        self.ranker = TurinRetrievalV3Ranker()
        self.analysis = TurinRetrievalV3QuestionAnalyzer().analyze("What teaching role did John Wood have in 1974?").as_dict()

    def test_deep_exact_passage_beats_first_generic_chunk(self):
        generic = self.ranker.score_passage({"chunk_id": "first", "chunk_text": "This long report discusses design education, research, projects, archives, institutions, curriculum, policy, and methods over many years."}, self.analysis, v32=True)
        exact = self.ranker.score_passage({"chunk_id": "deep", "chunk_text": "In 1974 John Wood taught design workshops for postgraduate students and explained the teaching programme."}, self.analysis, v32=True)
        self.assertGreater(exact["passage_score"], generic["passage_score"])

    def test_empty_vector_raw_entity_match_can_win(self):
        weak = self.ranker.score_passage({"chunk_id": "weak", "chunk_text": "The report discusses teaching and design across several years."}, self.analysis, v32=True)
        exact = self.ranker.score_passage({"chunk_id": "empty", "search_tsv": "", "chunk_text": "John Wood taught design workshops for students in 1974 with detailed course notes."}, self.analysis, v32=True)
        self.assertEqual(exact["passage_score_components"]["raw_exact_entity_match"], 1)
        self.assertGreater(exact["passage_score"], weak["passage_score"])

    def test_person_activity_proximity_is_inspectable(self):
        close = self.ranker.score_passage({"chunk_id": "close", "chunk_text": "John Wood taught workshops for design students in 1974 with detailed notes."}, self.analysis, v32=True)
        distant = self.ranker.score_passage({"chunk_id": "distant", "chunk_text": "John Wood wrote a biographical note. " + "history " * 40 + "Teaching was later discussed in the report."}, self.analysis, v32=True)
        self.assertLess(close["passage_score_components"]["minimum_token_distance"], distant["passage_score_components"]["minimum_token_distance"])
        self.assertGreater(close["passage_score_components"]["proximity_score"], distant["passage_score_components"]["proximity_score"])

    def test_ocr_hyphenated_text_matches_raw_entity(self):
        scored = self.ranker.score_passage({"chunk_id": "ocr", "chunk_text": "John\u00ad Wood taught the design course for students in 1974."}, self.analysis, v32=True)
        self.assertEqual(scored["passage_score_components"]["raw_exact_entity_match"], 1)


if __name__ == "__main__":
    unittest.main()