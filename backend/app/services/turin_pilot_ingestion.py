"""Deterministic page-scoped chunk preparation for the Turin ingestion pilot."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.services.ml_policy import parse_ml_pages


CHUNKING_VERSION = "turin-page-heading-v1"
MAX_CHUNK_CHARS = 1200


def permitted_pages(total_pages: int, ml_policy_status: str, ml_page_scope: str | None) -> list[int]:
    """Return the only original PDF pages permitted for controlled processing."""
    if ml_policy_status not in {"eligible_unrestricted", "eligible_page_restricted"}:
        raise ValueError(f"Document is not eligible for Turin ingestion: {ml_policy_status}")
    if ml_policy_status == "eligible_unrestricted":
        return list(range(1, total_pages + 1))

    parsed = parse_ml_pages(ml_page_scope)
    allowed_pages = parsed["allowed_pages"]
    if parsed["error"] or not allowed_pages:
        raise ValueError(f"Invalid restricted page scope: {ml_page_scope!r}")
    if any(page > total_pages for page in allowed_pages):
        raise ValueError(f"Restricted page scope exceeds PDF length {total_pages}: {ml_page_scope!r}")
    return allowed_pages


def deterministic_chunk_id(
    document_id: str,
    corpus_version: str,
    page_start: int,
    sequence_number: int,
    heading_path: str | None,
    text: str,
    chunking_version: str = CHUNKING_VERSION,
) -> str:
    payload = "|".join(
        [document_id, corpus_version, chunking_version, str(page_start), str(sequence_number), heading_path or "", text]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"turin_{document_id}_{page_start}_{sequence_number}_{digest}"


def _split_long_paragraph(paragraph: str) -> list[str]:
    if len(paragraph) <= MAX_CHUNK_CHARS:
        return [paragraph]
    pieces: list[str] = []
    remaining = paragraph
    while len(remaining) > MAX_CHUNK_CHARS:
        cut = remaining.rfind(" ", 0, MAX_CHUNK_CHARS + 1)
        if cut <= 0:
            cut = MAX_CHUNK_CHARS
        pieces.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


def chunks_for_page(markdown: str, page_number: int, sequence_start: int = 0) -> list[dict[str, Any]]:
    """Build page-local chunks while inheriting the most recent markdown heading."""
    heading_path: list[str] = []
    paragraph_lines: list[str] = []
    chunks: list[dict[str, Any]] = []
    sequence_number = sequence_start

    def emit_paragraph() -> None:
        nonlocal paragraph_lines, sequence_number
        paragraph = "\n".join(paragraph_lines).strip()
        paragraph_lines = []
        if not paragraph:
            return
        for piece in _split_long_paragraph(paragraph):
            chunks.append(
                {
                    "chunk_text": piece,
                    "page_start": page_number,
                    "page_end": page_number,
                    "sequence_number": sequence_number,
                    "heading_path": " > ".join(heading_path) or None,
                }
            )
            sequence_number += 1

    for line in markdown.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            emit_paragraph()
            level = len(heading.group(1))
            heading_path[level - 1 :] = [heading.group(2)]
            continue
        if line.strip():
            paragraph_lines.append(line.rstrip())
        else:
            emit_paragraph()
    emit_paragraph()
    return chunks