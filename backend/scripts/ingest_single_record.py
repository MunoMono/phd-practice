#!/usr/bin/env python3
"""Minimal single-record ingestion test pipeline.

Flow:
1) Fetch one record from DDR GraphQL by PID
2) Download PDF files to /tmp/ingest
3) Process each PDF with Docling
4) Chunk text for retrieval testing
5) Store chunks in document_chunks
6) Validate row count for the PID
"""

import argparse
import asyncio
import json
import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Sequence

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.services.docling_processor import DoclingProcessor


GRAPHQL_ENDPOINT = "https://api.ddrarchive.org/graphql"
DOWNLOAD_DIR = Path("/tmp/ingest")
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 120
DEFAULT_PUBLICATION_YEAR = 1970

GRAPHQL_QUERY = """
query GetRecordByPid($pid: ID!) {
    record_v1(id: $pid) {
    pid
    pdf_files {
      filename
      url
      signed_url
    }
    attached_media {
      pdf_files {
        filename
        url
        signed_url
      }
    }
  }
}
""".strip()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("ingest_single_record")


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def safe_filename(name: str, fallback: str) -> str:
    value = (name or "").strip()
    if not value:
        value = fallback
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    if not value.lower().endswith(".pdf"):
        value += ".pdf"
    return value


def chunk_text_structured(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Chunk markdown text by paragraph blocks while preserving speaker headings.

    This keeps transcript structure (e.g. "## Speaker Name") and avoids
    arbitrary fixed-length cuts through speaker turns.
    """
    if not text:
        return []

    # Keep speaker/paragraph boundaries from markdown export.
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)

        # Start a new chunk when adding this paragraph would exceed target size.
        if current and (current_len + 2 + paragraph_len) > chunk_size:
            chunks.append("\n\n".join(current))

            # Lightweight overlap: carry the tail paragraph if it is not huge.
            last = current[-1]
            if len(last) <= CHUNK_OVERLAP * 4:
                current = [last]
                current_len = len(last)
            else:
                current = []
                current_len = 0

        current.append(paragraph)
        current_len = current_len + paragraph_len + (2 if current_len else 0)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def fetch_record(pid: str) -> Dict:
    payload = {
        "query": GRAPHQL_QUERY,
        "variables": {"pid": pid},
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            GRAPHQL_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    body = response.json()
    if body.get("errors"):
        raise RuntimeError(f"GraphQL errors: {json.dumps(body['errors'])}")

    record = body.get("data", {}).get("record_v1")
    if not record:
        raise RuntimeError(f"No record_v1 found for PID {pid}")

    top_level_pdfs = record.get("pdf_files") or []
    attached_media = record.get("attached_media") or []

    flattened_attached_pdfs: List[Dict] = []
    for media in attached_media:
        flattened_attached_pdfs.extend(media.get("pdf_files") or [])

    return {
        "pid": record.get("pid") or pid,
        "pdf_files": top_level_pdfs or flattened_attached_pdfs,
    }


def download_pdf(pdf_entry: Dict, pid: str, index: int) -> Path:
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    filename = safe_filename(
        pdf_entry.get("filename", ""),
        f"{pid}_{index}.pdf",
    )
    target_path = DOWNLOAD_DIR / filename

    source_url = (pdf_entry.get("signed_url") or "").strip()
    if not source_url:
        source_url = (pdf_entry.get("url") or "").strip()
    if not source_url:
        raise RuntimeError(f"No signed_url or url for PDF #{index}: {filename}")

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        with client.stream("GET", source_url) as response:
            response.raise_for_status()
            with target_path.open("wb") as f:
                for chunk in response.iter_bytes():
                    if chunk:
                        f.write(chunk)

    logger.info("Downloaded PDF %s", target_path)
    return target_path


async def process_with_docling(pdf_path: Path, processor: DoclingProcessor) -> List[str]:
    result = await processor.process_document(
        file_path=str(pdf_path),
        file_type="pdf",
        extract_diagrams=False,
    )

    if result.get("status") == "failed":
        raise RuntimeError(result.get("error") or f"Docling failed for {pdf_path.name}")

    extracted_text = result.get("text") or ""
    chunks = chunk_text_structured(extracted_text, chunk_size=CHUNK_SIZE)
    return chunks


def get_document_chunks_columns(db) -> Sequence[str]:
    rows = db.execute(
        text(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'document_chunks'
            """
        )
    ).fetchall()
    return [row[0] for row in rows]


