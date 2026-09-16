"""Metadata role partitioning for Turin corpus, retrieval, and Granite context."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


ROLE_VERSION = 'turin-phase2-metadata-v2'


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {'', '[]', '{}', 'null', 'None'}
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _clean_mapping(values: Mapping[str, Any]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in values.items():
        if _has_value(value):
            cleaned[key] = value
    return cleaned


def _coalesce(*values: Any) -> Any:
    for value in values:
        if _has_value(value):
            return value
    return None


def partition_metadata(metadata: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    document_date = _coalesce(
        metadata.get('date_text'),
        metadata.get('date_begin'),
        metadata.get('artefact_date_from'),
        metadata.get('project_start_date'),
        metadata.get('interview_date'),
    )
    creator = _coalesce(metadata.get('creator'), metadata.get('creator_agent_label'))
    document_title = _coalesce(metadata.get('title'), metadata.get('record_title'))
    source_filename = _coalesce(
        metadata.get('source_filename'),
        metadata.get('asset_filename'),
        metadata.get('filename'),
    )

    corpus_control = _clean_mapping(
        {
            'use_for_ml': _coalesce(metadata.get('use_for_ml'), metadata.get('asset_use_for_ml')),
            'media_used_for_ml': metadata.get('media_used_for_ml', metadata.get('used_for_ml')),
            'ml_page_scope': _coalesce(metadata.get('ml_page_scope'), metadata.get('ml_pages')),
            'ml_policy_status': metadata.get('ml_policy_status'),
            'ml_exclusion_reason': metadata.get('ml_exclusion_reason'),
            'authority_id': metadata.get('authority_id', metadata.get('media_id')),
        }
    )

    rights_access = _clean_mapping(
        {
            'access_restriction': metadata.get('access_level'),
            'rights_owner': metadata.get('rights_owner'),
            'rights_holders': metadata.get('rights_holders'),
            'rights_note': metadata.get('rights_note'),
            'copyright_holder': metadata.get('copyright_holder'),
            'copyright_holder_other': metadata.get('copyright_holder_other'),
            'data_rights': metadata.get('data_rights'),
            'data_rights_holder': metadata.get('data_rights_holder'),
            'image_rights': metadata.get('image_rights'),
            'image_rights_holder': metadata.get('image_rights_holder'),
            'rights_statement_uri': metadata.get('rights_statement_uri'),
            'consent_status': metadata.get('current_consent_status'),
            'consent_scope': metadata.get('current_consent_scope'),
            'consent_evidence_uri': metadata.get('consent_evidence_uri'),
            'takedown_contact': metadata.get('takedown_contact'),
        }
    )

    retrieval_provenance = _clean_mapping(
        {
            'archive_record_pid': _coalesce(metadata.get('archive_record_pid'), metadata.get('record_pid')),
            'archive_record_id': _coalesce(metadata.get('archive_record_id'), metadata.get('record_id')),
            'attached_media_pid': _coalesce(metadata.get('attached_media_pid'), metadata.get('pid')),
            'asset_pid': metadata.get('asset_pid'),
            'asset_id': metadata.get('asset_id'),
            'asset_id_or_asset_pid': metadata.get('asset_id_or_asset_pid'),
            'media_id': _coalesce(metadata.get('authority_id'), metadata.get('media_id'), metadata.get('id')),
            'source_filename': source_filename,
            'source_uri': metadata.get('source_uri', metadata.get('master_url')),
            'archive_reference': metadata.get('archive_reference', metadata.get('reference_code')),
            'reference_code': metadata.get('reference_code', metadata.get('archive_reference')),
            'collection_title': metadata.get('record_title'),
            'repository': metadata.get('location_repository'),
            'accession_shelfmark': metadata.get('location_accession'),
            'box_number': metadata.get('location_box'),
            'container_title': metadata.get('box_title'),
            'location_note': metadata.get('location_note'),
            'record_public_uri': _coalesce(metadata.get('record_public_uri'), metadata.get('public_uri')),
            'page_count': metadata.get('page_count'),
            'page_count_source': metadata.get('page_count_source'),
            'page': metadata.get('source_page'),
            'page_scope': metadata.get('ml_page_scope'),
            'chunk_id': metadata.get('chunk_id'),
            'chunk_type': metadata.get('chunk_type'),
            'source_section': metadata.get('source_section'),
        }
    )

    catalogue_metadata = _clean_mapping(
        {
            'caption': _coalesce(metadata.get('caption'), metadata.get('master_label')),
            'title': document_title,
            'creator': creator,
            'date': document_date,
            'date_qualifier': metadata.get('date_qualifier'),
            'normalized_date': metadata.get('normalized_date'),
            'date_unknown': metadata.get('date_unknown'),
            'keywords': metadata.get('keywords'),
            'subjects': metadata.get('subjects'),
            'scope_and_content': metadata.get('scope_and_content'),
            'abstract': metadata.get('abstract'),
            'document_type': _coalesce(metadata.get('document_type'), metadata.get('category')),
            'extent_number': metadata.get('extent_number'),
            'extent_unit': metadata.get('extent_unit'),
            'project_theme': metadata.get('project_theme'),
            'project_title': metadata.get('project_title'),
            'methodology': metadata.get('methodology'),
            'language': metadata.get('language_codes'),
            'level': metadata.get('level'),
            'fonds_code': metadata.get('fonds_code'),
            'series_id': metadata.get('series_id'),
            'ddr_period': metadata.get('ddr_period'),
            'epistemic_stance': metadata.get('epistemic_stance'),
            'parent_collection': metadata.get('parent_collection'),
        }
    )

    return {
        'corpus_control': corpus_control,
        'rights_access': rights_access,
        'retrieval_provenance': retrieval_provenance,
        'catalogue_metadata': catalogue_metadata,
    }


def attach_metadata_roles(metadata: Mapping[str, Any]) -> Dict[str, Any]:
    payload = dict(metadata)
    payload.update(partition_metadata(payload))
    payload['metadata_roles_version'] = ROLE_VERSION
    return payload


def extract_metadata_roles(metadata: Optional[Mapping[str, Any]]) -> Dict[str, Dict[str, Any]]:
    payload = dict(metadata or {})
    if all(key in payload for key in ('corpus_control', 'rights_access', 'retrieval_provenance', 'catalogue_metadata')):
        return {
            'corpus_control': dict(payload.get('corpus_control') or {}),
            'rights_access': dict(payload.get('rights_access') or {}),
            'retrieval_provenance': dict(payload.get('retrieval_provenance') or {}),
            'catalogue_metadata': dict(payload.get('catalogue_metadata') or {}),
        }
    roles = partition_metadata(payload)
    roles.setdefault('rights_access', {})
    return roles


def _render_lines(label_map: Mapping[str, str], payload: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, label in label_map.items():
        value = payload.get(key)
        if not _has_value(value):
            continue
        if isinstance(value, (list, tuple, set)):
            rendered = '; '.join(str(item) for item in value if _has_value(item))
        else:
            rendered = str(value)
        if rendered:
            lines.append(f'{label}: {rendered}')
    return lines


def format_granite_source_block(index: int, chunk: Mapping[str, Any]) -> str:
    roles = {
        'retrieval_provenance': dict(chunk.get('provenance') or {}),
        'catalogue_metadata': dict(chunk.get('catalogue_metadata') or {}),
    }
    text = str(chunk.get('text') or '').strip()

    provenance_lines = _render_lines(
        {
            'archive_record_pid': 'ARCHIVE RECORD PID',
            'asset_pid': 'ASSET PID',
            'asset_id': 'ASSET ID',
            'media_id': 'MEDIA ID',
            'title': 'TITLE',
            'document_date': 'DATE',
            'creator': 'CREATOR',
            'archive_reference': 'ARCHIVE REFERENCE',
            'collection_title': 'COLLECTION',
            'repository': 'REPOSITORY',
            'page': 'PAGE',
            'source_section': 'SECTION',
            'chunk_id': 'CHUNK',
            'source_filename': 'SOURCE FILENAME',
        },
        roles['retrieval_provenance'],
    )
    catalogue_lines = _render_lines(
        {
            'caption': 'CAPTION',
            'document_type': 'DOCUMENT TYPE',
            'scope_and_content': 'SCOPE AND CONTENT',
            'abstract': 'ABSTRACT',
            'subjects': 'SUBJECTS',
            'project_theme': 'PROJECT THEME',
            'project_title': 'PROJECT TITLE',
            'methodology': 'METHODOLOGY',
            'language_codes': 'LANGUAGE CODES',
            'level': 'LEVEL',
            'fonds_code': 'FONDS CODE',
            'series_id': 'SERIES ID',
            'ddr_period': 'DDR PERIOD',
            'epistemic_stance': 'EPISTEMIC STANCE',
        },
        roles['catalogue_metadata'],
    )

    lines = [f'[SOURCE {index}]', '']
    lines.extend(provenance_lines)
    if catalogue_lines:
        lines.extend(['', 'ARCHIVE / CATALOGUE METADATA:'])
        lines.extend(catalogue_lines)
    lines.extend(['', 'SOURCE TEXT:', text])
    return '\n'.join(lines)


def format_inference_source_block(index: int, chunk: Mapping[str, Any]) -> str:
    """Format source context for the active model-neutral inference runtime."""
    return format_granite_source_block(index, chunk)