from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Set

from app.services.corpus_status_service import archive_resolution_status
from app.services.metadata_roles import extract_metadata_roles


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def is_asset_granular_document(document: Any) -> bool:
    return any(
        _has_value(value)
        for value in (
            getattr(document, 'asset_id', None),
            getattr(document, 'asset_pid', None),
            getattr(document, 'asset_id_or_asset_pid', None),
            getattr(document, 'source_uri', None),
        )
    )


def is_inventory_backed_document(document: Any) -> bool:
    return getattr(document, 'metadata_source', None) == 'archive_graphql.records_v1'


def select_source_documents(documents: Iterable[Any]) -> List[Any]:
    ordered = list(documents)
    inventory_docs = [document for document in ordered if is_inventory_backed_document(document)]
    if inventory_docs:
        return inventory_docs

    asset_record_pids: Set[str] = {
        str(document.archive_record_pid)
        for document in ordered
        if is_asset_granular_document(document) and _has_value(getattr(document, 'archive_record_pid', None))
    }

    selected: List[Any] = []
    for document in ordered:
        if is_asset_granular_document(document):
            selected.append(document)
            continue

        document_pid = getattr(document, 'pid', None)
        if _has_value(document_pid) and str(document_pid) in asset_record_pids:
            continue

        selected.append(document)

    return selected


def _build_persistence_payload(document: Any, authority_data: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        'metadata_roles_version': authority_data.get('metadata_roles_version'),
        'ingestion_version': getattr(document, 'ingestion_version', None),
        'corpus_version': getattr(document, 'corpus_version', None),
        'archive_metadata_sync': {
            'fetched_at': getattr(document, 'archive_metadata_fetched_at', None).isoformat() if getattr(document, 'archive_metadata_fetched_at', None) else None,
            'source': getattr(document, 'archive_metadata_source', None),
            'snapshot_hash': getattr(document, 'archive_metadata_snapshot_hash', None),
            'status': getattr(document, 'metadata_sync_status', None),
            'error': getattr(document, 'metadata_sync_error', None),
            'source_asset_checksum': getattr(document, 'source_asset_checksum', None),
            'source_asset_changed': bool(getattr(document, 'source_asset_changed', False)),
            'reingestion_required': bool(getattr(document, 'reingestion_required', False)),
        },
    }


def _build_source_metadata_payload(document: Any) -> Dict[str, Any]:
    authority_data = dict(getattr(document, 'authority_data', None) or {})
    roles = extract_metadata_roles(authority_data)
    page_count = getattr(document, 'page_count', None)
    page_count_source = authority_data.get('page_count_source') or ('persisted_document' if page_count is not None else None)
    source_filename = authority_data.get('source_filename') or getattr(document, 'filename', None)
    public_url = roles['retrieval_provenance'].get('record_public_uri') or authority_data.get('record_public_uri') or authority_data.get('public_uri')
    retrieval_provenance = dict(roles['retrieval_provenance'])
    if page_count is not None:
        retrieval_provenance.setdefault('page_count', page_count)
    if page_count_source:
        retrieval_provenance.setdefault('page_count_source', page_count_source)

    return {
        'authority_data': authority_data,
        'roles': roles,
        'page_count': page_count,
        'page_count_source': page_count_source,
        'source_filename': source_filename,
        'record_public_uri': public_url,
        'retrieval_provenance': retrieval_provenance,
    }