def ensure_minimal_chunk_columns(db) -> None:
    db.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS pid VARCHAR(255)"))
    db.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS source_filename TEXT"))
    db.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content TEXT"))


def insert_chunk_row(db, row: Dict) -> None:
    columns = list(row.keys())
    placeholders = [f":{column}" for column in columns]
    sql = f"INSERT INTO document_chunks ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
    db.execute(text(sql), row)


def store_chunks(db, pid: str, source_filename: str, chunks: List[str]) -> int:
    ensure_minimal_chunk_columns(db)
    columns = set(get_document_chunks_columns(db))

    document_id = f"pid_{pid}_{uuid.uuid4().hex[:10]}"
    for idx, chunk_content in enumerate(chunks):
        row: Dict[str, object] = {
            "pid": pid,
            "source_filename": source_filename,
            "chunk_index": idx,
            "content": chunk_content,
        }

        if "chunk_id" in columns:
            row["chunk_id"] = f"{document_id}_chunk_{idx}_{uuid.uuid4().hex[:6]}"
        if "document_id" in columns:
            row["document_id"] = document_id
        if "chunk_text" in columns:
            row["chunk_text"] = chunk_content
        if "chunk_index" in columns:
            row["chunk_index"] = idx
        if "chunk_type" in columns:
            row["chunk_type"] = "paragraph"
        if "publication_year" in columns:
            row["publication_year"] = DEFAULT_PUBLICATION_YEAR
        if "source_page" in columns:
            row["source_page"] = None
        if "chunk_metadata" in columns:
            row["chunk_metadata"] = json.dumps(
                {
                    "pid": pid,
                    "source_filename": source_filename,
                }
            )

        insert_chunk_row(db, row)

    return len(chunks)


def validate_count(db, pid: str) -> int:
    row = db.execute(
        text("SELECT COUNT(*) FROM document_chunks WHERE pid = :pid"),
        {"pid": pid},
    ).fetchone()
    return int(row[0] if row else 0)


def run(pid: str) -> None:
    logger.info("Starting single-record ingestion test for PID=%s", pid)

    record = fetch_record(pid)
    pdf_files = record.get("pdf_files", [])

    logger.info("Record PID: %s", record.get("pid"))
    logger.info("PDFs found: %d", len(pdf_files))

    if not pdf_files:
        raise RuntimeError("No pdf_files found on this record")

    processor = DoclingProcessor()

    db = SessionLocal()
    total_chunks = 0

    try:
        for i, pdf_entry in enumerate(pdf_files, start=1):
            downloaded = download_pdf(pdf_entry, pid=pid, index=i)
            chunks = asyncio.run(process_with_docling(downloaded, processor))
            created = store_chunks(
                db,
                pid=pid,
                source_filename=downloaded.name,
                chunks=chunks,
            )
            total_chunks += created
            logger.info("Processed %s -> %d chunks", downloaded.name, created)

        db.commit()

        validated = validate_count(db, pid)
        logger.info("Total chunks created this run: %d", total_chunks)
        if validated >= 0:
            logger.info("Validation count for PID %s in document_chunks: %d", pid, validated)
        else:
            logger.info("Validation count skipped: no PID-compatible column present")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest one GraphQL record for Docling retrieval testing")
    parser.add_argument("--pid", required=True, help="PID to ingest (example: 113304873833)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.pid)