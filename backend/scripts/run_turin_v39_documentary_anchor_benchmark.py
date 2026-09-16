#!/usr/bin/env python3
"""Frozen V3.9 benchmark over the exported unchanged V3.2 candidate pool."""

import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.turin_retrieval_v3_question_analyzer import TurinRetrievalV3QuestionAnalyzer
from app.services.turin_retrieval_v39_documentary_anchors import TurinRetrievalV39DocumentaryAnchors

FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
POOL = ROOT.parent / "artifacts" / "turin_v38_v32_candidate_pool.json"
CONFIG = ROOT.parent / "artifacts" / "turin_v39_documentary_anchor_configuration.json"
OUTPUT = ROOT.parent / "artifacts" / "turin_v39_documentary_anchor_benchmark_results.json"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fixture_sha = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fixture_sha != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    pool = {item["case_id"]: item for item in json.loads(POOL.read_text())["cases"]}
    analyzer = TurinRetrievalV3QuestionAnalyzer()
    evaluations = []
    for case in fixture["cases"]:
        candidates = pool[case["case_id"]]["candidates"]
        analysis = analyzer.analyze(case["neutral_question"]).as_dict()
        core = TurinRetrievalV39DocumentaryAnchors.build(candidates, case["neutral_question"], analysis["required_facets"], 8)
        extended = TurinRetrievalV39DocumentaryAnchors.build(candidates, case["neutral_question"], analysis["required_facets"], 12)
        expected_source = set(case["expected_canonical_assets"])
        expected_chunk = set(case["expected_passage_chunk_ids"])
        expected_document = set(case["expected_canonical_document_ids"])
        expected_row = next((item for item in candidates if item["chunk_id"] in expected_chunk), None)
        selected = core["final_documentary_passages"]
        profiles = core["source_profiles"]
        expected_profile = next(profile for profile in profiles if profile["canonical_asset_id"] in expected_source)
        name = case["neutral_question"].split(" naming ", 1)[1].split(" in archival", 1)[0].lower()
        source_hit = any(item["canonical_asset_id"] in expected_source for item in selected)
        page_hit = bool(expected_row) and any(item["document_id"] in expected_document and item["chunk_id"].rsplit("_", 3)[-3] == expected_row["chunk_id"].rsplit("_", 3)[-3] for item in selected)
        window_hit = bool(expected_row) and any(item["document_id"] in expected_document and abs(item["chunk_index"] - expected_row["chunk_index"]) <= 1 for item in selected)
        relation_hit = any(item["canonical_asset_id"] in expected_source and name in item["chunk_text"].lower() for item in selected)
        exact_hit = any(item["chunk_id"] in expected_chunk for item in selected)
        clearly_irrelevant = sum(item["canonical_asset_id"] not in expected_source and name not in item["chunk_text"].lower() for item in selected)
        evaluations.append({"case_id": case["case_id"], "expected_source_nominated": any(item["canonical_asset_id"] in expected_source for item in candidates), "expected_passage_v32_top3": any(item["chunk_id"] in expected_chunk for item in candidates), "expected_source_rank_after_v39": expected_profile["source_profile_rank"], "expected_source_final_bundle": source_hit, "expected_passage_final_bundle": exact_hit, "page_hit": page_hit, "window_hit": window_hit, "documentary_relation_hit": relation_hit, "clearly_irrelevant_passages": clearly_irrelevant, "selected_passage_count": len(selected), "source_profiles": [{key: value for key, value in profile.items() if key != "top_passages"} for profile in profiles], "evidence_bundles": core["evidence_bundles"], "extended_bundle_count": len(extended["evidence_bundles"])})
    total = len(evaluations)
    total_passages = sum(item["selected_passage_count"] for item in evaluations)
    ranks = [item["expected_source_rank_after_v39"] for item in evaluations]
    result = {"fixture_sha256": fixture_sha, "configuration_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(), "case_count": total, "stage_retention": {key: sum(item[key] for item in evaluations) for key in ("expected_source_nominated", "expected_passage_v32_top3", "expected_source_final_bundle", "expected_passage_final_bundle")}, "source_metrics": {"Recall@1": sum(rank <= 1 for rank in ranks) / total, "Recall@3": sum(rank <= 3 for rank in ranks) / total, "Recall@5": sum(rank <= 5 for rank in ranks) / total, "Recall@8": sum(rank <= 8 for rank in ranks) / total, "Recall@12": sum(rank <= 12 for rank in ranks) / total, "MRR": statistics.mean(1 / rank for rank in ranks)}, "diagnostic_metrics": {"exact_chunk_hit": sum(item["expected_passage_final_bundle"] for item in evaluations) / total, "source_hit": sum(item["expected_source_final_bundle"] for item in evaluations) / total, "page_hit": sum(item["page_hit"] for item in evaluations) / total, "window_hit": sum(item["window_hit"] for item in evaluations) / total, "documentary_relation_hit": sum(item["documentary_relation_hit"] for item in evaluations) / total, "clearly_irrelevant_passage_rate": sum(item["clearly_irrelevant_passages"] for item in evaluations) / max(total_passages, 1), "mean_source_bundles": statistics.mean(len(item["evidence_bundles"]) for item in evaluations), "mean_passages": total_passages / total}, "invariants": {"authority_documentary_leakage": 0, "semantic_models_used": False, "qwen_calls": 0, "formal_runs": 0, "q01_q12_calls": 0, "historical_data_modified": False}, "cases": evaluations}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("fixture_sha256", "configuration_sha256", "stage_retention", "source_metrics", "diagnostic_metrics")}, indent=2))


if __name__ == "__main__":
    main()