def _build_shared_document_payload(document: Any, metadata: Mapping[str, Any]) -> Dict[str, Any]:
    authority_data = metadata['authority_data']
    roles = metadata['roles']

    return {
        'document_id': document.document_id,
        'archive_resolution_status': archive_resolution_status(document),
        'pid': document.pid,
        'attached_media_pid': document.pid,
        'authority_id': getattr(document, 'authority_id', None),
        'archive_record_id': document.archive_record_id or roles['retrieval_provenance'].get('archive_record_id'),
        'archive_record_pid': document.archive_record_pid or roles['retrieval_provenance'].get('archive_record_pid'),
        'asset_id': document.asset_id or roles['retrieval_provenance'].get('asset_id'),
        'asset_pid': document.asset_pid or roles['retrieval_provenance'].get('asset_pid'),
        'asset_id_or_asset_pid': document.asset_id_or_asset_pid or roles['retrieval_provenance'].get('asset_id_or_asset_pid'),
        'title': getattr(document, 'title', None),
        'source_uri': getattr(document, 'source_uri', None),
        'used_for_ml': authority_data.get('use_for_ml', document.use_for_ml),
        'ml_pages': authority_data.get('ml_pages', ''),
        'ml_page_scope': authority_data.get('ml_page_scope', document.ml_page_scope),
        'ml_annotation': authority_data.get('ml_annotation', ''),
        'ml_policy_status': getattr(document, 'ml_policy_status', None),
        'ml_exclusion_reason': getattr(document, 'ml_exclusion_reason', None),
        'processing_status': getattr(document, 'processing_status', None),
        'ingestion_version': getattr(document, 'ingestion_version', None),
        'corpus_version': getattr(document, 'corpus_version', None),
        'metadata_roles_version': authority_data.get('metadata_roles_version'),
        'record_public_uri': metadata['record_public_uri'],
        'source_filename': metadata['source_filename'],
        'corpus_control': roles['corpus_control'],
        'rights_access': roles.get('rights_access', {}),
        'retrieval_provenance': metadata['retrieval_provenance'],
        'catalogue_metadata': roles['catalogue_metadata'],
        'persistence': _build_persistence_payload(document, authority_data),
        'page_count': metadata['page_count'],
        'page_count_source': metadata['page_count_source'],
    }


def build_document_list_payload(document: Any) -> Dict[str, Any]:
    authority_data = dict(getattr(document, 'authority_data', None) or {})
    roles = extract_metadata_roles(authority_data)
    return {
        'document_id': document.document_id,
        'archive_resolution_status': archive_resolution_status(document),
        'pid': document.pid,
        'attached_media_pid': document.pid,
        'archive_record_pid': document.archive_record_pid or roles['retrieval_provenance'].get('archive_record_pid'),
        'asset_id': document.asset_id or roles['retrieval_provenance'].get('asset_id'),
        'asset_pid': document.asset_pid or roles['retrieval_provenance'].get('asset_pid'),
        'asset_id_or_asset_pid': document.asset_id_or_asset_pid or roles['retrieval_provenance'].get('asset_id_or_asset_pid'),
        'title': document.title,
        'publication_year': document.publication_year,
        'page_count': document.page_count,
        'used_for_ml': authority_data.get('use_for_ml', document.use_for_ml),
        'ml_page_scope': authority_data.get('ml_page_scope', document.ml_page_scope),
        'ml_policy_status': document.ml_policy_status,
        'status': document.processing_status,
        'processing_status': document.processing_status,
        'metadata_roles_version': authority_data.get('metadata_roles_version'),
        'record_public_uri': roles['retrieval_provenance'].get('record_public_uri') or authority_data.get('record_public_uri'),
    }


def build_document_detail_payload(document: Any) -> Dict[str, Any]:
    metadata = _build_source_metadata_payload(document)
    payload = _build_shared_document_payload(document, metadata)
    payload.update(
        {
            'publication_year': getattr(document, 'publication_year', None),
            'filename': getattr(document, 'filename', None),
            'has_diagrams': getattr(document, 'has_diagrams', None),
            'created_at': document.created_at.isoformat(),
        }
    )
    return payload


def build_document_annotations_payload(document: Any) -> Dict[str, Any]:
    metadata = _build_source_metadata_payload(document)
    ml_processed_at = getattr(document, 'ml_processed_at', None)
    payload = _build_shared_document_payload(document, metadata)
    payload['ml_processed_at'] = ml_processed_at.isoformat() if ml_processed_at else None
    return payload