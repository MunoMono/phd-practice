#!/usr/bin/env python3
"""Read-only V3.4 expected-passage exclusion trace for the frozen Turin fixture."""

import hashlib
import json
from pathlib import Path

from app.core.database import LocalSessionLocal
from app.services.turin_retrieval_v34_slots import TurinRetrievalV34Slots
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
OUTPUT = ROOT / "artifacts" / "turin_v34_slot_failure_trace.json"


def main():
    fixture = json.loads(FIXTURE.read_text())
    fingerprint = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    service = TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2", selection_version="v3.4")
    database = LocalSessionLocal()
    try:
        failures = []
        for case in fixture["cases"]:
            analysis = service.analyzer.analyze(case["neutral_question"]).as_dict()
            result = service.retrieve(database, case["neutral_question"], 5, fixture["corpus_version"])
            expected_ids = set(case["expected_passage_chunk_ids"])
            expected_rows = [TurinRetrievalV3Ranker.score_passage(row, analysis, v32=True) for document_id in case["expected_canonical_document_ids"] for row in service._source_rows(database, document_id, fixture["corpus_version"])]
            for expected in [row for row in expected_rows if row["chunk_id"] in expected_ids]:
                matched = TurinRetrievalV34Slots.match(expected, analysis)
                expected_slots = matched["eligible_slots"]
                selected = next((item for item in result["final_five"] if item["chunk_id"] == expected["chunk_id"]), None)
                if selected:
                    continue
                ranked = {item["chunk_id"] for item in result["passage_ranking"]}
                required_missing = set(result["retrieval_adequacy"].get("unfilled_required_slots", []))
                competitor = next((item for item in result["final_five"] if set(item.get("filled_slots", [])) & set(expected_slots)), None)
                if expected["chunk_id"] not in ranked:
                    classification = "SOURCE_TRUNCATION"
                elif not expected_slots:
                    classification = "WRONG_SLOT_CLASSIFICATION"
                elif required_missing & set(expected_slots):
                    classification = "REQUIRED_SLOT_UNFILLED"
                elif competitor:
                    classification = "SLOT_MATCH_SCORE_FAILURE"
                else:
                    classification = "DUPLICATE_SLOT_CAPTURE"
                failures.append({
                    "benchmark_id": case["benchmark_id"],
                    "case_id": case["case_id"],
                    "expected_passage": {"chunk_id": expected["chunk_id"], "document_id": expected["document_id"], "passage_score": expected["passage_score"]},
                    "expected_slots": expected_slots,
                    "slot_assigned": bool(expected_slots),
                    "selected_competing_passage": None if competitor is None else {"chunk_id": competitor["chunk_id"], "document_id": competitor["document_id"], "filled_slots": competitor.get("filled_slots", []), "passage_score": competitor["passage_score"]},
                    "failure_class": classification,
                    "why_expected_lost": "Expected passage was not retained by the V3.4 slot-selected final evidence set.",
                })
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(json.dumps({"fixture_sha256": fingerprint, "failure_count": len(failures), "failure_counts": {label: sum(item["failure_class"] == label for item in failures) for label in sorted({item["failure_class"] for item in failures})}, "failures": failures}, indent=2) + "\n")
        print(json.dumps({"fixture_sha256": fingerprint, "failure_count": len(failures), "failure_counts": {label: sum(item["failure_class"] == label for item in failures) for label in sorted({item["failure_class"] for item in failures})}}, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()
