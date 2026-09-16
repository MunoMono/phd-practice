#!/usr/bin/env python3
"""Classify V3.1 passage failures inside the frozen neutral benchmark sources."""

import hashlib
import json
from pathlib import Path

from app.core.database import LocalSessionLocal
from app.services.turin_retrieval_v3_ranker import TurinRetrievalV3Ranker
from app.services.turin_retrieval_v3_service import TurinRetrievalV3Service

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "turin_v31_neutral_benchmark.json"
OUTPUT = ROOT / "artifacts" / "turin_v31_passage_failure_audit.json"


def fts_state(row):
    value = row.get("search_tsv")
    return "NULL" if value is None else "EMPTY" if str(value) == "" else "POPULATED"


def classify(expected, selected):
    if fts_state(expected) == "EMPTY":
        return "EMPTY_VECTOR_FAILURE"
    if expected["passage_score"] == selected["passage_score"]:
        return "TIE_BREAK_FAILURE"
    if expected["passage_score_components"]["entity_match"] == 0:
        return "ENTITY_ABSENT"
    if expected["passage_score_components"]["relation_match"] == 0 and selected["passage_score_components"]["relation_match"] > 0:
        return "RELATION_TERM_FAILURE"
    if expected["passage_score_components"]["phrase_proximity"] < selected["passage_score_components"]["phrase_proximity"]:
        return "PROXIMITY_FAILURE"
    if expected["passage_score_components"]["genericity_penalty"] > selected["passage_score_components"]["genericity_penalty"]:
        return "GENERICITY_FAILURE"
    return "FACET_SCORING_FAILURE"


def compact(row):
    return {"chunk_id": row["chunk_id"], "document_id": row["document_id"], "page": row.get("source_page"), "chunk_index": row["chunk_index"], "text": row["chunk_text"], "fts_state": fts_state(row), "passage_score": row["passage_score"], "components": row["passage_score_components"], "facets": row["facet_coverage"], "quality": "PASSAGE_IRRELEVANT" if row["passage_quality_exclusions"] else "CORE_FACETS_PRESENT" if row["facet_coverage"] else "CONTEXT_ONLY"}


def main():
    fixture = json.loads(FIXTURE.read_text())
    fingerprint = hashlib.sha256(json.dumps({key: value for key, value in fixture.items() if key != "sha256"}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if fingerprint != fixture["sha256"]:
        raise RuntimeError("Benchmark fixture fingerprint mismatch.")
    service = TurinRetrievalV3Service(use_authority_graph=True)
    database = LocalSessionLocal()
    try:
        misses = []
        for case in fixture["cases"]:
            analysis = service.analyzer.analyze(case["neutral_question"]).as_dict()
            rows = [TurinRetrievalV3Ranker.score_passage(row, analysis) for row in service._source_rows(database, case["expected_canonical_document_ids"][0], fixture["corpus_version"])]
            expected = next(row for row in rows if row["chunk_id"] in case["expected_passage_chunk_ids"])
            selected = max(rows, key=lambda row: (row["passage_score"], str(row["chunk_id"])))
            if expected["chunk_id"] != selected["chunk_id"]:
                misses.append({"benchmark_id": case["benchmark_id"], "question": case["neutral_question"], "expected_document": case["expected_canonical_document_ids"][0], "failure_class": classify(expected, selected), "expected": compact(expected), "selected": compact(selected), "ranking_trace": [compact(row) for row in sorted(rows, key=lambda row: (-row["passage_score"], str(row["chunk_id"])))[:10]]})
        counts = {label: sum(item["failure_class"] == label for item in misses) for label in sorted({item["failure_class"] for item in misses})}
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(json.dumps({"fixture_sha256": fingerprint, "case_count": len(fixture["cases"]), "misses": misses, "failure_counts": counts}, indent=2) + "\n")
        print(json.dumps({"fixture_sha256": fingerprint, "expected_source_passage_misses": len(misses), "failure_counts": counts}, indent=2))
    finally:
        database.close()


if __name__ == "__main__":
    main()