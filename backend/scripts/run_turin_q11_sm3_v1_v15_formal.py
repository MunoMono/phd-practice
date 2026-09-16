#!/usr/bin/env python3
"""Execute the one authorized SM3-v1 / v1.5 formal run without JSON repair."""

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
from app.services.turin_experiment_service import CONCISE_RESPONSE_REQUIREMENT, CONTEXT_ASSEMBLY_PROTOCOL_VERSION, V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, response_schema_definition, response_schema_version, structured_output_max_tokens
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "SM3-v1"
QUESTION_ID = "SM3"
CORPUS_VERSION = "corpus_f40d78dbce52"
PROTOCOL = V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION
AUTHORIZATION_ID = "turin-q11-sm3-v1-v15-primary-authorization"
EXPECTED_PARAMETERS = {"max_tokens": 1500, "temperature": 0.0, "top_p": 1.0, "do_sample": False, "granite_timeout_seconds": 1200}
EXPECTED_PROMPT_SHA256 = "37f84f56fc76ae9efea6f84f80f4303a5e7ec25226673f81bbcabff4c6056142"
EXPECTED_FACETS = [
    ("programme", ["Design in General Education"]),
    ("audience_reception", ["teachers", "pupils", "evaluation", "feedback"]),
]
EXPECTED_AUTHORITY_VARIANTS = [
    ("programme", "database_authorities.ddr_projects", "ddr_projects", "Design in General Education", "title", "Design in General Education", "controlled_query_expansion", "approved"),
]
EXPECTED_SYNONYMS = ["teachers", "pupils", "evaluation", "feedback"]
EXPECTED_REJECTED_TERMS = ["DGE", "schools", "users", "students"]


def authority_variant_snapshot(plan: RetrievalPlan) -> list[tuple[object, ...]]:
    return [
        (
            variant.facet_id, variant.authority_source, variant.authority_type,
            variant.authority_id, variant.field, variant.value, variant.role,
            variant.approval_state,
        )
        for variant in plan.authority_variants
    ]


def synonym_snapshot(plan: RetrievalPlan) -> list[tuple[str, str, str]]:
    return [
        (synonym.facet_id, synonym.value, synonym.approval_state)
        for synonym in plan.researcher_synonyms
    ]


