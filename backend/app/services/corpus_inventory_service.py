"""Archive PDF inventory and manifest generation for Turin Phase 2A."""

from __future__ import annotations

import csv
import json
import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

from app.core.database import LocalSessionLocal
from app.models.document import Document
from app.services.authority_service import AuthorityService
from app.services.corpus_identity import (
    DEFAULT_INGESTION_VERSION,
    build_corpus_version,
    build_stable_document_id,
    compute_sha256,
)
from app.services.metadata_roles import attach_metadata_roles
from app.services.ml_policy import evaluate_ml_policy

logger = logging.getLogger(__name__)

MANIFEST_FIELDS = [
    'document_id',
    'pid',
    'source_filename',
    'checksum_sha256',
    'title',
    'creator',
    'date_text',
    'document_type',
    'archive_reference',
    'page_count',
    'ocr_status',
    'ingestion_status',
    'ingestion_error',
    'chunk_count',
    'ingestion_version',
    'corpus_version',
    'source_uri',
    'source_path',
    'authority_id',
    'archive_record_id',
    'archive_record_pid',
    'asset_id',
    'asset_pid',
    'asset_id_or_asset_pid',
    'metadata_source',
    'access_level',
    'rights_note',
    'rights_owner',
    'rights_holders',
    'copyright_holder',
    'copyright_holder_other',
    'data_rights',
    'data_rights_holder',
    'image_rights',
    'image_rights_holder',
    'current_consent_status',
    'current_consent_scope',
    'consent_evidence_uri',
    'location_repository',
    'location_accession',
    'location_box',
    'box_title',
    'location_note',
    'language_codes',
    'keywords',
    'subjects',
    'extent_number',
    'extent_unit',
    'date_qualifier',
    'normalized_date',
    'date_unknown',
    'page_count_source',
    'media_used_for_ml',
    'use_for_ml',
    'ml_pages',
    'ml_page_scope',
    'ml_annotation',
    'ml_policy_status',
    'ml_exclusion_reason',
    'record_title',
    'record_public_uri',
]


