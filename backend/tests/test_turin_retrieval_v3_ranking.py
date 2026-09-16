import sys
import unittest
from pathlib import Path
BACKEND_ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(BACKEND_ROOT))
from app.services.turin_retrieval_v3_coverage import TurinRetrievalV3Coverage
from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker

class RankingTests(unittest.TestCase):
    def setUp(self): self.analysis=TurinRetrievalV3QuestionAnalyzer().analyze("What teaching role did Example Person have in 1974?").as_dict()
    def test_person_role_prefers_cooccurrence_and_rejects_metadata_as_evidence(self):
        generic=TurinRetrievalV3Ranker.score_passage({"chunk_id":"a","document_id":"a","chunk_text":"This report considers the history of design research over several decades."},self.analysis)
        direct=TurinRetrievalV3Ranker.score_passage({"chunk_id":"b","document_id":"b","chunk_text":"In 1974 Example Person led teaching seminars for students in design research."},self.analysis)
        self.assertGreater(direct["passage_score"],generic["passage_score"])
        self.assertNotIn("metadata_score",direct["passage_score_components"])
    def test_final_selection_covers_facets_without_canonical_duplicates(self):
        items=[{"chunk_id":"a","document_id":"a","asset_id":"one","passage_score":4,"facet_coverage":["PERSON_A"]},{"chunk_id":"b","document_id":"b","asset_id":"one","passage_score":3,"facet_coverage":["ACTIVITY"]},{"chunk_id":"c","document_id":"c","asset_id":"two","passage_score":2,"facet_coverage":["ACTIVITY"]}]
        selected=TurinRetrievalV3Coverage.select(items,["PERSON_A","ACTIVITY"])
        self.assertEqual([item["chunk_id"] for item in selected],["a","c"])
    def test_insufficient_retrieval_blocks_corpus_missingness(self):
        diagnostic=TurinRetrievalV3Coverage.adequacy([],self.analysis)
        self.assertEqual(diagnostic["status"],"RETRIEVAL_INSUFFICIENT")
        self.assertFalse(diagnostic["corpus_missingness_permitted"])

    def test_metadata_nominated_source_never_becomes_documentary_evidence(self):
        passage=TurinRetrievalV3Ranker.score_passage({"chunk_id":"metadata-first","document_id":"source","chunk_text":"<!-- image -->"},self.analysis)
        self.assertIn("image_marker",passage["passage_quality_exclusions"])
        self.assertEqual(passage["passage_score_components"]["documentary_information"],0)

    def test_deeper_relevant_passage_beats_generic_first_passage(self):
        generic=TurinRetrievalV3Ranker.score_passage({"chunk_id":"first","document_id":"source","chunk_text":"The report describes broad developments in design and education across several years."},self.analysis)
        deeper=TurinRetrievalV3Ranker.score_passage({"chunk_id":"later","document_id":"source","chunk_text":"In 1974 Example Person led teaching workshops and seminars for design students."},self.analysis)
        self.assertGreater(deeper["passage_score"],generic["passage_score"])

    def test_event_causation_favors_institutional_decision_language(self):
        analysis=TurinRetrievalV3QuestionAnalyzer().analyze("Why did the department close after a decision in 1978?").as_dict()
        decision=TurinRetrievalV3Ranker.score_passage({"chunk_id":"decision","document_id":"a","chunk_text":"The department decision to close in 1978 recorded the reason for closure."},analysis)
        generic=TurinRetrievalV3Ranker.score_passage({"chunk_id":"generic","document_id":"b","chunk_text":"The department supported research and design projects over many years."},analysis)
        self.assertGreater(decision["passage_score"],generic["passage_score"])

    def test_source_type_comparison_can_select_distinct_source_types(self):
        items=[{"chunk_id":"minutes","document_id":"a","asset_id":"a","source_type":"minutes","passage_score":3,"facet_coverage":["SOURCE_TYPE"]},{"chunk_id":"report","document_id":"b","asset_id":"b","source_type":"report","passage_score":2,"facet_coverage":["SOURCE_TYPE"]}]
        selected=TurinRetrievalV3Coverage.select(items,["SOURCE_TYPE"])
        self.assertEqual(len(selected),2)
        self.assertEqual({item["source_type"] for item in selected},{"minutes","report"})

if __name__=='__main__': unittest.main()