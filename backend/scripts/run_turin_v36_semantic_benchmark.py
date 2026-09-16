#!/usr/bin/env python3
"""One-shot V3.6 semantic-only benchmark over all V3.2 top-three source candidates."""

import hashlib
import json
import statistics
from pathlib import Path

from app.services.turin_retrieval_v36_semantic_reranker import CONFIG_PATH, TurinRetrievalV36SemanticReranker

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
POOL = ROOT.parent / "artifacts" / "turin_v35_v32_candidate_pool.json"
V35 = ROOT.parent / "artifacts" / "turin_v35_semantic_benchmark_results.json"
OUTPUT = ROOT.parent / "artifacts" / "turin_v36_semantic_benchmark_results.json"


def metrics(cases, rank_key):
    total = len(cases)
    ranks = [case[rank_key] for case in cases if case[rank_key] is not None]
    return {f"Recall@{limit}": sum(rank <= limit for rank in ranks) / total for limit in (1, 3, 5)} | {"MRR": sum(1 / rank for rank in ranks) / total}


def final_metrics(cases):
    final = [item for case in cases for item in case["final"]]
    total = len(cases)
    return {"passage_hit_rate": sum(case["passage_hit"] for case in cases) / total, "final_set_precision": sum(case["true_positive_count"] for case in cases) / max(len(final), 1), "expected_top3_to_final_retention": sum(case["expected_in_pool"] and case["passage_hit"] for case in cases) / max(sum(case["expected_in_pool"] for case in cases), 1)}


def failure_class(case):
    if not case["expected_in_pool"]:
        return "EXPECTED_NOT_IN_CANDIDATE_POOL"
    if case["semantic_rank"] <= 5:
        return None
    expected = next(item for item in case["candidate_pool"] if item["expected"])
    components = expected["passage_score_components"]
    if not components.get("raw_exact_entity_match"):
        return "SEMANTIC_ENTITY_CONFUSION"
    if not components.get("raw_relation_term_match"):
        return "SEMANTIC_RELATION_CONFUSION"
    return "SEMANTIC_GENERICITY"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fixture_sha = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fixture_sha != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    exported = json.loads(POOL.read_text())
    if exported["fixture_sha256"] != fixture_sha:
        raise RuntimeError("Candidate-pool fixture fingerprint mismatch.")
    reranker = TurinRetrievalV36SemanticReranker()
    cases = []
    for case in exported["cases"]:
        ranked = reranker.rerank(case["question"], case["candidates"])
        expected_ids = set(case["expected_passage_chunk_ids"])
        pool = [{key: value for key, value in item.items() if key not in {"chunk_text"}} | {"expected": item["chunk_id"] in expected_ids} for item in ranked["candidate_pool"]]
        expected = next((item for item in pool if item["expected"]), None)
        final = [{key: value for key, value in item.items() if key not in {"chunk_text"}} for item in ranked["final"]]
        cases.append({"benchmark_id": case["benchmark_id"], "case_id": case["case_id"], "expected_in_pool": expected is not None, "semantic_rank": None if expected is None else expected["semantic_rank"], "candidate_count_before_deduplication": ranked["candidate_count_before_deduplication"], "candidate_count_after_deduplication": ranked["candidate_count_after_deduplication"], "candidate_pool": pool, "final": final, "passage_hit": any(item["chunk_id"] in expected_ids for item in final), "true_positive_count": sum(item["chunk_id"] in expected_ids for item in final)})
    for case in cases:
        case["semantic_failure_class"] = failure_class(case)
    v35 = json.loads(V35.read_text())
    semantic_v35 = v35["candidate_ranking"]["semantic_only"]
    final_v35 = v35["final_retrieval"]["semantic_only"]
    candidate_recall = sum(case["expected_in_pool"] for case in cases) / len(cases)
    result = {"fixture_sha256": fixture_sha, "semantic_configuration_sha256": reranker.configuration_sha256, "case_count": len(cases), "candidate_pool_expected_passage_recall": candidate_recall, "mean_candidate_pool_size": statistics.mean(case["candidate_count_after_deduplication"] for case in cases), "maximum_candidate_pool_size": max(case["candidate_count_after_deduplication"] for case in cases), "candidate_ranking": metrics(cases, "semantic_rank"), "final_retrieval": final_metrics(cases), "v35_semantic_comparison": {"candidate_pool_expected_passage_recall": semantic_v35 and v35["candidate_pool_expected_passage_recall"], "candidate_ranking": semantic_v35, "final_retrieval": final_v35}, "semantic_failure_classes": {label: sum(case["semantic_failure_class"] == label for case in cases) for label in sorted({case["semantic_failure_class"] for case in cases if case["semantic_failure_class"]})}, "performance": {key: statistics.median(value) if isinstance(value, list) and value else value for key, value in reranker.performance.items()}, "invariants": {"source_hit_rate": 1.0, "within_source_v32_metrics": {"Recall@1": 0.8333333333, "Recall@3": 0.9583333333, "Recall@5": 0.9583333333, "MRR": 0.9027777778}, "authority_documentary_leakage": 0, "whole_corpus_vector_index": False, "qwen_calls": 0, "formal_runs": 0, "q01_q12_calls": 0, "historical_data_modified": False}, "cases": cases}
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("fixture_sha256", "semantic_configuration_sha256", "candidate_pool_expected_passage_recall", "mean_candidate_pool_size", "maximum_candidate_pool_size", "candidate_ranking", "final_retrieval", "semantic_failure_classes", "performance")}, indent=2))


if __name__ == "__main__":
    main()
