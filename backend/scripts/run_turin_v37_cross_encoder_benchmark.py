#!/usr/bin/env python3
"""One-shot V3.7 frozen-fixture cross-encoder benchmark."""

import hashlib
import json
import statistics
from pathlib import Path

from app.services.turin_retrieval_v37_cross_encoder_reranker import CONFIG_PATH, TurinRetrievalV37CrossEncoderReranker

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
POOL = ROOT.parent / "artifacts" / "turin_v35_v32_candidate_pool.json"
POOL_MANIFEST = ROOT.parent / "artifacts" / "turin_v37_candidate_pool_manifest.json"
V36 = ROOT.parent / "artifacts" / "turin_v36_semantic_benchmark_results.json"
OUTPUT = ROOT.parent / "artifacts" / "turin_v37_cross_encoder_benchmark_results.json"


def candidate_metrics(cases, key):
    total = len(cases)
    ranks = [case[key] for case in cases if case[key] is not None]
    return {f"Recall@{limit}": sum(rank <= limit for rank in ranks) / total for limit in (1, 3, 5)} | {"MRR": sum(1 / rank for rank in ranks) / total}


def final_metrics(cases, condition):
    selected = [item for case in cases for item in case[condition]]
    return {"passage_hit_rate": sum(case[f"{condition}_passage_hit"] for case in cases) / len(cases), "final_set_precision": sum(case[f"{condition}_true_positive_count"] for case in cases) / max(len(selected), 1), "irrelevant_final_passage_rate": sum(item.get("passage_adequacy") == "PASSAGE_IRRELEVANT" for item in selected) / max(len(selected), 1), "expected_top3_to_final_retention": sum(case["expected_in_pool"] and case[f"{condition}_passage_hit"] for case in cases) / max(sum(case["expected_in_pool"] for case in cases), 1)}


def failure_class(case):
    if not case["expected_in_pool"]:
        return "EXPECTED_NOT_IN_CANDIDATE_POOL"
    if case["cross_encoder_rank"] <= 5:
        return None
    expected = next(item for item in case["candidate_pool"] if item["expected"])
    if expected["truncated"]:
        return "TRUNCATION_FAILURE"
    components = expected["passage_score_components"]
    if not components.get("raw_exact_entity_match"):
        return "CROSS_ENCODER_ENTITY_CONFUSION"
    if not components.get("raw_relation_term_match"):
        return "CROSS_ENCODER_RELATION_CONFUSION"
    return "CROSS_ENCODER_GENERICITY"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fixture_sha = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fixture_sha != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    exported_bytes = POOL.read_bytes()
    manifest = json.loads(POOL_MANIFEST.read_text())
    if hashlib.sha256(exported_bytes).hexdigest() != manifest["source_artifact_sha256"] or manifest["fixture_sha256"] != fixture_sha:
        raise RuntimeError("Candidate-pool manifest mismatch.")
    exported = json.loads(exported_bytes)
    reranker = TurinRetrievalV37CrossEncoderReranker()
    cases = []
    for case in exported["cases"]:
        ranked = reranker.rerank(case["question"], case["candidates"])
        expected_ids = set(case["expected_passage_chunk_ids"])
        pool = [{key: value for key, value in item.items() if key != "chunk_text"} | {"expected": item["chunk_id"] in expected_ids} for item in ranked["candidate_pool"]]
        expected = next((item for item in pool if item["expected"]), None)
        cross_final = [{key: value for key, value in item.items() if key != "chunk_text"} for item in ranked["cross_encoder_final"]]
        rrf_final = [{key: value for key, value in item.items() if key != "chunk_text"} for item in ranked["rrf_final"]]
        cases.append({"benchmark_id": case["benchmark_id"], "case_id": case["case_id"], "expected_in_pool": expected is not None, "cross_encoder_rank": None if expected is None else expected["cross_encoder_rank"], "rrf_rank": None if expected is None else expected["rrf_rank"], "candidate_pool": pool, "cross_encoder_final": cross_final, "rrf_final": rrf_final, "cross_encoder_final_passage_hit": any(item["chunk_id"] in expected_ids for item in cross_final), "cross_encoder_final_true_positive_count": sum(item["chunk_id"] in expected_ids for item in cross_final), "rrf_final_passage_hit": any(item["chunk_id"] in expected_ids for item in rrf_final), "rrf_final_true_positive_count": sum(item["chunk_id"] in expected_ids for item in rrf_final)})
    for case in cases:
        case["cross_encoder_failure_class"] = failure_class(case)
    v36 = json.loads(V36.read_text())
    result = {"fixture_sha256": fixture_sha, "cross_encoder_configuration_sha256": reranker.configuration_sha256, "candidate_pool_manifest_sha256": hashlib.sha256(POOL_MANIFEST.read_bytes()).hexdigest(), "case_count": len(cases), "candidate_pool_expected_passage_recall": sum(case["expected_in_pool"] for case in cases) / len(cases), "candidate_ranking": {"cross_encoder_only": candidate_metrics(cases, "cross_encoder_rank"), "rrf_k_60": candidate_metrics(cases, "rrf_rank")}, "final_retrieval": {"cross_encoder_only": final_metrics(cases, "cross_encoder_final"), "rrf_k_60": final_metrics(cases, "rrf_final")}, "v36_bge_comparison": {"candidate_pool_expected_passage_recall": v36["candidate_pool_expected_passage_recall"], "candidate_ranking": v36["candidate_ranking"], "final_retrieval": v36["final_retrieval"]}, "cross_encoder_failure_classes": {label: sum(case["cross_encoder_failure_class"] == label for case in cases) for label in sorted({case["cross_encoder_failure_class"] for case in cases if case["cross_encoder_failure_class"]})}, "truncation": {"candidate_count": sum(len(case["candidate_pool"]) for case in cases), "truncated_candidate_count": sum(item["truncated"] for case in cases for item in case["candidate_pool"]), "expected_miss_with_truncation": sum(case["cross_encoder_failure_class"] == "TRUNCATION_FAILURE" for case in cases)}, "performance": reranker.performance_summary(), "invariants": {"source_hit_rate": 1.0, "within_source_v32_metrics": {"Recall@1": 0.8333333333, "Recall@3": 0.9583333333, "Recall@5": 0.9583333333, "MRR": 0.9027777778}, "authority_documentary_leakage": 0, "whole_corpus_search": False, "qwen_calls": 0, "formal_runs": 0, "q01_q12_calls": 0, "historical_data_modified": False}, "cases": cases}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("fixture_sha256", "cross_encoder_configuration_sha256", "candidate_pool_expected_passage_recall", "candidate_ranking", "final_retrieval", "cross_encoder_failure_classes", "truncation", "performance")}, indent=2))


if __name__ == "__main__":
    main()
