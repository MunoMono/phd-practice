#!/usr/bin/env python3
"""Validate v1.2 structured output using a non-research fixture only."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.granite_service import get_granite_service
from app.services.turin_experiment_service import ContextBuilder, GraniteExperimentService, OUTPUT_CAPACITY_PROTOCOL_VERSION, STRUCTURED_OUTPUT_MAX_TOKENS, structured_output_max_tokens


FIXTURE_QUESTION = "How do the fixture contributors distinguish practical method, empirical investigation, and theory?"
FIXTURE_TEXT = "Ada Example describes systematic design as a practical method. Ben Example argues that empirical investigation tests the method. Cara Example cautions that theory should not be treated as settled consensus."
FIXTURE_CHUNK = {
    "rank": 1, "score": 1.0, "pid": "123456789012", "archive_record_pid": "fixture-record-1",
    "document_id": "fixture-document-1", "archive_resolution_status": "fixture_resolved",
    "title": "Output-capacity fixture memorandum", "page_start": 1, "page_end": 1,
    "chunk_id": "fixture-output-capacity-chunk-1", "chunk_sequence": 1, "text": FIXTURE_TEXT,
    "provenance": {"archive_record_pid": "fixture-record-1"},
    "catalogue_metadata": {"title": "Output-capacity fixture memorandum", "extent_unit": "Fixture"},
}


async def main() -> None:
    if STRUCTURED_OUTPUT_MAX_TOKENS != 500:
        raise RuntimeError("Fixture validation requires the governed v1.2 500-token output limit.")
    granite = get_granite_service()
    if not granite.get_load_status()["model_ready"] and not granite.load_model():
        raise RuntimeError(f"Granite runtime could not load: {granite.get_load_status()['last_error']}")
    context = ContextBuilder().assemble_for_prompt("contested_interpretation", FIXTURE_QUESTION, [FIXTURE_CHUNK], input_budget=6000)
    inference = await GraniteExperimentService(granite).infer(
        "contested_interpretation", FIXTURE_QUESTION, context,
        max_tokens=structured_output_max_tokens(OUTPUT_CAPACITY_PROTOCOL_VERSION),
    )
    parsed = inference["parsed"]
    generation = inference["generation"]
    if parsed["response"] is None or parsed["repair_attempted"]:
        raise RuntimeError(f"v1.2 fixture did not parse without repair: repair_attempted={parsed['repair_attempted']}")
    if generation.get("done") is not True or generation.get("done_reason") != "stop":
        raise RuntimeError("v1.2 fixture did not stop naturally.")
    if generation.get("eval_count", STRUCTURED_OUTPUT_MAX_TOKENS) >= STRUCTURED_OUTPUT_MAX_TOKENS:
        raise RuntimeError("v1.2 fixture exhausted the governed output ceiling.")
    if not inference["provenance"] or not inference["provenance"]["valid"]:
        raise RuntimeError("v1.2 fixture failed provenance validation.")
    print(json.dumps({"fixture_only": True, "persisted_experiment_run": False, "generation": generation, "parsed": parsed, "provenance": inference["provenance"]}, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())