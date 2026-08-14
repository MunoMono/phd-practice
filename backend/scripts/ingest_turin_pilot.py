#!/usr/bin/env python3
"""Materialise and ingest 3-5 manifest-selected Turin PDFs into current chunks only."""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader, PdfWriter
from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.models.document import Document
from app.services.corpus_identity import compute_sha256
from app.services.corpus_inventory_service import CorpusInventoryService
from app.services.docling_processor import DoclingProcessor
from app.services.turin_pilot_ingestion import CHUNKING_VERSION, chunks_for_page, deterministic_chunk_id, permitted_pages


INGESTION_VERSION = "turin-controlled-pilot-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--download-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--document-id", action="append", dest="document_ids", required=True)
    parser.add_argument("--allow-single", action="store_true", help="Permit one manifest document for the serial full-corpus worker.")
    parser.add_argument("--classification", default="TURIN CONTROLLED-INGESTION PILOT")
    return parser.parse_args()


def publication_year(row: dict) -> int:
    date_text = str(row.get("date_text") or "")
    digits = "".join(character for character in date_text if character.isdigit())
    return int(digits[:4]) if len(digits) >= 4 else 1970


def download_source(row: dict, download_dir: Path) -> Path:
    download_dir.mkdir(parents=True, exist_ok=True)
    target = download_dir / f"{row['document_id']}.pdf"
    response = requests.get(row["source_uri"], timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)
    return target


def extract_page_markdown(source_path: Path, page_number: int, processor: DoclingProcessor) -> str:
    reader = PdfReader(str(source_path))
    writer = PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_file:
        writer.write(temporary_file)
        temporary_file.flush()
        result = asyncio.run(processor.process_document(temporary_file.name, file_type="pdf", extract_diagrams=False))
    if result.get("status") == "failed":
        raise RuntimeError(result.get("error") or f"Docling failed on page {page_number}")
    return result.get("text") or ""


def ensure_manifest_document(db, row: dict) -> Document:
    CorpusInventoryService().upsert_documents([row])
    document = db.query(Document).filter(Document.document_id == row["document_id"]).one()
    if document.source_uri != row["source_uri"] or document.asset_id_or_asset_pid != row["asset_id_or_asset_pid"]:
        raise ValueError(f"Persisted identity does not match manifest for {row['document_id']}")
    document.archive_metadata_source = "ddr_graphql.record_v1"
    document.metadata_sync_status = "current"
    document.archive_metadata_fetched_at = datetime.now(timezone.utc)
    document.corpus_version = row["corpus_version"]
    db.commit()
    return document


def insert_chunks(db, row: dict, source_checksum: str, chunks: list[dict]) -> tuple[int, int]:
    inserted = 0
    duplicate = 0
    for chunk in chunks:
        chunk_id = deterministic_chunk_id(
            row["document_id"], row["corpus_version"], chunk["page_start"], chunk["sequence_number"], chunk["heading_path"], chunk["chunk_text"]
        )
        result = db.execute(
            text(
                """
                INSERT INTO document_chunks (
                    chunk_id, document_id, chunk_text, chunk_index, chunk_type,
                    publication_year, source_page, page_end, source_section,
                    chunk_metadata, corpus_version, ingestion_version, chunking_version
                ) VALUES (
                    :chunk_id, :document_id, :chunk_text, :chunk_index, 'paragraph',
                    :publication_year, :source_page, :page_end, :source_section,
                    CAST(:chunk_metadata AS jsonb), :corpus_version, :ingestion_version, :chunking_version
                ) ON CONFLICT (chunk_id) DO NOTHING
                """
            ),
            {
                "chunk_id": chunk_id,
                "document_id": row["document_id"],
                "chunk_text": chunk["chunk_text"],
                "chunk_index": chunk["sequence_number"],
                "publication_year": publication_year(row),
                "source_page": chunk["page_start"],
                "page_end": chunk["page_end"],
                "source_section": chunk["heading_path"],
                "chunk_metadata": json.dumps(
                    {
                        "archive_record_pid": row["archive_record_pid"],
                        "asset_id": row.get("asset_id"),
                        "asset_pid": row.get("asset_pid"),
                        "source_filename": row["source_filename"],
                        "source_uri": row["source_uri"],
                        "source_checksum_sha256": source_checksum,
                        "ml_page_scope": row["ml_page_scope"],
                    }
                ),
                "corpus_version": row["corpus_version"],
                "ingestion_version": INGESTION_VERSION,
                "chunking_version": CHUNKING_VERSION,
            },
        )
        if result.rowcount:
            inserted += 1
        else:
            duplicate += 1
    db.commit()
    return inserted, duplicate


