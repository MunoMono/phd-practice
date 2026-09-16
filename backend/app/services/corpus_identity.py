"""Stable corpus identity helpers for Turin Phase 2A."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping


DEFAULT_INGESTION_VERSION = "turin-phase2a-archive-inventory-v1"


def compute_sha256(file_path: str | Path) -> str:
    """Return the SHA-256 checksum for a file."""
    digest = hashlib.sha256()
    with Path(file_path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_stable_document_id(
    pid: str,
    source_filename: str,
    source_uri: str | None = None,
    *,
    archive_record_pid: str | None = None,
    asset_identifier: str | None = None,
) -> str:
    """Build a deterministic document ID for a source PDF."""
    stable_bits = [
        (archive_record_pid or '').strip(),
        pid.strip(),
        (asset_identifier or '').strip(),
        source_filename.strip(),
    ]
    if source_uri:
        stable_bits.append(source_uri.strip())
    digest = hashlib.sha1("|".join(stable_bits).encode("utf-8")).hexdigest()[:12]
    safe_pid = "".join(ch for ch in pid if ch.isalnum())[:24] or "unknown"
    return f"doc_{safe_pid}_{digest}"


def build_corpus_version(
    rows: Iterable[Mapping[str, object]],
    ingestion_version: str = DEFAULT_INGESTION_VERSION,
) -> str:
    """Build a deterministic corpus version from membership and ingestion version."""
    normalized = []
    for row in rows:
        normalized.append(
            {
                "pid": row.get("pid"),
                "archive_record_pid": row.get("archive_record_pid"),
                "asset_id_or_asset_pid": row.get("asset_id_or_asset_pid"),
                "source_filename": row.get("source_filename"),
                "source_uri": row.get("source_uri"),
            }
        )

    normalized.sort(key=lambda item: (
        str(item.get("archive_record_pid") or ""),
        str(item.get("pid") or ""),
        str(item.get("asset_id_or_asset_pid") or ""),
        str(item.get("source_filename") or ""),
        str(item.get("source_uri") or ""),
    ))
    payload = json.dumps(
        {"ingestion_version": ingestion_version, "documents": normalized},
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"corpus_{digest}"