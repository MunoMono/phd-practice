#!/usr/bin/env python3
"""Generate a Turin Phase 2A corpus inventory manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.corpus_identity import DEFAULT_INGESTION_VERSION  # noqa: E402
from app.services.corpus_inventory_service import CorpusInventoryService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-csv', type=Path, required=True)
    parser.add_argument('--output-json', type=Path, required=True)
    parser.add_argument('--status', default='published')
    parser.add_argument('--pid', action='append', dest='pids', default=[])
    parser.add_argument('--include-non-ml', action='store_true')
    parser.add_argument('--download-dir', type=Path)
    parser.add_argument('--materialize-limit', type=int, default=0)
    parser.add_argument('--persist-db', action='store_true')
    parser.add_argument('--ingestion-version', default=DEFAULT_INGESTION_VERSION)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service = CorpusInventoryService()
    rows = service.flatten_published_pdf_sources(
        status=args.status,
        include_non_ml=args.include_non_ml,
        ingestion_version=args.ingestion_version,
    )

    if args.pids:
        wanted = set(args.pids)
        rows = [row for row in rows if row['pid'] in wanted]

    if args.download_dir:
        materialize_limit = args.materialize_limit if args.materialize_limit > 0 else None
        rows = service.materialize_sources(rows, args.download_dir, limit=materialize_limit)

    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    service.write_manifest_csv(rows, args.output_csv)
    service.write_manifest_json(rows, args.output_json)

    if args.persist_db:
        upserted = service.upsert_documents(rows)
        print(f'upserted_documents={upserted}')

    duplicate_checksums = service.find_duplicate_checksums(rows)
    print(f'manifest_rows={len(rows)}')
    print(f'corpus_version={rows[0]["corpus_version"] if rows else "none"}')
    print(f'duplicate_checksums={len(duplicate_checksums)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())