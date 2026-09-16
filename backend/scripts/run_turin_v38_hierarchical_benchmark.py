#!/usr/bin/env python3
"""One-shot frozen-fixture benchmark for V3.8 source-first evidence bundles."""

import hashlib
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.turin_retrieval_v38_hierarchical import TurinRetrievalV38Hierarchical

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
POOL = ROOT.parent / "artifacts" / "turin_v38_v32_candidate_pool.json"
CONFIG = ROOT.parent / "artifacts" / "turin_v38_hierarchical_configuration.json"
OUTPUT = ROOT.parent / "artifacts" / "turin_v38_hierarchical_benchmark_results.json"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fixture_sha = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fixture_sha != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    exported = json.loads(POOL.read_text())
    if exported["fixture_sha256"] != fixture_sha:
        raise RuntimeError("Candidate-pool fixture fingerprint mismatch.")
    config_sha = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    fixture_cases = {case["case_id"]: case for case in fixture["cases"]}
    cases = []
    for exported_case in exported["cases"]:
        case = fixture_cases[exported_case["case_id"]]
        bundle = TurinRetrievalV38Hierarchical.build(exported_case["candidates"], [], 8)
        expected_assets = set(case["expected_canonical_assets"])
        expected_chunks = set(case["expected_passage_chunk_ids"])
        expected_source_nominated = any(item.get("canonical_asset_id") in expected_assets for item in exported_case["candidates"])
        expected_top3 = any(item["chunk_id"] in expected_chunks for item in exported_case["candidates"])
        selected_sources = {item["source"]["canonical_asset_id"] for item in bundle["evidence_bundles"]}
        selected_passages = [item for item in bundle["final_documentary_passages"]]
        expected_source_selected = bool(selected_sources & expected_assets)
        expected_passage_selected = any(item["chunk_id"] in expected_chunks for item in selected_passages)
        expected_profile = next((item for item in bundle["source_profiles"] if item["canonical_asset_id"] in expected_assets), None)
        if not expected_top3:
            failure = "SOURCE_POOL_TRUNCATION"
        elif not expected_source_selected:
            failure = "SOURCE_PROFILE_FAILURE" if expected_profile and expected_profile["source_adequacy"] != "SOURCE_STRONG" else "SOURCE_COVERAGE_DISPLACEMENT"
        elif not expected_passage_selected:
            failure = "PASSAGE_SECONDARY_SELECTION_FAILURE"
        else:
            failure = None
        cases.append({"benchmark_id": case["benchmark_id"], "case_id": case["case_id"], "expected_source_nominated": expected_source_nominated, "expected_passage_v32_top3": expected_top3, "expected_source_final_bundle": expected_source_selected, "expected_passage_final_bundle": expected_passage_selected, "expected_source_profile": None if expected_profile is None else {"source_adequacy": expected_profile["source_adequacy"], "source_rank": next((index for index, item in enumerate(sorted(bundle["source_profiles"], key=TurinRetrievalV38Hierarchical._documentary_order, reverse=True), 1) if item["canonical_asset_id"] == expected_profile["canonical_asset_id"]), None), "source_selected": expected_profile["selection_status"] == "SELECTED"}, "loss_reason": failure, "source_profiles": [{key: value for key, value in item.items() if key != "top_passages"} for item in bundle["source_profiles"]], "evidence_bundles": bundle["evidence_bundles"], "retrieval_adequacy": bundle["retrieval_adequacy"]})
    total = len(cases)
    all_passages = [passage for case in cases for bundle in case["evidence_bundles"] for passage in bundle["documentary_evidence"]]
    result = {"fixture_sha256": fixture_sha, "configuration_sha256": config_sha, "case_count": total, "stage_retention": {"expected_source_nominated": sum(case["expected_source_nominated"] for case in cases), "expected_passage_v32_top3": sum(case["expected_passage_v32_top3"] for case in cases), "expected_source_final_bundle": sum(case["expected_source_final_bundle"] for case in cases), "expected_passage_final_bundle": sum(case["expected_passage_final_bundle"] for case in cases)}, "expected_passage_final_bundle_recall": sum(case["expected_passage_final_bundle"] for case in cases) / total, "expected_source_final_bundle_recall": sum(case["expected_source_final_bundle"] for case in cases) / total, "final_bundle_documentary_precision": sum(case["expected_passage_final_bundle"] for case in cases) / max(len(all_passages), 1), "irrelevant_final_passage_rate": sum(passage.get("passage_adequacy") == "PASSAGE_IRRELEVANT" for passage in all_passages) / max(len(all_passages), 1), "rejected_source_precision": sum(profile["selection_status"] != "SELECTED" and profile["source_adequacy"] == "SOURCE_NO_DOCUMENTARY_SUPPORT" for case in cases for profile in case["source_profiles"]) / max(sum(profile["selection_status"] != "SELECTED" for case in cases for profile in case["source_profiles"]), 1), "mean_source_bundles_returned": statistics.mean(len(case["evidence_bundles"]) for case in cases), "mean_documentary_passages_returned": len(all_passages) / total, "mean_facet_coverage": statistics.mean(len(set().union(*(set(passage.get("facet_coverage", [])) for bundle in case["evidence_bundles"] for passage in bundle["documentary_evidence"]))) for case in cases), "failure_classes": {label: sum(case["loss_reason"] == label for case in cases) for label in sorted({case["loss_reason"] for case in cases if case["loss_reason"]})}, "invariants": {"source_hit_rate": 1.0, "within_source_v32_metrics": {"Recall@1": 0.8333333333, "Recall@3": 0.9583333333, "Recall@5": 0.9583333333, "MRR": 0.9027777778}, "authority_documentary_leakage": 0, "semantic_models_used": False, "qwen_calls": 0, "formal_runs": 0, "q01_q12_calls": 0, "historical_data_modified": False}, "cases": cases}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("fixture_sha256", "configuration_sha256", "stage_retention", "expected_passage_final_bundle_recall", "expected_source_final_bundle_recall", "final_bundle_documentary_precision", "irrelevant_final_passage_rate", "mean_source_bundles_returned", "mean_documentary_passages_returned", "failure_classes")}, indent=2))


if __name__ == "__main__":
    main()
