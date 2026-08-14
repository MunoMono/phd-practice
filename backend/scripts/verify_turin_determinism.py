#!/usr/bin/env python3
"""Non-destructively regenerate and compare deterministic Turin chunks."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal
from app.services.docling_processor import DoclingProcessor
from app.services.turin_pilot_ingestion import CHUNKING_VERSION, chunks_for_page, deterministic_chunk_id, permitted_pages


CORPUS_VERSION = "corpus_f40d78dbce52"
INGESTION_VERSION = "turin-controlled-pilot-v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--document-id", action="append", dest="document_ids", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def source_path(document_id: str) -> Path:
    candidates = [
        ROOT / "artifacts/turin-controlled-pilot-sources" / f"{document_id}.pdf",
        ROOT / "artifacts/turin-controlled-corpus-sources" / f"{document_id}.pdf",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No controlled materialisation found for {document_id}")


def extract_page_markdown(path: Path, page: int, processor: DoclingProcessor) -> str:
    reader = PdfReader(str(path))
    writer = PdfWriter()
    writer.add_page(reader.pages[page - 1])
    with tempfile.NamedTemporaryFile(suffix=".pdf") as temporary_file:
        writer.write(temporary_file)
        temporary_file.flush()
        result = asyncio.run(processor.process_document(temporary_file.name, file_type="pdf", extract_diagrams=False))
    if result.get("status") != "completed":
        raise RuntimeError(result.get("error") or f"Docling failed on page {page}")
    return result.get("text") or ""


def persisted_chunks(document_id: str) -> list[dict]:
    database = LocalSessionLocal()
    try:
        rows = database.execute(
            text(
                """
                SELECT chunk_id, chunk_index, source_page, page_end, source_section,
                       chunk_text, corpus_version, chunking_version
                FROM document_chunks
                WHERE document_id = :document_id AND corpus_version = :corpus_version
                ORDER BY source_page, chunk_index
                """
            ),
            {"document_id": document_id, "corpus_version": CORPUS_VERSION},
        ).mappings().all()
        return [dict(row) for row in rows]
    finally:
        database.close()


def regenerated_chunks(row: dict, processor: DoclingProcessor) -> list[dict]:
    path = source_path(row["document_id"])
    reader = PdfReader(str(path))
    sequence = 0
    chunks: list[dict] = []
    for page in permitted_pages(len(reader.pages), row["ml_policy_status"], row["ml_page_scope"]):
        for chunk in chunks_for_page(extract_page_markdown(path, page, processor), page, sequence):
            sequence += 1
            chunks.append(
                {
                    "chunk_id": deterministic_chunk_id(row["document_id"], CORPUS_VERSION, chunk["page_start"], chunk["sequence_number"], chunk["heading_path"], chunk["chunk_text"]),
                    "chunk_index": chunk["sequence_number"],
                    "source_page": chunk["page_start"],
                    "page_end": chunk["page_end"],
                    "source_section": chunk["heading_path"],
                    "text_sha256": hashlib.sha256(chunk["chunk_text"].encode("utf-8")).hexdigest(),
                    "corpus_version": CORPUS_VERSION,
                    "chunking_version": CHUNKING_VERSION,
                }
            )
    return chunks


def main() -> None:
    args = parse_args()
    manifest = {row["document_id"]: row for row in json.loads(args.manifest.read_text(encoding="utf-8"))}
    if len(set(args.document_ids)) != 3:
        raise ValueError("Provide exactly three representative document IDs.")
    processor = DoclingProcessor()
    report = {"classification": "TURIN DETERMINISM SPOT CHECK", "corpus_version": CORPUS_VERSION, "ingestion_version": INGESTION_VERSION, "chunking_version": CHUNKING_VERSION, "documents": []}
    for document_id in args.document_ids:
        row = manifest[document_id]
        stored = persisted_chunks(document_id)
        regenerated = regenerated_chunks(row, processor)
        normalized_stored = [
            {**chunk, "text_sha256": hashlib.sha256(chunk.pop("chunk_text").encode("utf-8")).hexdigest()}
            for chunk in stored
        ]
        fields = ["chunk_id", "chunk_index", "source_page", "page_end", "source_section", "text_sha256", "corpus_version", "chunking_version"]
        mismatches = [index for index, (left, right) in enumerate(zip(normalized_stored, regenerated)) if any(left[field] != right[field] for field in fields)]
        report["documents"].append({"document_id": document_id, "ml_policy_status": row["ml_policy_status"], "ml_page_scope": row["ml_page_scope"], "stored_chunk_count": len(normalized_stored), "regenerated_chunk_count": len(regenerated), "mismatch_indexes": mismatches, "result": "match" if len(normalized_stored) == len(regenerated) and not mismatches else "mismatch"})
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if any(item["result"] != "match" for item in report["documents"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()