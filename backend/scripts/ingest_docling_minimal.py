"""Minimal Docling ingestion script for low-resource servers.

Features:
- one-file-at-a-time processing
- disk safety threshold
- resumable ingestion state
- immediate chunk persistence for FTS retrieval
"""

import asyncio
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.services.docling_processor import DoclingProcessor

MIN_FREE_GB = float(os.getenv("INGEST_MIN_FREE_GB", "10"))
CHUNK_SIZE = int(os.getenv("INGEST_CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("INGEST_CHUNK_OVERLAP", "120"))
DEFAULT_YEAR = int(os.getenv("INGEST_DEFAULT_YEAR", "1970"))


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def free_disk_gb(path: str = "/") -> float:
    usage = shutil.disk_usage(path)
    return usage.free / (1024 ** 3)


def upsert_ingestion_state(db, source_key: str, status: str, last_error: str = "") -> None:
    db.execute(
        text(
            """
            INSERT INTO ingestion_state (source_key, status, last_error, updated_at, retries)
            VALUES (
                :source_key,
                :status,
                :last_error,
                NOW(),
                CASE WHEN :status = 'failed' THEN 1 ELSE 0 END
            )
            ON CONFLICT (source_key)
            DO UPDATE SET
                status = EXCLUDED.status,
                last_error = EXCLUDED.last_error,
                updated_at = NOW(),
                retries = CASE
                    WHEN EXCLUDED.status = 'failed' THEN ingestion_state.retries + 1
                    ELSE ingestion_state.retries
                END
            """
        ),
        {
            "source_key": source_key,
            "status": status,
            "last_error": last_error,
        },
    )


async def process_file(path: Path, docling: DoclingProcessor) -> None:
    if free_disk_gb("/") < MIN_FREE_GB:
        raise RuntimeError(
            f"Low disk space: free disk below {MIN_FREE_GB:.1f} GB threshold"
        )

    db = SessionLocal()
    source_key = str(path.resolve())

    try:
        existing = db.execute(
            text("SELECT status FROM ingestion_state WHERE source_key = :source_key"),
            {"source_key": source_key},
        ).fetchone()
        if existing and existing.status == "completed":
            return

        upsert_ingestion_state(db, source_key, "processing")
        db.commit()

        result = await docling.process_document(
            file_path=str(path),
            file_type="tiff" if path.suffix.lower() in {".tif", ".tiff"} else "pdf",
            extract_diagrams=False,
        )

        if result.get("status") == "failed":
            raise RuntimeError(result.get("error") or "Docling extraction failed")

        extracted_text = result.get("text") or ""
        chunks = docling.chunk_text(
            extracted_text,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )

        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        pid = f"local_{path.stem[:200]}"
        file_type = "image/tiff" if path.suffix.lower() in {".tif", ".tiff"} else "application/pdf"

        db.execute(
            text(
                """
                INSERT INTO documents (
                    document_id,
                    pid,
                    title,
                    publication_year,
                    filename,
                    file_type,
                    extracted_text,
                    processing_status,
                    processed_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :document_id,
                    :pid,
                    :title,
                    :publication_year,
                    :filename,
                    :file_type,
                    :extracted_text,
                    'completed',
                    NOW(),
                    NOW(),
                    NOW()
                )
                """
            ),
            {
                "document_id": document_id,
                "pid": pid,
                "title": path.stem,
                "publication_year": DEFAULT_YEAR,
                "filename": path.name,
                "file_type": file_type,
                "extracted_text": extracted_text,
            },
        )

        for idx, chunk_text in enumerate(chunks):
            db.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        chunk_id,
                        document_id,
                        chunk_text,
                        chunk_index,
                        chunk_type,
                        publication_year,
                        source_page,
                        extraction_timestamp,
                        created_at
                    ) VALUES (
                        :chunk_id,
                        :document_id,
                        :chunk_text,
                        :chunk_index,
                        'paragraph',
                        :publication_year,
                        NULL,
                        NOW(),
                        NOW()
                    )
                    """
                ),
                {
                    "chunk_id": f"{document_id}_chunk_{idx}",
                    "document_id": document_id,
                    "chunk_text": chunk_text,
                    "chunk_index": idx,
                    "publication_year": DEFAULT_YEAR,
                },
            )

        upsert_ingestion_state(db, source_key, "completed")
        db.commit()

    except Exception as exc:
        db.rollback()
        upsert_ingestion_state(db, source_key, "failed", str(exc))
        db.commit()
        raise
    finally:
        db.close()


async def run(input_dir: Path) -> None:
    docling = DoclingProcessor()
    files = sorted(list(input_dir.rglob("*.pdf")) + list(input_dir.rglob("*.tif")) + list(input_dir.rglob("*.tiff")))

    for file_path in files:
        await process_file(file_path, docling)


if __name__ == "__main__":
    source_dir = Path(os.getenv("INGEST_INPUT_DIR", "./data"))
    if not source_dir.exists():
        raise SystemExit(f"Input directory does not exist: {source_dir}")

    asyncio.run(run(source_dir))
