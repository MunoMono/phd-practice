"""Immutable Turin experiment orchestration and snapshot persistence."""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.research_outputs import ExperimentRun, ExperimentRunAssessment, ExperimentRunEvidence
from app.services.granite_service import get_granite_service
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService, _git_commit
from app.services.turin_experiment_service import AuthorityContext, ContextBuilder, GraniteExperimentService


class ExperimentRunRequest(BaseModel):
    research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"]
    research_question: str = Field(min_length=1)
    retrieval: RetrievalValidationRequest
    context_budget: int = Field(default=6000, gt=0)
    context_mode: Literal["document_only", "document_plus_authority_context"] = "document_only"
    authority_context: list[AuthorityContext] = Field(default_factory=list)
    fixture_only: bool = False


class ResearcherAssessmentInput(BaseModel):
    retrieval_relevance: int | None = Field(default=None, ge=0, le=3)
    provenance_accuracy: int | None = Field(default=None, ge=0, le=3)
    interpretative_restraint: int | None = Field(default=None, ge=0, le=3)
    preservation_of_contestation: int | None = Field(default=None, ge=0, le=3)
    missingness_handling: int | None = Field(default=None, ge=0, le=3)
    failure_categories: list[str] = Field(default_factory=list)
    notes: str | None = None
    authority_influence_note: str | None = None


