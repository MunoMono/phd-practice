#!/usr/bin/env python3
"""Dry-run or apply canonical DDR metadata reconciliation for existing sources."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.database import LocalSessionLocal
from app.models.document import Document
from app.services.source_metadata_sync import SourceMetadataSyncService


def database_counts() -> dict[str, int]:
    db = LocalSessionLocal()
    try:
        return {
            'documents': db.query(Document).count(),
            'document_chunks': db.execute(text('SELECT count(*) FROM document_chunks')).scalar_one(),
        }
    finally:
        db.close()


def report_for_run(summary: dict[str, Any], before: dict[str, int], after: dict[str, int]) -> dict[str, Any]:
    changed = [result for result in summary['results'] if result['metadata_changed']]
    asset_changes = [result for result in summary['results'] if result['source_asset_changed']]
    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'baseline_counts': before,
        'after_counts': after,
        'reconciliation': summary,
        'representative_changes': changed[:10],
        'source_asset_changes_requiring_later_reingestion': asset_changes,
        'extraction_integrity': {
            'docling_invoked': False,
            'extracted_text_rewritten': False,
            'chunks_regenerated': False,
            'fts_rebuilt': False,
            'document_count_unchanged': before['documents'] == after['documents'],
            'chunk_count_unchanged': before['document_chunks'] == after['document_chunks'],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Persist metadata changes after reviewing a dry run.')
    parser.add_argument('--batch-size', type=int, default=50)
    parser.add_argument('--policy-status', action='append', dest='policy_statuses')
    parser.add_argument('--output', type=Path, help='Write the JSON report to this path.')
    args = parser.parse_args()

    before = database_counts()
    summary = SourceMetadataSyncService().sync_all_archive_metadata(
        dry_run=not args.apply,
        eligible_statuses=set(args.policy_statuses) if args.policy_statuses else None,
        batch_size=args.batch_size,
    )
    after = database_counts()
    report = report_for_run(summary, before, after)
    rendered = json.dumps(report, indent=2, default=str)
    if args.output:
        args.output.write_text(rendered + '\n', encoding='utf-8')
    print(rendered)
    return 0 if before == after else 1


if __name__ == '__main__':
    raise SystemExit(main())