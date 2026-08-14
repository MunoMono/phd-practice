#!/bin/bash

set -euo pipefail

TARGET_DATABASE="testamentary_traces_retrieval_validation"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-phd-practice-db}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
BACKUP_PATH=""
CLEANUP=0
CONFIRM_DROP=0
DRY_RUN=0

usage() {
    cat <<'EOF'
Usage:
  scripts/restore-innovationdesign-isolated.sh --backup <database.sql.gz> [--database <name>] [--dry-run]
  scripts/restore-innovationdesign-isolated.sh --cleanup --database <name> --yes-really-drop

Only databases named testamentary_traces_*_retrieval_validation are accepted.
EOF
}

require_safe_database() {
    local database="$1"
    if [[ "$database" == "testamentary-traces" || "$database" == "testamentary_traces" || "$database" == "postgres" || "$database" == "template0" || "$database" == "template1" ]]; then
        echo "ERROR: refusing dangerous active or system database name: $database" >&2
        exit 2
    fi
    if [[ ! "$database" =~ ^testamentary_traces_[a-z0-9_]*retrieval_validation$ ]]; then
        echo "ERROR: isolated target must match testamentary_traces_*_retrieval_validation" >&2
        exit 2
    fi
}

database_exists() {
    docker exec -i "$DB_CONTAINER_NAME" psql -U "$POSTGRES_USER" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DATABASE'" | grep -qx '1'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backup)
            BACKUP_PATH="${2:-}"
            shift 2
            ;;
        --database)
            TARGET_DATABASE="${2:-}"
            shift 2
            ;;
        --cleanup)
            CLEANUP=1
            shift
            ;;
        --yes-really-drop)
            CONFIRM_DROP=1
            shift
            ;;
        --dry-run)
            DRY_RUN=1
            shift
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

if [[ "$CLEANUP" == "1" ]]; then
    if [[ "$CONFIRM_DROP" != "1" ]]; then
        echo "ERROR: cleanup requires --yes-really-drop" >&2
        exit 2
    fi
    if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER_NAME"; then
        echo "ERROR: database container is not running: $DB_CONTAINER_NAME" >&2
        exit 1
    fi
    if ! database_exists; then
        echo "ERROR: isolated database does not exist: $TARGET_DATABASE" >&2
        exit 1
    fi
    if [[ "$DRY_RUN" == "1" ]]; then
        echo "DRY RUN: would drop isolated database $TARGET_DATABASE from $DB_CONTAINER_NAME"
        exit 0
    fi
    docker exec -i "$DB_CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
        -c "DROP DATABASE \"$TARGET_DATABASE\""
    echo "Dropped isolated database: $TARGET_DATABASE"
    exit 0
fi

if [[ -z "$BACKUP_PATH" ]]; then
    echo "ERROR: --backup is required" >&2
    usage >&2
    exit 2
fi
if [[ ! -f "$BACKUP_PATH" ]]; then
    echo "ERROR: backup file does not exist: $BACKUP_PATH" >&2
    exit 1
fi
if ! gzip -t "$BACKUP_PATH"; then
    echo "ERROR: backup failed gzip integrity verification: $BACKUP_PATH" >&2
    exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER_NAME"; then
    echo "ERROR: database container is not running: $DB_CONTAINER_NAME" >&2
    exit 1
fi
if database_exists; then
    echo "ERROR: isolated database already exists and will not be overwritten: $TARGET_DATABASE" >&2
    exit 1
fi

echo "Backup verified: $BACKUP_PATH"
echo "Isolated target: $DB_CONTAINER_NAME/$TARGET_DATABASE"
if [[ "$DRY_RUN" == "1" ]]; then
    echo "DRY RUN: would create $TARGET_DATABASE and restore the verified backup into it"
    exit 0
fi

docker exec -i "$DB_CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
    -c "CREATE DATABASE \"$TARGET_DATABASE\""

if ! gzip -dc "$BACKUP_PATH" | docker exec -i "$DB_CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$TARGET_DATABASE"; then
    echo "ERROR: restore failed; the isolated target was left in place for inspection: $TARGET_DATABASE" >&2
    exit 1
fi

echo "Restore completed into isolated database: $TARGET_DATABASE"