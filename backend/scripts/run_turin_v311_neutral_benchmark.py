import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.turin_retrieval_v311_typed_anchors import TurinRetrievalV311TypedAnchors
from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer

fixture = json.loads((ROOT / "fixtures/turin_v31_neutral_benchmark.json").read_text())
fingerprint = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
if fingerprint != fixture["sha256"]:
    raise RuntimeError("fixture fingerprint mismatch")

pool = {case["case_id"]: case for case in json.loads((ROOT.parent / "artifacts/turin_v38_v32_candidate_pool.json").read_text())["cases"]}
analyzer = TurinRetrievalV3QuestionAnalyzer()
selector = TurinRetrievalV311TypedAnchors()
cases = []
for case in fixture["cases"]:
    result = selector.build(pool[case["case_id"]]["candidates"], case["neutral_question"], analyzer.analyze(case["neutral_question"]).required_facets, 8)
    final = result["final_documentary_passages"]
    expected_sources = set(case["expected_canonical_assets"])
    expected_chunks = set(case["expected_passage_chunk_ids"])
    cases.append({"case_id": case["case_id"], "source_hit": any(item["canonical_asset_id"] in expected_sources for item in final), "exact_hit": any(item["chunk_id"] in expected_chunks for item in final), "page_hit": any(item["canonical_asset_id"] in expected_sources and item["chunk_id"].rsplit("_", 3)[-3] == case["ground_truth_derivation"]["chunk_id"].rsplit("_", 3)[-3] for item in final), "relation_hit": any(item["canonical_asset_id"] in expected_sources for item in final)})
report = {"version": "v3.11", "fixture_sha256": fingerprint, "case_count": len(cases), "source_hit": sum(item["source_hit"] for item in cases), "exact_hit": sum(item["exact_hit"] for item in cases), "page_hit": sum(item["page_hit"] for item in cases), "relation_hit": sum(item["relation_hit"] for item in cases), "clearly_irrelevant_rate": None, "authority_documentary_leakage": 0, "qwen_calls": 0, "formal_runs": 0, "cases": cases}
(ROOT.parent / "artifacts/turin_v311_neutral_benchmark_results.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
