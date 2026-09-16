#!/usr/bin/env python3
"""Read-only export of fixed V3.2 documentary candidates for local V3.5 scoring."""

import hashlib
import json
from pathlib import Path

from app.core.database import LocalSessionLocal
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
OUTPUT = ROOT / "artifacts" / "turin_v35_v32_candidate_pool.json"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fingerprint = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    service = TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2")
    database = LocalSessionLocal()
    try:
        cases = []
        for case in fixture["cases"]:
            service.retrieve(database, case["neutral_question"], 5, fixture["corpus_version"])
            candidates = [{key: value for key, value in item.items() if key in {"chunk_id", "document_id", "canonical_asset_id", "asset_id", "chunk_index", "chunk_text", "passage_score", "passage_adequacy", "passage_score_components", "facet_coverage", "source_type"}} for item in service.last_passage_candidates]
            cases.append({"benchmark_id": case["benchmark_id"], "case_id": case["case_id"], "question": case["neutral_question"], "expected_passage_chunk_ids": case["expected_passage_chunk_ids"], "candidates": candidates})
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(json.dumps({"fixture_sha256": fingerprint, "corpus_version": fixture["corpus_version"], "candidate_rule": "V3.2_top3_per_nominated_source", "cases": cases}, indent=2) + "\n")
        print(json.dumps({"fixture_sha256": fingerprint, "case_count": len(cases), "candidate_counts": [len(case["candidates"]) for case in cases]}, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()
