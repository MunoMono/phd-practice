"""Derived corpus-status contract for persisted Turin experiment documents."""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy import text


ARCHIVE_METADATA_SOURCE = 'ddr_graphql.record_v1'
ARCHIVE_RESOLUTION_RESOLVED_CURRENT = 'archive_resolved_current'
ARCHIVE_RESOLUTION_UNRESOLVED_LEGACY = 'unresolved_legacy'


def is_archive_resolved_current_document(document: Any) -> bool:
    """Return whether a persisted document has a current, explicit DDR identity."""
    return (
        getattr(document, 'archive_metadata_source', None) == ARCHIVE_METADATA_SOURCE
        and getattr(document, 'metadata_sync_status', None) in {'current', 'updated'}
        and bool(getattr(document, 'archive_record_id', None))
        and bool(getattr(document, 'archive_record_pid', None))
        and bool(getattr(document, 'asset_id', None) or getattr(document, 'asset_pid', None))
        and bool(getattr(document, 'source_uri', None))
    )


def archive_resolution_status(document: Any) -> str:
    if is_archive_resolved_current_document(document):
        return ARCHIVE_RESOLUTION_RESOLVED_CURRENT
    return ARCHIVE_RESOLUTION_UNRESOLVED_LEGACY


def build_corpus_status(persisted_document_count: int, archive_resolved_document_count: int) -> Dict[str, int | bool]:
    unresolved_legacy_document_count = persisted_document_count - archive_resolved_document_count
    if unresolved_legacy_document_count < 0:
        raise ValueError('archive-resolved document count cannot exceed persisted document count')

    return {
        'persistedDocumentCount': persisted_document_count,
        'archiveResolvedDocumentCount': archive_resolved_document_count,
        'unresolvedLegacyDocumentCount': unresolved_legacy_document_count,
        'invariantSatisfied': (
            persisted_document_count
            == archive_resolved_document_count + unresolved_legacy_document_count
        ),
    }


def get_corpus_status(db: Any) -> Dict[str, int | bool]:
    counts = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS persisted_document_count,
                COUNT(*) FILTER (
                    WHERE archive_metadata_source = :archive_metadata_source
                        AND metadata_sync_status IN ('current', 'updated')
                        AND archive_record_id IS NOT NULL
                        AND archive_record_pid IS NOT NULL
                        AND (asset_id IS NOT NULL OR asset_pid IS NOT NULL)
                        AND source_uri IS NOT NULL
                ) AS archive_resolved_document_count
            FROM documents
            """
        ),
        {'archive_metadata_source': ARCHIVE_METADATA_SOURCE},
    ).fetchone()
    return build_corpus_status(
        int(counts.persisted_document_count or 0),
        int(counts.archive_resolved_document_count or 0),
    )