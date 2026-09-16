import sys
import unittest
from pathlib import Path
BACKEND_ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BACKEND_ROOT))
from app.services.turin_retrieval_v3_benchmark import aggregate_metrics,evaluate_case

class BenchmarkTests(unittest.TestCase):
    def test_neutral_case_reports_rank_and_correct_passage(self):
        case={"case_id":"project-job-number","expected_canonical_assets":["asset-job-171"],"expected_passage_ids":["chunk-later"]}
        result={"canonical_source_ranking":[{"canonical_asset_id":"other"},{"canonical_asset_id":"asset-job-171"}],"final_five":[{"canonical_asset_id":"asset-job-171","chunk_id":"chunk-later"}]}
        evaluation=evaluate_case(case,result)
        self.assertTrue(evaluation["top_50"]);self.assertTrue(evaluation["top_5"]);self.assertTrue(evaluation["passage_hit"]);self.assertEqual(evaluation["reciprocal_rank"],.5)
    def test_metrics_are_retrieval_only(self):
        metrics=aggregate_metrics([{"top_50":True,"top_20":True,"top_10":True,"top_5":True,"reciprocal_rank":1,"passage_hit":True,"false_positive_count":0}])
        self.assertEqual(metrics["MRR"],1);self.assertEqual(metrics["irrelevant_final_passage_rate"],0)

if __name__=='__main__':unittest.main()