class CorpusInventoryService:
    def __init__(self, authority_service: Optional[AuthorityService] = None):
        self.authority_service = authority_service or AuthorityService()

    @staticmethod
    def _first_non_empty(*values: Any) -> Optional[str]:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text and text not in {'[]', '{}', 'null', 'None'}:
                return text
        return None

    def _build_date_text(self, media_item: Dict[str, Any]) -> Optional[str]:
        return self._first_non_empty(
            media_item.get('date_begin') if media_item.get('date_begin') == media_item.get('date_end') else None,
            f"{media_item.get('date_begin')}–{media_item.get('date_end')}" if media_item.get('date_begin') and media_item.get('date_end') else None,
            media_item.get('artefact_date_from') if media_item.get('artefact_date_from') == media_item.get('artefact_date_to') else None,
            f"{media_item.get('artefact_date_from')}–{media_item.get('artefact_date_to')}" if media_item.get('artefact_date_from') and media_item.get('artefact_date_to') else None,
        )

    def _extract_creator(self, media_item: Dict[str, Any]) -> Optional[str]:
        creator_label = self._first_non_empty(media_item.get('creator_agent_label'))
        if creator_label:
            return creator_label

        creators = media_item.get('creators') or []
        labels = []
        for creator in creators:
            if isinstance(creator, dict):
                label = self._first_non_empty(
                    creator.get('label'),
                    creator.get('title'),
                    creator.get('name'),
                )
                if label:
                    labels.append(label)
            else:
                label = self._first_non_empty(creator)
                if label:
                    labels.append(label)
        return '; '.join(labels) if labels else None

    @staticmethod
    def _extract_keyword_labels(values: Any) -> List[str]:
        if not values:
            return []

        labels: List[str] = []
        for value in values:
            if isinstance(value, dict):
                label = value.get('label')
            else:
                label = value
            text = str(label).strip() if label is not None else ''
            if text:
                labels.append(text)
        return labels

    @staticmethod
    def _match_digital_asset(media_item: Dict[str, Any], pdf_file: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for asset in media_item.get('digital_assets') or []:
            if asset.get('role') != 'pdf_master':
                continue
            if asset.get('filename') == pdf_file.get('filename'):
                return asset
        return None

    def flatten_published_pdf_sources(
        self,
        status: str = 'published',
        include_non_ml: bool = False,
        ingestion_version: str = DEFAULT_INGESTION_VERSION,
    ) -> List[Dict[str, Any]]:
        records = self.authority_service.fetch_published_records(status=status)
        return self.flatten_records_pdf_sources(records, include_non_ml=include_non_ml, ingestion_version=ingestion_version)

    def flatten_records_pdf_sources(
        self,
        records: Iterable[Dict[str, Any]],
        include_non_ml: bool = False,
        ingestion_version: str = DEFAULT_INGESTION_VERSION,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []

        for record in records:
            attached_media = record.get('attached_media') or []
            for media_item in attached_media:
                pdf_files = [
                    pdf_file for pdf_file in (media_item.get('pdf_files') or [])
                    if pdf_file.get('role') == 'pdf_master'
                ]

                for pdf_file in pdf_files:
                    asset = self._match_digital_asset(media_item, pdf_file)
                    asset_use_for_ml = asset.get('use_for_ml') if asset else None
                    asset_identifier = self._first_non_empty(
                        asset.get('assetId') if asset else None,
                        asset.get('pid') if asset else None,
                    )
                    policy = evaluate_ml_policy(
                        asset_present=asset is not None,
                        asset_use_for_ml=asset_use_for_ml,
                        ml_pages=asset.get('ml_pages') if asset else None,
                    )

                    source_uri = pdf_file.get('url')
                    source_filename = pdf_file.get('filename')
                    pid = media_item.get('pid')
                    if not (pid and source_uri and source_filename):
                        continue

                    title = self._first_non_empty(pdf_file.get('label'), asset.get('label') if asset else None, media_item.get('title'), record.get('title'))
                    asset_keywords = self._extract_keyword_labels(asset.get('keywords') if asset else None)
                    media_keywords = self._extract_keyword_labels(media_item.get('keywords'))
                    row = {
                        'document_id': build_stable_document_id(
                            pid,
                            source_filename,
                            source_uri,
                            archive_record_pid=record.get('pid'),
                            asset_identifier=asset_identifier,
                        ),
                        'pid': pid,
                        'source_filename': source_filename,
                        'checksum_sha256': None,
                        'title': title,
                        'creator': self._extract_creator(media_item),
                        'date_text': self._first_non_empty(asset.get('display_date') if asset else None, self._build_date_text(media_item)),
                        'date_qualifier': self._first_non_empty(asset.get('date_qualifier') if asset else None),
                        'normalized_date': self._first_non_empty(asset.get('normalized_date') if asset else None),
                        'date_unknown': asset.get('date_unknown') if asset else None,
                        'document_type': media_item.get('category'),
                        'archive_reference': media_item.get('reference_code'),
                        'page_count': None,
                        'page_count_source': None,
                        'ocr_status': 'unverified_remote_source',
                        'ingestion_status': 'pending',
                        'ingestion_error': None,
                        'chunk_count': None,
                        'ingestion_version': ingestion_version,
                        'corpus_version': None,
                        'source_uri': source_uri,
                        'source_path': None,
                        'authority_id': media_item.get('id'),
                        'archive_record_id': record.get('id'),
                        'archive_record_pid': record.get('pid'),
                        'asset_id': asset.get('assetId') if asset else None,
                        'asset_pid': asset.get('pid') if asset else None,
                        'asset_id_or_asset_pid': asset_identifier,
                        'metadata_source': 'archive_graphql.records_v1',
                        'attached_media_pid': pid,
                        'access_level': self._first_non_empty(media_item.get('access_level'), record.get('access_level')),
                        'rights_note': self._first_non_empty(
                            asset.get('rights_holders') if asset else None,
                            asset.get('data_rights_holder') if asset else None,
                            asset.get('copyright_holder') if asset else None,
                            media_item.get('rights_holders'),
                            media_item.get('copyright_holder'),
                            record.get('rights_holders'),
                            record.get('copyright_holder'),
                        ),
                        'rights_owner': self._first_non_empty(asset.get('rights_owner') if asset else None, media_item.get('rights_owner'), record.get('rights_owner')),
                        'rights_holders': self._first_non_empty(asset.get('rights_holders') if asset else None, media_item.get('rights_holders'), record.get('rights_holders')),
                        'copyright_holder': self._first_non_empty(asset.get('copyright_holder') if asset else None, media_item.get('copyright_holder'), record.get('copyright_holder')),
                        'copyright_holder_other': self._first_non_empty(media_item.get('copyright_holder_other'), record.get('copyright_holder_other')),
                        'data_rights': self._first_non_empty(asset.get('data_rights') if asset else None, media_item.get('data_rights'), record.get('data_rights')),
                        'data_rights_holder': self._first_non_empty(asset.get('data_rights_holder') if asset else None, media_item.get('data_rights_holder'), record.get('data_rights_holder')),
                        'image_rights': self._first_non_empty(asset.get('image_rights') if asset else None, media_item.get('image_rights'), record.get('image_rights')),
                        'image_rights_holder': self._first_non_empty(asset.get('image_rights_holder') if asset else None, media_item.get('image_rights_holder'), record.get('image_rights_holder')),
                        'rights_statement_uri': self._first_non_empty(media_item.get('rights_statement_uri'), record.get('rights_statement_uri')),
                        'level': media_item.get('level'),
                        'fonds_code': media_item.get('fonds_code'),
                        'series_id': media_item.get('series_id'),
                        'ddr_period': media_item.get('ddr_period'),
                        'scope_and_content': media_item.get('scope_and_content'),
                        'methodology': media_item.get('methodology'),
                        'project_theme': media_item.get('project_theme'),
                        'project_title': media_item.get('project_title'),
                        'location_repository': self._first_non_empty(asset.get('location_repository') if asset else None, media_item.get('location_repository'), record.get('location_repository')),
                        'location_accession': self._first_non_empty(asset.get('location_accession') if asset else None, media_item.get('location_accession'), record.get('location_accession')),
                        'location_box': self._first_non_empty(asset.get('location_box') if asset else None, media_item.get('location_box'), record.get('location_box')),
                        'box_title': self._first_non_empty(media_item.get('box_title'), record.get('box_title')),
                        'location_note': self._first_non_empty(asset.get('location_note') if asset else None, media_item.get('location_note'), record.get('location_note')),
                        'current_consent_status': self._first_non_empty(media_item.get('current_consent_status'), record.get('current_consent_status')),
                        'current_consent_scope': self._first_non_empty(media_item.get('current_consent_scope'), record.get('current_consent_scope')),
                        'consent_evidence_uri': self._first_non_empty(media_item.get('consent_evidence_uri'), record.get('consent_evidence_uri')),
                        'takedown_contact': self._first_non_empty(media_item.get('takedown_contact'), record.get('takedown_contact')),
                        'abstract': media_item.get('abstract'),
                        'caption': self._first_non_empty(asset.get('label') if asset else None, media_item.get('caption'), media_item.get('title')),
                        'keywords': asset_keywords or media_keywords,
                        'subjects': media_item.get('subjects') or [],
                        'parent_collection': media_item.get('parent_collection'),
                        'language_codes': self._first_non_empty(asset.get('language_codes') if asset else None, media_item.get('language_codes'), record.get('language_codes')),
                        'extent_number': self._first_non_empty(asset.get('extent_number') if asset else None, media_item.get('extent_number')),
                        'extent_unit': self._first_non_empty(asset.get('extent_unit') if asset else None, media_item.get('extent_unit')),
                        'media_used_for_ml': media_item.get('used_for_ml'),
                        'use_for_ml': policy.get('use_for_ml'),
                        'ml_pages': asset.get('ml_pages') if asset else None,
                        'ml_page_scope': policy.get('ml_page_scope'),
                        'ml_annotation': self._first_non_empty(
                            asset.get('ml_annotation') if asset else None,
                            media_item.get('ml_annotation'),
                        ),
                        'ml_policy_status': policy.get('ml_policy_status'),
                        'ml_exclusion_reason': policy.get('ml_exclusion_reason'),
                        'record_title': record.get('title'),
                        'record_public_uri': record.get('public_uri'),
                    }
                    rows.append(row)

        corpus_version = build_corpus_version(rows, ingestion_version=ingestion_version)
        for row in rows:
            row['corpus_version'] = corpus_version

        rows.sort(key=lambda row: (str(row['pid']), str(row['source_filename'])))
        return rows

    @staticmethod
    def _page_count_from_pdfinfo(file_path: str | Path) -> Optional[int]:
        try:
            result = subprocess.run(
                ['pdfinfo', str(file_path)],
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None

        for line in result.stdout.splitlines():
            if line.startswith('Pages:'):
                value = line.split(':', 1)[1].strip()
                return int(value) if value.isdigit() else None
        return None

    @staticmethod
    def _detect_text_layer(file_path: str | Path) -> str:
        try:
            result = subprocess.run(
                ['pdftotext', str(file_path), '-'],
                check=True,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return 'unknown'
        except subprocess.CalledProcessError:
            return 'unreadable'

        extracted = (result.stdout or '').strip()
        return 'text_layer_present' if extracted else 'text_layer_empty'

    def materialize_sources(
        self,
        rows: Iterable[Dict[str, Any]],
        download_dir: str | Path,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        download_path = Path(download_dir)
        download_path.mkdir(parents=True, exist_ok=True)
        materialized_rows: List[Dict[str, Any]] = []

        for index, row in enumerate(rows):
            next_row = dict(row)
            if limit is not None and index >= limit:
                materialized_rows.append(next_row)
                continue

            target_path = download_path / next_row['source_filename']
            try:
                if not target_path.exists():
                    response = requests.get(next_row['source_uri'], timeout=60)
                    response.raise_for_status()
                    target_path.write_bytes(response.content)
                next_row['source_path'] = str(target_path)
                next_row['checksum_sha256'] = compute_sha256(target_path)
                next_row['page_count'] = self._page_count_from_pdfinfo(target_path)
                next_row['page_count_source'] = 'pdfinfo_materialized_source' if next_row['page_count'] is not None else None
                next_row['ocr_status'] = self._detect_text_layer(target_path)
                next_row['ingestion_status'] = 'inventory_ready'
            except Exception as exc:
                next_row['source_path'] = str(target_path)
                next_row['ingestion_status'] = 'inventory_failed'
                next_row['ingestion_error'] = str(exc)
            materialized_rows.append(next_row)

        return materialized_rows

    def upsert_documents(self, rows: Iterable[Dict[str, Any]]) -> int:
        db = LocalSessionLocal()
        upserted = 0
        try:
            for row in rows:
                source_uri = row.get('source_uri')
                document_id = row['document_id']
                existing = None
                if source_uri:
                    existing = db.query(Document).filter(Document.source_uri == source_uri).first()
                if existing is None:
                    existing = db.query(Document).filter(Document.document_id == document_id).first()

                publication_year = 1970
                date_text = row.get('date_text') or ''
                if isinstance(date_text, str):
                    digits = ''.join(ch for ch in date_text if ch.isdigit())
                    if len(digits) >= 4:
                        publication_year = int(digits[:4])

                payload = {
                    'document_id': document_id,
                    'pid': row['pid'],
                    'authority_id': row.get('authority_id'),
                    'archive_record_id': row.get('archive_record_id'),
                    'archive_record_pid': row.get('archive_record_pid'),
                    'asset_id': row.get('asset_id'),
                    'asset_pid': row.get('asset_pid'),
                    'asset_id_or_asset_pid': row.get('asset_id_or_asset_pid'),
                    'title': row.get('title'),
                    'publication_year': publication_year,
                    'filename': row['source_filename'],
                    'file_type': 'application/pdf',
                    's3_key': row.get('source_uri'),
                    'source_uri': row.get('source_uri'),
                    'source_path': row.get('source_path'),
                    'file_size_bytes': Path(row['source_path']).stat().st_size if row.get('source_path') and Path(row['source_path']).exists() else None,
                    'checksum_sha256': row.get('checksum_sha256'),
                    'page_count': row.get('page_count'),
                    'ocr_status': row.get('ocr_status'),
                    'processing_status': row.get('ml_policy_status') or row.get('ingestion_status') or 'pending',
                    'processing_error': row.get('ingestion_error'),
                    'ingestion_version': row.get('ingestion_version'),
                    'corpus_version': row.get('corpus_version'),
                    'metadata_source': row.get('metadata_source'),
                    'use_for_ml': row.get('use_for_ml'),
                    'ml_page_scope': row.get('ml_page_scope'),
                    'ml_policy_status': row.get('ml_policy_status'),
                    'ml_exclusion_reason': row.get('ml_exclusion_reason'),
                    'authority_data': attach_metadata_roles({
                        'pid': row.get('pid'),
                        'media_id': row.get('authority_id'),
                        'authority_id': row.get('authority_id'),
                        'record_id': row.get('archive_record_id'),
                        'record_pid': row.get('archive_record_pid'),
                        'asset_id': row.get('asset_id'),
                        'asset_pid': row.get('asset_pid'),
                        'asset_id_or_asset_pid': row.get('asset_id_or_asset_pid'),
                        'title': row.get('title'),
                        'source_filename': row.get('source_filename'),
                        'source_uri': row.get('source_uri'),
                        'record_title': row.get('record_title'),
                        'record_public_uri': row.get('record_public_uri'),
                        'creator': row.get('creator'),
                        'date_text': row.get('date_text'),
                        'document_type': row.get('document_type'),
                        'archive_reference': row.get('archive_reference'),
                        'page_count': row.get('page_count'),
                        'page_count_source': row.get('page_count_source'),
                        'rights_note': row.get('rights_note'),
                        'rights_owner': row.get('rights_owner'),
                        'rights_holders': row.get('rights_holders'),
                        'copyright_holder': row.get('copyright_holder'),
                        'copyright_holder_other': row.get('copyright_holder_other'),
                        'data_rights': row.get('data_rights'),
                        'data_rights_holder': row.get('data_rights_holder'),
                        'image_rights': row.get('image_rights'),
                        'image_rights_holder': row.get('image_rights_holder'),
                        'rights_statement_uri': row.get('rights_statement_uri'),
                        'access_level': row.get('access_level'),
                        'current_consent_status': row.get('current_consent_status'),
                        'current_consent_scope': row.get('current_consent_scope'),
                        'consent_evidence_uri': row.get('consent_evidence_uri'),
                        'level': row.get('level'),
                        'fonds_code': row.get('fonds_code'),
                        'series_id': row.get('series_id'),
                        'ddr_period': row.get('ddr_period'),
                        'scope_and_content': row.get('scope_and_content'),
                        'methodology': row.get('methodology'),
                        'project_theme': row.get('project_theme'),
                        'project_title': row.get('project_title'),
                        'location_repository': row.get('location_repository'),
                        'location_accession': row.get('location_accession'),
                        'location_box': row.get('location_box'),
                        'box_title': row.get('box_title'),
                        'location_note': row.get('location_note'),
                        'current_consent_status': row.get('current_consent_status'),
                        'takedown_contact': row.get('takedown_contact'),
                        'abstract': row.get('abstract'),
                        'caption': row.get('caption'),
                        'keywords': row.get('keywords'),
                        'subjects': row.get('subjects'),
                        'parent_collection': row.get('parent_collection'),
                        'language_codes': row.get('language_codes'),
                        'extent_number': row.get('extent_number'),
                        'extent_unit': row.get('extent_unit'),
                        'date_qualifier': row.get('date_qualifier'),
                        'normalized_date': row.get('normalized_date'),
                        'date_unknown': row.get('date_unknown'),
                        'media_used_for_ml': row.get('media_used_for_ml'),
                        'use_for_ml': row.get('use_for_ml'),
                        'ml_pages': row.get('ml_pages'),
                        'ml_page_scope': row.get('ml_page_scope'),
                        'ml_annotation': row.get('ml_annotation'),
                        'ml_policy_status': row.get('ml_policy_status'),
                        'ml_exclusion_reason': row.get('ml_exclusion_reason'),
                    }),
                }

                if existing is None:
                    db.add(Document(**payload))
                else:
                    for key, value in payload.items():
                        setattr(existing, key, value)
                upserted += 1

            db.commit()
            return upserted
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def find_duplicate_checksums(rows: Iterable[Dict[str, Any]]) -> Dict[str, List[str]]:
        seen: Dict[str, List[str]] = {}
        for row in rows:
            checksum = row.get('checksum_sha256')
            if not checksum:
                continue
            seen.setdefault(str(checksum), []).append(str(row.get('source_filename')))
        return {checksum: filenames for checksum, filenames in seen.items() if len(filenames) > 1}

    @staticmethod
    def find_source_record(rows: Iterable[Dict[str, Any]], pid: str, source_filename: str) -> Optional[Dict[str, Any]]:
        for row in rows:
            if row.get('pid') == pid and row.get('source_filename') == source_filename:
                return row
        return None

    @staticmethod
    def write_manifest_csv(rows: Iterable[Dict[str, Any]], file_path: str | Path) -> None:
        with Path(file_path).open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field) for field in MANIFEST_FIELDS})

    @staticmethod
    def write_manifest_json(rows: Iterable[Dict[str, Any]], file_path: str | Path) -> None:
        with Path(file_path).open('w', encoding='utf-8') as handle:
            json.dump(list(rows), handle, indent=2, ensure_ascii=True)