#!/usr/bin/env python3
"""Run a local-only Turin Granite fixture smoke test; never a DDR research run."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.granite_service import get_granite_service
from app.services.turin_experiment_service import ContextBuilder, GraniteExperimentService


FIXTURE_ID = "turin-known-relationship-fixture-v1"
FIXTURE_CHUNKS = [{
    "id": "fixture-chunk-1",
    "chunk_id": "fixture-chunk-1",
    "document_id": "fixture-doc-1",
    "pid": "fixture-pid-1",
    "source_page": 4,
    "archive_resolution_status": "resolved_current",
    "text": "Archer and Baynes agreed that the Design Education Unit should continue.",
    "catalogue_metadata": {"title": "DEU memorandum"},
}]


async def main() -> None:
    granite = get_granite_service()
    if not granite.get_load_status()["model_ready"] and not granite.load_model():
        raise RuntimeError(f"Local Granite runtime could not load: {granite.get_load_status()['last_error']}")

    context = ContextBuilder().assemble(FIXTURE_CHUNKS, context_budget=3000)
    service = GraniteExperimentService(granite)
    results = []
    for _ in range(2):
        results.append(await service.infer(
            "known_relationship",
            "What relationship does the supplied source document support?",
            context,
            max_tokens=512,
        ))

    first, second = results
    comparison = {
        "byte_identical": first["raw_response"] == second["raw_response"],
        "structured_field_differences": (
            [] if first["parsed"]["response"] == second["parsed"]["response"]
            else ["parsed_response"]
        ),
    }
    print(json.dumps({
        "classification": "FIXTURE / INFRASTRUCTURE VALIDATION — NOT A DDR RESEARCH RUN",
        "fixture_identifier": FIXTURE_ID,
        "prompt": first["prompt_template"],
        "context": {
            "mode": context.context_mode,
            "characters": context.context_character_count,
            "chunk_count": context.document_chunk_count,
        },
        "model": first["model"],
        "run_1": {
            "generation": first["generation"],
            "inference_duration_seconds": first["inference_duration_seconds"],
            "raw_response": first["raw_response"],
            "parse_status": "parsed" if first["parsed"]["response"] else "failed",
            "repair_attempted": first["parsed"]["repair_attempted"],
            "structural_normalisations": first["parsed"]["structural_normalisations"],
            "repaired_response": first["parsed"]["repaired_response"],
            "provenance": first["provenance"],
        },
        "run_2": {
            "raw_response": second["raw_response"],
            "parse_status": "parsed" if second["parsed"]["response"] else "failed",
            "repair_attempted": second["parsed"]["repair_attempted"],
            "structural_normalisations": second["parsed"]["structural_normalisations"],
            "repaired_response": second["parsed"]["repaired_response"],
        },
        "repeatability": comparison,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())