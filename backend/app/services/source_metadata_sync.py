"""Targeted, provenance-aware refresh of persisted DDR archive metadata."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
from typing import Any, Dict, Mapping, Optional, Sequence

from app.core.database import LocalSessionLocal
from app.models.document import Document
from app.services.authority_service import AuthorityService
from app.services.metadata_roles import attach_metadata_roles
from app.services.ml_policy import evaluate_ml_policy

logger = logging.getLogger(__name__)


ARCHIVE_METADATA_SOURCE = 'ddr_graphql.record_v1'
_TRACKED_METADATA_FIELDS = (
    'title', 'creator_agent_label', 'creators', 'date_begin', 'date_end',
    'artefact_date_from', 'artefact_date_to', 'scope_and_content', 'abstract',
    'caption', 'subjects', 'keywords', 'copyright_holder', 'data_rights',
    'data_rights_holder', 'image_rights', 'image_rights_holder',
    'rights_statement_uri', 'takedown_contact', 'access_level',
    'current_consent_status', 'current_consent_scope', 'consent_evidence_uri',
    'location_repository', 'location_accession', 'location_box', 'location_note',
    'reference_code', 'parent_collection', 'use_for_ml', 'ml_pages',
)


def _normalise(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _normalise(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return value


def _snapshot_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_normalise(payload), sort_keys=True, separators=(',', ':'), default=str)
    return sha256(encoded.encode('utf-8')).hexdigest()


def _asset_identity(asset: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        'asset_id': asset.get('assetId') or asset.get('asset_id'),
        'asset_pid': asset.get('pid') or asset.get('asset_pid'),
        'source_uri': asset.get('url') or asset.get('source_uri'),
        'filename': asset.get('filename') or asset.get('source_filename'),
        'role': asset.get('role'),
    }


class SourceMetadataSyncService:
    """Synchronise metadata for one existing source without re-ingesting it."""

    def __init__(self, authority_service: Optional[AuthorityService] = None, session_factory=LocalSessionLocal):
        self.authority_service = authority_service or AuthorityService()
        self.session_factory = session_factory

    @staticmethod
    def _matching_media(record: Mapping[str, Any], document: Document) -> Optional[Dict[str, Any]]:
        media_items = record.get('attached_media') or []
        for media in media_items:
            if media.get('pid') == document.pid or str(media.get('id')) == str(document.authority_id):
                return dict(media)
        return None

    @staticmethod
    def _matching_asset(media: Mapping[str, Any], document: Document) -> Optional[Dict[str, Any]]:
        assets = media.get('digital_assets') or []

        def with_master_url(asset: Mapping[str, Any]) -> Dict[str, Any]:
            enriched = dict(asset)
            if enriched.get('url'):
                return enriched
            for master_file in media.get('pdf_files') or []:
                if master_file.get('filename') == enriched.get('filename'):
                    enriched['url'] = master_file.get('url')
                    return enriched
            return enriched

        for asset in assets:
            if asset.get('assetId') == document.asset_id or asset.get('pid') == document.asset_pid:
                return with_master_url(asset)
        for asset in assets:
            if asset.get('url') and asset.get('url') == document.source_uri:
                return with_master_url(asset)
        expected_role = 'tiff_master' if (document.file_type or '').endswith('tiff') else 'pdf_master'
        for asset in assets:
            if asset.get('role') == expected_role:
                return with_master_url(asset)
        return None

    @staticmethod
    def _build_snapshot(record: Mapping[str, Any], media: Mapping[str, Any], asset: Mapping[str, Any], policy: Mapping[str, Any]) -> Dict[str, Any]:
        snapshot = deepcopy(dict(record))
        snapshot.pop('attached_media', None)
        snapshot.update({
            key: value for key, value in media.items()
            if key != 'digital_assets' and value is not None
        })
        snapshot.update({key: value for key, value in asset.items() if value is not None})
        snapshot.update({
            'authority_id': media.get('id'),
            'record_id': record.get('id'),
            'record_pid': record.get('pid'),
            'record_title': record.get('title'),
            'record_public_uri': record.get('public_uri'),
            'asset_id': asset.get('assetId'),
            'asset_pid': asset.get('pid'),
            'asset_id_or_asset_pid': asset.get('assetId') or asset.get('pid'),
            'asset_filename': asset.get('filename'),
            'source_filename': asset.get('filename'),
            'source_uri': asset.get('url'),
            'master_url': asset.get('url'),
            'asset_use_for_ml': asset.get('use_for_ml'),
            'use_for_ml': policy.get('use_for_ml'),
            'ml_pages': asset.get('ml_pages'),
            'ml_annotation': asset.get('ml_annotation') or media.get('ml_annotation'),
            'ml_page_scope': policy.get('ml_page_scope'),
            'ml_policy_status': policy.get('ml_policy_status'),
            'ml_exclusion_reason': policy.get('ml_exclusion_reason'),
        })
        return attach_metadata_roles(snapshot)

    @staticmethod
    def _changed_fields(previous: Mapping[str, Any], current: Mapping[str, Any], policy_changed: bool) -> list[str]:
        changed = [field for field in _TRACKED_METADATA_FIELDS if previous.get(field) != current.get(field)]
        if policy_changed and 'ml_policy_status' not in changed:
            changed.append('ml_policy_status')
        return changed

    @staticmethod
    def _current_asset_identity(document: Document) -> Dict[str, Any]:
        file_type = document.file_type or ''
        return {
            'asset_id': document.asset_id,
            'asset_pid': document.asset_pid,
            'source_uri': document.source_uri,
            'filename': document.filename,
            'role': 'tiff_master' if file_type.endswith('tiff') else 'pdf_master',
        }

    def _record_error(self, document: Document, error: str, db: Any) -> Dict[str, Any]:
        document.metadata_sync_status = 'error'
        document.metadata_sync_error = error
        db.commit()
        return {
            'document_id': document.document_id,
            'sync_status': 'error',
            'fetched_at': None,
            'metadata_changed': False,
            'policy_changed': False,
            'source_asset_changed': bool(document.source_asset_changed),
            'reingestion_required': bool(document.reingestion_required),
            'changed_fields': [],
            'errors': [error],
        }

    def sync_archive_metadata(self, document_id: str) -> Dict[str, Any]:
        db = self.session_factory()
        try:
            document = db.query(Document).filter(Document.document_id == document_id).first()
            if document is None:
                raise LookupError(f'Document {document_id} was not found')

            record_pid = document.archive_record_pid or document.pid
            record = self.authority_service.fetch_record_by_pid(record_pid)
            if not record:
                return self._record_error(document, f'DDR GraphQL returned no record for PID {record_pid}', db)

            media = self._matching_media(record, document)
            if not media:
                return self._record_error(document, f'DDR GraphQL record {record_pid} has no matching attached media', db)

            asset = self._matching_asset(media, document)
            if not asset:
                return self._record_error(document, f'DDR GraphQL media {document.pid} has no matching source asset', db)

            policy = evaluate_ml_policy(
                asset_present=True,
                asset_use_for_ml=asset.get('use_for_ml'),
                ml_pages=asset.get('ml_pages'),
            )
            snapshot = self._build_snapshot(record, media, asset, policy)
            prior_snapshot = dict(document.authority_data or {})
            fetched_at = datetime.now(timezone.utc)
            snapshot_hash = _snapshot_hash(snapshot)
            upstream_asset_identity = _asset_identity(asset)
            upstream_asset_identity_hash = _snapshot_hash(upstream_asset_identity)
            local_asset_identity_hash = _snapshot_hash(self._current_asset_identity(document))
            asset_changed = local_asset_identity_hash != upstream_asset_identity_hash
            policy_changed = any(
                getattr(document, field) != policy.get(field)
                for field in ('use_for_ml', 'ml_page_scope', 'ml_policy_status', 'ml_exclusion_reason')
            )
            changed_fields = self._changed_fields(prior_snapshot, snapshot, policy_changed)
            metadata_changed = snapshot_hash != document.archive_metadata_snapshot_hash if document.archive_metadata_snapshot_hash else bool(changed_fields)

            document.authority_data = snapshot
            document.authority_id = media.get('id') or document.authority_id
            document.archive_record_id = record.get('id') or document.archive_record_id
            document.archive_record_pid = record.get('pid') or document.archive_record_pid
            document.title = snapshot.get('title') or document.title
            document.use_for_ml = policy.get('use_for_ml')
            document.ml_page_scope = policy.get('ml_page_scope')
            document.ml_policy_status = policy.get('ml_policy_status')
            document.ml_exclusion_reason = policy.get('ml_exclusion_reason')
            document.archive_metadata_fetched_at = fetched_at
            document.archive_metadata_source = ARCHIVE_METADATA_SOURCE
            document.archive_metadata_snapshot_hash = snapshot_hash
            document.source_asset_checksum = asset.get('checksum_sha256') or asset.get('checksum')
            document.source_asset_identity_hash = upstream_asset_identity_hash
            document.source_asset_changed = int(asset_changed)
            document.reingestion_required = int(asset_changed)
            document.metadata_sync_status = 'source_asset_changed' if asset_changed else ('updated' if metadata_changed else 'current')
            document.metadata_sync_error = None
            db.commit()

            return {
                'document_id': document.document_id,
                'sync_status': document.metadata_sync_status,
                'fetched_at': fetched_at.isoformat(),
                'metadata_changed': metadata_changed,
                'policy_changed': policy_changed,
                'source_asset_changed': asset_changed,
                'reingestion_required': bool(document.reingestion_required),
                'changed_fields': changed_fields,
                'errors': [],
            }
        except LookupError:
            raise
        except Exception as error:
            db.rollback()
            logger.exception('Archive metadata sync failed for %s', document_id)
            try:
                document = db.query(Document).filter(Document.document_id == document_id).first()
                if document is not None:
                    return self._record_error(document, str(error), db)
            except Exception:
                db.rollback()
            return {
                'document_id': document_id,
                'sync_status': 'error',
                'fetched_at': None,
                'metadata_changed': False,
                'policy_changed': False,
                'source_asset_changed': False,
                'reingestion_required': False,
                'changed_fields': [],
                'errors': [str(error)],
            }
        finally:
            db.close()