"""Immutable Turin experiment orchestration and snapshot persistence."""

from __future__ import annotations

import copy
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.models.research_outputs import ExperimentRun, ExperimentRunAssessment, ExperimentRunEvidence
from app.services.granite_service import get_granite_service
from app.services.retrieval_validation_service import QueryExpansion, RetrievalValidationRequest, RetrievalValidationService, _git_commit
from app.services.authority_registry import AuthorityRegistry
from app.services.turin_experiment_service import AuthorityContext, ContextBuilder, GraniteExperimentService


class ExperimentRunRequest(BaseModel):
    research_case: Literal["known_relationship", "contested_interpretation", "scoped_missingness"]
    research_question: str = Field(min_length=1)
    retrieval: RetrievalValidationRequest
    context_budget: int = Field(default=6000, gt=0)
    context_mode: Literal["document_only", "document_plus_authority_context"] = "document_only"
    authority_context: list[AuthorityContext] = Field(default_factory=list)
    authority_intent: str | None = None
    authority_missingness: dict[str, Any] | None = None
    fixture_only: bool = False


class ResearchInterrogationRequest(BaseModel):
    research_question: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    context_budget: int = Field(default=6000, gt=0)


YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")
YEAR_RANGE_PATTERN = re.compile(r"\b((?:19|20)\d{2})\s*(?:to|[-–/])\s*(\d{2,4})\b", re.IGNORECASE)
PROJECT_PATTERN = re.compile(r"\b(?:ddr\s+)?(?:job(?:s)?|project(?:s)?)\b", re.IGNORECASE)
PROJECT_RANGE_PATTERN = re.compile(r"\b(?:job(?:s)?|project(?:s)?)\s+(?:numbers?\s+)?(\d+)\s*(?:to|[-–])\s*(\d+)\b", re.IGNORECASE)
PROJECT_NUMBER_PATTERN = re.compile(r"\b(?:job|project)\s+(?:number\s+)?(\d+)\b", re.IGNORECASE)
DOCUMENTARY_PROJECT_PATTERN = re.compile(r"\b(?:archive|documentary|document(?:s|ary)?|source(?:s)?|evidence|suggest|imply|interpret)\b", re.IGNORECASE)
DOCUMENTARY_REQUEST_PATTERN = re.compile(r"\b(?:archive|documentary|document(?:s|ary)?|source(?:s)?|evidence|corpus|search|find|show|suggest|imply|interpret)\b", re.IGNORECASE)


@dataclass
class AuthorityResolution:
    contexts: list[AuthorityContext]
    intent: str | None = None
    requires_documentary_retrieval: bool = False
    missingness: dict[str, Any] | None = None


def requested_years(question: str) -> list[int]:
    return sorted({int(value) for value in YEAR_PATTERN.findall(question)})


def researcher_name_expansions(question: str) -> list[QueryExpansion]:
    names = re.findall(r"\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b", question)
    return [QueryExpansion(value=name) for name in dict.fromkeys(names)]


def project_intent(question: str, years: list[int]) -> tuple[str, tuple[int, int] | int | None, bool] | None:
    if not PROJECT_PATTERN.search(question):
        return None
    documentary = bool(DOCUMENTARY_PROJECT_PATTERN.search(question))
    range_match = PROJECT_RANGE_PATTERN.search(question)
    if range_match:
        start, end = sorted((int(range_match.group(1)), int(range_match.group(2))))
        return "project_job_range", (start, end), documentary
    number_match = PROJECT_NUMBER_PATTERN.search(question)
    if number_match:
        return "project_job", int(number_match.group(1)), documentary
    if years:
        return "project_year", years[0], documentary
    return "project_list", None, documentary


