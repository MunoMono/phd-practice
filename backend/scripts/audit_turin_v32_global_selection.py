#!/usr/bin/env python3
"""Trace frozen-fixture V3.2 passages that are strong within a source but absent globally."""

import hashlib
import json
from pathlib import Path

from app.core.database import LocalSessionLocal
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
OUTPUT = ROOT / "artifacts" / "turin_v32_global_selection_audit.json"


def classify(expected, selected):
    if any(item["passage_score"] > expected["passage_score"] and not item.get("passage_quality_exclusions") for item in selected):
        return "GENERIC_PASSAGE_DOMINANCE"
    if any(set(item.get("facet_coverage", [])) - set(expected.get("facet_coverage", [])) for item in selected):
        return "DIVERSITY_OVERREWARD"
    return "TOP_K_TRUNCATION"


def compact(item):
    return {key: item.get(key) for key in ("chunk_id", "document_id", "canonical_asset_id", "chunk_index", "source_page", "passage_score", "passage_adequacy", "facet_coverage", "lane_nominations", "source_signals", "authority_graph_signals", "selection_reason") } | {"components": item.get("passage_score_components")}


def main():
    fixture = json.loads(FIXTURE.read_text())
    fingerprint = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    service = TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2")
    database = LocalSessionLocal()
    try:
        failures = []
        ranges = {"passage_score": [], "source_confidence": []}
        for case in fixture["cases"]:
            result = service.retrieve(database, case["neutral_question"], 5, fixture["corpus_version"])
            source_signals = {item["document_id"]: item["source_signals"] for item in result["canonical_source_ranking"]}
            expected_id = case["expected_passage_chunk_ids"][0]
            expected = next((item for item in result["passage_ranking"] if item["chunk_id"] == expected_id), None)
            selected = result["final_five"]
            if expected and expected_id not in {item["chunk_id"] for item in selected}:
                failures.append({"benchmark_id": case["benchmark_id"], "expected_source_rank": next((index for index, item in enumerate(result["canonical_source_ranking"], 1) if item["document_id"] == case["expected_canonical_document_ids"][0]), None), "expected_within_source_rank": next((index for index, item in enumerate([row for row in result["passage_ranking"] if row["document_id"] == expected["document_id"]], 1) if item["chunk_id"] == expected_id), None), "expected_global_rank": next((index for index, item in enumerate(sorted(result["passage_ranking"], key=lambda row: -row["passage_score"]), 1) if item["chunk_id"] == expected_id), None), "failure_class": classify(expected, selected), "expected": compact(expected), "selected": [compact(item) for item in selected]})
            for item in result["passage_ranking"]:
                ranges["passage_score"].append(item["passage_score"])
                ranges["source_confidence"].append(sum(source_signals.get(item["document_id"], {}).values()))
        OUTPUT.parent.mkdir(exist_ok=True)
        payload = {"fixture_sha256": fingerprint, "failures": failures, "failure_counts": {kind: sum(item["failure_class"] == kind for item in failures) for kind in sorted({item["failure_class"] for item in failures})}, "score_ranges": {key: {"min": min(values), "max": max(values)} for key, values in ranges.items()}}
        OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps({"failure_count": len(failures), "failure_counts": payload["failure_counts"], "score_ranges": payload["score_ranges"]}, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()