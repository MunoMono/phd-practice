#!/usr/bin/env python3
"""Finalize the already-persisted SM1-v2 raw response without model inference."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun
from app.services.turin_experiment_service import (
    ConciseArchivalAnalysisResponse,
    _parse_response,
    response_schema_definition,
    response_schema_hash,
    response_schema_version,
    validate_provenance,
)
from app.services.turin_question_register import TURIN_QUESTION_REGISTER


RUN_ID = "experiment-381bc274183b"
AUTHORIZATION_ID = "turin-q09-sm1-v2-v15-retrieval-plan-revision-authorization"
PROTOCOL = "turin-retrieval-protocol-v1.5"


def verify_recovery_preconditions(db, run: ExperimentRun) -> None:
    evidence = sorted(run.evidence, key=lambda item: item.rank)
    generation = run.generation_metadata_json or {}
    _, question = TURIN_QUESTION_REGISTER["SM1"]
    if any((
        run.run_id != RUN_ID, run.question_id != "SM1", run.exact_research_question != question,
        run.retrieval_plan_id != "SM1-v2", run.retrieval_plan_version != "2.0",
        run.retrieval_protocol_version != PROTOCOL, run.corpus_version != "corpus_f40d78dbce52",
        run.formal_authorization_id != AUTHORIZATION_ID, run.status != "failed",
        run.error_code != "persistence_failure", not run.raw_model_response,
        run.parsed_response_json is not None, run.structured_response_json is not None,
        run.provenance_validation_json is not None,
        run.repair_attempted, generation.get("done") is not True,
        generation.get("done_reason") != "stop", generation.get("eval_count") != 428,
        generation.get("max_tokens") != 1500, len(evidence) != 6,
        any(not item.included_in_context for item in evidence),
        db.query(ExperimentRun).filter(ExperimentRun.formal_authorization_id == AUTHORIZATION_ID).count() != 1,
        db.query(ExperimentRun).filter(ExperimentRun.retrieval_plan_id == "SM1-v2", ExperimentRun.fixture_only.is_(False)).count() != 1,
        db.query(ExperimentRun).filter(ExperimentRun.question_id.in_(["SM2", "SM3", "SM4"])).count() != 0,
    )):
        raise RuntimeError("SM1-v2 raw-recovery preconditions failed; no finalization was attempted.")


def finalise_from_raw(db, run: ExperimentRun) -> ExperimentRun:
    response, normalisations = _parse_response(run.raw_model_response, ConciseArchivalAnalysisResponse)
    if normalisations:
        raise RuntimeError("SM1-v2 raw response needs structural normalization; recovery forbids altering persisted model output.")
    context = SimpleNamespace(
        supplied_chunks=[
            {"chunk_id": item.chunk_id, "pid": item.pid, "page": item.page_start, "text": item.supplied_excerpt}
            for item in sorted(run.evidence, key=lambda item: item.rank)
        ],
        omitted_chunk_ids=run.omitted_chunk_ids_json or [],
        context="",
    )
    provenance = validate_provenance(response, context)
    schema = response_schema_definition(PROTOCOL)
    response_json = response.model_dump(mode="json")
    run.response_schema_json = schema
    run.response_schema_version = response_schema_version(PROTOCOL)
    run.response_schema_hash = response_schema_hash(schema)
    run.parse_status = "parsed"
    run.parsed_response_json = response_json
    run.display_response_json = response_json
    run.structured_response_json = response_json
    run.provenance_validation_json = provenance.model_dump(mode="json")
    run.status = "completed"
    run.error_code = None
    run.error_message = None
    db.commit()
    db.refresh(run)
    return run


async def main() -> None:
    db = LocalSessionLocal()
    try:
        run = db.query(ExperimentRun).filter(ExperimentRun.run_id == RUN_ID).one_or_none()
        if run is None:
            raise RuntimeError("SM1-v2 recovery run does not exist.")
        verify_recovery_preconditions(db, run)
        finalised = finalise_from_raw(db, run)
        print(json.dumps({
            "run_id": finalised.run_id,
            "status": finalised.status,
            "parse_status": finalised.parse_status,
            "provenance": finalised.provenance_validation_json,
            "parsed_response": finalised.parsed_response_json,
            "new_granite_invocation": False,
        }, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())