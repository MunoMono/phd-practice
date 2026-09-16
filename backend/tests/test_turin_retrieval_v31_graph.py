import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v3_coverage import TurinRetrievalV3Coverage
from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker
from app.services.turin_retrieval_v31_authority_graph import TurinRetrievalV31AuthorityGraph


def edge(authority_type, authority_id, label, relation_type, document_id="doc-1", trigger=""):
    return {"relation_id": f"{authority_type}-{authority_id}-{document_id}", "authority_type": authority_type, "authority_id": authority_id, "authority_label": label, "relation_type": relation_type, "document_id": document_id, "trigger_value_raw": trigger or label}


class TurinV31GraphTests(unittest.TestCase):
    def setUp(self):
        self.analyzer = TurinRetrievalV3QuestionAnalyzer()
        self.graph = TurinRetrievalV31AuthorityGraph()

    def test_person_edge_resolves_expected_source(self):
        analysis = self.analyzer.analyze("What did John Wood teach?").as_dict()
        matches = self.graph.resolve(analysis["question"], analysis, [edge("agent_employment", "JOHNWOOD", "John Wood", "PERSON_ASSOCIATED_WITH_SOURCE")])
        self.assertEqual(matches[0]["authority_id"], "JOHNWOOD")
        self.assertEqual(matches[0]["resolution_method"], "exact_normalized_authority_label")

    def test_job_edge_resolves_expected_source(self):
        analysis = self.analyzer.analyze("What survives for Job 171?").as_dict()
        matches = self.graph.resolve(analysis["question"], analysis, [edge("ddr_projects", "171", "Interface project", "PROJECT_SOURCE")])
        self.assertEqual(matches[0]["resolution_method"], "exact_project_identifier")

    def test_collection_edge_resolves_expected_source(self):
        analysis = self.analyzer.analyze("Find Design Education Unit material.").as_dict()
        matches = self.graph.resolve(analysis["question"], analysis, [edge("archive_collection", "deu", "Design Education Unit", "SOURCE_COLLECTION")])
        self.assertEqual(matches[0]["authority_type"], "archive_collection")

    def test_multiple_edges_resolve_once_per_authority(self):
        analysis = self.analyzer.analyze("What did John Wood teach?").as_dict()
        edges = [edge("agent_employment", "JOHNWOOD", "John Wood", "PERSON_ASSOCIATED_WITH_SOURCE", "doc-1"), edge("agent_employment", "JOHNWOOD", "John Wood", "PERSON_ASSOCIATED_WITH_SOURCE", "doc-2")]
        self.assertEqual(len(self.graph.resolve(analysis["question"], analysis, edges)), 1)

    def test_graph_signal_cannot_change_passage_score(self):
        analysis = self.analyzer.analyze("What did John Wood teach?").as_dict()
        base = {"chunk_id": "passage", "document_id": "doc", "chunk_text": "John Wood taught design workshops for postgraduate students in 1974, with substantial course discussion."}
        graph_enriched = {**base, "authority_graph_signals": {"authority_edge_count": 99}, "source_signals": {"authority_graph_score": 1}}
        self.assertEqual(TurinRetrievalV3Ranker.score_passage(base, analysis)["passage_score"], TurinRetrievalV3Ranker.score_passage(graph_enriched, analysis)["passage_score"])

    def test_graph_only_weak_source_is_not_final_evidence(self):
        analysis = self.analyzer.analyze("What did John Wood teach?").as_dict()
        weak = TurinRetrievalV3Ranker.score_passage({"chunk_id": "weak", "document_id": "doc", "asset_id": "asset", "chunk_text": "<!-- image -->", "authority_graph_signals": {"authority_edge_count": 1}}, analysis)
        final = TurinRetrievalV3Coverage.select([item for item in [weak] if not item["passage_quality_exclusions"]], analysis["required_facets"])
        self.assertEqual(final, [])

    def test_empty_vector_chunk_can_be_ranked_by_raw_text(self):
        analysis = self.analyzer.analyze("What did John Wood teach?").as_dict()
        chunk = TurinRetrievalV3Ranker.score_passage({"chunk_id": "empty-vector", "document_id": "doc", "chunk_text": "John Wood taught design workshops for postgraduate students in 1974, with substantial course discussion.", "search_tsv": ""}, analysis)
        self.assertGreater(chunk["passage_score"], 0)


if __name__ == "__main__":
    unittest.main()