def authority_only_retrieval(question: str, top_k: int, intent: str) -> dict[str, Any]:
    return {
        "transparency": {
            "original_query": question,
            "normalised_query": question,
            "expanded_query": question,
            "query_expansions": [],
            "expansion_sources": [],
            "filters": {"corpus_version": "corpus_f40d78dbce52"},
            "top_k": top_k,
            "ranking_function": None,
            "retrieval_method": "authority_only",
            "authority_intent": intent,
            "documentary_retrieval": "not_requested_for_structured_authority_question",
        },
        "results": [],
        "diagnostics": {"result_count": 0, "notes": ["Documentary retrieval was not requested for this structured authority question."]},
        "corpus_versions": ["corpus_f40d78dbce52"],
    }


def temporal_basis_for_year(result: dict[str, Any], year: int) -> str | None:
    metadata = result.get("catalogue_metadata") or {}
    candidates = [
        ("source text", str(result.get("text") or "")),
        ("catalogue date", str(metadata.get("date") or "")),
        ("document title", str(result.get("title") or "")),
    ]
    for label, value in candidates:
        if str(year) in value:
            return f"{label} explicitly names {year}"
        for match in YEAR_RANGE_PATTERN.finditer(value):
            start = int(match.group(1))
            end_token = match.group(2)
            end = int(end_token) if len(end_token) == 4 else (start // 100) * 100 + int(end_token)
            if start <= year <= end:
                return f"{label} records {match.group(0)}"
    return None


def apply_temporal_guardrail(retrieval: dict[str, Any], years: list[int]) -> dict[str, Any]:
    if not years:
        return retrieval

    guarded = copy.deepcopy(retrieval)
    accepted = []
    rejected = []
    for result in guarded["results"]:
        bases = {year: temporal_basis_for_year(result, year) for year in years}
        if all(bases.values()):
            result["temporal_basis"] = bases
            accepted.append(result)
        else:
            rejected.append({"chunk_id": result["chunk_id"], "missing_years": [year for year, basis in bases.items() if basis is None]})
    guarded["results"] = accepted
    guarded["diagnostics"] = {
        **guarded["diagnostics"],
        "requested_years": years,
        "temporally_valid_result_count": len(accepted),
        "temporal_rejections": rejected,
    }
    guarded["transparency"] = {
        **guarded["transparency"],
        "temporal_guardrail": {"requested_years": years, "rejected_chunk_ids": [item["chunk_id"] for item in rejected]},
        "result_count": len(accepted),
    }
    return guarded


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
    structured_response = run.structured_response_json or {}
    if run.provenance_validation_json and not run.provenance_validation_json.get("valid", False):
        interpretative_status = "provenance_warning"
    elif run.status == "completed_with_missingness" or structured_response.get("missingness"):
        interpretative_status = "researcher_review_required"
    elif run.status == "failed":
        interpretative_status = "unsupported"
    else:
        interpretative_status = "unassessed"
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
        "interpretative_status": interpretative_status,
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
        self.authority_registry = AuthorityRegistry()

    async def run_archival_experiment(self, db: Any, request: ExperimentRunRequest) -> ExperimentRun:
        retrieval = self.retrieval_service.retrieve(db, request.retrieval)
        return await self._run_with_retrieval(db, request, retrieval)

    def resolve_authority_context(self, db: Any, question: str, years: list[int]) -> list[AuthorityContext]:
        return self.resolve_authority_resolution(db, question, years).contexts

    def resolve_authority_resolution(self, db: Any, question: str, years: list[int]) -> AuthorityResolution:
        intent = project_intent(question, years)
        if intent:
            resolution = self.resolve_project_authority_context(db, *intent, question=question)
            lead_names = [context.fields.get("project_lead_name") for context in resolution.contexts if context.fields.get("project_lead_name")]
            if lead_names and re.search(r"\b(?:lead(?:ing)?|projects? did)\b", question, re.IGNORECASE):
                resolution.contexts.extend(self.resolve_named_staff_context(db, lead_names, years))
            return resolution

        if not re.search(r"\b(who\s+worked|staff|worked\s+at|employment|head of department)\b", question, re.IGNORECASE):
            contexts = self.authority_registry.resolve(db, question)
            if not contexts:
                selected = self.authority_registry.selected_types(question)
                return AuthorityResolution(
                    contexts=[],
                    intent=selected[0] if selected else None,
                    missingness={"scope": "database authority", "category": "no_matching_authority_record", "explanation": "The supplied database authority does not establish a matching record. This does not establish historical absence.", "follow_up_action": "Refine the authority term or review the authority register."} if selected else None,
                )
            selected_types = sorted({context.authority_type for context in contexts})
            return AuthorityResolution(
                contexts=contexts,
                intent="+".join(selected_types),
                requires_documentary_retrieval=bool(DOCUMENTARY_REQUEST_PATTERN.search(question)),
            )

        requested_year = years[0] if len(years) == 1 else None
        rows = db.execute(
            text(
                """
                SELECT authority_id, label, metadata
                FROM database_authorities
                WHERE authority_type = 'agent_employment'
                  AND (:year_start IS NULL OR COALESCE(metadata->>'start_date', '0000-01-01') <= :year_end)
                  AND (:year_end IS NULL OR COALESCE(metadata->>'end_date', '9999-12-31') >= :year_start)
                ORDER BY label
                """
            ),
            {
                "year_start": f"{requested_year}-01-01" if requested_year else None,
                "year_end": f"{requested_year}-12-31" if requested_year else None,
            },
        ).mappings().all()
        return AuthorityResolution(contexts=[
            AuthorityContext(
                source="database_authorities.agent_employment",
                authority_type="agent_employment",
                authority_id=row["authority_id"],
                role="structural_context",
                fields={"name": row["label"], **dict(row["metadata"] or {}), "requested_year": requested_year},
            )
            for row in rows
        ], intent="staff_employment", requires_documentary_retrieval=True)

    def resolve_named_staff_context(self, db: Any, names: list[str], years: list[int]) -> list[AuthorityContext]:
        requested_year = years[0] if len(years) == 1 else None
        rows = db.execute(text("SELECT authority_id, label, metadata FROM database_authorities WHERE authority_type = 'agent_employment' ORDER BY label")).mappings().all()
        contexts = []
        for row in rows:
            metadata = dict(row["metadata"] or {})
            if row["label"] not in names:
                continue
            start, end = metadata.get("start_date"), metadata.get("end_date")
            if requested_year and start and end and not (str(start)[:4] <= str(requested_year) <= str(end)[:4]):
                continue
            contexts.append(AuthorityContext(source="database_authorities.agent_employment", authority_type="agent_employment", authority_id=row["authority_id"], role="structural_context", fields={"name": row["label"], **metadata, "requested_year": requested_year, "authority_join": "project_lead_name matched agent_employment.label"}))
        return contexts

    def resolve_project_authority_context(self, db: Any, intent: str, criterion: tuple[int, int] | int | None, requires_documentary_retrieval: bool, question: str = "") -> AuthorityResolution:
        rows = db.execute(
            text("""
                SELECT authority_id, label, metadata
                FROM database_authorities
                WHERE authority_type = 'ddr_projects'
                  AND authority_id ~ '^[0-9]+$'
                ORDER BY authority_id::integer
            """)
        ).mappings().all()
        question_text = question.lower()
        lead_matches = [row for row in rows if (row["metadata"] or {}).get("project_lead_name") and str((row["metadata"] or {})["project_lead_name"]).lower() in question_text]
        funder_matches = [row for row in rows if (row["metadata"] or {}).get("funder_name") and str((row["metadata"] or {})["funder_name"]).lower() in question_text]

        def project_context(row: dict[str, Any], filter_description: str) -> AuthorityContext:
            metadata = dict(row["metadata"] or {})
            return AuthorityContext(
                source="database_authorities.ddr_projects",
                authority_type="ddr_projects",
                authority_id=str(row["authority_id"]),
                role="structural_context",
                fields={
                    "job_number": int(row["authority_id"]),
                    "title": row["label"],
                    "funder_name": metadata.get("funder_name"),
                    "duration_text": metadata.get("duration_text"),
                    "project_lead_name": metadata.get("project_lead_name"),
                    "start_year": metadata.get("start_year"),
                    "end_year": metadata.get("end_year"),
                    "authority_filter": filter_description,
                },
            )

        if intent == "project_job_range":
            start, end = criterion
            selected = [row for row in rows if start <= int(row["authority_id"]) <= end]
            return AuthorityResolution(
                contexts=[project_context(row, f"job_number between {start} and {end}") for row in selected],
                intent=intent,
                requires_documentary_retrieval=requires_documentary_retrieval,
                missingness=None if selected else {"scope": "project authority", "category": "no_matching_job_numbers", "explanation": f"The supplied project authority has no job-number records between {start} and {end}. This does not establish historical absence.", "follow_up_action": "Review the project authority register or refine the numeric range."},
            )
        if intent == "project_job":
            selected = [row for row in rows if int(row["authority_id"]) == criterion]
            return AuthorityResolution(
                contexts=[project_context(row, f"job_number equals {criterion}") for row in selected],
                intent=intent,
                requires_documentary_retrieval=requires_documentary_retrieval,
                missingness=None if selected else {"scope": "project authority", "category": "no_matching_job_number", "explanation": f"The supplied project authority has no record for job {criterion}. This does not establish historical absence.", "follow_up_action": "Review the project authority register or refine the job number."},
            )
        if intent == "project_year":
            year = int(criterion)
            temporal_rows = []
            for row in rows:
                metadata = dict(row["metadata"] or {})
                start_year = metadata.get("start_year")
                end_year = metadata.get("end_year")
                start = int(start_year) if isinstance(start_year, int) or str(start_year).isdigit() else None
                end = int(end_year) if isinstance(end_year, int) or str(end_year).isdigit() else None
                if start is not None or end is not None:
                    temporal_rows.append((row, start, end))
            if not temporal_rows:
                return AuthorityResolution(contexts=[], intent=intent, missingness={"scope": "project authority", "category": "insufficient_project_temporal_authority", "explanation": f"The supplied project authority does not contain explicit start or end years sufficient to identify projects intersecting {year}.", "follow_up_action": "Refresh the project authority with explicit project dates before making a year-based project list."})
            selected = [row for row, start, end in temporal_rows if (start or end) <= year <= (end or start)]
            if lead_matches:
                selected = [row for row in selected if row in lead_matches]
            if funder_matches:
                selected = [row for row in selected if row in funder_matches]
            return AuthorityResolution(
                contexts=[project_context(row, f"explicit project year intersects {year}") for row in selected],
                intent=intent,
                requires_documentary_retrieval=requires_documentary_retrieval,
                missingness=None if selected else {"scope": "project authority", "category": "no_projects_with_explicit_dates_for_year", "explanation": f"No supplied project-authority record with an explicit start or end year intersects {year}. This does not establish historical absence.", "follow_up_action": "Review dated project register records for the requested year."},
            )
        selected = lead_matches or funder_matches or rows
        filter_description = "project_lead_name matched question" if lead_matches else "funder_name matched question" if funder_matches else "all project authority records"
        return AuthorityResolution(
            contexts=[project_context(row, filter_description) for row in selected],
            intent=intent,
            requires_documentary_retrieval=requires_documentary_retrieval,
        )

    async def run_research_interrogation(self, db: Any, request: ResearchInterrogationRequest) -> ExperimentRun:
        years = requested_years(request.research_question)
        resolution = self.resolve_authority_resolution(db, request.research_question, years)
        authority_context = resolution.contexts
        if resolution.intent and not resolution.requires_documentary_retrieval:
            retrieval = authority_only_retrieval(request.research_question, request.top_k, resolution.intent)
        elif resolution.intent and resolution.missingness:
            retrieval = authority_only_retrieval(request.research_question, request.top_k, resolution.intent)
        else:
            project_expansions = [
                QueryExpansion(value=context.fields["title"], source="database_authority", authority_source=context.source, authority_id=context.authority_id, authority_field="title", authority_role="controlled_query_expansion")
                for context in authority_context if context.authority_type == "ddr_projects"
            ]
            retrieval = self.retrieval_service.retrieve(
                db,
                RetrievalValidationRequest(
                    query=request.research_question,
                    top_k=request.top_k,
                    corpus_version="corpus_f40d78dbce52",
                    expansions=[*researcher_name_expansions(request.research_question), *project_expansions],
                ),
            )
            retrieval = apply_temporal_guardrail(retrieval, years)
        research_case = "scoped_missingness" if re.search(r"\b(women|woman|gender|demographic)\b", request.research_question, re.IGNORECASE) else "known_relationship"
        experiment_request = ExperimentRunRequest(
            research_case=research_case,
            research_question=request.research_question,
            retrieval=RetrievalValidationRequest(query=request.research_question, top_k=request.top_k, corpus_version="corpus_f40d78dbce52"),
            context_budget=request.context_budget,
            context_mode="document_plus_authority_context" if authority_context else "document_only",
            authority_context=authority_context,
            authority_intent=resolution.intent,
            authority_missingness=resolution.missingness,
        )
        return await self._run_with_retrieval(db, experiment_request, retrieval)

    async def _run_with_retrieval(self, db: Any, request: ExperimentRunRequest, retrieval: dict[str, Any]) -> ExperimentRun:
        context = self.context_builder.assemble_for_prompt(request.research_case, request.research_question, retrieval["results"], authority_context=request.authority_context, input_budget=request.context_budget, authority_mode=request.context_mode)
        if not retrieval["results"]:
            if request.authority_context:
                return self._persist_authority_only(db, request, retrieval, context)
            if request.authority_missingness:
                return self._persist_authority_missingness(db, request, retrieval, context)
            return self._persist_scoped_missingness(db, request, retrieval, context)
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

    def _persist_scoped_missingness(self, db: Any, request: ExperimentRunRequest, retrieval: dict[str, Any], context: Any) -> ExperimentRun:
        years = retrieval.get("diagnostics", {}).get("requested_years", [])
        time_scope = f" for {', '.join(map(str, years))}" if years else ""
        no_evidence_explanation = "No retrieved source passage had an explicit temporal basis for the requested claim." if years else "No source passage was retrieved by this query."
        response = {
            "answer": "The supplied authority and retrieved corpus do not establish this.",
            "evidence": [],
            "inferences": [],
            "contradictions": [],
            "missingness": [{"scope": f"retrieved corpus{time_scope}", "category": "insufficient_temporally_valid_evidence" if years else "zero_retrieval", "explanation": no_evidence_explanation, "follow_up_action": "Locate dated staff records, correspondence, or authority entries for the requested year." if years else "Try a narrower person, project, or document query."}],
            "follow_up_queries": ["Search dated staff records for the requested year." if years else "Search for a named person, project, or document."],
            "authority_assertions": [],
        }
        inference = {
            "parsed": {"response": response, "repair_attempted": False, "repaired_response": None},
            "provenance": {"valid": True, "checked_claims": 0, "valid_claims": 0, "invalid_claims": 0, "issues": []},
            "model": {},
            "generation": {},
            "inference_duration_seconds": 0,
            "prompt_template": {"prompt_name": "turin_scoped_missingness", "prompt_version": "v3"},
            "raw_response": None,
        }
        return self._persist(db, request, retrieval, context, inference, None, status_override="completed_with_missingness")

    def _persist_authority_only(self, db: Any, request: ExperimentRunRequest, retrieval: dict[str, Any], context: Any) -> ExperimentRun:
        if any(item.authority_type == "ddr_projects" for item in request.authority_context):
            documentary_retrieval = retrieval["transparency"].get("retrieval_method", "postgresql_fts") == "postgresql_fts"
            response = {
                "answer": "Matching DDR project records are listed as database authority context." if not documentary_retrieval else "Matching DDR project records are listed as database authority context; no documentary source passage was retrieved.",
                "evidence": [],
                "inferences": [],
                "contradictions": [],
                "missingness": [] if not documentary_retrieval else [{"scope": "documentary evidence", "category": "no_documentary_retrieval_for_resolved_project", "explanation": "The project authority resolved the requested job, but the eligible corpus retrieval returned no documentary source passage.", "follow_up_action": "Refine the archive query or locate source records that document this project."}],
                "follow_up_queries": [] if not documentary_retrieval else ["Search the archive using the project title and related DDR report references."],
                "authority_assertions": [],
            }
            inference = {"parsed": {"response": response, "repair_attempted": False, "repaired_response": None}, "provenance": {"valid": True, "checked_claims": 0, "valid_claims": 0, "invalid_claims": 0, "issues": []}, "model": {}, "generation": {}, "inference_duration_seconds": 0, "prompt_template": {"prompt_name": "turin_project_authority_only", "prompt_version": "v1"}, "raw_response": None}
            return self._persist(db, request, retrieval, context, inference, None, status_override="completed_with_missingness" if documentary_retrieval else "completed")
        if any(item.authority_type != "agent_employment" for item in request.authority_context):
            interpretative = any(item.fields.get("epistemic_type") == "interpretative_analytical" for item in request.authority_context)
            documentary_retrieval = retrieval["transparency"].get("retrieval_method", "postgresql_fts") == "postgresql_fts"
            response = {
                "answer": "Matching database classification records are listed separately; they are system classifications, not source-document assertions." if interpretative else "Matching database authority records are listed as database authority context.",
                "evidence": [], "inferences": [], "contradictions": [],
                "missingness": [] if not documentary_retrieval else [{"scope": "documentary evidence", "category": "no_documentary_retrieval_for_authority", "explanation": "The selected database authority resolved the requested classification, but eligible corpus retrieval returned no documentary source passage.", "follow_up_action": "Refine the archive query or locate source records for the selected authority term."}],
                "follow_up_queries": [] if not documentary_retrieval else ["Search the archive using the selected authority label."], "authority_assertions": [],
            }
            inference = {"parsed": {"response": response, "repair_attempted": False, "repaired_response": None}, "provenance": {"valid": True, "checked_claims": 0, "valid_claims": 0, "invalid_claims": 0, "issues": []}, "model": {}, "generation": {}, "inference_duration_seconds": 0, "prompt_template": {"prompt_name": "turin_registry_authority_only", "prompt_version": "v1"}, "raw_response": None}
            return self._persist(db, request, retrieval, context, inference, None, status_override="completed_with_missingness" if documentary_retrieval else "completed")
        response = {
            "answer": "Database authority records with tenure spanning the requested year are listed separately. The retrieved corpus does not establish a documentary staffing claim for that year.",
            "evidence": [],
            "inferences": [],
            "contradictions": [],
            "missingness": [{"scope": "documentary evidence", "category": "no_temporally_valid_documentary_support", "explanation": "No retrieved source passage had an explicit temporal basis for the requested staffing claim.", "follow_up_action": "Locate dated staff lists, correspondence, or reports for the requested year."}],
            "follow_up_queries": ["Search dated staff lists for the requested year."],
            "authority_assertions": [],
        }
        inference = {
            "parsed": {"response": response, "repair_attempted": False, "repaired_response": None},
            "provenance": {"valid": True, "checked_claims": 0, "valid_claims": 0, "invalid_claims": 0, "issues": []},
            "model": {},
            "generation": {},
            "inference_duration_seconds": 0,
            "prompt_template": {"prompt_name": "turin_authority_only", "prompt_version": "v1"},
            "raw_response": None,
        }
        return self._persist(db, request, retrieval, context, inference, None, status_override="completed_with_missingness")

    def _persist_authority_missingness(self, db: Any, request: ExperimentRunRequest, retrieval: dict[str, Any], context: Any) -> ExperimentRun:
        response = {"answer": "The supplied project authority cannot establish this structured project list.", "evidence": [], "inferences": [], "contradictions": [], "missingness": [request.authority_missingness], "follow_up_queries": [], "authority_assertions": []}
        inference = {"parsed": {"response": response, "repair_attempted": False, "repaired_response": None}, "provenance": {"valid": True, "checked_claims": 0, "valid_claims": 0, "invalid_claims": 0, "issues": []}, "model": {}, "generation": {}, "inference_duration_seconds": 0, "prompt_template": {"prompt_name": "turin_project_authority_missingness", "prompt_version": "v1"}, "raw_response": None}
        return self._persist(db, request, retrieval, context, inference, None, status_override="completed_with_missingness")

    def _persist(self, db: Any, request: ExperimentRunRequest, retrieval: dict[str, Any], context: Any, inference: dict[str, Any] | None, error: tuple[str, str] | None, status_override: str | None = None) -> ExperimentRun:
        run_id = f"experiment-{uuid.uuid4().hex[:12]}"
        model = (inference or {}).get("model", {})
        parsed = (inference or {}).get("parsed", {})
        structured_response = parsed.get("response")
        parse_status = "parsed" if structured_response else ("not_invoked" if inference is None else "failed")
        if error and error[0] in {"provenance_validation_failure", "parse_failure"}:
            failure_label = "provenance validation" if error[0] == "provenance_validation_failure" else "structured response validation"
            structured_response = {
                "answer": f"No generated documentary claim is shown because {failure_label} failed.",
                "evidence": [],
                "inferences": [],
                "contradictions": [],
                "missingness": [{"scope": "generated response", "category": error[0], "explanation": error[1], "follow_up_action": "Review the preserved raw model response and retrieved evidence."}],
                "follow_up_queries": [],
                "authority_assertions": [],
            }
            parse_status = "parsed_with_provenance_failure" if error[0] == "provenance_validation_failure" else "failed_with_safe_response"
        corpus_versions = retrieval.get("corpus_versions", [])
        run = ExperimentRun(
            run_id=run_id, research_case=request.research_case,
            prompt_name=(inference or {}).get("prompt_template", {}).get("prompt_name", f"turin_{request.research_case}"),
            prompt_version=(inference or {}).get("prompt_template", {}).get("prompt_version", "uninvoked"), system_prompt_version="v1",
            exact_research_question=request.research_question, corpus_version=corpus_versions[0] if len(corpus_versions) == 1 else None,
            git_commit=os.getenv("GIT_COMMIT") or _git_commit(), retrieval_method=retrieval["transparency"].get("retrieval_method", "postgresql_fts"), retrieval_config_json=_snapshot(retrieval["transparency"]),
            retrieval_diagnostics_json=_snapshot(retrieval["diagnostics"]), context_mode=context.context_mode,
            context_character_count=context.context_character_count, context_chunk_count=context.document_chunk_count,
            omitted_chunk_ids_json=_snapshot(context.omitted_chunk_ids),
            context_budget_json=_snapshot({"context_builder_version": context.context_builder_version, "input_budget_chars": context.input_budget_chars, "fixed_prompt_chars": context.fixed_prompt_chars, "available_evidence_chars": context.available_evidence_chars, "assembled_input_chars": context.assembled_input_chars, "evidence_decisions": context.evidence_decisions}),
            authority_context_json=_snapshot({"used": bool(request.authority_context) and request.context_mode == "document_plus_authority_context", "version": "v1", "contexts": [item.model_dump() for item in request.authority_context]}),
            model_name=model.get("model_name"), model_runtime=model.get("runtime"), model_quantisation=model.get("quantized"),
            model_parameters_json=_snapshot((inference or {}).get("generation", {})), model_seed_if_actual="0" if (inference or {}).get("generation", {}).get("do_sample") is False else None,
            inference_duration_ms=((inference or {}).get("inference_duration_seconds") or 0) * 1000 if inference else None,
            raw_model_response=(inference or {}).get("raw_response"), repair_attempted=bool(parsed.get("repair_attempted", False)),
            raw_repair_response=parsed.get("repaired_response"), parse_status=parse_status,
            structured_response_json=_snapshot(structured_response) if structured_response else None,
            provenance_validation_json=_snapshot((inference or {}).get("provenance")) if (inference or {}).get("provenance") is not None else None,
            status=status_override or ("completed" if error is None else "failed"), error_code=error[0] if error else None, error_message=error[1] if error else None, fixture_only=request.fixture_only,
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