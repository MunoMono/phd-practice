#!/usr/bin/env python3
"""Freeze and execute the twelve governed Turin evidence-pipeline V2 Qwen runs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.database import LocalSessionLocal
from app.models.research_outputs import TurinRetrievalPlan
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, _git_commit, _snapshot, serialize_run
from app.services.exploratory_retrieval_service import ExploratoryRetrievalService
from app.services.inference_service import get_inference_service
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.retrieval_protocol import RetrievalPlan
from app.services.turin_evidence_pipeline_service import EvidencePacketBuilder, EvidencePipelineStageError, StagedEvidencePipeline
from app.services.turin_experiment_service import ContextAssemblyResult
from app.services.turin_question_register import TURIN_QUESTION_REGISTER

PROTOCOL_VERSION = "turin-evidence-pipeline-v2.0-qwen-formal"
CORPUS_VERSION = "corpus_f40d78dbce52"
METADATA_SNAPSHOT = "turin-archive-metadata-v1"
MODEL = "qwen3:8b-q4_K_M"
QUESTION_PLANS = (("Q01", "KR1", "KR1-v1"), ("Q02", "KR2", "KR2-v1"), ("Q03", "KR3", "KR3-v1"), ("Q04", "KR4", "KR4-v1"), ("Q05", "CI1", "CI1-v1"), ("Q06", "CI2", "CI2-v1"), ("Q07", "CI3", "CI3-v2"), ("Q08", "CI4", "CI4-v1"), ("Q09", "SM1", "SM1-v2"), ("Q10", "SM2", "SM2-v1"), ("Q11", "SM3", "SM3-v1"), ("Q12", "SM4", "SM4-v2"))
RECOVERY_PREDECESSOR_RUN_IDS = {
    "KR1": "experiment-86d4723154b9", "KR2": "experiment-7c541a085457",
    "KR3": "experiment-ed2b071de782", "KR4": "experiment-6a24ca8f40fc",
    "CI1": "experiment-14e7ed243e4e", "CI2": "experiment-0951f03189d6",
    "CI3": "experiment-01cff2d67fe2", "CI4": "experiment-d143f72f959c",
    "SM1": "experiment-9b0568ebd9e8", "SM2": "experiment-df1086a92f56",
    "SM3": "experiment-c0fdca9960ff", "SM4": "experiment-8ffd3484796a",
}
RECOVERY_CATEGORY = "infrastructure_failure_before_inference"
RECOVERY_FINGERPRINT = "f2ec8d62788a0aec28061f810924bc7efe2fd5b15092b047c86f55e64587c966"
FROZEN_CONFIG = {
    "corpus_version": CORPUS_VERSION, "searchable_documents": 95, "searchable_chunks": 12884,
    "metadata_snapshot": METADATA_SNAPSHOT, "retrieval": "exploratory_archive_retrieval_v3", "source_count": 5,
    "model": {"provider": "remote_ollama", "name": MODEL, "runtime": "Mac Studio M2 Max", "num_ctx": 16384, "temperature": 0.2, "think": False, "stage_a_max_output_tokens": 1500, "stage_b_max_output_tokens": 1000, "stage_c_max_output_tokens": 768},
    "semantic_clarification": "DIRECT_SUPPORT is a source-level Stage A evidence-relevance classification. It does not itself establish a DIRECT_DOCUMENTARY claim. Final direct documentary claims require a validated evidence-map antecedent.",
}


def fingerprint() -> str:
    return hashlib.sha256(json.dumps(FROZEN_CONFIG, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_plan(db: Any, question_id: str, plan_id: str) -> RetrievalPlan:
    stored = db.query(TurinRetrievalPlan).filter(TurinRetrievalPlan.plan_id == plan_id).one_or_none()
    if stored is None:
        raise RuntimeError(f"Missing approved plan {plan_id}.")
    plan = RetrievalPlan.model_validate(stored.plan_json)
    plan.require_formal_approval()
    if plan.question_id != question_id or plan.retrieval_scope != "corpus_wide" or plan.run_classification != "primary":
        raise RuntimeError(f"Plan {plan_id} is not the approved primary plan for {question_id}.")
    return plan


def recovery_authorization_id(question_id: str) -> str:
    return f"turin-qwen-v2-{question_id.lower()}-canonical-second-preinference-recovery-authorization"


def preflight(db: Any, freeze: bool, completed_questions: set[str] | None = None) -> list[dict[str, Any]]:
    if settings.ENVIRONMENT.lower() != "production":
        raise RuntimeError("V2 formal execution is production-only.")
    runtime = get_inference_service()
    remote_health = runtime.check_remote_runtime()
    if runtime.provider != "remote_ollama" or runtime.model_name != MODEL or not remote_health:
        raise RuntimeError("Remote Qwen runtime does not match the frozen V2 identity.")
    current = {"temperature": runtime.temperature, "num_ctx": runtime.qwen_num_ctx}
    if current != {"temperature": 0.2, "num_ctx": 16384}:
        raise RuntimeError("Remote Qwen parameters do not match frozen V2 configuration.")
    frozen = fingerprint()
    snapshot = db.execute(text("SELECT configuration_fingerprint, configuration_json FROM turin_evidence_pipeline_protocol_snapshots WHERE protocol_version=:protocol"), {"protocol": PROTOCOL_VERSION}).mappings().one_or_none()
    if snapshot is None:
        if not freeze:
            raise RuntimeError("V2 protocol snapshot has not been frozen.")
        commit = os.getenv("GIT_COMMIT") or _git_commit()
        if not commit:
            raise RuntimeError("V2 protocol freeze requires the deployed Git commit.")
        db.execute(text("INSERT INTO turin_evidence_pipeline_protocol_snapshots (protocol_version, configuration_fingerprint, configuration_json, git_commit, corpus_version, metadata_snapshot) VALUES (:protocol,:fingerprint,:config,:commit,:corpus,:metadata)"), {"protocol": PROTOCOL_VERSION, "fingerprint": frozen, "config": json.dumps(FROZEN_CONFIG), "commit": commit, "corpus": CORPUS_VERSION, "metadata": METADATA_SNAPSHOT})
        db.commit()
    elif snapshot["configuration_fingerprint"] != frozen or dict(snapshot["configuration_json"]) != FROZEN_CONFIG:
        raise RuntimeError("Frozen V2 protocol snapshot differs from runtime configuration.")
    rows = []
    completed_questions = completed_questions or set()
    for label, question_id, plan_id in QUESTION_PLANS:
        research_case, question = TURIN_QUESTION_REGISTER[question_id]
        plan = load_plan(db, question_id, plan_id)
        authorization_id = recovery_authorization_id(question_id)
        authorization = db.execute(text("""
            SELECT a.plan_id, a.plan_version, a.execution_protocol_version, a.corpus_version, a.model_name
            FROM turin_formal_protocol_authorizations a
            JOIN experiment_runs first_recovery ON first_recovery.run_id = a.prior_non_evaluable_run_id
            JOIN turin_formal_run_recoveries r ON r.recovery_of_run_id = a.prior_non_evaluable_run_id
            JOIN turin_qwen_v2_recovery_authorizations s ON s.original_run_id = first_recovery.recovery_of_run_id
            WHERE a.authorization_id=:id AND a.prior_non_evaluable_run_id=:original_run_id
              AND a.authorization_category='qwen_evidence_pipeline_v2_canonical_second_preinference_recovery'
              AND r.recovery_category=:category AND s.inference_started=false
              AND s.configuration_fingerprint=:fingerprint
        """), {"id": authorization_id, "original_run_id": RECOVERY_PREDECESSOR_RUN_IDS[question_id], "category": RECOVERY_CATEGORY, "fingerprint": RECOVERY_FINGERPRINT}).mappings().one_or_none()
        if authorization is None or any((authorization["plan_id"] != plan_id, authorization["plan_version"] != plan.plan_version, authorization["execution_protocol_version"] != PROTOCOL_VERSION, authorization["corpus_version"] != CORPUS_VERSION, authorization["model_name"] != MODEL)):
            raise RuntimeError(f"Authorization mismatch for {label}.")
        prior = db.execute(text("SELECT count(*) FROM experiment_runs WHERE formal_authorization_id=:id"), {"id": authorization_id}).scalar_one()
        if prior and question_id not in completed_questions:
            raise RuntimeError(f"Recovery authorization already consumed for {label}; no rerun is permitted.")
        rows.append({"Q": label, "question_id": question_id, "category": research_case, "question": question, "plan": plan_id, "ready": True})
    return rows


def context_from_packets(packets: list[Any]) -> ContextAssemblyResult:
    supplied = [chunk for packet in packets for chunk in packet.document_context["ordered_chunks"]]
    return ContextAssemblyResult(context="", context_mode="document_only", document_chunk_count=len(supplied), authority_context_count=0, context_character_count=sum(len(item["text"]) for item in supplied), context_budget=12000, input_budget_chars=12000, available_evidence_chars=sum(len(item["text"]) for item in supplied), assembled_input_chars=sum(len(item["text"]) for item in supplied), omitted_chunk_ids=[], omitted_chunks={}, supplied_chunks=supplied, evidence_decisions=[{"chunk_id": item["chunk_id"], "original_chars": len(item["text"]), "supplied_chars": len(item["text"]), "included_in_context": True, "excerpted": False, "exclusion_reason": None} for item in supplied])


async def execute_one(db: Any, item: tuple[str, str, str]) -> dict[str, Any]:
    label, question_id, plan_id = item
    research_case, question = TURIN_QUESTION_REGISTER[question_id]
    plan = load_plan(db, question_id, plan_id)
    request = ExperimentRunRequest(research_case=research_case, research_question=question, question_id=question_id, retrieval=RetrievalValidationRequest(query=question, top_k=5, corpus_version=CORPUS_VERSION), retrieval_plan=plan, execution_protocol_version=PROTOCOL_VERSION, recovery_of_run_id=RECOVERY_PREDECESSOR_RUN_IDS[question_id], recovery_category=RECOVERY_CATEGORY, formal_authorization_id=recovery_authorization_id(question_id), allow_repair=False)
    retrieval = ExploratoryRetrievalService().retrieve(db, question, 5, CORPUS_VERSION)
    packets = EvidencePacketBuilder().build(db, retrieval["results"])
    context = context_from_packets(packets)
    service = ExperimentRunService(inference_service=get_inference_service())
    shell = service._persist(db, request, retrieval, context, {"model": service.inference_service.get_model_info(), "generation": {"protocol_fingerprint": fingerprint()}, "parsed": {}, "prompt_template": {"prompt_name": "turin_evidence_pipeline_v2", "prompt_version": PROTOCOL_VERSION}}, None, status_override="running")
    raw: dict[str, Any] = {}
    async def save_raw(stage: str, artifact: dict[str, Any]) -> None:
        raw[stage] = artifact
        shell.raw_model_response = json.dumps(raw)
        shell.generation_metadata_json = _snapshot({"protocol_fingerprint": fingerprint(), "raw_stages_persisted": list(raw)})
        db.commit()
    try:
        artifact = await StagedEvidencePipeline(service.inference_service).run(question, packets, on_raw_response=save_raw)
        artifact["frozen_protocol"] = {"version": PROTOCOL_VERSION, "fingerprint": fingerprint(), "configuration": FROZEN_CONFIG}
        inference = {"model": service.inference_service.get_model_info(), "generation": {"protocol_fingerprint": fingerprint(), "inference_calls": artifact["inference_calls"]}, "parsed": {"response": artifact}, "provenance": artifact["provenance"], "inference_duration_seconds": artifact["timings"]["total_pipeline_ms"] / 1000, "prompt_template": {"prompt_name": "turin_evidence_pipeline_v2", "prompt_version": PROTOCOL_VERSION}, "response_schema": {}, "response_schema_version": PROTOCOL_VERSION, "response_schema_hash": fingerprint()}
        run = service._finalize_write_ahead_run(db, shell, inference, None)
    except Exception as exc:
        run = service._finalize_write_ahead_run(db, shell, None, ("evidence_pipeline_failure", f"{type(exc).__name__}: {exc}"))
    return {"Q": label, "run_id": run.run_id, "status": run.status, "sources": len(packets), "provenance": (run.provenance_validation_json or {}).get("final_synthesis", {}).get("valid"), "runtime_ms": run.inference_duration_ms}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--start-at", choices=[label for label, _, _ in QUESTION_PLANS], default="Q01")
    args = parser.parse_args()
    db = LocalSessionLocal()
    try:
        start_index = next(index for index, (label, _, _) in enumerate(QUESTION_PLANS) if label == args.start_at)
        completed_questions = {question_id for _, question_id, _ in QUESTION_PLANS[:start_index]}
        rows = preflight(db, freeze=True, completed_questions=completed_questions if args.execute else None)
        if not args.execute:
            print(json.dumps({"protocol": PROTOCOL_VERSION, "fingerprint": fingerprint(), "preflight": rows}, indent=2))
            return
        results = []
        for item in QUESTION_PLANS[start_index:]:
            preflight(db, freeze=False, completed_questions=completed_questions)
            results.append(await execute_one(db, item))
            completed_questions.add(item[1])
        print(json.dumps({"protocol": PROTOCOL_VERSION, "fingerprint": fingerprint(), "runs": results}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())