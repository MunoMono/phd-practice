#!/usr/bin/env python3
"""Execute exactly one formal Q06 run from persisted plan CI2-v1 in production."""

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
from app.services.experiment_run_service import ExperimentRunService, ResearchInterrogationRequest, is_q06_v13_capacity_reexecution_eligible, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_protocol import RETRIEVAL_PROTOCOL_VERSION, RetrievalPlan
from app.services.turin_experiment_service import CONTEXT_ASSEMBLY_PROTOCOL_VERSION
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "CI2-v1"
QUESTION_ID = "CI2"
CORPUS_VERSION = "corpus_f40d78dbce52"
EXECUTION_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.3"
AUTHORIZATION_ID = "turin-q06-v13-output-capacity-reexecution-authorization"
PRIOR_RUN_ID = "experiment-cb1d519cd8ad"
RECOVERY_CATEGORY = "protocol_v1_3_reexecution_after_v1_2_structured_output_exhaustion"
EXPECTED_PARAMETERS = {"max_tokens": 1000, "temperature": 0.0, "top_p": 1.0, "do_sample": False, "granite_timeout_seconds": 1200}


def load_validated_plan(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q06 formal execution is production-only.")

    stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored_plan is None:
        raise RuntimeError("Persisted plan CI2-v1 was not found.")
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
        raise RuntimeError("Persisted CI2-v1 does not match the approved formal Q06 configuration.")
    if not expected_case or not expected_question:
        raise RuntimeError("Registered Q06 question is unavailable.")
    plan.require_formal_approval()
    if CONTEXT_ASSEMBLY_PROTOCOL_VERSION != "turin-retrieval-protocol-v1.1":
        raise RuntimeError("Q06 formal execution requires the active v1.1 context allocator.")
    protocol_registered = db.execute(
        text("SELECT count(*) FROM turin_retrieval_protocol_amendments WHERE protocol_version = :protocol"),
        {"protocol": EXECUTION_PROTOCOL_VERSION},
    ).scalar_one()
    if protocol_registered != 1:
        raise RuntimeError("Q06 formal execution requires the registered v1.3 protocol amendment.")
    authorization = db.execute(
        text("SELECT prior_non_evaluable_run_id, plan_id, plan_version, plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json, replacement_incident_id, replacement_intended_run_id FROM turin_formal_protocol_authorizations WHERE authorization_id = :authorization_id"),
        {"authorization_id": AUTHORIZATION_ID},
    ).mappings().one_or_none()
    if authorization is None or dict(authorization["model_parameters_json"]) != EXPECTED_PARAMETERS or any([
        authorization["prior_non_evaluable_run_id"] != PRIOR_RUN_ID,
        authorization["plan_id"] != PLAN_ID,
        authorization["plan_version"] != "1.0",
        authorization["plan_protocol_version"] != RETRIEVAL_PROTOCOL_VERSION,
        authorization["execution_protocol_version"] != EXECUTION_PROTOCOL_VERSION,
        authorization["corpus_version"] != CORPUS_VERSION,
        authorization["retrieval_scope"] != "corpus_wide",
        authorization["run_classification"] != "primary",
        authorization["authorization_category"] != RECOVERY_CATEGORY,
        authorization["model_name"] != "granite3.1-dense:2b-instruct-q4_K_M",
        authorization["replacement_incident_id"] is not None,
        authorization["replacement_intended_run_id"] is not None,
    ]):
        raise RuntimeError("Q06 v1.3 formal execution requires the exact append-only authorization record.")
    if "corpus_f40d78dbce52" != CORPUS_VERSION:
        raise RuntimeError("Q06 formal execution requires the governed corpus version.")
    prior_run = db.query(ExperimentRun).filter(ExperimentRun.run_id == PRIOR_RUN_ID).one_or_none()
    if prior_run is None or not is_q06_v13_capacity_reexecution_eligible(prior_run, plan, CORPUS_VERSION):
        raise RuntimeError("Q06 v1.3 reexecution requires the terminal governed v1.2 capacity-failure parent.")
    existing = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE formal_authorization_id = :authorization_id"),
        {"authorization_id": AUTHORIZATION_ID},
    ).scalar_one()
    if existing != 0:
        raise RuntimeError("Q06 reexecution is blocked because its authorization already has an execution.")
    v13_runs = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE question_id = :question_id AND retrieval_protocol_version = :protocol AND fixture_only = false"),
        {"question_id": QUESTION_ID, "protocol": EXECUTION_PROTOCOL_VERSION},
    ).scalar_one()
    if v13_runs != 0:
        raise RuntimeError("Q06 reexecution is blocked because a v1.3 formal run already exists.")
    evaluable_runs = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE question_id = :question_id AND status IN ('completed', 'completed_with_missingness') AND parse_status = 'parsed'"),
        {"question_id": QUESTION_ID},
    ).scalar_one()
    if evaluable_runs != 0:
        raise RuntimeError("Q06 reexecution is blocked because an evaluable Q06 result exists.")
    downstream_runs = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI3', 'CI4', 'SM1', 'SM2', 'SM3', 'SM4')"),
    ).scalar_one()
    if downstream_runs != 0:
        raise RuntimeError("Q06 formal execution is blocked because later formal questions have runs.")
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
            shell.recovery_of_run_id != PRIOR_RUN_ID,
            shell.recovery_category != RECOVERY_CATEGORY,
            shell.formal_authorization_id != AUTHORIZATION_ID,
            shell.model_parameters_json != EXPECTED_PARAMETERS,
        ]):
            raise RuntimeError("Q06 replacement write-ahead shell is not durably present with the governed identity.")
        print(json.dumps({"write_ahead_shell": {"run_id": shell.run_id, "status": shell.status, "question_id": shell.question_id, "plan_id": shell.retrieval_plan_id, "protocol": shell.retrieval_protocol_version, "corpus": shell.corpus_version, "parent_run_id": shell.recovery_of_run_id, "recovery_category": shell.recovery_category, "authorization_id": shell.formal_authorization_id, "model_parameters": shell.model_parameters_json, "started_at": shell.created_at.isoformat()}}, default=str))
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
                recovery_of_run_id=PRIOR_RUN_ID,
                recovery_category=RECOVERY_CATEGORY,
                fixture_only=False,
            ),
            on_write_ahead_shell=verify_write_ahead_shell,
        )
        if run.retrieval_plan_id != PLAN_ID or run.corpus_version != CORPUS_VERSION:
            raise RuntimeError("Persisted Q06 run does not match the required plan or corpus snapshot.")
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())