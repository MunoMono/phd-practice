import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v3_coverage import TurinRetrievalV3Coverage
from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker
from app.services.turin_retrieval_v34_slots import TurinRetrievalV34Slots


class TurinV34SlotTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = TurinRetrievalV3QuestionAnalyzer()
        self.ranker = TurinRetrievalV3Ranker()

    def scored(self, analysis, chunk_id, text, **extra):
        return self.ranker.score_passage({"chunk_id": chunk_id, "document_id": chunk_id, "asset_id": chunk_id, "chunk_index": 0, "chunk_text": text, **extra}, analysis, v32=True)

    def select(self, analysis, *candidates):
        return TurinRetrievalV3Coverage.select(list(candidates), analysis["required_facets"], 5, "v3.4", analysis)

    def test_exact_person_role_fills_subject_role_relation(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        passage = self.scored(analysis, "role", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.")
        final = self.select(analysis, passage)
        self.assertIn("SUBJECT_ROLE_RELATION", final[0]["filled_slots"])

    def test_co_occurrence_fills_direct_relationship_slot(self):
        analysis = self.analyzer.analyze("How did John Wood and Mary Smith work together?").as_dict()
        passage = self.scored(analysis, "both", "John Wood and Mary Smith worked together on detailed design research and teaching activities recorded in the unit papers.")
        final = self.select(analysis, passage)
        self.assertIn("DIRECT_CO_OCCURRENCE", final[0]["filled_slots"])

    def test_retrospective_interpretation_cannot_fill_explicit_causation(self):
        analysis = self.analyzer.analyze("What caused the unit closure decision?").as_dict()
        retrospective = self.scored(analysis, "retro", "An interview later reflected on the unit closure and discussed its history, people, archives, and institutional setting in detail.", source_type="interview")
        final = self.select(analysis, retrospective)
        self.assertNotIn("EXPLICIT_CAUSAL_STATEMENT", final[0]["filled_slots"])

    def test_strong_passage_can_fill_multiple_slots_once(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        passage = self.scored(analysis, "multi", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.")
        final = self.select(analysis, passage)
        self.assertEqual(len(final), 1)
        self.assertGreaterEqual(len(final[0]["filled_slots"]), 3)

    def test_unfilled_required_slot_lowers_adequacy(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        identity_only = self.scored(analysis, "identity", "John Wood appears in a detailed biographical archive description concerning research papers, meetings, and institutional records from 1974.")
        final = self.select(analysis, identity_only)
        adequacy = TurinRetrievalV3Coverage.adequacy(final, analysis)
        self.assertEqual(adequacy["status"], "RETRIEVAL_PARTIAL")
        self.assertIn("SUBJECT_ROLE_RELATION", adequacy["unfilled_required_slots"])

    def test_optional_slot_does_not_add_irrelevant_padding(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        relevant = self.scored(analysis, "role", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.")
        irrelevant = self.scored(analysis, "image", "<!-- image -->")
        self.assertEqual(len(self.select(analysis, relevant, irrelevant)), 1)

    def test_evidence_set_can_contain_fewer_than_five_passages(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        passage = self.scored(analysis, "role", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.")
        self.assertLess(len(self.select(analysis, passage)), 5)

    def test_source_diversity_cannot_replace_required_evidence(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        exact = self.scored(analysis, "exact", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.", source_type="report")
        generic = self.scored(analysis, "generic", "A lengthy calendar discusses institutional research, education, policy, archives, and meetings throughout the academic year in substantial detail.", source_type="calendar")
        final = self.select(analysis, generic, exact)
        self.assertEqual(final[0]["chunk_id"], "exact")

    def test_graph_signals_do_not_change_slots_or_passage_score(self):
        analysis = self.analyzer.analyze("What teaching role did John Wood have in 1974?").as_dict()
        base = self.scored(analysis, "base", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.")
        graph = self.scored(analysis, "graph", "In 1974 John Wood taught design workshops for postgraduate students, with detailed course notes and responsibilities.", source_signals={"authority_graph_score": 1}, authority_graph_signals={"authority_edge_count": 99})
        self.assertEqual(base["passage_score"], graph["passage_score"])
        self.assertEqual(TurinRetrievalV34Slots.match(base, analysis)["eligible_slots"], TurinRetrievalV34Slots.match(graph, analysis)["eligible_slots"])


if __name__ == "__main__":
    unittest.main()
