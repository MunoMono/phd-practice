#!/usr/bin/env python3
"""Execute one neutral DEV benchmark case; registered Turin questions are refused."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.services.inference_service import get_inference_service
from app.services.turin_evidence_pipeline_service import EVIDENCE_PIPELINE_PROTOCOL_VERSION, EvidencePacketBuilder, EvidencePipelineStageError, StagedEvidencePipeline, score_benchmark_case


async def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("DEV-"):
        raise SystemExit("Usage: run_turin_corpus_dev_case.py DEV-001")
    case_id = sys.argv[1]
    db = LocalSessionLocal()
    try:
        benchmark = db.execute(text("SELECT benchmark_json FROM turin_corpus_dev_benchmarks WHERE benchmark_version='turin-corpus-dev-benchmark-v1'" )).scalar_one()
        case = next((item for item in benchmark["cases"] if item["case_id"] == case_id), None)
        if case is None:
            raise RuntimeError("Unknown development case.")
        existing = db.execute(text("SELECT count(*) FROM turin_corpus_dev_benchmark_runs WHERE benchmark_version='turin-corpus-dev-benchmark-v1' AND case_id=:case_id"), {"case_id": case_id}).scalar_one()
        if existing:
            raise RuntimeError("This immutable development case already has a result; create a versioned benchmark revision to rerun it.")
        service = get_inference_service()
        run_id = f"dev-benchmark-{uuid.uuid4().hex[:12]}"
        configuration = {"protocol": EVIDENCE_PIPELINE_PROTOCOL_VERSION, "num_ctx": service.qwen_num_ctx, "max_input_tokens": service.max_input_tokens, "think": False}
        db.execute(text("""INSERT INTO turin_corpus_dev_benchmark_runs
            (run_id, benchmark_version, case_id, model_name, configuration_json)
            VALUES (:run_id, 'turin-corpus-dev-benchmark-v1', :case_id, :model, CAST(:configuration AS jsonb))"""),
            {"run_id": run_id, "case_id": case_id, "model": service.model_name, "configuration": json.dumps(configuration)})
        db.execute(text("""INSERT INTO turin_corpus_dev_benchmark_run_artifacts
            (run_id, artifact_sequence, artifact_type, artifact_json)
            VALUES (:run_id, 0, 'WRITE_AHEAD', CAST(:artifact AS jsonb))"""),
            {"run_id": run_id, "artifact": json.dumps({"case": case, "status": "started"})})
        db.commit()
        rows = db.execute(text("""SELECT dc.chunk_id, dc.document_id, dc.chunk_text, dc.chunk_index, dc.source_page, dc.source_section,
            d.pid, d.archive_record_pid, d.title, d.authority_data, d.asset_id, d.asset_pid, d.filename, d.source_uri, d.corpus_version,
            1.0 AS score FROM document_chunks dc JOIN documents d USING(document_id)
            WHERE dc.document_id = ANY(:document_ids) AND dc.chunk_index = 1 ORDER BY dc.document_id"""), {"document_ids": case["allowed_document_ids"]}).mappings().all()
        retrieval = [{"chunk_id": row["chunk_id"], "document_id": row["document_id"], "text": row["chunk_text"], "chunk_sequence": row["chunk_index"], "page_start": row["source_page"], "score": row["score"], "pid": row["pid"], "archive_record_pid": row["archive_record_pid"], "title": row["title"], "provenance": {"asset_id": row["asset_id"], "asset_pid": row["asset_pid"], "source_filename": row["filename"]}, "catalogue_metadata": dict(row["authority_data"] or {})} for row in rows]
        packets = EvidencePacketBuilder().build(db, retrieval)
        if not service.get_load_status().get("model_ready") and not service.load_model():
            raise RuntimeError("Qwen runtime is not ready.")
        try:
            artifact = await StagedEvidencePipeline(service).run(case["question"], packets)
        except Exception as exc:
            partial = exc.partial_artifact if isinstance(exc, EvidencePipelineStageError) else {}
            db.execute(text("""INSERT INTO turin_corpus_dev_benchmark_run_artifacts
                (run_id, artifact_sequence, artifact_type, artifact_json)
                VALUES (:run_id, 1, 'FAILED', CAST(:artifact AS jsonb))"""),
                {"run_id": run_id, "artifact": json.dumps({"error": str(exc), "partial_artifact": partial})})
            db.commit()
            raise
        scorecard = score_benchmark_case(case, artifact, packets)
        db.execute(text("""INSERT INTO turin_corpus_dev_benchmark_run_artifacts
            (run_id, artifact_sequence, artifact_type, artifact_json)
            VALUES (:run_id, 1, 'COMPLETED', CAST(:artifact AS jsonb))"""),
            {"run_id": run_id, "artifact": json.dumps({"scorecard": scorecard, "packets": [packet.model_dump() for packet in packets], **artifact})})
        db.commit()
        print(json.dumps({"run_id": run_id, "scorecard": scorecard}, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())