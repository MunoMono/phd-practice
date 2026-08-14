#!/usr/bin/env python3
"""Run the frozen Turin ingestion contract serially, one constrained worker per asset."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS_VERSION = "corpus_f40d78dbce52"
INGESTION_VERSION = "turin-controlled-pilot-v1"
CHUNKING_VERSION = "turin-page-heading-v1"
PILOT_IDS = {
    "doc_230440137378_063f52d0a4b3",
    "doc_287080879712_c9058a9ca3df",
    "doc_521129471965_ac7a965d232a",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--pilot-result", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--download-dir", type=Path, required=True)
    parser.add_argument("--database", default="testamentary_traces_retrieval_validation")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json_write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def frozen_configuration(manifest: Path, download_dir: Path) -> dict:
    return {
        "corpus_version": CORPUS_VERSION,
        "ingestion_version": INGESTION_VERSION,
        "chunking_version": CHUNKING_VERSION,
        "docling_version": "2.15.0",
        "ocr_enabled": False,
        "worker_memory_limit": "6g",
        "worker_memory_reservation": "4g",
        "worker_cpus": 2,
        "docling_threads": 1,
        "blas_threads": 1,
        "model_cache": "/root/.cache/docling",
        "source_materialisation_path": str(download_dir),
        "deterministic_chunk_id_algorithm": "sha256(document_id, corpus_version, chunking_version, page_start, sequence, heading_path, text)",
        "ml_page_scope_interpretation": "all pages only for eligible_unrestricted; parsed inclusive numeric pages/ranges for eligible_page_restricted",
        "manifest_sha256": sha256_file(manifest),
    }


def load_checkpoint(args: argparse.Namespace, pilot_result: dict) -> dict:
    if args.checkpoint.exists():
        checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
        if checkpoint["configuration"]["corpus_version"] != CORPUS_VERSION:
            raise ValueError("Checkpoint corpus version does not match the frozen contract.")
        return checkpoint

    documents = {
        item["document_id"]: {**item, "checkpoint_status": "pilot_completed"}
        for item in pilot_result["documents"]
        if item["status"] == "completed"
    }
    return {
        "classification": "TURIN CONTROLLED-INGESTION FULL CORPUS",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "configuration": frozen_configuration(args.manifest, args.download_dir),
        "documents": documents,
    }


def run_worker(args: argparse.Namespace, document_id: str, output_path: Path) -> tuple[int, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "docker", "compose", "--profile", "docling", "run", "--rm", "--no-deps",
        "--entrypoint", "python", "-e", f"POSTGRES_DB={args.database}",
        "-v", f"{ROOT / 'artifacts'}:/artifacts", "docling-worker",
        "scripts/ingest_turin_pilot.py",
        "--manifest", "/artifacts/turin-phase2a/authoritative-turin-ingestion-manifest.json",
        "--document-id", document_id,
        "--allow-single",
        "--classification", "TURIN CONTROLLED-INGESTION FULL CORPUS",
        "--download-dir", "/artifacts/turin-controlled-corpus-sources",
        "--output", f"/artifacts/turin-phase2a/full-corpus-results/{document_id}.json",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    return completed.returncode, (completed.stdout + completed.stderr)[-8000:]


def main() -> int:
    args = parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    pilot_result = json.loads(args.pilot_result.read_text(encoding="utf-8"))
    checkpoint = load_checkpoint(args, pilot_result)
    eligible = [row for row in manifest if row["ml_policy_status"] in {"eligible_unrestricted", "eligible_page_restricted"}]
    if len(eligible) != 97 or any(row["corpus_version"] != CORPUS_VERSION for row in eligible):
        raise ValueError("Authoritative manifest does not contain the expected frozen eligible corpus.")

    for row in eligible:
        document_id = row["document_id"]
        existing = checkpoint["documents"].get(document_id, {})
        if existing.get("status") == "completed" or existing.get("checkpoint_status") == "pilot_completed":
            continue
        output_path = args.results_dir / f"{document_id}.json"
        exit_status, worker_output = run_worker(args, document_id, output_path)
        result = {"document_id": document_id, "status": "failed", "worker_exit_status": exit_status, "worker_output": worker_output}
        if output_path.exists():
            worker_result = json.loads(output_path.read_text(encoding="utf-8"))
            if worker_result.get("documents"):
                result = worker_result["documents"][0]
                result["worker_exit_status"] = exit_status
        result["checkpoint_status"] = "completed" if result.get("status") == "completed" and exit_status == 0 else "failed"
        checkpoint["documents"][document_id] = result
        checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json_write(args.checkpoint, checkpoint)
        print(f"{document_id}: {result['checkpoint_status']}", flush=True)

    checkpoint["completed_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json_write(args.checkpoint, checkpoint)
    failures = [item for item in checkpoint["documents"].values() if item.get("checkpoint_status") == "failed"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())