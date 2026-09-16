"""Run one non-persistent live diagnostic of batched source classification."""

import asyncio
import json

from app.services.inference_service import get_inference_service
from app.services.turin_evidence_pipeline_service import (
    SourceEvidencePacket,
    StagedEvidencePipeline,
)


def packet(index: int, documentary_text: str, matched_metadata: list[str] | None = None) -> SourceEvidencePacket:
    metadata = matched_metadata or ["neutral fixture"]
    return SourceEvidencePacket(
        source_id=f"neutral-{index}:chunk-{index}",
        document={"document_id": f"neutral-{index}", "archive_record_pid": f"record-{index}", "attached_media_pid": f"media-{index}", "asset_pid": f"asset-{index}", "title": f"Neutral source {index}", "matched_metadata": metadata},
        retrieval_match={"chunk_id": f"chunk-{index}", "page": index, "score": 1.0, "channels": ["TEXT_MATCH"], "matched_metadata": metadata},
        document_context={"ordered_chunks": [{"chunk_id": f"chunk-{index}", "page": index, "text": documentary_text}]},
        source_status={"catalogue_object_type": "fixture", "temporal_status": "unknown", "basis": "neutral diagnostic"},
    )


async def main() -> None:
    packets = [
        packet(1, "Alex Morgan taught a pilot studio with students in 1977."),
        packet(2, "The department held a seminar in 1977; no individual teacher is named."),
        packet(3, "A later note suggests that Alex Morgan may have influenced the curriculum."),
        packet(4, "The curriculum planning file records a proposed sequence of workshop sessions.", ["person: Alex Morgan", "topic: curriculum"]),
        packet(5, "A finance ledger records printing costs and no teaching activity."),
    ]
    inference = get_inference_service()
    await asyncio.to_thread(inference.load_model)
    artifact = await StagedEvidencePipeline(inference).run(
        "Classify each neutral documentary passage independently.", packets
    )
    calls = artifact["inference_calls"]
    classifications = artifact["evidence_map"]["source_classifications"]
    metadata_only_source = next(item for item in classifications if item["source_id"] == "neutral-4:chunk-4")
    metadata_boundary_pass = (
        not metadata_only_source["subject_named"]
        and metadata_only_source["relationship_to_question"] != "DIRECT_SUPPORT"
    )
    print(json.dumps({
        "persisted": False,
        "source_accounting": {"count": len(classifications), "total": len(packets)},
        "metadata_only_source_classification": metadata_only_source,
        "metadata_documentary_boundary_pass": metadata_boundary_pass,
        "provenance": artifact["provenance"],
        "stage_a": calls[0],
        "stage_b": calls[1],
        "stage_c": calls[2],
        "final_missingness_count": len(artifact["final_synthesis"]["missing_or_not_established"]),
        "timings": artifact["timings"],
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())