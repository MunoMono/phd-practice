#!/usr/bin/env python3
"""Run the non-formal staged-evidence Q01 diagnostic; never a comparison run."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun, TurinRetrievalPlan
from app.services.inference_service import get_inference_service
from app.services.retrieval_protocol import RetrievalPlan
from app.services.retrieval_validation_service import RetrievalValidationRequest, RetrievalValidationService
from app.services.turin_evidence_pipeline_service import EVIDENCE_PIPELINE_PROTOCOL_VERSION, EvidencePacketBuilder, EvidencePipelineStageError, StagedEvidencePipeline
from app.services.turin_question_register import TURIN_QUESTION_REGISTER

BASELINE_RUN_ID = "experiment-b2a58dbd9f2f"
QUESTION_ID = "KR1"
PLAN_ID = "KR1-v1"
CORPUS_VERSION = "corpus_f40d78dbce52"
MODEL = "qwen3:8b-q4_K_M"


async def main() -> None:
    db = LocalSessionLocal()
    try:
        baseline = db.query(ExperimentRun).filter(ExperimentRun.run_id == BASELINE_RUN_ID).one_or_none()
        if baseline is None or any((baseline.question_id != QUESTION_ID, baseline.retrieval_plan_id != PLAN_ID, baseline.corpus_version != CORPUS_VERSION, baseline.fixture_only)):
            raise RuntimeError("The thin-context Q01 baseline identity is not intact.")
        prior = db.execute(text("SELECT count(*) FROM turin_evidence_pipeline_diagnostic_runs WHERE diagnostic_namespace='q01-staged-evidence-development'" )).scalar_one()
        if prior:
            raise RuntimeError("The Q01 staged-evidence development diagnostic already exists; no retry is performed.")
        stored_plan = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == PLAN_ID).one()
        plan = RetrievalPlan.model_validate(stored_plan.plan_json)
        plan.require_formal_approval()
        research_case, question = TURIN_QUESTION_REGISTER[QUESTION_ID]
        if research_case != "known_relationship":
            raise RuntimeError("Unexpected Q01 research-case identity.")
        retrieval = RetrievalValidationService().retrieve(db, RetrievalValidationRequest(query=question, top_k=plan.top_k, corpus_version=CORPUS_VERSION, retrieval_plan=plan))
        service = get_inference_service()
        if service.model_name != MODEL or not service.get_load_status().get("model_ready") and not service.load_model():
            raise RuntimeError("Qwen diagnostic runtime is not ready.")
        packets = EvidencePacketBuilder().build(db, retrieval["results"])
        run_id = f"diagnostic-{uuid.uuid4().hex[:12]}"
        try:
            artifact = await StagedEvidencePipeline(service).run(question, packets)
        except EvidencePipelineStageError as exc:
            artifact = {"protocol_version": EVIDENCE_PIPELINE_PROTOCOL_VERSION, "question": question, "status": "failed", "error": str(exc), **exc.partial_artifact}
        db.execute(text("""INSERT INTO turin_evidence_pipeline_diagnostic_runs
            (run_id, protocol_version, diagnostic_namespace, baseline_run_id, question_id, retrieval_plan_id, corpus_version, model_name, artifact_json)
            VALUES (:run_id, :protocol, 'q01-staged-evidence-development', :baseline, :question_id, :plan_id, :corpus, :model, CAST(:artifact AS jsonb))"""),
            {"run_id": run_id, "protocol": EVIDENCE_PIPELINE_PROTOCOL_VERSION, "baseline": BASELINE_RUN_ID, "question_id": QUESTION_ID, "plan_id": PLAN_ID, "corpus": CORPUS_VERSION, "model": MODEL, "artifact": json.dumps({"retrieval": retrieval, "packets": [packet.model_dump() for packet in packets], **artifact})})
        db.commit()
        print(json.dumps({"run_id": run_id, "diagnostic_namespace": "q01-staged-evidence-development", "packet_count": len(packets), "artifact": artifact}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())