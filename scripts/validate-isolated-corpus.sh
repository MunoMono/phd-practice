#!/bin/bash

set -euo pipefail

TARGET_DATABASE="testamentary_traces_retrieval_validation"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-phd-practice-db}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"

usage() {
    echo "Usage: scripts/validate-isolated-corpus.sh [--database <name>]"
}

require_safe_database() {
    if [[ ! "$1" =~ ^testamentary_traces_[a-z0-9_]*retrieval_validation$ ]]; then
        echo "ERROR: validator accepts only testamentary_traces_*_retrieval_validation targets" >&2
        exit 2
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --database)
            TARGET_DATABASE="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

require_safe_database "$TARGET_DATABASE"

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER_NAME"; then
    echo "ERROR: database container is not running: $DB_CONTAINER_NAME" >&2
    exit 1
fi
if ! docker exec -i "$DB_CONTAINER_NAME" psql -U "$POSTGRES_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DATABASE'" | grep -qx '1'; then
    echo "ERROR: isolated database does not exist: $TARGET_DATABASE" >&2
    exit 1
fi

has_search_tsv="$(docker exec -i "$DB_CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$TARGET_DATABASE" -tAc "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'document_chunks' AND column_name = 'search_tsv')")"
if [[ "$has_search_tsv" != "t" ]]; then
    echo "database=$TARGET_DATABASE"
    echo "search_tsv=missing"
    echo "baseline_match=no"
    echo "ERROR: search_tsv is absent; apply backend/migrations/006_lightweight_fts_ingestion.sql only after confirming accepted chunks are present." >&2
    exit 2
fi

stats="$(docker exec -i "$DB_CONTAINER_NAME" psql -U "$POSTGRES_USER" -d "$TARGET_DATABASE" -At -F '|' -c "
WITH resolved AS (
    SELECT document_id,
        archive_metadata_source = 'ddr_graphql.record_v1'
        AND metadata_sync_status IN ('current', 'updated')
        AND archive_record_id IS NOT NULL
        AND archive_record_pid IS NOT NULL
        AND (asset_id IS NOT NULL OR asset_pid IS NOT NULL)
        AND source_uri IS NOT NULL AS is_resolved
    FROM documents
), chunked AS (
    SELECT DISTINCT document_id FROM document_chunks
)
SELECT
    (SELECT COUNT(*) FROM documents),
    (SELECT COUNT(*) FROM document_chunks),
    (SELECT COUNT(*) FROM documents WHERE corpus_version = 'corpus_f40d78dbce52'),
    (SELECT COUNT(*) FROM documents WHERE corpus_version IS NULL),
    (SELECT COUNT(*) FROM document_chunks WHERE corpus_version = 'corpus_f40d78dbce52'),
    (SELECT COUNT(*) FROM document_chunks WHERE corpus_version IS NULL),
    (SELECT COUNT(*) FROM chunked),
    (SELECT COUNT(*) FROM document_chunks WHERE search_tsv IS NOT NULL),
    (SELECT COUNT(*) FROM document_chunks WHERE search_tsv IS NULL),
    (SELECT COUNT(*) FROM resolved WHERE is_resolved),
    (SELECT COUNT(*) FROM resolved WHERE NOT is_resolved),
    (SELECT COUNT(*) FROM resolved JOIN chunked USING (document_id) WHERE is_resolved),
    (SELECT COUNT(*) FROM resolved JOIN chunked USING (document_id) WHERE NOT is_resolved),
    (SELECT EXISTS (SELECT 1 FROM pg_indexes WHERE tablename = 'document_chunks' AND indexname = 'idx_document_chunks_search_tsv'))
")"

IFS='|' read -r documents chunks current_documents legacy_documents current_chunks legacy_chunks chunked_documents searchable_chunks null_search_vectors resolved unresolved resolved_chunked unresolved_chunked gin_index <<< "$stats"

echo "database=$TARGET_DATABASE"
echo "documents=$documents"
echo "chunks=$chunks"
echo "current_documents=$current_documents"
echo "legacy_documents=$legacy_documents"
echo "current_chunks=$current_chunks"
echo "legacy_chunks=$legacy_chunks"
echo "distinct_chunked_documents=$chunked_documents"
echo "search_tsv_non_null=$searchable_chunks"
echo "search_tsv_null=$null_search_vectors"
echo "resolved_current=$resolved"
echo "unresolved_legacy=$unresolved"
echo "resolved_current_represented_by_chunks=$resolved_chunked"
echo "unresolved_legacy_represented_by_chunks=$unresolved_chunked"
echo "gin_fts_index=$gin_index"

if [[ "$documents" != "138" || "$chunks" != "13490" || "$current_documents" != "109" || "$legacy_documents" != "29" || "$current_chunks" != "12884" || "$legacy_chunks" != "606" || "$resolved" != "97" || "$unresolved" != "29" || "$searchable_chunks" != "$chunks" || "$null_search_vectors" != "0" || "$gin_index" != "t" ]]; then
    echo "baseline_match=no"
    echo "ERROR: restored database does not match the accepted corpus baseline; no data was modified." >&2
    exit 2
fi

echo "baseline_match=yes"