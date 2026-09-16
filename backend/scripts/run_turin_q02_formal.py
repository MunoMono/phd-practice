#!/usr/bin/env python3
"""Execute exactly one formal Q02 run from persisted plan KR2-v1 in production."""

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
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "KR2-v1"
QUESTION_ID = "KR2"
CORPUS_VERSION = "corpus_f40d78dbce52"
EXECUTION_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.1"
AUTHORIZATION_ID = "turin-q02-v11-primary-authorization"


def load_validated_plan(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q02 formal execution is production-only.")

    stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored_plan is None:
        raise RuntimeError("Persisted plan KR2-v1 was not found.")
    plan = RetrievalPlan.model_validate(stored_plan.plan_json)
    expected_case, expected_question = TURIN_QUESTION_REGISTER[QUESTION_ID]
    if (
        plan.plan_id != PLAN_ID
        or plan.question_id != QUESTION_ID
        or plan.plan_version != "1.0"
        or plan.protocol_version != RETRIEVAL_PROTOCOL_VERSION
        or plan.retrieval_scope != "corpus_wide"
        or plan.run_classification != "primary"
        or stored_plan.researcher_approval_state != "approved"
        or plan.researcher_approval_state != "approved"
    ):
        raise RuntimeError("Persisted KR2-v1 does not match the approved formal Q02 configuration.")
    if not expected_case or not expected_question:
        raise RuntimeError("Registered Q02 question is unavailable.")
    plan.require_formal_approval()
    authorization = db.execute(
        text("SELECT authorization_id, prior_non_evaluable_run_id, plan_id, plan_version, plan_protocol_version, execution_protocol_version, corpus_version, retrieval_scope, run_classification, authorization_category, model_name, model_parameters_json FROM turin_formal_protocol_authorizations WHERE authorization_id = :authorization_id"),
        {"authorization_id": AUTHORIZATION_ID},
    ).mappings().one_or_none()
    expected_parameters = {"max_tokens": 350, "temperature": 0.0, "top_p": 1.0, "do_sample": False}
    if authorization is None or dict(authorization["model_parameters_json"]) != expected_parameters or any([
        authorization["prior_non_evaluable_run_id"] != "experiment-ac4550d6a2d2",
        authorization["plan_id"] != PLAN_ID,
        authorization["plan_version"] != "1.0",
        authorization["plan_protocol_version"] != RETRIEVAL_PROTOCOL_VERSION,
        authorization["execution_protocol_version"] != EXECUTION_PROTOCOL_VERSION,
        authorization["corpus_version"] != CORPUS_VERSION,
        authorization["retrieval_scope"] != "corpus_wide",
        authorization["run_classification"] != "primary",
        authorization["authorization_category"] != "protocol_v1_1_reexecution_after_non_evaluable_v1_0_commissioning",
        authorization["model_name"] != "granite3.1-dense:2b-instruct-q4_K_M",
    ]):
        raise RuntimeError("Q02 v1.1 formal execution requires the exact append-only authorization record.")
    existing = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE question_id = :question_id AND retrieval_protocol_version = :protocol AND retrieval_scope = 'corpus_wide' AND retrieval_run_classification = 'primary'"),
        {"question_id": QUESTION_ID, "protocol": EXECUTION_PROTOCOL_VERSION},
    ).scalar_one()
    if existing != 0:
        raise RuntimeError("Q02 formal execution is blocked because a primary run already exists.")
    return plan


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan = load_validated_plan(db)
        research_case, research_question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        granite = get_granite_service()
        if not granite.get_load_status()["model_ready"] and not granite.load_model():
            raise RuntimeError(f"Governed Granite runtime could not load: {granite.get_load_status()['last_error']}")
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
        )
        if run.retrieval_plan_id != PLAN_ID or run.corpus_version != CORPUS_VERSION:
            raise RuntimeError("Persisted Q02 run does not match the required plan or corpus snapshot.")
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())