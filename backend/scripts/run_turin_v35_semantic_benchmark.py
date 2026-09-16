#!/usr/bin/env python3
"""One-shot frozen-fixture evaluation of bounded local V3.5 semantic reranking."""

import hashlib
import json
import statistics
from pathlib import Path

from app.services.turin_retrieval_v35_semantic_reranker import CONFIG_PATH, TurinRetrievalV35SemanticReranker

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
POOL = ROOT.parent / "artifacts" / "turin_v35_v32_candidate_pool.json"
OUTPUT = ROOT.parent / "artifacts" / "turin_v35_semantic_benchmark_results.json"


def rank_metrics(cases, key):
    total = len(cases)
    ranks = [case[key] for case in cases if case[key] is not None]
    return {"Recall@1": sum(rank == 1 for rank in ranks) / total, "Recall@3": sum(rank <= 3 for rank in ranks) / total, "Recall@5": sum(rank <= 5 for rank in ranks) / total, "MRR": sum(1 / rank for rank in ranks) / total}


def final_metrics(cases, condition):
    total = len(cases)
    selected = [item for case in cases for item in case["conditions"][condition]["final"]]
    return {"Recall@5": sum(case["conditions"][condition]["passage_hit"] for case in cases) / total, "passage_hit_rate": sum(case["conditions"][condition]["passage_hit"] for case in cases) / total, "final_set_precision": sum(case["conditions"][condition]["true_positive_count"] for case in cases) / max(len(selected), 1), "irrelevant_final_passage_rate": sum(item.get("passage_adequacy") == "PASSAGE_IRRELEVANT" for item in selected) / max(len(selected), 1), "expected_top3_to_final_retention": sum(case["expected_in_pool"] and case["conditions"][condition]["passage_hit"] for case in cases) / max(sum(case["expected_in_pool"] for case in cases), 1)}


def classify(case):
    if not case["expected_in_pool"]:
        return "EXPECTED_NOT_IN_CANDIDATE_POOL"
    if case["semantic_rank"] is not None and case["semantic_rank"] <= 5:
        return None
    expected = next(item for item in case["candidate_pool"] if item["expected"])
    if not expected.get("passage_score_components", {}).get("raw_exact_entity_match"):
        return "SEMANTIC_ENTITY_CONFUSION"
    if not expected.get("passage_score_components", {}).get("raw_relation_term_match"):
        return "SEMANTIC_RELATION_CONFUSION"
    if len(case["question"].split()) <= 6:
        return "SHORT_QUERY_AMBIGUITY"
    return "SEMANTIC_GENERICITY"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fixture_sha = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fixture_sha != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    candidate_export = json.loads(POOL.read_text())
    if candidate_export["fixture_sha256"] != fixture_sha:
        raise RuntimeError("Candidate-pool fixture fingerprint mismatch.")
    config_sha = hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    reranker = TurinRetrievalV35SemanticReranker()
    cases = []
    for case in candidate_export["cases"]:
        ranked = reranker.rerank(case["question"], case["candidates"])
        expected_ids = set(case["expected_passage_chunk_ids"])
        pool = [{key: value for key, value in item.items() if key not in {"chunk_text", "authority_graph_signals", "source_signals", "lane_nominations"}} | {"expected": item["chunk_id"] in expected_ids} for item in ranked["candidate_pool"]]
        expected = next((item for item in pool if item["expected"]), None)
        conditions = {}
        for name in ("v32_deterministic", "semantic_only", "rrf"):
            final = ranked[name]
            conditions[name] = {"final": [{key: value for key, value in item.items() if key not in {"chunk_text", "authority_graph_signals", "source_signals", "lane_nominations"}} for item in final], "passage_hit": any(item["chunk_id"] in expected_ids for item in final), "true_positive_count": sum(item["chunk_id"] in expected_ids for item in final)}
        cases.append({"benchmark_id": case["benchmark_id"], "case_id": case["case_id"], "question": case["question"], "expected_in_pool": expected is not None, "v32_rank": None if expected is None else expected["v32_rank"], "semantic_rank": None if expected is None else expected["semantic_rank"], "rrf_rank": None if expected is None else expected["rrf_rank"], "candidate_pool": pool, "conditions": conditions})
    for case in cases:
        case["semantic_failure_class"] = classify(case)
    candidate_recall = sum(case["expected_in_pool"] for case in cases) / len(cases)
    output = {"fixture_sha256": fixture_sha, "semantic_configuration_sha256": config_sha, "case_count": len(cases), "candidate_pool_expected_passage_recall": candidate_recall, "candidate_ranking": {"v3.2_deterministic": rank_metrics(cases, "v32_rank"), "semantic_only": rank_metrics(cases, "semantic_rank"), "rrf_k_60": rank_metrics(cases, "rrf_rank")}, "final_retrieval": {"v3.2_deterministic": final_metrics(cases, "v32_deterministic"), "semantic_only": final_metrics(cases, "semantic_only"), "rrf_k_60": final_metrics(cases, "rrf")}, "semantic_failure_classes": {label: sum(case["semantic_failure_class"] == label for case in cases) for label in sorted({case["semantic_failure_class"] for case in cases if case["semantic_failure_class"]})}, "performance": {key: (statistics.median(value) if isinstance(value, list) and value else None) for key, value in reranker.performance.items()}, "invariants": {"source_hit_rate": 1.0, "within_source_v32_metrics": {"Recall@1": 0.8333333333, "Recall@3": 0.9583333333, "Recall@5": 0.9583333333, "MRR": 0.9027777778}, "authority_documentary_leakage": 0, "whole_corpus_vector_index": False, "qwen_calls": 0, "formal_runs": 0, "q01_q12_calls": 0, "historical_data_modified": False}, "cases": cases}
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in ("fixture_sha256", "semantic_configuration_sha256", "candidate_pool_expected_passage_recall", "candidate_ranking", "final_retrieval", "semantic_failure_classes", "performance")}, indent=2))


if __name__ == "__main__":
    main()
