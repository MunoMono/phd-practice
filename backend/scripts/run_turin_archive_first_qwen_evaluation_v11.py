#!/usr/bin/env python3
"""Run one governed v1.1 Qwen call per frozen archive-first evidence set."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.inference_service import InferenceService
from app.services.turin_archive_first_qwen_protocol_v11 import (
    OUTPUT_TOKEN_LIMIT,
    PROTOCOL_VERSION,
    build_compact_prompt,
    generation_record,
    parse_and_validate,
)


OUTPUT_DIR = BACKEND_ROOT / "artifacts"
REVIEW_PATH = OUTPUT_DIR / "turin_archive_first_q01_q12_retrieval_review_20260903.json"
V1_PATH = OUTPUT_DIR / "turin_archive_first_qwen_evaluation_v1_20260903.json"
OUTPUT_PATH = OUTPUT_DIR / "turin_archive_first_qwen_evaluation_v11_20260903.json"
MARKDOWN_PATH = OUTPUT_DIR / "turin_archive_first_qwen_evaluation_v11_20260903.md"
ASSESSMENT_PATH = OUTPUT_DIR / "turin_archive_first_qwen_v11_researcher_assessment_20260903.md"
COMPARISON_PATH = OUTPUT_DIR / "turin_archive_first_qwen_v11_vs_v1_vs_historical_20260903.md"
MODEL_NAME = "qwen3:8b-q4_K_M"
QUESTION_ORDER = ("Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08", "Q09", "Q10", "Q11", "Q12")


def source_context(question: dict) -> list[dict]:
    nominations = {item["asset_pid"]: item for item in question["archive_nominated_assets"]}
    sources = []
    for index, passage in enumerate(question["selected_documentary_passages"], start=1):
        nomination = nominations.get(passage["asset_pid"], {})
        normalized_date = str(nomination.get("normalized_date") or "")
        year = int(normalized_date[:4]) if normalized_date[:4].isdigit() else None
        sources.append({"source_id": f"S{index}", "title": passage["source_identity"], "date": nomination.get("display_date"), "source_type": nomination.get("source_type"), "temporal_class": "contemporary DDR-era" if year is not None and year <= 1985 else "later/undated", "page": passage["page"], "documentary_passage": passage["passage_excerpt"]})
    return sources


def fingerprint(question: str, sources: list[dict]) -> str:
    return hashlib.sha256(json.dumps({"question": question, "sources": sources}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def status(validation: dict, transport_error: str | None) -> str:
    if transport_error:
        return "TRANSPORT_FAILURE" if "http" in transport_error.lower() else "INFRASTRUCTURE_FAILURE"
    if "INVALID_JSON" in validation["flags"] or "SCHEMA_SHAPE_DEVIATION" in validation["flags"]:
        return "SCHEMA_FAILURE"
    return "COMPLETED_VALID" if validation["valid"] else "COMPLETED_WITH_VALIDATION_FAILURE"


def v1_reliability(v1: dict, v11_questions: list[dict]) -> dict:
    return {
        "v1": {"attempted": len(v1["questions"]), "valid_completions": sum(item["status"] == "completed" and item["mechanical_evaluation"].get("provenance_valid") for item in v1["questions"]), "schema_failures": sum(item["status"] == "failed" for item in v1["questions"]), "provenance_failures": sum(not item["mechanical_evaluation"].get("provenance_valid") for item in v1["questions"])},
        "v1_1": {"attempted": len(v11_questions), "valid_completions": sum(item["status"] == "COMPLETED_VALID" for item in v11_questions), "schema_failures": sum(item["status"] == "SCHEMA_FAILURE" for item in v11_questions), "transport_failures": sum(item["status"] == "TRANSPORT_FAILURE" for item in v11_questions), "infrastructure_failures": sum(item["status"] == "INFRASTRUCTURE_FAILURE" for item in v11_questions), "provenance_failures": sum(not item["generation_record"]["validation"]["valid"] for item in v11_questions), "mis_sectioned_limits": sum("MISSECTIONED_LIMIT" in item["generation_record"]["validation"]["flags"] for item in v11_questions), "uncited_claims": sum("UNCITED_CLAIM" in item["generation_record"]["validation"]["flags"] for item in v11_questions), "fabricated_source_identities": sum("INVALID_SOURCE_ID" in item["generation_record"]["validation"]["flags"] for item in v11_questions)},
    }


def report_template(artifact: dict) -> str:
    lines = ["# Turin Archive-First Qwen Evaluation v1.1", "", f"- Protocol: `{PROTOCOL_VERSION}`", "- Retrieval rerun: `NO`", "- Corpus modified: `NO`", "- Historical runs modified: `NO`", ""]
    for item in artifact["questions"]:
        validation = item["generation_record"]["validation"]
        lines.extend([f"## {item['question_id']}", "", item["exact_registered_question"], "", f"- Status: `{item['status']}`", f"- Validation flags: `{', '.join(validation['flags']) or 'NONE'}`", "", "### Raw generation", "", "```json", item["generation_record"]["raw_text"], "```", ""])
    return "\n".join(lines)


def assessment_template(artifact: dict) -> str:
    lines = ["# Turin Archive-First Qwen v1.1 Researcher Assessment", "", "Interpretive classifications are researcher-assigned, not inferred from provenance validation.", ""]
    for item in artifact["questions"]:
        lines.extend([f"## {item['question_id']}", "", f"- Structural status: `{item['status']}`", "- Interpretive outcome: `PENDING_RESEARCHER_REVIEW`", "- Contribution type: `PENDING_RESEARCHER_REVIEW`", "- Retrieval/evidence-surface effect: `PENDING_RESEARCHER_REVIEW`", "- Protocol-envelope effect: `PENDING_RESEARCHER_REVIEW`", "- Interpretive effect: `PENDING_RESEARCHER_REVIEW`", ""])
    return "\n".join(lines)


async def main() -> None:
    if any(path.exists() for path in (OUTPUT_PATH, MARKDOWN_PATH, ASSESSMENT_PATH, COMPARISON_PATH)):
        raise RuntimeError("v1.1 aggregate artifact already exists; no second inference attempt is permitted.")
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    v1 = json.loads(V1_PATH.read_text(encoding="utf-8"))
    service = InferenceService()
    if service.provider != "remote_ollama" or service.model_name != MODEL_NAME or not service.check_remote_runtime():
        raise RuntimeError("Required remote Qwen runtime is unavailable.")
    records = []
    for question in sorted(review["questions"], key=lambda item: QUESTION_ORDER.index(item["question_id"])):
        sources = source_context(question)
        prompt = build_compact_prompt(question["exact_registered_question"], sources)
        input_estimate = (len(prompt) + 3) // 4
        raw_text = None
        generation = None
        transport_error = None
        try:
            generated = await service.generate_experiment(prompt, max_tokens=OUTPUT_TOKEN_LIMIT, temperature=service.temperature, top_p=1.0, do_sample=False, response_schema=None, stage=f"{PROTOCOL_VERSION}:{question['question_id']}")
            raw_text, generation = generated["raw_response"], generated["generation"]
            parsed, validation = parse_and_validate(raw_text, {source["source_id"] for source in sources})
        except Exception as exc:
            parsed = None
            validation = {"valid": False, "parse_error": f"{type(exc).__name__}: {exc}", "flags": ["TRANSPORT_OR_INFRASTRUCTURE_FAILURE"]}
            transport_error = f"{type(exc).__name__}: {exc}"
        record = {"question_id": question["question_id"], "registered_question_id": question["registered_question_id"], "exact_registered_question": question["exact_registered_question"], "research_case": question["research_dimensions_exercised"][0], "evidence_set_fingerprint": fingerprint(question["exact_registered_question"], sources), "fixed_evidence_sources": sources, "generation_record": generation_record(raw_text, generation, parsed, validation, input_estimate), "status": status(validation, transport_error)}
        records.append(record)
        (OUTPUT_DIR / f"turin_archive_first_qwen_evaluation_v11_20260903_{question['question_id'].lower()}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    artifact = {"protocol": PROTOCOL_VERSION, "run_timestamp_utc": datetime.now(timezone.utc).isoformat(), "corpus_version": "corpus_turin_archive_first_cc11e8678168", "archive_snapshot_version": "turin-archive-asset-snapshot-v1", "retrieval_rerun": False, "corpus_modified": False, "historical_runs_modified": False, "model_runtime_config": {**service.get_model_info(), "think": False, "output_token_limit": OUTPUT_TOKEN_LIMIT}, "questions": records, "structural_reliability_vs_v1": v1_reliability(v1, records)}
    OUTPUT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    MARKDOWN_PATH.write_text(report_template(artifact), encoding="utf-8")
    ASSESSMENT_PATH.write_text(assessment_template(artifact), encoding="utf-8")
    COMPARISON_PATH.write_text(assessment_template(artifact), encoding="utf-8")
    print(json.dumps({"protocol": PROTOCOL_VERSION, "metrics": artifact["structural_reliability_vs_v1"], "artifacts": [str(path) for path in (OUTPUT_PATH, MARKDOWN_PATH, ASSESSMENT_PATH, COMPARISON_PATH)]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())