def _snapshot(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def serialize_assessment(assessment: ExperimentRunAssessment | None) -> dict[str, Any] | None:
    if assessment is None:
        return None
    return {
        "retrieval_relevance": assessment.retrieval_relevance,
        "provenance_accuracy": assessment.provenance_accuracy,
        "interpretative_restraint": assessment.interpretative_restraint,
        "preservation_of_contestation": assessment.preservation_of_contestation,
        "missingness_handling": assessment.missingness_handling,
        "failure_categories": assessment.failure_categories_json or [],
        "notes": assessment.notes,
        "authority_influence_note": assessment.authority_influence_note,
        "assessed_at": assessment.assessed_at.isoformat() if assessment.assessed_at else None,
        "updated_at": assessment.updated_at.isoformat() if assessment.updated_at else None,
    }


def serialize_run(run: ExperimentRun, include_evidence: bool = True) -> dict[str, Any]:
    payload = {
        "run_id": run.run_id,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "locked_at": run.locked_at.isoformat() if run.locked_at else None,
        "research_case": run.research_case,
        "prompt": {"name": run.prompt_name, "version": run.prompt_version, "system_version": run.system_prompt_version, "question": run.exact_research_question},
        "corpus_version": run.corpus_version,
        "git_commit": run.git_commit,
        "retrieval_method": run.retrieval_method,
        "retrieval": run.retrieval_config_json,
        "retrieval_diagnostics": run.retrieval_diagnostics_json,
        "context": {"mode": run.context_mode, "character_count": run.context_character_count, "chunk_count": run.context_chunk_count, "omitted_chunk_ids": run.omitted_chunk_ids_json, "budget": run.context_budget_json},
        "authority_context": run.authority_context_json,
        "model": {"name": run.model_name, "runtime": run.model_runtime, "quantisation": run.model_quantisation, "parameters": run.model_parameters_json, "seed_if_actual": run.model_seed_if_actual, "inference_duration_ms": run.inference_duration_ms, "configuration": "deterministic-requested"},
        "raw_model_response": run.raw_model_response,
        "repair_attempted": run.repair_attempted,
        "raw_repair_response": run.raw_repair_response,
        "parse_status": run.parse_status,
        "structured_response": run.structured_response_json,
        "provenance_validation": run.provenance_validation_json,
        "status": run.status,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "fixture_only": bool(run.fixture_only),
        "classification": "FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN" if run.fixture_only else "ARCHIVAL EXPERIMENT RUN",
        "assessment": serialize_assessment(run.assessment),
    }
    if include_evidence:
        payload["retrieved_evidence"] = [{
            "rank": item.rank, "score": item.score, "document_id": item.document_id,
            "pid": item.pid, "archive_record_pid": item.archive_record_pid,
            "archive_resolution_status": item.archive_resolution_status,
            "page_start": item.page_start, "page_end": item.page_end,
            "chunk_id": item.chunk_id, "chunk_sequence": item.chunk_sequence,
            "excerpt": item.excerpt, "supplied_excerpt": item.supplied_excerpt, "included_in_context": item.included_in_context,
            "original_chars": item.original_chars, "supplied_chars": item.supplied_chars,
            "excerpted": item.excerpted, "exclusion_reason": item.exclusion_reason,
            "snapshot": item.snapshot_json,
        } for item in sorted(run.evidence or [], key=lambda evidence: evidence.rank)]
    return payload


def render_run_report(run: ExperimentRun) -> str:
    payload = serialize_run(run)
    context = payload["context"]
    lines = [
        f"# Turin experiment run {payload['run_id']}",
        "",
        f"- Status: {payload['status']}",
        f"- Failure code: {payload['error_code'] or 'none'}",
        f"- Failure message: {payload['error_message'] or 'none recorded'}",
        f"- Created: {payload['created_at']}",
        f"- Research case: {payload['research_case']}",
        f"- Corpus version: {payload['corpus_version']}",
        f"- Prompt: {payload['prompt']['name']} / {payload['prompt']['version']}",
        f"- Context builder: {(context['budget'] or {}).get('context_builder_version', 'legacy/unrecorded')}",
        "",
        "## Research question",
        payload["prompt"]["question"],
        "",
        "## Retrieval and source evidence",
    ]
    for item in payload.get("retrieved_evidence", []):
        state = "supplied" if item["included_in_context"] else f"not supplied ({item['exclusion_reason'] or 'budget'})"
        lines.extend([f"### Rank {item['rank']} · {item['chunk_id']}", f"PID: {item['pid']} · document: {item['document_id']} · page: {item['page_start']}", f"Score: {item['score']} · Context: {state} · Supplied characters: {item['supplied_chars'] or 0}/{item['original_chars'] or len(item['excerpt'])}", "", item["excerpt"], ""])
    lines.extend(["## Generated response", payload["raw_model_response"] or "No model response was generated.", "", "## Structured response", json.dumps(payload["structured_response"], indent=2), "", "## Provenance validation", json.dumps(payload["provenance_validation"], indent=2), "", "## Researcher assessment", json.dumps(payload["assessment"], indent=2), ""])
    return "\n".join(lines)


class ExperimentRunService:
    def __init__(self, retrieval_service: RetrievalValidationService | None = None, context_builder: ContextBuilder | None = None, granite_service: Any | None = None):
        self.retrieval_service = retrieval_service or RetrievalValidationService()
        self.context_builder = context_builder or ContextBuilder()
        self.granite_service = granite_service or get_granite_service()

    async def run_archival_experiment(self, db: Any, request: ExperimentRunRequest) -> ExperimentRun:
        retrieval = self.retrieval_service.retrieve(db, request.retrieval)
        context = self.context_builder.assemble_for_prompt(request.research_case, request.research_question, retrieval["results"], authority_context=request.authority_context, input_budget=request.context_budget, authority_mode=request.context_mode)
        if not retrieval["results"]:
            return self._persist(db, request, retrieval, context, None, ("zero_retrieval", "No source passage was retrieved by this query."))
        try:
            inference = await GraniteExperimentService(self.granite_service, self.context_builder).infer(request.research_case, request.research_question, context)
            error = None
            if inference["parsed"]["response"] is None:
                error = ("parse_failure", inference["parsed"].get("parse_error") or "Model response did not match the structured schema.")
            elif inference["provenance"] and not inference["provenance"]["valid"]:
                error = ("provenance_validation_failure", "; ".join(inference["provenance"]["issues"]))
            return self._persist(db, request, retrieval, context, inference, error)
        except Exception as exc:
            return self._persist(db, request, retrieval, context, None, ("granite_failure", f"{type(exc).__name__}: {exc}"))

    def _persist(self, db: Any, request: ExperimentRunRequest, retrieval: dict[str, Any], context: Any, inference: dict[str, Any] | None, error: tuple[str, str] | None) -> ExperimentRun:
        run_id = f"experiment-{uuid.uuid4().hex[:12]}"
        model = (inference or {}).get("model", {})
        parsed = (inference or {}).get("parsed", {})
        corpus_versions = retrieval.get("corpus_versions", [])
        run = ExperimentRun(
            run_id=run_id, research_case=request.research_case,
            prompt_name=(inference or {}).get("prompt_template", {}).get("prompt_name", f"turin_{request.research_case}"),
            prompt_version=(inference or {}).get("prompt_template", {}).get("prompt_version", "uninvoked"), system_prompt_version="v1",
            exact_research_question=request.research_question, corpus_version=corpus_versions[0] if len(corpus_versions) == 1 else None,
            git_commit=os.getenv("GIT_COMMIT") or _git_commit(), retrieval_method="postgresql_fts", retrieval_config_json=_snapshot(retrieval["transparency"]),
            retrieval_diagnostics_json=_snapshot(retrieval["diagnostics"]), context_mode=context.context_mode,
            context_character_count=context.context_character_count, context_chunk_count=context.document_chunk_count,
            omitted_chunk_ids_json=_snapshot(context.omitted_chunk_ids),
            context_budget_json=_snapshot({"context_builder_version": context.context_builder_version, "input_budget_chars": context.input_budget_chars, "fixed_prompt_chars": context.fixed_prompt_chars, "available_evidence_chars": context.available_evidence_chars, "assembled_input_chars": context.assembled_input_chars, "evidence_decisions": context.evidence_decisions}),
            authority_context_json=_snapshot({"used": bool(request.authority_context) and request.context_mode == "document_plus_authority_context", "version": "v1", "contexts": [item.model_dump() for item in request.authority_context]}),
            model_name=model.get("model_name"), model_runtime=model.get("runtime"), model_quantisation=model.get("quantized"),
            model_parameters_json=_snapshot((inference or {}).get("generation", {})), model_seed_if_actual="0" if (inference or {}).get("generation", {}).get("do_sample") is False else None,
            inference_duration_ms=((inference or {}).get("inference_duration_seconds") or 0) * 1000 if inference else None,
            raw_model_response=(inference or {}).get("raw_response"), repair_attempted=bool(parsed.get("repair_attempted", False)),
            raw_repair_response=parsed.get("repaired_response"), parse_status="parsed" if parsed.get("response") else ("not_invoked" if inference is None else "failed"),
            structured_response_json=_snapshot(parsed["response"]) if parsed.get("response") else None,
            provenance_validation_json=_snapshot((inference or {}).get("provenance")) if (inference or {}).get("provenance") is not None else None,
            status="completed" if error is None else "failed", error_code=error[0] if error else None, error_message=error[1] if error else None, fixture_only=request.fixture_only,
        )
        db.add(run)
        decisions = {item["chunk_id"]: item for item in context.evidence_decisions}
        supplied = {item["chunk_id"]: item for item in context.supplied_chunks}
        for result in retrieval["results"]:
            decision = decisions.get(result["chunk_id"], {})
            db.add(ExperimentRunEvidence(run_id=run_id, rank=result["rank"], score=result["score"], document_id=result["document_id"], pid=result.get("pid"), archive_record_pid=result.get("archive_record_pid"), archive_resolution_status=result["archive_resolution_status"], page_start=result.get("page_start"), page_end=result.get("page_end"), chunk_id=result["chunk_id"], chunk_sequence=result.get("chunk_sequence"), excerpt=result["text"], supplied_excerpt=supplied.get(result["chunk_id"], {}).get("text"), included_in_context=bool(decision.get("included_in_context")), original_chars=decision.get("original_chars"), supplied_chars=decision.get("supplied_chars"), excerpted=decision.get("excerpted"), exclusion_reason=decision.get("exclusion_reason"), snapshot_json=_snapshot(copy.deepcopy(result))))
        db.commit()
        db.refresh(run)
        return run

    def save_assessment(self, db: Any, run: ExperimentRun, input: ResearcherAssessmentInput) -> ExperimentRunAssessment:
        assessment = run.assessment or ExperimentRunAssessment(run_id=run.run_id)
        for field, value in input.model_dump().items():
            setattr(assessment, f"{field}_json" if field == "failure_categories" else field, value)
        assessment.assessed_at = datetime.now(timezone.utc)
        if assessment.id is None:
            db.add(assessment)
        run.assessment = assessment
        db.commit()
        db.refresh(assessment)
        return assessment