def load_preflight(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q11 formal execution is production-only.")
    stored = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored is None:
        raise RuntimeError("SM3-v1 is not registered.")
    plan = RetrievalPlan.model_validate(stored.plan_json)
    case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
    schema = response_schema_definition(PROTOCOL)
    if any((
        plan.question_id != QUESTION_ID, plan.plan_version != "1.0", plan.protocol_version != "turin-retrieval-protocol-v1.0",
        plan.top_k != 5, plan.run_classification != "primary", plan.retrieval_scope != "corpus_wide",
        [(facet.facet_id, facet.alternatives) for facet in plan.lexical_facets] != EXPECTED_FACETS,
        authority_variant_snapshot(plan) != EXPECTED_AUTHORITY_VARIANTS,
        synonym_snapshot(plan) != [("audience_reception", value, "approved") for value in EXPECTED_SYNONYMS],
        stored.plan_json.get("rejected_terms") not in (None, EXPECTED_REJECTED_TERMS),
        plan.temporal_strata or plan.authority_linked_document_ids or plan.authority_document_link_ids,
        stored.researcher_approval_state != "approved", plan.researcher_approval_state != "approved",
        case != "scoped_missingness", not question,
        structured_output_max_tokens(PROTOCOL) != 1500,
        response_schema_version(PROTOCOL) != "turin-archival-analysis-response-v1.5-concise",
        schema["properties"]["answer"].get("maxLength") != 180,
        any(schema["properties"][field].get("maxItems") != 1 for field in ("evidence", "inferences", "contradictions", "missingness", "follow_up_queries", "authority_assertions")),
        CONTEXT_ASSEMBLY_PROTOCOL_VERSION != "turin-retrieval-protocol-v1.1",
        hashlib.sha256(CONCISE_RESPONSE_REQUIREMENT.encode()).hexdigest() != EXPECTED_PROMPT_SHA256,
    )):
        raise RuntimeError("SM3-v1/v1.5 preflight identity does not match the governed configuration.")
    plan.require_formal_approval()
    authorization = db.execute(text("SELECT plan_id, plan_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json FROM turin_formal_protocol_authorizations WHERE authorization_id=:id"), {"id": AUTHORIZATION_ID}).mappings().one_or_none()
    if authorization is None or dict(authorization["model_parameters_json"]) != EXPECTED_PARAMETERS or any((
        authorization["plan_id"] != PLAN_ID, authorization["plan_version"] != "1.0", authorization["execution_protocol_version"] != PROTOCOL,
        authorization["corpus_version"] != CORPUS_VERSION, authorization["retrieval_scope"] != "corpus_wide", authorization["run_classification"] != "primary",
        authorization["authorization_category"] != "q11_sm3_v15_primary_authorization", authorization["model_name"] != "granite3.1-dense:2b-instruct-q4_K_M",
    )):
        raise RuntimeError("Q11 requires its exact SM3-v1/v1.5 authorization.")
    for label, sql, expected in (
        ("authorization consumption", "SELECT count(*) FROM experiment_runs WHERE formal_authorization_id=:id", 0),
        ("SM3 formal runs", "SELECT count(*) FROM experiment_runs WHERE question_id='SM3' AND fixture_only=false", 0),
        ("SM3 evaluable results", "SELECT count(*) FROM turin_formal_run_evaluability_classifications WHERE question_id='SM3'", 0),
        ("Q12 runs", "SELECT count(*) FROM experiment_runs WHERE question_id='SM4' AND fixture_only=false", 0),
    ):
        if db.execute(text(sql), {"id": AUTHORIZATION_ID}).scalar_one() != expected:
            raise RuntimeError(f"Q11 execution blocked: {label} is no longer {expected}.")
    return plan


async def verify_write_ahead_shell(run: ExperimentRun) -> None:
    db = LocalSessionLocal()
    try:
        shell = db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).one_or_none()
        if shell is None or any((
            shell.status != "running", shell.formal_authorization_id != AUTHORIZATION_ID, shell.question_id != QUESTION_ID,
            shell.retrieval_plan_id != PLAN_ID, shell.retrieval_plan_version != "1.0", shell.retrieval_protocol_version != PROTOCOL,
            shell.corpus_version != CORPUS_VERSION, shell.retrieval_scope != "corpus_wide", shell.retrieval_run_classification != "primary",
            shell.model_name != "granite3.1-dense:2b-instruct-q4_K_M", shell.model_parameters_json != EXPECTED_PARAMETERS,
        )):
            raise RuntimeError("Q11 write-ahead shell is not durably present with the governed identity.")
        print(json.dumps({"write_ahead_shell": {"run_id": shell.run_id, "status": shell.status, "authorization_id": shell.formal_authorization_id, "question_id": shell.question_id, "plan_id": shell.retrieval_plan_id, "plan_version": shell.retrieval_plan_version, "protocol": shell.retrieval_protocol_version, "corpus": shell.corpus_version, "top_k": 5, "classification": shell.retrieval_run_classification, "model": shell.model_name, "parameters": shell.model_parameters_json, "started_at": shell.created_at.isoformat()}}, default=str), flush=True)
    finally:
        db.close()


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan = load_preflight(db)
        ExperimentRunService._persist_plan_snapshot(db, plan)
        print(json.dumps({"immutable_snapshot": "pass"}), flush=True)
        case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        granite = get_granite_service()
        if not granite.get_load_status().get("model_ready") and not granite.load_model():
            raise RuntimeError(f"Granite runtime could not load: {granite.get_load_status().get('last_error')}")
        if granite.timeout_seconds != 1200 or granite.model_name != "granite3.1-dense:2b-instruct-q4_K_M" or granite.get_load_status().get("model_status") != "ready":
            raise RuntimeError("Granite health/configuration preflight failed.")
        run = await ExperimentRunService(granite_service=granite).run_archival_experiment(
            db,
            ExperimentRunRequest(
                research_case=case, research_question=question, question_id=QUESTION_ID,
                retrieval=RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION),
                context_budget=6000, retrieval_plan=plan, execution_protocol_version=PROTOCOL,
                formal_authorization_id=AUTHORIZATION_ID, fixture_only=False, allow_repair=False,
            ),
            on_write_ahead_shell=verify_write_ahead_shell,
        )
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())