#!/usr/bin/env python3
"""Non-persistent production diagnostic for the formal Qwen evidence call path."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.inference_service import InferenceService
from app.services.turin_evidence_pipeline_service import SourceEvidencePacket, StagedEvidencePipeline


class DiagnosticResponse(BaseModel):
    status: Literal["diagnostic_ok"]


def packet(index: int) -> SourceEvidencePacket:
    source_id = f"neutral-source-{index}"
    chunk_id = f"neutral-chunk-{index}"
    return SourceEvidencePacket(
        source_id=source_id,
        document={"document_id": f"neutral-document-{index}", "title": f"Neutral record {index}"},
        retrieval_match={"chunk_id": chunk_id, "page": 1, "score": 1.0, "matched_text": f"Neutral record {index} states that the fixture is documentary text."},
        document_context={"section_heading": None, "page": 1, "preceding_text": None, "matched_text": f"Neutral record {index} states that the fixture is documentary text.", "following_text": None, "page_text": None, "relevant_tables": [], "relevant_captions": [], "ordered_chunks": [{"chunk_id": chunk_id, "page": 1, "text": f"Neutral record {index} states that the fixture is documentary text.", "chunk_index": 0}]},
        source_status={"catalogue_object_type": "neutral_fixture", "temporal_status": "unknown", "basis": "diagnostic"},
    )


async def main() -> None:
    inference = InferenceService()
    if inference.provider != "remote_ollama" or inference.model_name != "qwen3:8b-q4_K_M":
        raise RuntimeError("Diagnostic requires the frozen remote Qwen identity.")
    pipeline = StagedEvidencePipeline(inference)
    tiny_raw: list[dict[str, object]] = []

    async def tiny_callback(stage: str, artifact: dict[str, object]) -> None:
        tiny_raw.append({"stage": stage, "output_tokens": artifact["generation"].get("eval_count")})

    tiny, tiny_artifact = await pipeline._generate(
        "transport_diagnostic",
        "Return only this JSON: {\"status\":\"diagnostic_ok\"}.",
        DiagnosticResponse,
        32,
        on_raw_response=tiny_callback,
    )
    pipeline_raw: list[dict[str, object]] = []

    async def pipeline_callback(stage: str, artifact: dict[str, object]) -> None:
        pipeline_raw.append({"stage": stage, "output_tokens": artifact["generation"].get("eval_count")})

    artifact = await pipeline.run("What does the neutral fixture documentary text establish?", [packet(index) for index in range(1, 6)], on_raw_response=pipeline_callback)
    print(json.dumps({
        "provider": inference.provider,
        "model": inference.model_name,
        "tiny": {"status": tiny.status, "raw_callback": tiny_raw, "output_tokens": tiny_artifact["generation"].get("eval_count")},
        "pipeline": {
            "stages": pipeline_raw,
            "calls": len(artifact["inference_calls"]),
            "sources": len(artifact["source_analyses"]),
            "provenance": artifact["provenance"],
            "evidential_limits": artifact["evidence_map"]["NOT_ESTABLISHED"],
        },
        "persisted": False,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
