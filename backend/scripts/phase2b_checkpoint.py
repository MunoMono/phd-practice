"""Persist and verify a representative Turin Phase 2B policy sample."""

from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
REPO_ROOT = BACKEND_ROOT.parent

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import LocalSessionLocal  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.services.corpus_inventory_service import CorpusInventoryService  # noqa: E402


def main() -> int:
    service = CorpusInventoryService()
    rows = service.flatten_published_pdf_sources()

    wanted_statuses = [
        'eligible_unrestricted',
        'eligible_page_restricted',
        'excluded_use_for_ml_false',
    ]
    selected = [
        next(row for row in rows if row['ml_policy_status'] == status)
        for status in wanted_statuses
    ]

    materialized = service.materialize_sources(
        selected[:2],
        REPO_ROOT / 'artifacts' / 'turin-phase2b-sample-pdfs',
        limit=2,
    )
    materialized.append(selected[2])

    upserted = service.upsert_documents(materialized)

    db = LocalSessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter(Document.document_id.in_([row['document_id'] for row in materialized]))
            .order_by(Document.document_id)
            .all()
        )
        payload = [
            {
                'document_id': doc.document_id,
                'pid': doc.pid,
                'archive_record_pid': doc.archive_record_pid,
                'authority_id': doc.authority_id,
                'asset_id': doc.asset_id,
                'asset_pid': doc.asset_pid,
                'asset_id_or_asset_pid': doc.asset_id_or_asset_pid,
                'source_uri': doc.source_uri,
                'checksum_sha256': doc.checksum_sha256,
                'page_count': doc.page_count,
                'ocr_status': doc.ocr_status,
                'processing_status': doc.processing_status,
                'use_for_ml': doc.use_for_ml,
                'ml_page_scope': doc.ml_page_scope,
                'ml_policy_status': doc.ml_policy_status,
                'ml_exclusion_reason': doc.ml_exclusion_reason,
            }
            for doc in docs
        ]
    finally:
        db.close()

    artifact = {
        'upserted': upserted,
        'documents': payload,
    }
    output_path = REPO_ROOT / 'artifacts' / 'turin-phase2b-sample-persistence.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(artifact, indent=2), encoding='utf-8')
    print(output_path)
    print(json.dumps(artifact, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())