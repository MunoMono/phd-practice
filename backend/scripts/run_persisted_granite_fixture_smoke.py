#!/usr/bin/env python3
"""Persist one fixture-only local Granite run; never a DDR research run."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import LocalSessionLocal
from app.models.research_outputs import ExperimentRun
from app.services.experiment_run_service import ExperimentRunRequest, ExperimentRunService, serialize_run
from app.services.granite_service import get_granite_service
from app.services.retrieval_validation_service import RetrievalValidationRequest


class FixtureRetrievalService:
    def retrieve(self, _db, request):
        result = {
            "rank": 1, "score": 1.0, "pid": "fixture-pid-1", "archive_record_pid": "fixture-record-1",
            "document_id": "fixture-doc-1", "archive_resolution_status": "resolved_current", "title": "Fixture memorandum",
            "page_start": 4, "page_end": 4, "chunk_id": "fixture-chunk-1", "chunk_sequence": 1,
            "text": "Archer and Baynes agreed that the Design Education Unit should continue.", "included_in_context": True,
            "provenance": {"archive_record_pid": "fixture-record-1"}, "catalogue_metadata": {"title": "Fixture memorandum"},
        }
        return {
            "transparency": {"original_query": request.query, "normalised_query": request.query, "expanded_query": request.query, "query_expansions": [], "filters": {}, "top_k": request.top_k, "ranking_function": "fixture"},
            "results": [result], "diagnostics": {"result_count": 1, "notes": ["Fixture-only retrieval provider."]}, "corpus_versions": ["fixture-v1"],
        }


async def main() -> None:
    db = LocalSessionLocal()
    try:
        granite = get_granite_service()
        if not granite.get_load_status()["model_ready"] and not granite.load_model():
            raise RuntimeError(f"Local Granite runtime could not load: {granite.get_load_status()['last_error']}")
        service = ExperimentRunService(retrieval_service=FixtureRetrievalService(), granite_service=granite)
        run = await service.run_archival_experiment(
            db,
            ExperimentRunRequest(
                research_case="known_relationship",
                research_question="What relationship does the supplied source document support?",
                retrieval=RetrievalValidationRequest(query="Archer Baynes", top_k=1),
                fixture_only=True,
            ),
        )
        reloaded = db.query(ExperimentRun).filter(ExperimentRun.run_id == run.run_id).first()
        print(json.dumps({
            "classification": "FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN",
            "run": serialize_run(reloaded),
            "reload_verified": reloaded is not None and reloaded.raw_model_response == run.raw_model_response,
            "json_export": serialize_run(reloaded),
        }, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())