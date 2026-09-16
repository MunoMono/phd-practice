#!/usr/bin/env python3
"""Execute exactly one formal Q04 run from persisted plan KR4-v1 in production."""

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
from app.models.research_outputs import TurinRetrievalPlan
from app.services.experiment_run_service import ExperimentRunService, ResearchInterrogationRequest, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_protocol import RETRIEVAL_PROTOCOL_VERSION, RetrievalPlan
from app.services.turin_experiment_service import CONTEXT_ASSEMBLY_PROTOCOL_VERSION
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "KR4-v1"
QUESTION_ID = "KR4"
CORPUS_VERSION = "corpus_f40d78dbce52"
EXECUTION_PROTOCOL_VERSION = "turin-retrieval-protocol-v1.1"


def load_validated_plan(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q04 formal execution is production-only.")

    stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored_plan is None:
        raise RuntimeError("Persisted plan KR4-v1 was not found.")
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
        raise RuntimeError("Persisted KR4-v1 does not match the approved formal Q04 configuration.")
    if not expected_case or not expected_question:
        raise RuntimeError("Registered Q04 question is unavailable.")
    plan.require_formal_approval()
    if CONTEXT_ASSEMBLY_PROTOCOL_VERSION != EXECUTION_PROTOCOL_VERSION:
        raise RuntimeError("Q04 formal execution requires the active v1.1 context allocator.")
    protocol_registered = db.execute(
        text("SELECT count(*) FROM turin_retrieval_protocol_amendments WHERE protocol_version = :protocol"),
        {"protocol": EXECUTION_PROTOCOL_VERSION},
    ).scalar_one()
    if protocol_registered != 1:
        raise RuntimeError("Q04 formal execution requires the registered v1.1 protocol amendment.")
    if "corpus_f40d78dbce52" != CORPUS_VERSION:
        raise RuntimeError("Q04 formal execution requires the governed corpus version.")
    existing = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE question_id = :question_id AND retrieval_scope = 'corpus_wide' AND retrieval_run_classification = 'primary'"),
        {"question_id": QUESTION_ID},
    ).scalar_one()
    if existing != 0:
        raise RuntimeError("Q04 formal execution is blocked because a primary run already exists.")
    downstream_runs = db.execute(
        text("SELECT count(*) FROM experiment_runs WHERE question_id IN ('CI1', 'CI2', 'CI3', 'CI4', 'SM1', 'SM2', 'SM3', 'SM4')"),
    ).scalar_one()
    if downstream_runs != 0:
        raise RuntimeError("Q04 formal execution is blocked because later formal questions have runs.")
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
                fixture_only=False,
            ),
        )
        if run.retrieval_plan_id != PLAN_ID or run.corpus_version != CORPUS_VERSION:
            raise RuntimeError("Persisted Q04 run does not match the required plan or corpus snapshot.")
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())