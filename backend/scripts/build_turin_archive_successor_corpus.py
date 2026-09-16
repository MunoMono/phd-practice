"""Build a governed successor corpus from the persisted Archive asset snapshot.

The script never changes the frozen corpus. It copies frozen chunks into a new
namespace and runs Docling only for snapshot assets with no exact document
identity. Run Q02 assets first, then use --all-new after review.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import text

from app.core.database import LocalSessionLocal
from app.services.docling_processor import DoclingProcessor
from app.services.ml_policy import parse_ml_pages


SNAPSHOT_VERSION = "turin-archive-asset-snapshot-v1"
FROZEN_CORPUS_VERSION = "corpus_f40d78dbce52"
INGESTION_VERSION = "turin-archive-first-successor-v1"
Q02_ASSET_PIDS = ("062054716175", "852120727979", "723660822664")


def successor_corpus_version(rows: list[dict[str, Any]]) -> str:
    identities = sorted(
        (row["asset_pid"], row["asset_id"], row["record_pid"], row["attached_media_pid"])
        for row in rows
    )
    digest = hashlib.sha256(json.dumps(identities, separators=(",", ":")).encode()).hexdigest()[:12]
    return f"corpus_turin_archive_first_{digest}"


def _year(row: dict[str, Any]) -> int:
    normalized = str(row.get("normalized_date") or "")
    return int(normalized[:4]) if len(normalized) >= 4 and normalized[:4].isdigit() else 1970


def _chunk_id(corpus_version: str, document_id: str, page_number: int, index: int) -> str:
    digest = hashlib.sha1(f"{corpus_version}|{document_id}|{page_number}|{index}".encode()).hexdigest()[:16]
    return f"chunk_{digest}"


def _snapshot_rows(db, snapshot_export: Path) -> list[dict[str, Any]]:
    persisted_rows = {row["asset_pid"]: dict(row) for row in db.execute(text("""
        SELECT record_pid, attached_media_pid, asset_pid, asset_id, label,
               display_date, normalized_date, use_for_ml, ml_pages,
               source_type, record_title, attached_media_title, keywords,
               people, projects, box_title, collection_title,
               source_snapshot_provenance
        FROM turin_archive_asset_snapshots
        WHERE source_snapshot_version = :snapshot_version AND use_for_ml = true
        ORDER BY asset_pid
    """), {"snapshot_version": SNAPSHOT_VERSION}).mappings()}
    export_rows = json.loads(snapshot_export.read_text(encoding="utf-8"))
    rows = []
    for export_row in export_rows:
        persisted = persisted_rows.get(export_row.get("asset_pid"))
        if persisted is not None:
            rows.append({**persisted, "source_uri": export_row.get("source_uri"), "archive_record_id": export_row.get("archive_record_id")})
    if len(rows) != len(persisted_rows) or any(not row["source_uri"] for row in rows):
        raise ValueError("complete snapshot export does not exactly supply access URLs for persisted eligible assets")
    return rows


def _existing_document_ids(db, rows: list[dict[str, Any]]) -> set[str]:
    existing = set()
    for row in rows:
        matches = db.execute(text("""
            SELECT document_id FROM documents
            WHERE asset_pid = :asset_pid OR asset_id = :asset_id
        """), row).scalars()
        existing.update(matches)
    return existing


def _chunked_document_ids(db, document_ids: set[str]) -> set[str]:
    if not document_ids:
        return set()
    return set(db.execute(text("""
        SELECT DISTINCT document_id FROM document_chunks
        WHERE corpus_version = :corpus_version AND document_id = ANY(:document_ids)
    """), {"corpus_version": FROZEN_CORPUS_VERSION, "document_ids": list(document_ids)}).scalars())


def _frozen_document_ids(db, document_ids: set[str]) -> set[str]:
    if not document_ids:
        return set()
    return set(db.execute(text("""
        SELECT document_id FROM documents
        WHERE corpus_version = :corpus_version AND document_id = ANY(:document_ids)
    """), {"corpus_version": FROZEN_CORPUS_VERSION, "document_ids": list(document_ids)}).scalars())


def _metadata(row: dict[str, Any], source_uri: str, checksum: str) -> dict[str, Any]:
    return {
        "archive_snapshot_version": SNAPSHOT_VERSION,
        "archive_snapshot_provenance": row["source_snapshot_provenance"],
        "archive_record_pid": row["record_pid"],
        "archive_record_id": row["archive_record_id"],
        "attached_media_pid": row["attached_media_pid"],
        "asset_pid": row["asset_pid"],
        "asset_id": row["asset_id"],
        "canonical_asset_identity": {"asset_pid": row["asset_pid"], "asset_id": row["asset_id"], "role": "pdf_master"},
        "access_pdf_mapping": {"source_uri": source_uri, "role": "pdf_display"},
        "source_checksum_sha256": checksum,
        "ml_pages": row["ml_pages"],
    }


async def _materialize_new_asset(db, row: dict[str, Any], corpus_version: str, artifacts_dir: Path) -> dict[str, Any]:
    source_dir = artifacts_dir / "sources"
    extraction_dir = artifacts_dir / "docling"
    source_dir.mkdir(parents=True, exist_ok=True)
    extraction_dir.mkdir(parents=True, exist_ok=True)
    source_path = source_dir / f"{row['asset_id']}.pdf"
    if not source_path.exists():
        response = requests.get(row["source_uri"], timeout=120)
        response.raise_for_status()
        source_path.write_bytes(response.content)
    checksum = hashlib.sha256(source_path.read_bytes()).hexdigest()
    document_id = f"doc_archive_{row['asset_pid']}_{hashlib.sha1(row['asset_id'].encode()).hexdigest()[:12]}"
    policy = parse_ml_pages(row["ml_pages"])
    if policy["error"]:
        raise ValueError(f"invalid ml_pages for {row['asset_pid']}: {policy['error']}")
    docling = DoclingProcessor()

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import AcceleratorOptions, PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        do_ocr=docling.enable_ocr,
        accelerator_options=AcceleratorOptions(num_threads=int(os.getenv("DOCLING_MAX_THREADS", "1"))),
    )
    conversion = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    ).convert(str(source_path))
    document = conversion.document if conversion else None
    if document is None:
        raise RuntimeError("Docling conversion returned no document")
    pages = sorted(document.pages)
    allowed_pages = set(policy["allowed_pages"] or pages)
    page_text = {page: document.export_to_markdown(page_no=page) for page in pages if page in allowed_pages}
    extracted_text = "\n\n".join(text_value for text_value in page_text.values() if text_value)
    metadata = _metadata(row, row["source_uri"], checksum)
    extraction_path = extraction_dir / f"{row['asset_pid']}.json"
    extraction_path.write_text(json.dumps({"document_id": document_id, "pages": page_text, "metadata": metadata}, indent=2), encoding="utf-8")

    db.execute(text("""
        INSERT INTO documents (document_id, pid, archive_record_id, archive_record_pid, asset_pid, asset_id,
            asset_id_or_asset_pid, title, publication_year, filename, file_type, source_uri,
            source_path, checksum_sha256, page_count, extracted_text, processing_status,
            processed_at, ocr_status, ingestion_version, corpus_version, use_for_ml,
            ml_page_scope, ml_policy_status, authority_data, archive_metadata_source,
            metadata_sync_status, created_at, updated_at)
        VALUES (:document_id, :pid, :archive_record_id, :record_pid, :asset_pid, :asset_id,
            :asset_id, :label, :year, :filename, 'application/pdf', :source_uri, :source_path,
            :checksum, :page_count, :extracted_text, 'completed', NOW(), 'docling_completed',
            :ingestion_version, :corpus_version, 1, :ml_page_scope, :ml_policy_status,
            CAST(:authority_data AS jsonb), :archive_metadata_source, :metadata_sync_status, NOW(), NOW())
        ON CONFLICT (document_id) DO UPDATE SET
            archive_record_id = EXCLUDED.archive_record_id,
            archive_record_pid = EXCLUDED.archive_record_pid,
            asset_pid = EXCLUDED.asset_pid,
            asset_id = EXCLUDED.asset_id,
            source_uri = EXCLUDED.source_uri,
            archive_metadata_source = EXCLUDED.archive_metadata_source,
            metadata_sync_status = EXCLUDED.metadata_sync_status,
            authority_data = EXCLUDED.authority_data,
            updated_at = NOW()
    """), {**row, "document_id": document_id, "pid": row["attached_media_pid"], "year": _year(row),
             "filename": source_path.name, "source_uri": row["source_uri"], "source_path": str(source_path),
             "checksum": checksum, "page_count": len(pages), "extracted_text": extracted_text,
             "ingestion_version": INGESTION_VERSION, "corpus_version": corpus_version,
             "archive_metadata_source": "ddr_graphql.record_v1", "metadata_sync_status": "current",
             "ml_page_scope": policy["normalized_scope"] or "all_pages",
             "ml_policy_status": "eligible_page_restricted" if policy["is_restricted"] else "eligible_unrestricted",
             "authority_data": json.dumps(metadata)})
    chunks = 0
    for page, text_value in page_text.items():
        for index, chunk_text in enumerate(docling.chunk_text(text_value)):
            db.execute(text("""
                INSERT INTO document_chunks (chunk_id, document_id, chunk_text, chunk_index,
                    chunk_type, publication_year, source_page, source_filename, content,
                    corpus_version, ingestion_version, chunking_version, chunk_metadata, created_at)
                VALUES (:chunk_id, :document_id, :chunk_text, :chunk_index, 'paragraph', :year,
                    :source_page, :filename, :chunk_text, :corpus_version, :ingestion_version,
                    'docling-page-800-120-v1', CAST(:chunk_metadata AS jsonb), NOW())
                ON CONFLICT (chunk_id) DO NOTHING
            """), {"chunk_id": _chunk_id(corpus_version, document_id, page, index), "document_id": document_id,
                     "chunk_text": chunk_text, "chunk_index": index, "year": _year(row), "source_page": page,
                     "filename": source_path.name, "corpus_version": corpus_version,
                     "ingestion_version": INGESTION_VERSION, "chunk_metadata": json.dumps(metadata)})
            chunks += 1
    return {"asset_pid": row["asset_pid"], "document_id": document_id, "pages": len(page_text), "chunks": chunks, "checksum_sha256": checksum}


def _copy_frozen_chunks(db, corpus_version: str) -> int:
    return db.execute(text("""
        INSERT INTO document_chunks (chunk_id, document_id, chunk_text, chunk_index, chunk_type,
            publication_year, embedding_vector, embedding_model, key_concepts, drift_score,
            chunk_metadata, created_at, search_tsv, source_page, source_section, pid,
            source_filename, content, page_end, corpus_version, ingestion_version, chunking_version)
        SELECT 'successor_' || substr(md5(:corpus_version || '|' || chunk_id), 1, 24),
            document_id, chunk_text, chunk_index, chunk_type, publication_year, embedding_vector,
            embedding_model, key_concepts, drift_score,
            chunk_metadata || jsonb_build_object('reused_from_corpus_version', corpus_version), NOW(),
            search_tsv, source_page, source_section, pid, source_filename, content, page_end,
            :corpus_version, :ingestion_version, chunking_version
        FROM document_chunks
        WHERE corpus_version = :frozen_corpus
        ON CONFLICT (chunk_id) DO NOTHING
    """), {"corpus_version": corpus_version, "ingestion_version": INGESTION_VERSION, "frozen_corpus": FROZEN_CORPUS_VERSION}).rowcount


async def main(arguments) -> None:
    db = LocalSessionLocal()
    try:
        rows = _snapshot_rows(db, Path(arguments.snapshot_export))
        corpus_version = successor_corpus_version(rows)
        exact_existing = _existing_document_ids(db, rows)
        chunked_existing = _chunked_document_ids(db, exact_existing)
        frozen_existing = _frozen_document_ids(db, exact_existing)
        new_rows = [row for row in rows if row["asset_pid"] not in {
            value for value, in db.execute(text("SELECT asset_pid FROM documents WHERE asset_pid IS NOT NULL")).all()
        }]
        selected = [row for row in new_rows if arguments.all_new or row["asset_pid"] in Q02_ASSET_PIDS]
        if not arguments.execute:
            print(json.dumps({"successor_corpus_version": corpus_version, "eligible_assets": len(rows), "reused_governed_documents": len(chunked_existing), "known_representation_mismatches": len(frozen_existing - chunked_existing), "new_assets": len(new_rows), "selected_assets": [row["asset_pid"] for row in selected]}, indent=2))
            return
        artifacts_dir = Path(arguments.artifacts_dir) / corpus_version
        _copy_frozen_chunks(db, corpus_version)
        outcomes = []
        for row in selected:
            outcomes.append(await _materialize_new_asset(db, row, corpus_version, artifacts_dir))
            db.commit()
        counts = dict(db.execute(text("SELECT count(DISTINCT document_id) AS documents, count(*) AS chunks FROM document_chunks WHERE corpus_version=:corpus_version"), {"corpus_version": corpus_version}).mappings().one())
        report = {"successor_corpus_version": corpus_version, "snapshot_version": SNAPSHOT_VERSION, "eligible_assets": len(rows), "reused_governed_documents": len(chunked_existing), "known_representation_mismatches": len(frozen_existing - chunked_existing), "newly_materialized": outcomes, "counts": counts, "created_at_utc": datetime.now(timezone.utc).isoformat()}
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        (artifacts_dir / "successor-corpus-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--all-new", action="store_true")
    parser.add_argument("--artifacts-dir", default="/app/artifacts/turin-archive-first-successor-v1")
    parser.add_argument("--snapshot-export", default="/app/artifacts/turin-archive-asset-snapshot-v1-complete.json")
    asyncio.run(main(parser.parse_args()))