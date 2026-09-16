import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.turin_retrieval_v310_query_anchors import TurinRetrievalV310QueryAnchors as V310

class V310AnchorTests(unittest.TestCase):
    def row(self, asset, text, score=5):
        return {"chunk_id":asset+"-chunk","document_id":asset,"canonical_asset_id":asset,"asset_pid":asset,"title":asset,"chunk_index":0,"chunk_text":text,"passage_score":score,"passage_adequacy":"PASSAGE_STRONG","facet_coverage":["PERSON_A"],"passage_score_components":{"core_facets_present":1},"source_signals":{},"authority_graph_signals":{}}
    def test_exact_project_rejects_other_project(self):
        result=V310.build([self.row("171","Job 171 project record"),self.row("97","Job 97 project record",9)],"What documents concern Job 171?",["CONCEPT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"],"171")
        self.assertEqual(result["source_profiles"][1]["selection_status"],"NOMINATED_BUT_ANCHOR_MISMATCH")
    def test_person_pair_prefers_same_passage(self):
        result=V310.build([self.row("pair","Ken Baynes and Phil Roberts in the Design Education Unit"),self.row("single","Ken Baynes curriculum",9)],"What connects Ken Baynes and Phil Roberts in the Design Education Unit?",["PERSON_A","PERSON_B"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"],"pair")
    def test_person_object_cooccurrence_beats_person_only(self):
        result=V310.build([self.row("role","John Wood console ergonomics",5),self.row("generic","John Wood",9)],"How is John Wood's console role documented?",["PERSON_A"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"],"role")
    def test_event_anchor_rejects_generic_retrospective(self):
        result=V310.build([self.row("decision","DDR closure decision resolved"),self.row("generic","DDR history",9)],"Why was the DDR closure decision made?",["EVENT"])
        self.assertEqual(result["evidence_bundles"][0]["source"]["asset_pid"],"decision")

if __name__=='__main__': unittest.main()
