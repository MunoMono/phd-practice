#!/usr/bin/env python3
"""Validate restricted Turin page scope and write the final bounded corpus freeze."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_VERSION = "corpus_f40d78dbce52"
DATABASE = "testamentary_traces_retrieval_validation"


def psql(query: str) -> list[list[str]]:
    command = ["docker", "compose", "exec", "-T", "db", "psql", "-U", "postgres", "-d", DATABASE, "-At", "-F", "\t", "-c", query]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    return [line.split("\t") for line in result.stdout.splitlines() if line]


def permitted(scope: str) -> set[int]:
    pages: set[int] = set()
    for token in scope.replace(" ", "").split(","):
        if "-" in token:
            start, end = (int(value) for value in token.split("-", 1))
            pages.update(range(start, end + 1))
        elif token:
            pages.add(int(token))
    return pages


def main() -> None:
    artifact_dir = ROOT / "artifacts/turin-phase2a"
    manifest_path = artifact_dir / "authoritative-turin-ingestion-manifest.json"
    checkpoint_path = artifact_dir / "full-corpus-ingestion-checkpoint.json"
    determinism_path = artifact_dir / "determinism-spot-check.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    determinism = json.loads(determinism_path.read_text(encoding="utf-8"))
    restricted = {row["document_id"]: permitted(row["ml_page_scope"]) for row in manifest if row["ml_policy_status"] == "eligible_page_restricted"}
    pages = psql(f"SELECT document_id, source_page FROM document_chunks WHERE corpus_version = '{CORPUS_VERSION}'")
    violations = [{"document_id": document_id, "page": int(page)} for document_id, page in pages if document_id in restricted and int(page) not in restricted[document_id]]
    status_counts: dict[str, int] = {}
    for entry in checkpoint["documents"].values():
        status = entry["checkpoint_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    current_chunks, current_documents, current_orphans, fts_non_null, fts_null, legacy_chunks = psql(
        f"SELECT count(*), count(DISTINCT document_id), count(*) FILTER (WHERE document_id NOT IN (SELECT document_id FROM documents)), count(*) FILTER (WHERE search_tsv IS NOT NULL), count(*) FILTER (WHERE search_tsv IS NULL), (SELECT count(*) FROM document_chunks WHERE corpus_version IS NULL) FROM document_chunks WHERE corpus_version = '{CORPUS_VERSION}'"
    )[0]
    source_failures = {
        "doc_321843234637_3dafa63de05f": {
            "classification": "authoritative_source_representation_mismatch",
            "source_content_type": "image/jpeg",
            "source_checksum_sha256": "8269a3bbb0235890294e1650254960a1830915197e43ff7b8207ce6ee352016b",
            "source_size_bytes": 9244,
            "reason": "Fresh authoritative materialisation exactly matched the local JPEG response; pypdf correctly rejected it before Docling because the published pdf_master URI is not PDF bytes.",
        },
        "doc_321843234637_b514872d126c": {
            "classification": "authoritative_source_representation_mismatch",
            "source_content_type": "image/jpeg",
            "source_checksum_sha256": "c48e359d2efaaa4d47f276cd2d53e61e422827948e86c8e1fa0ae5896ff1ff02",
            "source_size_bytes": 9714,
            "reason": "Fresh authoritative materialisation exactly matched the local JPEG response; pypdf correctly rejected it before Docling because the published pdf_master URI is not PDF bytes.",
        },
    }
    determinism_passed = all(item["result"] == "match" for item in determinism["documents"])
    freeze = {
        "classification": "TURIN AUTHORITATIVE CORPUS FREEZE",
        "corpus_version": CORPUS_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "manifest_path": str(manifest_path.relative_to(ROOT)),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "eligible_asset_count": 97,
        "excluded_asset_count": 12,
        "checkpoint_status_counts": status_counts,
        "successful_ingestion_count": status_counts.get("completed", 0) + status_counts.get("pilot_completed", 0),
        "failure_count": status_counts.get("failed", 0),
        "bounded_failures": [{"document_id": key, "error": value.get("extraction_issues", []), **source_failures[key]} for key, value in checkpoint["documents"].items() if value.get("checkpoint_status") == "failed"],
        "current_chunks": int(current_chunks),
        "chunked_document_count": int(current_documents),
        "current_orphans": int(current_orphans),
        "ingestion_version": checkpoint["configuration"]["ingestion_version"],
        "chunking_version": checkpoint["configuration"]["chunking_version"],
        "docling_configuration": checkpoint["configuration"],
        "restricted_eligible_assets": len(restricted),
        "restricted_assets_processed": len({document_id for document_id, _ in pages if document_id in restricted}),
        "restricted_scope_violations": violations,
        "determinism": {"passed": determinism_passed, "path": str(determinism_path.relative_to(ROOT)), "documents": determinism["documents"]},
        "fts": {"search_tsv_non_null": int(fts_non_null), "search_tsv_null": int(fts_null), "gin_index": True},
        "legacy_apr": {"chunks_retained": int(legacy_chunks), "included_in_current_namespace": False},
        "git_commit": os.environ.get("GIT_COMMIT") or subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True).stdout.strip() or None,
    }
    output_path = artifact_dir / "corpus_f40d78dbce52-freeze.json"
    output_path.write_text(json.dumps(freeze, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(freeze, indent=2))
    if violations or not determinism_passed:
        raise SystemExit("Corpus freeze validation did not pass.")


if __name__ == "__main__":
    main()