#!/usr/bin/env python3
"""Validate write-ahead persistence using non-research fixture runs only."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService
from app.services.granite_service import get_granite_service
from app.services.retrieval_validation_service import RetrievalValidationRequest
from app.services.turin_experiment_service import V13_OUTPUT_CAPACITY_PROTOCOL_VERSION, V14_OUTPUT_CAPACITY_PROTOCOL_VERSION, V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION

QUESTION = "What relationship is explicitly stated in the write-ahead fixture memorandum?"
TEXT = "The fixture memorandum explicitly states that Ada Example collaborated with Ben Example."
CHUNK = {
    "rank": 1,
    "score": 1.0,
    "pid": "123456789012",
    "archive_record_pid": "fixture-write-ahead-record",
    "document_id": "fixture-write-ahead-document",
    "archive_resolution_status": "fixture_resolved",
    "title": "Write-ahead fixture memorandum",
    "page_start": 1,
    "page_end": 1,
    "chunk_id": "fixture-write-ahead-chunk",
    "chunk_sequence": 1,
    "text": TEXT,
    "provenance": {"archive_record_pid": "fixture-write-ahead-record"},
    "catalogue_metadata": {"title": "Write-ahead fixture memorandum", "extent_unit": "Fixture"},
}


class FixtureRetrieval:
    def retrieve(self, _db, request):
        return {
            "results": [CHUNK],
            "corpus_versions": ["fixture-write-ahead-corpus"],
            "transparency": {"original_query": request.query, "retrieval_method": "fixture"},
            "diagnostics": {"result_count": 1, "notes": ["Non-research write-ahead fixture."]},
        }


class InvalidJsonGranite:
    timeout_seconds = 600

    def get_load_status(self):
        return {"model_ready": True, "model_status": "ready"}

    def get_model_info(self):
        return {"model_name": "fixture-invalid-json", "runtime": "fake", "quantized": "fixture"}

    async def generate_experiment(self, *_args, **_kwargs):
        return {"raw_response": '{"answer":"unterminated', "generation": {"done": True, "done_reason": "length"}}


def requested_protocol() -> tuple[str | None, int | None]:
    if "--v15" in sys.argv:
        return V15_STRUCTURED_RESPONSE_CONTRACT_PROTOCOL_VERSION, 1500
    if "--v14" in sys.argv:
        return V14_OUTPUT_CAPACITY_PROTOCOL_VERSION, 1500
    if "--v13" in sys.argv:
        return V13_OUTPUT_CAPACITY_PROTOCOL_VERSION, 1000
    return None, None


async def verify_capacity_write_ahead_shell(run: ExperimentRun) -> None:
    protocol, max_tokens = requested_protocol()
    verification_db = LocalSessionLocal()
    try:
        shell = verification_db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).one_or_none()
        if shell is None or any([
            shell.fixture_only is not True,
            shell.status != "running",
            shell.retrieval_protocol_version != protocol,
            shell.model_parameters_json.get("max_tokens") != max_tokens,
            shell.model_parameters_json.get("granite_timeout_seconds") != 1200,
        ]):
            raise RuntimeError("Capacity fixture write-ahead shell is not durably present with the governed execution identity.")
        print({"write_ahead_shell": {"run_id": shell.run_id, "fixture_only": shell.fixture_only, "protocol": shell.retrieval_protocol_version, "max_tokens": shell.model_parameters_json["max_tokens"], "granite_timeout_seconds": shell.model_parameters_json["granite_timeout_seconds"], "status": shell.status}})
    finally:
        verification_db.close()


async def run_fixture(service, db, on_write_ahead_shell=None):
    return await service.run_archival_experiment(
        db,
        ExperimentRunRequest(
            research_case="known_relationship",
            research_question=QUESTION,
            retrieval=RetrievalValidationRequest(query=QUESTION, top_k=1),
            execution_protocol_version=requested_protocol()[0],
            fixture_only=True,
            allow_repair=False,
        ),
        on_write_ahead_shell=on_write_ahead_shell,
    )


async def main() -> None:
    db = LocalSessionLocal()
    try:
        parse_failure_only = "--parse-failure-only" in sys.argv
        v15_normal_only = "--v15" in sys.argv
        normal = None
        if not parse_failure_only:
            granite = get_granite_service()
            if not granite.get_load_status()["model_ready"] and not granite.load_model():
                raise RuntimeError("Granite fixture runtime is unavailable.")
            normal = await run_fixture(ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=granite), db, verify_capacity_write_ahead_shell if requested_protocol()[0] else None)
        invalid = None if v15_normal_only else await run_fixture(ExperimentRunService(retrieval_service=FixtureRetrieval(), granite_service=InvalidJsonGranite()), db)
        if normal and (normal.status != "completed" or not normal.raw_model_response or not normal.parsed_response_json):
            raise RuntimeError("Normal fixture did not retain a completed raw and parsed response.")
        expected_protocol, expected_max_tokens = requested_protocol()
        if normal and expected_protocol and (normal.retrieval_protocol_version != expected_protocol or normal.generation_metadata_json.get("max_tokens") != expected_max_tokens):
            raise RuntimeError("Capacity fixture did not retain the requested protocol and output ceiling.")
        if normal and "--v15" in sys.argv:
            response = normal.parsed_response_json or {}
            if normal.response_schema_version != "turin-archival-analysis-response-v1.5-concise":
                raise RuntimeError("v1.5 fixture did not retain the concise response schema.")
            if normal.generation_metadata_json.get("done_reason") != "stop" or normal.generation_metadata_json.get("eval_count", 1500) >= 1500:
                raise RuntimeError("v1.5 fixture did not stop naturally below the output ceiling.")
            if len(str(response.get("answer", ""))) > 180 or any(len(response.get(field, [])) > 1 for field in ("evidence", "inferences", "contradictions", "missingness", "follow_up_queries", "authority_assertions")):
                raise RuntimeError("v1.5 fixture did not satisfy concise response cardinality or answer length.")
        if invalid and (invalid.error_code != "output_token_exhaustion" or not invalid.raw_model_response or invalid.parsed_response_json is not None):
            raise RuntimeError("Induced parse failure did not preserve raw output.")
        print({"normal_run_id": normal.run_id if normal else None, "normal_created_at": normal.created_at.isoformat() if normal else None, "normal_status": normal.status if normal else None, "normal_protocol": normal.retrieval_protocol_version if normal else None, "normal_generation": normal.generation_metadata_json if normal else None, "normal_raw_persisted": bool(normal and normal.raw_model_response), "normal_parsed_persisted": bool(normal and normal.parsed_response_json), "normal_provenance_valid": bool(normal and (normal.provenance_validation_json or {}).get("valid")), "invalid_run_id": invalid.run_id if invalid else None, "invalid_status": invalid.status if invalid else None, "invalid_error_code": invalid.error_code if invalid else None, "raw_preserved": bool(invalid and invalid.raw_model_response), "fixture_only": True})
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
