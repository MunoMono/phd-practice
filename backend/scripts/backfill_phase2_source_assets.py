#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.authority_service import AuthorityService
from app.services.corpus_inventory_service import CorpusInventoryService


def _filter_rows(rows, media_pids, asset_ids, asset_pids, policy_statuses):
    filtered = []
    for row in rows:
        if media_pids and row.get('pid') not in media_pids:
            continue
        if asset_ids and row.get('asset_id') not in asset_ids:
            continue
        if asset_pids and row.get('asset_pid') not in asset_pids:
            continue
        if policy_statuses and row.get('ml_policy_status') not in policy_statuses:
            continue
        filtered.append(row)
    return filtered


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill bounded Phase 2 source assets into documents table.')
    parser.add_argument('--archive-record-pid', action='append', dest='archive_record_pids', default=[], help='Archive record PID to fetch with record_v1(id: PID). Repeatable.')
    parser.add_argument('--attached-media-pid', action='append', dest='media_pids', default=[], help='Attached media PID to keep. Repeatable.')
    parser.add_argument('--asset-id', action='append', dest='asset_ids', default=[], help='Asset ID to keep. Repeatable.')
    parser.add_argument('--asset-pid', action='append', dest='asset_pids', default=[], help='Asset PID to keep. Repeatable.')
    parser.add_argument('--ml-policy-status', action='append', dest='policy_statuses', default=[], help='Policy status to keep. Repeatable.')
    parser.add_argument('--materialize-dir', default='', help='Optional directory for bounded PDF materialization to capture checksum/page count.')
    parser.add_argument('--output-json', default='', help='Optional path to write the selected rows and summary as JSON.')
    parser.add_argument('--dry-run', action='store_true', help='Print selected rows without writing to the database.')
    args = parser.parse_args()

    authority_service = AuthorityService()
    inventory_service = CorpusInventoryService(authority_service=authority_service)

    if args.archive_record_pids:
        records = []
        for archive_record_pid in args.archive_record_pids:
            record = authority_service.fetch_record_by_pid(archive_record_pid)
            if not record:
                raise SystemExit(f'No archive record found for PID {archive_record_pid}')
            records.append(record)
        rows = inventory_service.flatten_records_pdf_sources(records)
    else:
        rows = inventory_service.flatten_published_pdf_sources()

    rows = _filter_rows(rows, set(args.media_pids), set(args.asset_ids), set(args.asset_pids), set(args.policy_statuses))

    if args.materialize_dir:
        rows = inventory_service.materialize_sources(rows, args.materialize_dir)

    summary = {
        'rows': len(rows),
        'policy_counts': dict(sorted(Counter(row.get('ml_policy_status') for row in rows).items())),
        'eligible_rows': sum(1 for row in rows if row.get('use_for_ml')),
        'excluded_rows': sum(1 for row in rows if not row.get('use_for_ml')),
        'unique_document_ids': len({row.get('document_id') for row in rows}),
        'unique_source_uris': len({row.get('source_uri') for row in rows if row.get('source_uri')}),
    }

    artifact = {
        'summary': summary,
        'documents': rows,
    }

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(artifact, indent=2), encoding='utf-8')

    print(json.dumps(artifact, indent=2))

    if args.dry_run:
        return 0

    upserted = inventory_service.upsert_documents(rows)
    print(json.dumps({'upserted': upserted, 'archive_record_pids': args.archive_record_pids, 'summary': summary}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())