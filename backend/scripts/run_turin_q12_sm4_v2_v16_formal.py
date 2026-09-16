#!/usr/bin/env python3
"""Execute the one authorized SM4-v2 / v1.6 zero-documentary formal run."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun, TurinRetrievalPlan
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_protocol import RetrievalPlan
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.turin_experiment_service import CONCISE_RESPONSE_REQUIREMENT, ContextBuilder, V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION, response_schema_definition, response_schema_version, structured_output_max_tokens
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "SM4-v2"
QUESTION_ID = "SM4"
CORPUS_VERSION = "corpus_f40d78dbce52"
PROTOCOL = V16_ZERO_DOCUMENTARY_INFERENCE_PROTOCOL_VERSION
AUTHORIZATION_ID = "turin-q12-sm4-v2-v16-zero-documentary-primary-authorization"
EXPECTED_PARAMETERS = {"max_tokens": 1500, "temperature": 0.0, "top_p": 1.0, "do_sample": False, "granite_timeout_seconds": 1200}
EXPECTED_PROMPT_SHA256 = "37f84f56fc76ae9efea6f84f80f4303a5e7ec25226673f81bbcabff4c6056142"
EXPECTED_STRATA = [
    {"stratum_id": "contemporary", "classification": "contemporary DDR document", "top_k": 3, "year_from": 1973, "year_to": 1977, "source_type": "any"},
    {"stratum_id": "retrospective", "classification": "later retrospective account", "top_k": 2, "year_from": 1978, "year_to": None, "source_type": "any"},
]


class CapturingContextBuilder(ContextBuilder):
    """Retains the assembled context only to report the pre-inference contract."""

    captured = None

    def assemble_for_prompt(self, *args, **kwargs):
        self.captured = super().assemble_for_prompt(*args, **kwargs)
        return self.captured


def temporal_strata_snapshot(plan: RetrievalPlan) -> list[dict[str, object]]:
    return [
        {
            "stratum_id": stratum.stratum_id,
            "classification": stratum.classification,
            "top_k": stratum.top_k,
            "year_from": stratum.year_from,
            "year_to": stratum.year_to,
            "source_type": stratum.source_type,
        }
        for stratum in plan.temporal_strata
    ]


def load_preflight(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q12 formal execution is production-only.")
    stored = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored is None:
        raise RuntimeError("SM4-v2 is not registered.")
    plan = RetrievalPlan.model_validate(stored.plan_json)
    case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
    schema = response_schema_definition(PROTOCOL)
    if any((
        plan.question_id != QUESTION_ID, plan.plan_version != "2.0", plan.protocol_version != "turin-retrieval-protocol-v1.0",
        plan.top_k != 5, plan.run_classification != "primary", plan.retrieval_scope != "corpus_wide",
        plan.supersedes_plan_id != "SM4-v1", temporal_strata_snapshot(plan) != EXPECTED_STRATA,
        plan.authority_linked_document_ids or plan.authority_document_link_ids,
        stored.researcher_approval_state != "approved", plan.researcher_approval_state != "approved",
        case != "scoped_missingness", not question,
        structured_output_max_tokens(PROTOCOL) != 1500,
        response_schema_version(PROTOCOL) != "turin-archival-analysis-response-v1.5-concise",
        schema["properties"]["answer"].get("maxLength") != 180,
        any(schema["properties"][field].get("maxItems") != 1 for field in ("evidence", "inferences", "contradictions", "missingness", "follow_up_queries", "authority_assertions")),
        hashlib.sha256(CONCISE_RESPONSE_REQUIREMENT.encode()).hexdigest() != EXPECTED_PROMPT_SHA256,
    )):
        raise RuntimeError("SM4-v2/v1.6 preflight identity does not match the governed configuration.")
    plan.require_formal_approval()
    authorization = db.execute(text("SELECT question_id, plan_id, plan_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json, allow_zero_documentary_inference FROM turin_formal_protocol_authorizations WHERE authorization_id=:id"), {"id": AUTHORIZATION_ID}).mappings().one_or_none()
    if authorization is None or dict(authorization["model_parameters_json"]) != EXPECTED_PARAMETERS or any((
        authorization["question_id"] != QUESTION_ID, authorization["plan_id"] != PLAN_ID, authorization["plan_version"] != "2.0",
        authorization["execution_protocol_version"] != PROTOCOL, authorization["corpus_version"] != CORPUS_VERSION,
        authorization["retrieval_scope"] != "corpus_wide", authorization["run_classification"] != "primary",
        authorization["authorization_category"] != "q12_sm4_v2_v16_zero_documentary_primary_authorization",
        authorization["model_name"] != "granite3.1-dense:2b-instruct-q4_K_M", authorization["allow_zero_documentary_inference"] is not True,
    )):
        raise RuntimeError("Q12 requires its exact unconsumed SM4-v2/v1.6 zero-documentary authorization.")
    for label, sql, expected in (
        ("authorization consumption", "SELECT count(*) FROM experiment_runs WHERE formal_authorization_id=:id", 0),
        ("SM4 formal runs", "SELECT count(*) FROM experiment_runs WHERE question_id='SM4' AND fixture_only=false", 0),
        ("SM4 evaluable results", "SELECT count(*) FROM turin_formal_run_evaluability_classifications WHERE question_id='SM4'", 0),
    ):
        if db.execute(text(sql), {"id": AUTHORIZATION_ID}).scalar_one() != expected:
            raise RuntimeError(f"Q12 execution blocked: {label} is no longer {expected}.")
    ExperimentRunService._persist_plan_snapshot(db, plan)
    db.rollback()
    return plan


async def verify_write_ahead_shell(run: ExperimentRun, context_builder: CapturingContextBuilder) -> None:
    db = LocalSessionLocal()
    try:
        shell = db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).one_or_none()
        context = context_builder.captured
        if shell is None or context is None or any((
            shell.status != "running", shell.formal_authorization_id != AUTHORIZATION_ID, shell.question_id != QUESTION_ID,
            shell.retrieval_plan_id != PLAN_ID, shell.retrieval_plan_version != "2.0", shell.retrieval_protocol_version != PROTOCOL,
            shell.corpus_version != CORPUS_VERSION, shell.retrieval_scope != "corpus_wide", shell.retrieval_run_classification != "primary",
            shell.model_name != "granite3.1-dense:2b-instruct-q4_K_M", shell.model_parameters_json != EXPECTED_PARAMETERS,
            context.document_chunk_count != 0, context.authority_context_count != 1,
            "[DOCUMENTARY EVIDENCE]\nNo documentary passages were retrieved for this question." not in context.context,
            "[ARCHIVE / DATABASE AUTHORITY CONTEXT — NOT DOCUMENTARY EVIDENCE]" not in context.context,
        )):
            raise RuntimeError("Q12 write-ahead shell or zero-documentary context contract is invalid.")
        print(json.dumps({"write_ahead_shell": {"run_id": shell.run_id, "status": shell.status, "authorization_id": shell.formal_authorization_id, "question_id": shell.question_id, "plan_id": shell.retrieval_plan_id, "plan_version": shell.retrieval_plan_version, "protocol": shell.retrieval_protocol_version, "corpus": shell.corpus_version, "documentary_evidence_count": context.document_chunk_count, "authority_context_count": context.authority_context_count, "max_tokens": 1500, "timeout": 1200, "started_at": shell.created_at.isoformat()}}, default=str), flush=True)
        print(json.dumps({"deterministic_context": context.context}, ensure_ascii=False), flush=True)
    finally:
        db.close()


def audits(payload: dict) -> dict:
    response = payload.get("parsed_response") or {}
    provenance = payload.get("provenance_validation") or {}
    evidence = response.get("evidence") or []
    authority_assertions = response.get("authority_assertions") or []
    answer = str(response.get("answer") or "").lower()
    joined = json.dumps(response, ensure_ascii=False).lower()
    return {
        "provenance_audit": {"documentary_evidence_claims_emitted": len(evidence), "claims_checked": provenance.get("checked_claims"), "valid_claims": provenance.get("valid_claims"), "invalid_claims": provenance.get("invalid_claims"), "valid": provenance.get("valid"), "issues": provenance.get("issues", []), "fabricated_source_pids": [item.get("source_pid") for item in evidence], "fabricated_chunk_ids": [item.get("chunk_id") for item in evidence], "fabricated_quotations": [item.get("quotation_or_paraphrase") for item in evidence], "authority_claims": authority_assertions},
        "bounded_inference_audit": {"acknowledged_zero_documentary_evidence": "YES" if "no documentary" in joined or "no retrieved" in joined else "NO", "kept_authority_separate": "YES" if "authority" in joined and ("documentary" in joined or "document" in joined) else "PARTLY", "treated_title_as_structural": "YES" if "authority" in joined else "NO", "inferred_responsibilities": "YES" if any(term in answer for term in ("responsib", "duty", "duties")) else "NO", "inferred_research_activity": "YES" if "research activity" in joined else "NO", "inferred_practice_activity": "YES" if "practice activity" in joined else "NO", "inferred_leadership_or_seniority": "YES" if any(term in joined for term in ("leadership", "senior", "lead ")) else "NO", "inferred_continuity_beyond_authority_dates": "YES" if any(term in joined for term in ("after 1977", "beyond 1977", "continued")) else "NO", "unsupported_biographical_narrative": "YES" if len(answer) > 180 else "NO", "preserved_uncertainty": "YES" if any(term in joined for term in ("does not establish", "cannot establish", "insufficient", "no documentary")) else "NO"},
    }


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan = load_preflight(db)
        case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        service = ExperimentRunService()
        authority_resolution = service.resolve_authority_resolution(db, question, [1973, 1977])
        authorities = authority_resolution.contexts
        if len(authorities) != 1 or authorities[0].authority_id != "HENRIETTAR" or authorities[0].fields.get("job_title_label") != "Departmental Secretary (Research & Practice)" or authorities[0].fields.get("start_date") != "1973-01-01" or authorities[0].fields.get("end_date") != "1977-12-31":
            raise RuntimeError("Q12 authority context does not match the governed HENRIETTAR record.")
        granite = get_granite_service()
        if not granite.get_load_status().get("model_ready") and not granite.load_model():
            raise RuntimeError(f"Granite runtime could not load: {granite.get_load_status().get('last_error')}")
        if granite.timeout_seconds != 1200 or granite.max_input_chars != 6000 or granite.model_name != "granite3.1-dense:2b-instruct-q4_K_M" or granite.get_load_status().get("model_status") != "ready":
            raise RuntimeError("Granite health/configuration preflight failed.")
        context_builder = CapturingContextBuilder()
        run = await ExperimentRunService(context_builder=context_builder, granite_service=granite).run_archival_experiment(
            db,
            ExperimentRunRequest(
                research_case=case, research_question=question, question_id=QUESTION_ID,
                retrieval=RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION),
                context_budget=6000, context_mode="document_plus_authority_context", authority_context=authorities,
                authority_intent=authority_resolution.intent, retrieval_plan=plan, execution_protocol_version=PROTOCOL,
                formal_authorization_id=AUTHORIZATION_ID, fixture_only=False, allow_repair=False,
                allow_zero_documentary_inference=True,
            ),
            on_write_ahead_shell=lambda shell: verify_write_ahead_shell(shell, context_builder),
        )
        payload = serialize_run(run)
        print(json.dumps({"run": payload, "audits": audits(payload)}, indent=2, ensure_ascii=False, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())