def run(args: argparse.Namespace) -> dict:
    rows = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = [row for row in rows if row["document_id"] in set(args.document_ids)]
    minimum_documents = 1 if args.allow_single else 3
    if len(set(args.document_ids)) != len(args.document_ids) or len(selected) != len(args.document_ids) or not minimum_documents <= len(selected) <= 5:
        raise ValueError(f"Select exactly {minimum_documents}-5 unique manifest document IDs.")
    if any(row["corpus_version"] != "corpus_f40d78dbce52" for row in selected):
        raise ValueError("Pilot selection must use corpus_f40d78dbce52.")

    processor = DoclingProcessor()
    report = {"classification": args.classification, "corpus_version": "corpus_f40d78dbce52", "ingestion_version": INGESTION_VERSION, "chunking_version": CHUNKING_VERSION, "documents": []}
    for row in selected:
        started_at = datetime.now(timezone.utc)
        started_monotonic = time.monotonic()
        entry = {"document_id": row["document_id"], "asset_id": row.get("asset_id"), "asset_pid": row.get("asset_pid"), "source_uri": row["source_uri"], "ml_policy_status": row["ml_policy_status"], "ml_page_scope": row["ml_page_scope"], "status": "failed", "extraction_issues": [], "started_at": started_at.isoformat()}
        db = LocalSessionLocal()
        try:
            ensure_manifest_document(db, row)
            source_path = download_source(row, args.download_dir)
            source_checksum = compute_sha256(source_path)
            reader = PdfReader(str(source_path))
            allowed_pages = permitted_pages(len(reader.pages), row["ml_policy_status"], row["ml_page_scope"])
            all_chunks: list[dict] = []
            sequence = 0
            for page_number in allowed_pages:
                markdown = extract_page_markdown(source_path, page_number, processor)
                page_chunks = chunks_for_page(markdown, page_number, sequence)
                sequence += len(page_chunks)
                all_chunks.extend(page_chunks)
            inserted, duplicates = insert_chunks(db, row, source_checksum, all_chunks)
            db.execute(text("UPDATE documents SET checksum_sha256 = :checksum, page_count = :page_count, source_path = :source_path, ocr_status = 'docling_completed', processing_status = 'completed', ingestion_version = :ingestion_version WHERE document_id = :document_id"), {"checksum": source_checksum, "page_count": len(reader.pages), "source_path": str(source_path), "ingestion_version": INGESTION_VERSION, "document_id": row["document_id"]})
            db.commit()
            fts_ready = db.execute(text("SELECT COUNT(*) = COUNT(*) FILTER (WHERE search_tsv IS NOT NULL) FROM document_chunks WHERE document_id = :document_id AND corpus_version = :corpus_version"), {"document_id": row["document_id"], "corpus_version": row["corpus_version"]}).scalar_one()
            entry.update({"status": "completed", "source_path": str(source_path), "source_checksum_sha256": source_checksum, "file_size_bytes": source_path.stat().st_size, "available_page_count": len(reader.pages), "permitted_pages": allowed_pages, "processed_page_count": len(allowed_pages), "excluded_page_count": len(reader.pages) - len(allowed_pages), "chunk_count": len(all_chunks), "inserted_chunk_count": inserted, "duplicate_chunk_count": duplicates, "fts_ready": bool(fts_ready)})
        except Exception as exc:
            db.rollback()
            entry["extraction_issues"].append(str(exc))
        finally:
            db.close()
            entry["completed_at"] = datetime.now(timezone.utc).isoformat()
            entry["duration_seconds"] = round(time.monotonic() - started_monotonic, 3)
            entry["peak_memory_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            entry["worker_exit_status"] = 0 if entry["status"] == "completed" else 1
        report["documents"].append(entry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if all(item["status"] == "completed" for item in result["documents"]) else 1)