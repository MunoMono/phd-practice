#!/usr/bin/env python3
"""Evaluate Qwen once per registered Turin question using frozen archive-first evidence."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.inference_service import InferenceService


PROTOCOL_VERSION = "turin-archive-first-qwen-evaluation-v1"
SUCCESSOR_CORPUS_VERSION = "corpus_turin_archive_first_cc11e8678168"
ARCHIVE_SNAPSHOT_VERSION = "turin-archive-asset-snapshot-v1"
MODEL_NAME = "qwen3:8b-q4_K_M"
OUTPUT_DIR = BACKEND_ROOT / "artifacts"
REVIEW_PATH = OUTPUT_DIR / "turin_archive_first_q01_q12_retrieval_review_20260903.json"
HISTORICAL_EXPORT_PATH = OUTPUT_DIR / "turin-qwen-v2-final-governed-export-20260903.json"
QUESTION_ORDER = ("Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08", "Q09", "Q10", "Q11", "Q12")


class CitedStatement(BaseModel):
    statement: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list, max_length=8)


class QwenEvidenceResponse(BaseModel):
    direct_documentary_evidence: list[CitedStatement] = Field(default_factory=list, max_length=10)
    cross_source_interpretation: list[CitedStatement] = Field(default_factory=list, max_length=8)
    contested_or_qualified_evidence: list[CitedStatement] = Field(default_factory=list, max_length=8)
    what_the_evidence_does_not_establish: list[CitedStatement] = Field(default_factory=list, max_length=8)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _source_context(question: dict[str, Any]) -> list[dict[str, Any]]:
    nominations = {
        item["asset_pid"]: item for item in question["archive_nominated_assets"]
    }
    sources = []
    for index, passage in enumerate(question["selected_documentary_passages"], start=1):
        nomination = nominations.get(passage["asset_pid"], {})
        normalized_date = str(nomination.get("normalized_date") or "")
        year = int(normalized_date[:4]) if normalized_date[:4].isdigit() else None
        sources.append({
            "source_id": f"S{index}",
            "title": passage["source_identity"],
            "date": nomination.get("display_date"),
            "source_type": nomination.get("source_type"),
            "temporal_class": "contemporary DDR-era" if year is not None and year <= 1985 else "later/undated",
            "archive_identity": {"asset_pid": passage["asset_pid"], "asset_id": passage["asset_id"]},
            "page": passage["page"],
            "documentary_passage": passage["passage_excerpt"],
            "evidence_classification": passage["classification"],
        })
    return sources


def _prompt(question: str, sources: list[dict[str, Any]]) -> str:
    source_text = "\n\n".join(
        "\n".join((
            source["source_id"],
            f"Source title: {source['title']}",
            f"Date: {source['date'] or 'undated'}",
            f"Source type: {source['source_type'] or 'unspecified'}",
            f"Contemporary/retrospective: {source['temporal_class']}",
            f"Archive identity: {json.dumps(source['archive_identity'], sort_keys=True)}",
            f"Page: {source['page']}",
            f"Documentary passage: {source['documentary_passage']}",
            f"Evidence classification: {source['evidence_classification']}",
        )) for source in sources
    )
    return f"""You are evaluating a fixed archival documentary evidence set. Use only supplied documentary passages. Archive identity, date, source type, and evidence classification identify and contextualise sources; they are not documentary proof.

Return only JSON matching the requested schema with exactly these four substantive sections:
- direct_documentary_evidence
- cross_source_interpretation
- contested_or_qualified_evidence
- what_the_evidence_does_not_establish

Every substantive statement must cite supplied source IDs such as S1 in its sources array. In the cross-source section, explicitly label each statement as an inference. Do not invent or alter source IDs, archive IDs, pages, quotations, people, projects, titles, events, causation, reception, or historical absence. A source classified CONTEXTUAL must not be presented as direct documentary proof. State an empty array where no supported statement is available.

REGISTERED QUESTION
{question}

