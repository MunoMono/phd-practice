#!/usr/bin/env python3
"""Freeze neutral cases from persisted graph edges and explicit documentary label occurrences."""

import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from app.core.database import LocalSessionLocal

CORPUS_VERSION = "corpus_f40d78dbce52"
SNAPSHOT_VERSION = "turin-archive-authority-graph-v1"
OUTPUT = Path(__file__).resolve().parents[1] / "fixtures" / "turin_v31_neutral_benchmark.json"


def main():
    database = LocalSessionLocal()
    try:
        rows = database.execute(text("""
            WITH governed AS (
                SELECT d.document_id FROM documents d
                WHERE d.corpus_version=:corpus AND d.use_for_ml=1
                  AND d.ml_policy_status IN ('eligible_unrestricted','eligible_page_restricted')
                  AND EXISTS (SELECT 1 FROM document_chunks dc WHERE dc.document_id=d.document_id AND dc.corpus_version=d.corpus_version)
            ), candidates AS (
                  SELECT DISTINCT ON (r.relation_id) r.authority_type,r.authority_id,r.authority_label,r.relation_type,
                      r.document_id,r.asset_pid,d.asset_id,dc.chunk_id,dc.chunk_index
                FROM turin_archive_authority_source_relations r
                JOIN governed g USING(document_id)
                JOIN documents d ON d.document_id=r.document_id AND d.corpus_version=:corpus
                JOIN document_chunks dc ON dc.document_id=r.document_id AND dc.corpus_version=:corpus
                WHERE r.snapshot_version=:snapshot
                  AND lower(dc.chunk_text) LIKE '%' || lower(CASE WHEN r.relation_type='PROJECT_SOURCE' THEN 'Job ' || r.authority_id ELSE r.authority_label END) || '%'
                ORDER BY r.relation_id,dc.chunk_index,dc.chunk_id
            ) SELECT * FROM candidates ORDER BY relation_type,authority_label,document_id LIMIT 24
        """), {"corpus": CORPUS_VERSION, "snapshot": SNAPSHOT_VERSION}).mappings().all()
        cases = []
        for index, row in enumerate(rows, 1):
            label = f"Job {row.authority_id}" if row.relation_type == "PROJECT_SOURCE" else row.authority_label
            cases.append({"benchmark_id": f"neutral-{index:02d}", "case_id": f"neutral-{index:02d}", "neutral_question": f"Find documentary material naming {label} in archival asset {row.asset_pid}.", "question_type": row.relation_type.lower(), "expected_authority_ids": [row.authority_id], "expected_canonical_document_ids": [row.document_id], "expected_canonical_assets": [row.asset_id or row.asset_pid], "expected_asset_pids": [row.asset_pid], "expected_passage_ids": [row.chunk_id], "expected_passage_chunk_ids": [row.chunk_id], "expected_relation_type": row.relation_type, "why_ground_truth_is_objective": "Persisted exact graph edge and exact authority-label occurrence in the identified governed chunk.", "ground_truth_derivation": {"snapshot_version": SNAPSHOT_VERSION, "authority_type": row.authority_type, "authority_id": row.authority_id, "document_id": row.document_id, "asset_id": row.asset_id, "asset_pid": row.asset_pid, "chunk_id": row.chunk_id, "chunk_index": row.chunk_index}})
        payload = {"fixture_version": "turin-v31-neutral-benchmark-v1", "corpus_version": CORPUS_VERSION, "graph_snapshot_version": SNAPSHOT_VERSION, "cases": cases}
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        payload["sha256"] = hashlib.sha256(canonical).hexdigest()
        OUTPUT.parent.mkdir(exist_ok=True)
        OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
        print(json.dumps({"cases": len(cases), "path": str(OUTPUT), "sha256": payload["sha256"]}))
    finally:
        database.close()


if __name__ == "__main__":
    main()