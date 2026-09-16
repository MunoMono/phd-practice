#!/usr/bin/env python3
"""Execute the single authorized Qwen comparison of historical Q09 / SM1-v2."""

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
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, serialize_run
from app.services.inference_service import get_inference_service
from app.services.retrieval_protocol import RetrievalPlan
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.turin_experiment_service import QWEN_COMPARISON_PROTOCOL_VERSION
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


AUTHORIZATION_ID = "turin-qwen-q09-sm1-v2-comparison-authorization"
HISTORICAL_RUN_ID = "experiment-381bc274183b"
QUESTION_ID = "SM1"
PLAN_ID = "SM1-v2"
CORPUS_VERSION = "corpus_f40d78dbce52"
MODEL = "qwen3:8b-q4_K_M"
EXPECTED_PARAMETERS = {"max_tokens": 1500, "temperature": 0.0, "top_p": 1.0, "do_sample": False, "runtime_timeout_seconds": 600}


def preflight(db) -> RetrievalPlan:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("The Qwen comparison is production-only.")
    historical = db.query(ExperimentRun).filter(ExperimentRun.run_id == HISTORICAL_RUN_ID).one_or_none()
    if historical is None or any((
        historical.question_id != QUESTION_ID,
        historical.retrieval_plan_id != PLAN_ID,
        historical.retrieval_plan_version != "2.0",
        historical.retrieval_protocol_version != "turin-retrieval-protocol-v1.5",
        historical.corpus_version != CORPUS_VERSION,
        historical.model_name != "granite3.1-dense:2b-instruct-q4_K_M",
        historical.status != "completed",
    )):
        raise RuntimeError("The immutable Granite SM1-v2 baseline does not match the registered comparison identity.")
    stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one_or_none()
    if stored_plan is None:
        raise RuntimeError("SM1-v2 is not registered.")
    plan = RetrievalPlan.model_validate(stored_plan.plan_json)
    if any((plan.question_id != QUESTION_ID, plan.plan_version != "2.0", plan.top_k != 6, plan.retrieval_scope != "corpus_wide", plan.run_classification != "primary")):
        raise RuntimeError("SM1-v2 no longer matches the frozen comparison plan.")
    plan.require_formal_approval()
    authorization = db.execute(text("SELECT question_id, plan_id, plan_version, execution_protocol_version, corpus_version, model_name, model_parameters_json FROM turin_formal_protocol_authorizations WHERE authorization_id=:id"), {"id": AUTHORIZATION_ID}).mappings().one_or_none()
    if authorization is None or any((
        authorization["question_id"] != QUESTION_ID,
        authorization["plan_id"] != PLAN_ID,
        authorization["plan_version"] != "2.0",
        authorization["execution_protocol_version"] != QWEN_COMPARISON_PROTOCOL_VERSION,
        authorization["corpus_version"] != CORPUS_VERSION,
        authorization["model_name"] != MODEL,
        dict(authorization["model_parameters_json"]) != EXPECTED_PARAMETERS,
    )):
        raise RuntimeError("The Qwen comparison authorization is absent or does not match its exact identity.")
    prior_runs = db.execute(text("SELECT count(*) FROM experiment_runs WHERE retrieval_protocol_version=:protocol AND question_id=:question_id AND retrieval_plan_id=:plan_id AND fixture_only=false"), {"protocol": QWEN_COMPARISON_PROTOCOL_VERSION, "question_id": QUESTION_ID, "plan_id": PLAN_ID}).scalar_one()
    if prior_runs != 0:
        raise RuntimeError("Qwen Q09/SM1-v2 comparison already has a persisted run; no retry is authorized.")
    return plan


async def main() -> None:
    db = LocalSessionLocal()
    try:
        plan = preflight(db)
        research_case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        inference_service = get_inference_service()
        if inference_service.model_name != MODEL or inference_service.timeout_seconds != 600:
            raise RuntimeError("Qwen comparison runtime is not ready with its authorized configuration.")
        if not inference_service.get_load_status().get("model_ready") and not inference_service.load_model():
            raise RuntimeError("Qwen comparison runtime could not load the authorized model.")
        if not inference_service.get_load_status().get("model_ready"):
            raise RuntimeError("Qwen comparison runtime is not ready with its authorized configuration.")
        run = await ExperimentRunService(inference_service=inference_service).run_archival_experiment(
            db,
            ExperimentRunRequest(
                research_case=research_case,
                research_question=question,
                question_id=QUESTION_ID,
                retrieval=RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION),
                context_budget=6000,
                retrieval_plan=plan,
                execution_protocol_version=QWEN_COMPARISON_PROTOCOL_VERSION,
                formal_authorization_id=AUTHORIZATION_ID,
                fixture_only=False,
                allow_repair=False,
            ),
        )
        historical_chunks = [row[0] for row in db.execute(text("SELECT chunk_id FROM experiment_run_evidence WHERE run_id=:run_id AND included_in_context=true ORDER BY rank"), {"run_id": HISTORICAL_RUN_ID})]
        qwen_chunks = [row[0] for row in db.execute(text("SELECT chunk_id FROM experiment_run_evidence WHERE run_id=:run_id AND included_in_context=true ORDER BY rank"), {"run_id": run.run_id})]
        print(json.dumps({"run": serialize_run(run), "comparison": {"historical_run_id": HISTORICAL_RUN_ID, "evidence_identical": historical_chunks == qwen_chunks, "historical_chunk_ids": historical_chunks, "qwen_chunk_ids": qwen_chunks}}, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())