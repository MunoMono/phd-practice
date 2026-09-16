#!/usr/bin/env python3
"""Compare V3 and V3.1 retrieval only against a frozen neutral fixture."""

import hashlib
import json
from pathlib import Path

from app.core.database import LocalSessionLocal
from app.services.turin_retrieval_v3_benchmark import aggregate_metrics, evaluate_case
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service
from app.services.turin_retrieval_v34_slots import TurinRetrievalV34Slots

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
OUTPUT = ROOT / "artifacts" / "turin_v31_neutral_benchmark_results.json"


def main():
    fixture = json.loads(FIXTURE.read_text())
    frozen = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if frozen != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    database = LocalSessionLocal()
    try:
        runs = {}
        for name, service in (("v3.3", TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2", selection_version="v3.3")), ("v3.4", TurinRetrievalV3Service(use_authority_graph=True, passage_version="v3.2", selection_version="v3.4"))):
            evaluations = [evaluate_case(case, service.retrieve(database, case["neutral_question"], 5, fixture["corpus_version"])) for case in fixture["cases"]]
            within_source = []
            for case in fixture["cases"]:
                analysis = service.analyzer.analyze(case["neutral_question"]).as_dict()
                rows = [TurinRetrievalV3Ranker.score_passage(row, analysis, v32=service.passage_version == "v3.2") for row in service._source_rows(database, case["expected_canonical_document_ids"][0], fixture["corpus_version"])]
                ranked = sorted(rows, key=lambda row: (-row["passage_score"], row["chunk_index"], str(row["chunk_id"])))
                rank = next((index for index, row in enumerate(ranked, 1) if row["chunk_id"] in case["expected_passage_chunk_ids"]), None)
                expected = next((row for row in ranked if row["chunk_id"] in case["expected_passage_chunk_ids"]), None)
                expected_slots = TurinRetrievalV34Slots.match(expected, analysis)["eligible_slots"] if expected else []
                within_source.append({"rank": rank, "top_1": rank == 1, "top_3": bool(rank and rank <= 3), "top_5": bool(rank and rank <= 5), "expected_slots": expected_slots})
            for evaluation, source_rank in zip(evaluations, within_source):
                evaluation["expected_top3"] = source_rank["top_3"]
                evaluation["expected_top3_to_final"] = source_rank["top_3"] and evaluation["passage_hit"]
                slots = evaluation["expected_slots"] = source_rank["expected_slots"]
                selected = service.retrieve(database, next(case["neutral_question"] for case in fixture["cases"] if case["case_id"] == evaluation["case_id"]), 5, fixture["corpus_version"])["final_five"]
                evaluation["expected_slot_assigned"] = bool(slots)
                evaluation["expected_slot_selected"] = any(item.get("chunk_id") in set(next(case["expected_passage_chunk_ids"] for case in fixture["cases"] if case["case_id"] == evaluation["case_id"])) and set(item.get("filled_slots", [])) & set(slots) for item in selected)
                adequacy = service.coverage.adequacy(selected, service.analyzer.analyze(next(case["neutral_question"] for case in fixture["cases"] if case["case_id"] == evaluation["case_id"])).as_dict())["metrics"]
                evaluation["required_slot_fill"] = adequacy.get("required_slots_filled", 0) / max(adequacy.get("required_slots_total", 0), 1)
                evaluation["preferred_slot_fill"] = adequacy.get("preferred_slots_filled", 0) / max(adequacy.get("preferred_slots_total", 0), 1)
            total = len(within_source)
            runs[name] = {"metrics": aggregate_metrics(evaluations), "within_source_metrics": {"Recall@1": sum(row["top_1"] for row in within_source) / total, "Recall@3": sum(row["top_3"] for row in within_source) / total, "Recall@5": sum(row["top_5"] for row in within_source) / total, "MRR": sum(1 / row["rank"] if row["rank"] else 0 for row in within_source) / total}, "cases": evaluations}
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(json.dumps({"fixture_sha256": frozen, "case_count": len(fixture["cases"]), "runs": runs}, indent=2) + "\n")
        print(json.dumps({"fixture_sha256": frozen, "case_count": len(fixture["cases"]), "metrics": {key: value["metrics"] for key, value in runs.items()}}, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()