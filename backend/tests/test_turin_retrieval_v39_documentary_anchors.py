import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.turin_retrieval_v39_documentary_anchors import TurinRetrievalV39DocumentaryAnchors


class TurinV39DocumentaryAnchorTests(unittest.TestCase):
    @staticmethod
    def passage(chunk_id, asset_pid, score, adequacy="PASSAGE_STRONG", facets=None):
        return {"chunk_id": chunk_id, "document_id": f"document-{asset_pid}", "canonical_asset_id": f"asset-{asset_pid}", "asset_pid": asset_pid, "chunk_index": 0, "chunk_text": "Bruce Archer documentary record", "passage_score": score, "passage_adequacy": adequacy, "facet_coverage": facets or ["PERSON_A"], "passage_score_components": {"core_facets_present": 1, "raw_exact_entity_match": 1, "raw_relation_term_match": 0, "raw_phrase_match": 0, "proximity_score": 0.0}, "source_signals": {"authority_graph_score": 0.5}}

    def test_explicit_asset_gate_protects_documentary_anchor(self):
        target = self.passage("target", "123", 5.5)
        generic = self.passage("generic", "456", 8.0)
        result = TurinRetrievalV39DocumentaryAnchors.build([generic, target], "Find documentary material naming Bruce Archer in archival asset 123.", ["PERSON_A"])
        self.assertEqual([bundle["source"]["asset_pid"] for bundle in result["evidence_bundles"]], ["123"])
        self.assertEqual(result["source_profiles"][0]["documentary_anchor"]["best_chunk_id"], "target")

    def test_pass_b_does_not_pad_completed_facet_set(self):
        first = self.passage("first", "123", 6.0)
        duplicate = self.passage("duplicate", "456", 7.0)
        result = TurinRetrievalV39DocumentaryAnchors.build([first, duplicate], "Find documentary material naming Bruce Archer in archival asset 123.", ["PERSON_A"])
        self.assertEqual(len(result["evidence_bundles"]), 1)
        self.assertEqual(result["source_profiles"][1]["selection_status"], "NOT_SELECTED_NO_MISSING_FACET")

    def test_anchor_score_excludes_source_nomination_signals(self):
        first = self.passage("first", "123", 6.0)
        first["source_signals"] = {"authority_graph_score": 999}
        result = TurinRetrievalV39DocumentaryAnchors.build([first], "Find documentary material naming Bruce Archer in archival asset 123.", ["PERSON_A"])
        anchor = result["source_profiles"][0]["documentary_anchor"]
        self.assertEqual(anchor["anchor_score"], 341.0)
        self.assertEqual(result["source_profiles"][0]["source_nomination_confidence"], 999)


if __name__ == "__main__":
    unittest.main()
