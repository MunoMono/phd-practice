#!/usr/bin/env python3
"""Execute exactly one formal Q01 run from persisted plan KR1-v1 in production."""

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
from app.services.experiment_run_service import (
    ExperimentRunService,
    ResearchInterrogationRequest,
    is_failure_recovery_eligible,
    is_instrument_implementation_correction_eligible,
    serialize_run,
)
from app.services.granite_service import get_granite_service
from app.services.retrieval_protocol import RETRIEVAL_PROTOCOL_VERSION, RetrievalPlan
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


PLAN_ID = "KR1-v1"
QUESTION_ID = "KR1"
CORPUS_VERSION = "corpus_f40d78dbce52"


def load_validated_plan(db) -> tuple[RetrievalPlan, str]:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("Q01 formal execution is production-only.")

    stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored_plan is None:
        raise RuntimeError("Persisted plan KR1-v1 was not found.")
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
        raise RuntimeError("Persisted KR1-v1 does not match the approved formal Q01 configuration.")
    plan.require_formal_approval()
    if stored_plan.question_id != QUESTION_ID or stored_plan.protocol_version != RETRIEVAL_PROTOCOL_VERSION:
        raise RuntimeError("Persisted KR1-v1 relational metadata does not match its approved snapshot.")
    if plan.authority_linked_document_ids or plan.authority_document_link_ids:
        raise RuntimeError("Primary Q01 plan must not restrict candidate documents through authority links.")
    attempts = db.query(ExperimentRun).filter(
        ExperimentRun.question_id == QUESTION_ID,
        ExperimentRun.retrieval_protocol_version == RETRIEVAL_PROTOCOL_VERSION,
        ExperimentRun.retrieval_scope == "corpus_wide",
        ExperimentRun.retrieval_run_classification == "primary",
    ).all()
    if len(attempts) == 1 and is_failure_recovery_eligible(attempts[0], plan, CORPUS_VERSION):
        recovery_of_run_id = attempts[0].run_id
        recovery_category = "infrastructure_failure_before_inference"
    elif len(attempts) == 2:
        correction_source = next((run for run in attempts if run.run_id == "experiment-e3f6bdfaf192"), None)
        if correction_source is None or not is_instrument_implementation_correction_eligible(correction_source, plan, CORPUS_VERSION):
            raise RuntimeError("Q01 correction re-execution is blocked: the documented non-evaluable instrument failure is not eligible.")
        recovery_of_run_id = correction_source.run_id
        recovery_category = "instrument_implementation_correction"
    else:
        raise RuntimeError("Q01 recovery is blocked: no sole eligible recovery source exists.")
    authorized = db.execute(
        text("SELECT 1 FROM turin_formal_run_recoveries WHERE recovery_of_run_id = :run_id AND plan_id = :plan_id AND protocol_version = :protocol AND corpus_version = :corpus AND recovery_category = :category"),
        {"run_id": recovery_of_run_id, "plan_id": PLAN_ID, "protocol": RETRIEVAL_PROTOCOL_VERSION, "corpus": CORPUS_VERSION, "category": recovery_category},
    ).first()
    if authorized is None:
        raise RuntimeError("Q01 recovery is blocked: no append-only recovery authorization exists.")
    return plan, recovery_of_run_id, recovery_category


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan, recovery_of_run_id, recovery_category = load_validated_plan(db)
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
                recovery_of_run_id=recovery_of_run_id,
                recovery_category=recovery_category,
                fixture_only=False,
            ),
        )
        if run.retrieval_plan_id != PLAN_ID or run.corpus_version != CORPUS_VERSION:
            raise RuntimeError("Persisted Q01 run does not match the required plan or corpus snapshot.")
        print(json.dumps(serialize_run(run), indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())