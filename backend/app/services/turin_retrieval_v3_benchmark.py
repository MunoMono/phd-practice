"""Neutral, retrieval-only benchmark metrics for Turin retrieval v3."""

from __future__ import annotations

from typing import Any


def evaluate_case(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    expected = set(case["expected_canonical_assets"])
    ranked = [item.get("canonical_asset_id") for item in result.get("canonical_source_ranking", [])]
    final = [item.get("canonical_asset_id") for item in result.get("final_five", [])]
    rank = next((index for index, item in enumerate(ranked, 1) if item in expected), None)
    passage_hit = any(item.get("canonical_asset_id") in expected and item.get("chunk_id") in set(case.get("expected_passage_ids", [])) for item in result.get("final_five", []))
    true_positive_count = sum(item.get("canonical_asset_id") in expected and item.get("chunk_id") in set(case.get("expected_passage_ids", [])) for item in result.get("final_five", []))
    graph_sources = [item for item in result.get("canonical_source_ranking", []) if item.get("authority_graph_signals", {}).get("authority_edge_count")]
    graph_expected = [item for item in graph_sources if item.get("canonical_asset_id") in expected]
    graph_final = [item for item in result.get("final_five", []) if item.get("authority_graph_signals", {}).get("authority_edge_count")]
    facet_coverage = [len(item.get("facet_coverage", [])) / max(len(result.get("question_analysis", {}).get("required_facets", [])), 1) for item in result.get("final_five", [])]
    strong = [item for item in result.get("final_five", []) if item.get("passage_adequacy") == "PASSAGE_STRONG"]
    return {"case_id": case["case_id"], "top_50": bool(set(ranked[:50]) & expected), "top_20": bool(set(ranked[:20]) & expected), "top_10": bool(set(ranked[:10]) & expected), "top_5": bool(set(final[:5]) & expected), "reciprocal_rank": 1 / rank if rank else 0.0, "passage_hit": passage_hit, "true_positive_count": true_positive_count, "source_diversity": len(set(final)), "false_positive_count": sum(item not in expected for item in final), "irrelevant_padding_count": sum(item.get("passage_adequacy") == "PASSAGE_IRRELEVANT" for item in result.get("final_five", [])), "strong_passage_count": len(strong), "mean_facet_coverage": sum(facet_coverage) / max(len(facet_coverage), 1), "final_passage_count": len(final), "graph_nominated_sources": len(graph_sources), "graph_expected_sources": len(graph_expected), "graph_final_sources": len(graph_final), "graph_passage_successes": sum(item.get("canonical_asset_id") in expected for item in graph_final)}


def aggregate_metrics(evaluations: list[dict[str, Any]]) -> dict[str, float]:
    total = max(len(evaluations), 1)
    graph_nominated = sum(item.get("graph_nominated_sources", 0) for item in evaluations)
    graph_final = sum(item.get("graph_final_sources", 0) for item in evaluations)
    final_total = sum(item.get("final_passage_count", 0) for item in evaluations)
    expected_assigned = sum(item.get("expected_slot_assigned", False) for item in evaluations)
    expected_selected = sum(item.get("expected_slot_selected", False) for item in evaluations)
    return {"Recall@50": sum(item["top_50"] for item in evaluations) / total, "Recall@20": sum(item["top_20"] for item in evaluations) / total, "Recall@10": sum(item["top_10"] for item in evaluations) / total, "Recall@5": sum(item["top_5"] for item in evaluations) / total, "MRR": sum(item["reciprocal_rank"] for item in evaluations) / total, "source_hit_rate": sum(item["top_50"] for item in evaluations) / total, "passage_hit_rate": sum(item["passage_hit"] for item in evaluations) / total, "final_evidence_precision": sum(item["true_positive_count"] for item in evaluations) / max(final_total, 1), "final_set_precision": sum(item["true_positive_count"] for item in evaluations) / max(final_total, 1), "strong_passage_retention_rate": sum(item["strong_passage_count"] for item in evaluations) / max(final_total, 1), "required_slot_fill_rate": sum(item.get("required_slot_fill", 0.0) for item in evaluations) / total, "preferred_slot_fill_rate": sum(item.get("preferred_slot_fill", 0.0) for item in evaluations) / total, "expected_passage_slot_assignment_accuracy": expected_assigned / total, "expected_top3_to_slot_selected_retention": expected_selected / max(sum(item.get("expected_top3", False) for item in evaluations), 1), "expected_top3_to_final_retention": sum(item.get("expected_top3_to_final", False) for item in evaluations) / max(sum(item.get("expected_top3", False) for item in evaluations), 1), "mean_selected_passage_count": final_total / total, "mean_final_passages_returned": final_total / total, "irrelevant_padding_count": sum(item["irrelevant_padding_count"] for item in evaluations), "irrelevant_final_passage_rate": sum(item["false_positive_count"] for item in evaluations) / max(final_total, 1), "mean_facet_coverage": sum(item.get("mean_facet_coverage", 0) for item in evaluations) / total, "graph_nominated_sources": graph_nominated, "graph_nomination_precision": sum(item.get("graph_expected_sources", 0) for item in evaluations) / max(graph_nominated, 1), "graph_nomination_passage_success_rate": sum(item.get("graph_passage_successes", 0) for item in evaluations) / max(graph_final, 1)}