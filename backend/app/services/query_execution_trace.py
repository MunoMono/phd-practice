"""Project query responses into auditable, production-neutral execution traces."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


class ExecutionOutcome(str, Enum):
    SUCCESS = "success"
    VALIDATED_BOUNDED_ANSWER = "validated_bounded_answer"
    SCOPED_LIMIT = "scoped_limit"
    SYNTHESIS_VALIDATION_ERROR = "explicit_synthesis_validation_error"
    RETRIEVAL_COVERAGE_ERROR = "retrieval_coverage_error"


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _stage_errors(stage_execution: Mapping[str, Any]) -> list[dict[str, Any]]:
    errors = []
    for stage, value in stage_execution.items():
        if not isinstance(value, Mapping):
            continue
        if value.get("status") == "failed" or value.get("parse_error"):
            errors.append({
                "stage": stage,
                "status": value.get("status"),
                "error": value.get("error") or value.get("parse_error"),
            })
    return errors


def _source_detail(source: Mapping[str, Any]) -> dict[str, Any]:
    provenance = source.get("provenance")
    provenance_pid = provenance.get("pid") if isinstance(provenance, Mapping) else None
    return {
        "source_pid": source.get("pid") or provenance_pid,
        "source_title": source.get("title") or source.get("source_title"),
        "source_date": source.get("source_date") or source.get("display_date"),
        "chunk_id": source.get("chunk_id"),
        "relation_derivation_if_any": source.get("archive_nomination") or source.get("relation_derivation"),
    }


def _outcome(response: Mapping[str, Any], answer: str, errors: list[dict[str, Any]]) -> ExecutionOutcome:
    diagnostics = response.get("retrieval_diagnostics") or {}
    coverage = diagnostics.get("source_family_coverage") or diagnostics.get("retrieval_adequacy") or {}
    selected_evidence = _items(response.get("retrieved_evidence"))
    authority_evidence = _items(response.get("authority_evidence"))
    coverage_failed = (
        coverage.get("requirements_satisfied") is False
        or str(coverage.get("status", "")).upper() in {"INSUFFICIENT", "RETRIEVAL_INSUFFICIENT"}
    )
    if (coverage_failed or not answer) and not selected_evidence and not authority_evidence:
        return ExecutionOutcome.RETRIEVAL_COVERAGE_ERROR
    if not answer or errors or response.get("answer_state") == "synthesis_unavailable":
        return ExecutionOutcome.SYNTHESIS_VALIDATION_ERROR
    if response.get("answer_state") == "evidential_limit" or "limit" in str(response.get("answer_origin", "")):
        return ExecutionOutcome.SCOPED_LIMIT
    if _items(response.get("missingness")):
        return ExecutionOutcome.VALIDATED_BOUNDED_ANSWER
    return ExecutionOutcome.SUCCESS


def build_query_execution_trace(
    response: Mapping[str, Any],
    *,
    external_test_id: str | None,
    question_text: str,
    question_classification: str | None = None,
) -> dict[str, Any]:
    """Build a stable trace from fields the endpoint actually returned."""
    retrieval = response.get("retrieval") or {}
    stage_execution = response.get("stage_execution") or {}
    selected_sources = _items(response.get("retrieved_evidence"))
    errors = _items(response.get("errors")) + _stage_errors(stage_execution)
    answer = str(response.get("answer") or "").strip()
    source_details = [_source_detail(source) for source in selected_sources]
    resolved_entities = _items(retrieval.get("resolved_entities"))
    retrieval_contract = retrieval.get("retrieval_contract") or {}
    trace = {
        "trace_schema": "query-execution-trace-v1",
        "run_id": response.get("run_id") or response.get("query_id"),
        "uat_id_or_external_test_id": external_test_id,
        "question_text": question_text,
        "question_classification": question_classification or stage_execution.get("classification"),
        "retrieval_mode": retrieval.get("strategy") or response.get("mode"),
        "route_decision": retrieval.get("route_decision"),
        "resolved_presets": [retrieval["archive_question_preset"]] if retrieval.get("archive_question_preset") else [],
        "authority_lookups": _items(response.get("authority_evidence")),
        "retrieval_contract": retrieval_contract,
        "entity_anchors": _items(retrieval_contract.get("entity_anchors")) or resolved_entities,
        "project_anchors": _items(retrieval_contract.get("project_anchors")) or [
            item for item in resolved_entities if item.get("authority_type") in {"project", "ddr_projects"}
        ],
        "temporal_constraints": {
            "requirement": retrieval_contract.get("temporal_requirement", "none"),
            "buckets": _items(retrieval_contract.get("temporal_buckets")),
        },
        "candidate_sources": _items(response.get("archival_discovery")),
        "candidate_chunks": _items(response.get("candidate_chunks")),
        "document_availability": _items(response.get("document_availability")),
        "corpus_representation_gaps": _items(response.get("corpus_representation_gaps")),
        "retrieval_diagnostics": response.get("retrieval_diagnostics") or {},
        "selected_sources": selected_sources,
        "selected_chunks": [source for source in selected_sources if source.get("chunk_id")],
        "evidence_type_per_item": _items(response.get("evidence_ledger")) or _items(response.get("source_classifications")) or _items(response.get("evidence_cards")),
        "source_details": source_details,
        "claim_plan": response.get("final_claim_plan"),
        "claim_validation": response.get("claim_validation") or {},
        "missingness_decision": response.get("missingness_decision"),
        "model_input_evidence_ids": [
            source.get("source_id") or source.get("chunk_id")
            for source in selected_sources
            if source.get("source_id") or source.get("chunk_id")
        ],
        "raw_model_output": response.get("raw_model_output"),
        "inference_calls": _items(response.get("inference_calls")),
        "validated_claims": (response.get("provenance_validation") or {}).get("claim_provenance") or [],
        "rejected_or_qualified_claims": _items(response.get("rejected_evidence_cards")),
        "scoped_limit_state": _items(response.get("missingness")),
        "final_answer": answer or None,
        "ui_source_stack": _items(response.get("evidence_cards")) or selected_sources,
        "errors": errors,
        "latency_timing": response.get("timings") or {},
    }
    trace["execution_outcome"] = _outcome(response, answer, errors).value
    if not answer and not errors:
        trace["errors"] = [{"stage": "response", "error": "Query completed without an answer."}]
    return trace


def build_query_error_trace(
    *,
    run_id: str,
    external_test_id: str | None,
    question_text: str,
    question_classification: str | None,
    error: str,
    outcome: ExecutionOutcome = ExecutionOutcome.SYNTHESIS_VALIDATION_ERROR,
) -> dict[str, Any]:
    return {
        "trace_schema": "query-execution-trace-v1",
        "run_id": run_id,
        "uat_id_or_external_test_id": external_test_id,
        "question_text": question_text,
        "question_classification": question_classification,
        "execution_outcome": outcome.value,
        "final_answer": None,
        "errors": [{"stage": "execution", "error": error}],
    }