FIXED SOURCES
{source_text}
"""


def _validate_response(parsed: QwenEvidenceResponse, sources: list[dict[str, Any]], research_case: str) -> dict[str, Any]:
    source_ids = {source["source_id"] for source in sources}
    classifications = {source["source_id"]: source["evidence_classification"] for source in sources}
    sections = {
        "direct_documentary_evidence": parsed.direct_documentary_evidence,
        "cross_source_interpretation": parsed.cross_source_interpretation,
        "contested_or_qualified_evidence": parsed.contested_or_qualified_evidence,
        "what_the_evidence_does_not_establish": parsed.what_the_evidence_does_not_establish,
    }
    cited = [source for statements in sections.values() for statement in statements for source in statement.sources]
    unknown_sources = sorted(set(cited) - source_ids)
    direct_without_sources = [statement.statement for statement in parsed.direct_documentary_evidence if not statement.sources]
    contextual_promoted = [
        statement.statement for statement in parsed.direct_documentary_evidence
        if statement.sources and any(classifications.get(source) == "CONTEXTUAL" for source in statement.sources)
    ]
    unlabelled_inferences = [
        statement.statement for statement in parsed.cross_source_interpretation
        if "inference" not in statement.statement.lower()
    ]
    uses_unsupplied_identity = any(
        identity not in {str(value) for source in sources for value in source["archive_identity"].values()}
        for identity in __import__("re").findall(r"\b\d{12,64}\b", json.dumps(parsed.model_dump()))
    )
    issues = []
    if unknown_sources:
        issues.append(f"Unknown source references: {unknown_sources}")
    if direct_without_sources:
        issues.append("Direct documentary statements without source IDs")
    if contextual_promoted:
        issues.append("Contextual evidence promoted to direct fact")
    if uses_unsupplied_identity:
        issues.append("Unsupplied archive identity in generated response")
    return {
        "provenance_valid": not issues,
        "cited_sources_actually_supplied": not unknown_sources,
        "fabricated_source_identity": bool(unknown_sources or uses_unsupplied_identity),
        "direct_claims_linked_to_direct_or_partial_evidence": not contextual_promoted and not direct_without_sources,
        "contextual_evidence_promoted_to_direct_fact": bool(contextual_promoted),
        "cross_source_inference_explicitly_labelled": not unlabelled_inferences,
        "contested_evidence_acknowledged": bool(parsed.contested_or_qualified_evidence) if research_case == "contested_interpretation" else None,
        "evidential_limits_stated": bool(parsed.what_the_evidence_does_not_establish),
        "issues": issues,
    }


def _historical_comparison(question: dict[str, Any], mechanical: dict[str, Any], historical: dict[str, Any]) -> dict[str, Any]:
    old = historical.get(question["registered_question_id"])
    if old is None:
        return {"category": "DIFFERENT_BUT_NOT_CLEARLY_BETTER", "reference": None, "reason": "No matching historical V2 export record."}
    old_valid = bool(((old.get("provenance_validation_json") or {}).get("final_synthesis") or {}).get("valid"))
    if old.get("status") != "completed" and mechanical["provenance_valid"]:
        category, reason = "IMPROVED", "Historical V2 record did not complete; this fixed-evidence response completed with mechanical provenance checks."
    elif old_valid and not mechanical["provenance_valid"]:
        category, reason = "REGRESSED", "Historical V2 provenance passed while the new response has a visible mechanical provenance failure."
    elif old_valid and mechanical["provenance_valid"]:
        category, reason = "DIFFERENT_BUT_NOT_CLEARLY_BETTER", "Both outputs pass their available mechanical provenance checks; evidential quality needs researcher assessment."
    else:
        category, reason = "UNCHANGED", "Neither output supplies a mechanically clearer provenance advantage."
    return {"category": category, "reference": {"run_id": old.get("run_id"), "status": old.get("status")}, "reason": reason}


def _markdown(artifact: dict[str, Any]) -> str:
    lines = ["# Turin Archive-First Qwen Evaluation V1", "", f"- Protocol: `{PROTOCOL_VERSION}`", f"- Corpus: `{SUCCESSOR_CORPUS_VERSION}`", "- Retrieval rerun: `NO`", "- Historical runs modified: `NO`", "- Corpus modified: `NO`", ""]
    for item in artifact["questions"]:
        lines.extend([f"## {item['question_id']}", "", item["question"], "", f"Evidence fingerprint: `{item['evidence_set_fingerprint']}`", f"Provenance valid: `{item['mechanical_evaluation']['provenance_valid']}`", "", "### Raw model output", "", item["raw_model_output"], "", "### Researcher assessment", "", "| Field | Value |", "| --- | --- |", f"| Primary stress test | {item['research_case']} |", "| Evidence set quality |  |", "| Qwen direct-evidence handling |  |", "| Qwen cross-source inference |  |", "| Qwen treatment of contestation |  |", "| Qwen missingness handling |  |", f"| Provenance | {item['mechanical_evaluation']['provenance_valid']} |", "| Useful |  |", "| Overstated / flattened |  |", "| Research significance |  |", "", f"Historical comparison: `{item['historical_comparison']['category']}` - {item['historical_comparison']['reason']}", ""])
    return "\n".join(lines)


async def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUTPUT_DIR / f"turin_archive_first_qwen_evaluation_v1_{stamp}.json"
    markdown_path = OUTPUT_DIR / f"turin_archive_first_qwen_evaluation_v1_{stamp}.md"
    comparison_path = OUTPUT_DIR / f"turin_archive_first_qwen_vs_historical_v2_{stamp}.md"
    if any(path.exists() for path in (json_path, markdown_path, comparison_path)):
        raise RuntimeError("Archive-first Qwen evaluation artifact already exists; no inference retry is permitted.")
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    historical_runs = json.loads(HISTORICAL_EXPORT_PATH.read_text(encoding="utf-8"))["runs"]
    historical = {run["question_id"]: run for run in historical_runs}
    service = InferenceService()
    if service.provider != "remote_ollama" or service.model_name != MODEL_NAME or not service.check_remote_runtime():
        raise RuntimeError("The established remote Qwen runtime is not available with the required model identity.")
    model_config = {**service.get_model_info(), "think": False, "output_token_limit": service.final_synthesis_max_output_tokens}
    questions = []
    for question in sorted(review["questions"], key=lambda item: QUESTION_ORDER.index(item["question_id"])):
        sources = _source_context(question)
        evidence_fingerprint = _fingerprint({"question": question["exact_registered_question"], "sources": sources})
        prompt = _prompt(question["exact_registered_question"], sources)
        try:
            generated = await service.generate_experiment(prompt, max_tokens=service.final_synthesis_max_output_tokens, temperature=service.temperature, top_p=1.0, do_sample=False, response_schema=QwenEvidenceResponse.model_json_schema(), stage=f"{PROTOCOL_VERSION}:{question['question_id']}")
            raw = generated["raw_response"]
            parsed = QwenEvidenceResponse.model_validate_json(raw)
            mechanical = _validate_response(parsed, sources, question["research_dimensions_exercised"][0])
            status = "completed"
            error = None
        except Exception as exc:
            raw, parsed, mechanical, status, error = "", None, {"provenance_valid": False, "issues": [f"Infrastructure or schema failure: {type(exc).__name__}: {exc}"]}, "failed", f"{type(exc).__name__}: {exc}"
            generated = None
        record = {"question_id": question["question_id"], "registered_question_id": question["registered_question_id"], "question": question["exact_registered_question"], "research_case": question["research_dimensions_exercised"][0], "evidence_set_fingerprint": evidence_fingerprint, "fixed_evidence_sources": sources, "raw_model_output": raw, "parsed_model_output": parsed.model_dump() if parsed else None, "generation": generated.get("generation") if generated else None, "mechanical_evaluation": mechanical, "status": status, "error": error}
        record["historical_comparison"] = _historical_comparison(question, mechanical, historical)
        questions.append(record)
        (OUTPUT_DIR / f"turin_archive_first_qwen_evaluation_v1_{stamp}_{question['question_id'].lower()}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    artifact = {"protocol": PROTOCOL_VERSION, "run_timestamp_utc": datetime.now(timezone.utc).isoformat(), "corpus_version": SUCCESSOR_CORPUS_VERSION, "archive_snapshot_version": ARCHIVE_SNAPSHOT_VERSION, "retrieval_rerun": False, "historical_runs_modified": False, "corpus_modified": False, "model_runtime_config": model_config, "questions": questions}
    json_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    markdown = _markdown(artifact)
    markdown_path.write_text(markdown, encoding="utf-8")
    comparison_path.write_text(markdown, encoding="utf-8")
    print(json.dumps({"protocol": PROTOCOL_VERSION, "questions_attempted": len(questions), "questions_completed": sum(item["status"] == "completed" for item in questions), "provenance_passes": sum(item["mechanical_evaluation"].get("provenance_valid") for item in questions), "artifacts": [str(json_path), str(markdown_path), str(comparison_path)]}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())