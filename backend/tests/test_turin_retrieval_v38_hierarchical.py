import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v38_hierarchical import TurinRetrievalV38Hierarchical


class TurinV38HierarchicalTests(unittest.TestCase):
    @staticmethod
    def passage(chunk_id, asset_id, score, adequacy="PASSAGE_STRONG", facets=None, core=1, relation=1, family=None):
        return {"chunk_id": chunk_id, "document_id": asset_id, "canonical_asset_id": asset_id, "asset_id": asset_id, "asset_pid": family or asset_id, "chunk_index": 0, "chunk_text": "Documentary evidence.", "passage_score": score, "passage_adequacy": adequacy, "facet_coverage": facets or ["PERSON_A", "ACTIVITY"], "passage_score_components": {"core_facets_present": core, "raw_relation_term_match": relation, "raw_exact_entity_match": 1, "raw_temporal_match": 0}, "source_signals": {"authority_graph_score": 99}, "authority_graph_signals": {"authority_edge_count": 99}, "lane_nominations": [{"lane": "authority_graph", "score": 99}]}

    def test_documentary_strength_beats_graph_nominated_weak_source(self):
        weak = self.passage("weak", "weak", 1, adequacy="PASSAGE_WEAK", facets=[], core=0, relation=0)
        strong = self.passage("strong", "strong", 5)
        result = TurinRetrievalV38Hierarchical.build([weak, strong], ["PERSON_A", "ACTIVITY"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["canonical_asset_id"], "strong")
        self.assertEqual(result["source_profiles"][0]["source_nomination"]["authority_graph_signals"]["authority_edge_count"], 99)

    def test_second_passage_requires_new_documentary_facet(self):
        first = self.passage("first", "asset", 5, facets=["PERSON_A", "ACTIVITY"])
        redundant = self.passage("redundant", "asset", 4, facets=["PERSON_A", "ACTIVITY"])
        added = self.passage("added", "asset", 3, adequacy="PASSAGE_PARTIAL", facets=["TEMPORAL"])
        result = TurinRetrievalV38Hierarchical.build([first, redundant, added], ["PERSON_A", "ACTIVITY"])
        self.assertEqual([item["chunk_id"] for item in result["evidence_bundles"][0]["documentary_evidence"]], ["first", "added"])

    def test_sibling_is_suppressed_without_principal_facet(self):
        first = self.passage("first", "asset-a", 5, family="family")
        sibling = self.passage("sibling", "asset-b", 4, family="family")
        result = TurinRetrievalV38Hierarchical.build([first, sibling], ["PERSON_A", "ACTIVITY"])
        self.assertEqual(len(result["evidence_bundles"]), 1)
        sibling_profile = next(item for item in result["source_profiles"] if item["canonical_asset_id"] == "asset-b")
        self.assertEqual(sibling_profile["selection_status"], "SIBLING_SOURCE_SUPPRESSED")

    def test_irrelevant_source_is_retained_only_in_diagnostics(self):
        irrelevant = self.passage("image", "asset", -5, adequacy="PASSAGE_IRRELEVANT", facets=[], core=0, relation=0)
        result = TurinRetrievalV38Hierarchical.build([irrelevant], ["PERSON_A"])
        self.assertEqual(result["evidence_bundles"], [])
        self.assertEqual(result["source_profiles"][0]["selection_status"], "NOMINATED_BUT_DOCUMENTARY_SUPPORT_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
