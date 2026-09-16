"""Measure the real exploratory Stage A prompt without invoking Qwen."""

import json

from app.core.database import LocalSessionLocal
from app.services.exploratory_retrieval_service import ExploratoryRetrievalService
from app.services.turin_evidence_pipeline_service import (
    BatchedSourceAnalyses,
    EvidencePacketBuilder,
    batched_source_prompt_metrics,
)


QUESTION = "How is Bruce Archer's role in teaching and learning practice with students represented across multiple DDR documents, and what aspects of that role are directly evidenced rather than inferred?"


def main() -> None:
    database = LocalSessionLocal()
    try:
        retrieval = ExploratoryRetrievalService().retrieve(
            database, QUESTION, 5, "corpus_f40d78dbce52"
        )
        packets = EvidencePacketBuilder().build(database, retrieval["results"])
    finally:
        database.close()
    print(json.dumps({
        "selected_source_count": len(packets),
        "source_ids": [packet.source_id for packet in packets],
        "prompt_metrics": batched_source_prompt_metrics(QUESTION, packets, BatchedSourceAnalyses),
    }, indent=2))


if __name__ == "__main__":
    main()