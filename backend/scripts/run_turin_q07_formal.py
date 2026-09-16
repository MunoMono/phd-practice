#!/usr/bin/env python3
"""Execute exactly one formal Q07 / CI3 run from persisted plan CI3-v1 in production."""

from __future__ import annotations

import asyncio
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
from app.services.experiment_run_service import ExperimentRunService, ResearchInterrogationRequest, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_protocol import RETRIEVAL_PROTOCOL_VERSION, RetrievalPlan
from app.services.turin_experiment_service import CONTEXT_ASSEMBLY_PROTOCOL_VERSION, RESPONSE_SCHEMA_VERSION, structured_output_max_tokens
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "CI3-v1"
QUESTION_ID = "CI3"
CORPUS_VERSION = "corpus_f40d78dbce52"
EXECUTION_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.3"
AUTHORIZATION_ID = "turin-q07-ci3-v13-primary-authorization"
AUTHORIZATION_CATEGORY = "q07_ci3_v13_primary_authorization"
EXPECTED_PARAMETERS = {"max_tokens": 1000, "temperature": 0.0, "top_p": 1.0, "do_sample": False, "granite_timeout_seconds": 1200}


def load_validated_plan(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q07 formal execution is production-only.")

    stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored_plan is None:
        raise RuntimeError("Persisted plan CI3-v1 was not found.")
    plan = RetrievalPlan.model_validate(stored_plan.plan_json)
    expected_case, expected_question = TURIN_QUESTION_REGISTER[QUESTION_ID]
    if (
        plan.plan_id != PLAN_ID
        or plan.question_id != QUESTION_ID
        or plan.plan_version != "1.0"
        or plan.protocol_version != RETRIEVAL_PROTOCOL_VERSION
        or plan.retrieval_scope != "corpus_wide"
        or plan.run_classification != "primary"
        or plan.top_k != 5
        or stored_plan.researcher_approval_state != "approved"
        or plan.researcher_approval_state != "approved"
    ):
        raise RuntimeError("Persisted CI3-v1 does not match the approved formal Q07 configuration.")
    if not expected_case or not expected_question:
        raise RuntimeError("Registered Q07 question is unavailable.")
    plan.require_formal_approval()
    if CONTEXT_ASSEMBLY_PROTOCOL_VERSION != "turin-retrieval-protocol-v1.1":
        raise RuntimeError("Q07 formal execution requires the active v1.1 context allocator.")
    if RESPONSE_SCHEMA_VERSION != "turin-archival-analysis-response-v1":
        raise RuntimeError("Q07 formal execution requires the frozen response schema.")
    if structured_output_max_tokens(EXECUTION_PROTOCOL_VERSION) != 1000:
        raise RuntimeError("Q07 formal execution requires the v1.3 1000-token capacity.")
    protocol_registered = db.execute(
        text("SELECT count(*) FROM turin_retrieval_protocol_amendments WHERE protocol_version = :protocol"),
        {"protocol": EXECUTION_PROTOCOL_VERSION},
    ).scalar_one()
    if protocol_registered != 1:
        raise RuntimeError("Q07 formal execution requires the registered v1.3 protocol amendment.")
    authorization = db.execute(
        text("SELECT prior_non_evaluable_run_id, plan_id, plan_version, plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json, replacement_incident_id, replacement_intended_run_id FROM turin_formal_protocol_authorizations WHERE authorization_id = :authorization_id"),
        {"authorization_id": AUTHORIZATION_ID},
    ).mappings().one_or_none()
    if authorization is None or dict(authorization["model_parameters_json"]) != EXPECTED_PARAMETERS or any([
        authorization["prior_non_evaluable_run_id"] is not None,
        authorization["plan_id"] != PLAN_ID,
        authorization["plan_version"] != "1.0",
        authorization["plan_protocol_version"] != RETRIEVAL_PROTOCOL_VERSION,
        authorization["execution_protocol_version"] != EXECUTION_PROTOCOL_VERSION,
        authorization["corpus_version"] != CORPUS_VERSION,
        authorization["retrieval_scope"] != "corpus_wide",
        authorization["run_classification"] != "primary",
        authorization["authorization_category"] != AUTHORIZATION_CATEGORY,
        authorization["model_name"] != "granite3.1-dense:2b-instruct-q4_K_M",
        authorization["replacement_incident_id"] is not None,
        authorization["replacement_intended_run_id"] is not None,
    ]):
        raise RuntimeError("Q07 formal execution requires the exact append-only authorization record.")
    for label, query, expected in [
        ("authorization consumption", "SELECT count(*) FROM experiment_runs WHERE formal_authorization_id = :authorization_id", 0),
        ("Q07 formal runs", "SELECT count(*) FROM experiment_runs WHERE question_id = :question_id AND fixture_only = false", 0),
        ("Q07 evaluable results", "SELECT count(*) FROM turin_formal_run_evaluability_classifications WHERE question_id = :question_id", 0),
        ("Q08-Q12 runs", "SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI4', 'SM1', 'SM2', 'SM3', 'SM4')", 0),
    ]:
        params = {"authorization_id": AUTHORIZATION_ID, "question_id": QUESTION_ID}
        if db.execute(text(query), params).scalar_one() != expected:
            raise RuntimeError(f"Q07 formal execution is blocked: {label} is no longer {expected}.")
    return plan


async def verify_write_ahead_shell(run: ExperimentRun) -> None:
    verification_db = LocalSessionLocal()
    try:
        shell = verification_db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).one_or_none()
        if shell is None or any([
            shell.status != "running",
            shell.question_id != QUESTION_ID,
            shell.retrieval_plan_id != PLAN_ID,
            shell.retrieval_plan_version != "1.0",
            shell.retrieval_protocol_version != EXECUTION_PROTOCOL_VERSION,
            shell.corpus_version != CORPUS_VERSION,
            shell.recovery_of_run_id is not None,
            shell.recovery_category is not None,
            shell.formal_authorization_id != AUTHORIZATION_ID,
            shell.model_name != "granite3.1-dense:2b-instruct-q4_K_M",
            shell.model_parameters_json != EXPECTED_PARAMETERS,
        ]):
            raise RuntimeError("Q07 write-ahead shell is not durably present with the governed identity.")
        print(json.dumps({"write_ahead_shell": {"run_id": shell.run_id, "status": shell.status, "question_id": shell.question_id, "plan_id": shell.retrieval_plan_id, "protocol": shell.retrieval_protocol_version, "corpus": shell.corpus_version, "authorization_id": shell.formal_authorization_id, "model_parameters": shell.model_parameters_json, "started_at": shell.created_at.isoformat()}}, default=str), flush=True)
    finally:
        verification_db.close()


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan = load_validated_plan(db)
        research_case, research_question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        granite = get_granite_service()
        granite_status = granite.get_load_status()
        if not granite_status.get("model_ready") and not granite.load_model():
            raise RuntimeError(f"Governed Granite runtime could not load: {granite.get_load_status().get('last_error')}")
        if granite.timeout_seconds != 1200 or granite.model_name != "granite3.1-dense:2b-instruct-q4_K_M":
            raise RuntimeError("Q07 formal execution requires the governed Granite timeout and model.")
        granite_status = granite.get_load_status()
        if granite_status.get("model_status") != "ready" or not granite_status.get("model_ready"):
            raise RuntimeError(f"Governed Granite runtime is not healthy: {granite_status.get('last_error')}")
        run = await ExperimentRunService(granite_service=granite).run_research_interrogation(
            db,
            ResearchInterrogationRequest(
                research_case=research_case,
                research_question=research_question,
                question_id=QUESTION_ID,
                top_k=plan.top_k,
                context_budget=6000,
                retrieval_plan=plan,
                execution_protocol_version=EXECUTION_PROTOCOL_VERSION,
                formal_authorization_id=AUTHORIZATION_ID,
                fixture_only=False,
            ),
            on_write_ahead_shell=verify_write_ahead_shell,
        )
        if run.retrieval_plan_id != PLAN_ID or run.corpus_version != CORPUS_VERSION:
            raise RuntimeError("Persisted Q07 run does not match the required plan or corpus snapshot.")
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
