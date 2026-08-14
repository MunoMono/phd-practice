#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"

ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
RESTORE_ROOT="${RESTORE_ROOT:-${PROJECT_DIR}/backups/full/restore}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_DB="${POSTGRES_DB:-testamentary-traces}"
DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-phd-practice-db}"
RESTORE_TARGET_DIR="${RESTORE_TARGET_DIR:-${PROJECT_DIR}}"
SKIP_DB_RESTORE="${SKIP_DB_RESTORE:-0}"
SKIP_APP_RESTORE="${SKIP_APP_RESTORE:-0}"
VERIFY_CHECKSUM="${VERIFY_CHECKSUM:-1}"
ASSUME_YES="${ASSUME_YES:-0}"

load_env_file() {
    local file_path="$1"

    if [ -f "${file_path}" ]; then
        set -a
        # shellcheck disable=SC1090
        source "${file_path}"
        set +a
    fi
}

confirm() {
    local prompt="$1"
    local answer

    read -r -p "${prompt} (yes/no): " answer
    [ "${answer}" = "yes" ]
}

if [ $# -lt 1 ]; then
    echo "Usage: $0 [--yes] <backup-archive.tar.gz>"
    exit 1
fi

while [ $# -gt 0 ]; do
    case "$1" in
        --yes|-y)
            ASSUME_YES=1
            shift
            ;;
        --)
            shift
            break
            ;;
        -*)
            echo "ERROR: Unknown option: $1"
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if [ $# -lt 1 ]; then
    echo "Usage: $0 [--yes] <backup-archive.tar.gz>"
    exit 1
fi

ARCHIVE_PATH="$1"

if [ ! -f "${ARCHIVE_PATH}" ]; then
    echo "ERROR: Backup archive not found: ${ARCHIVE_PATH}"
    exit 1
fi

load_env_file "${ENV_FILE}"

BACKUP_BASENAME="$(basename "${ARCHIVE_PATH}" .tar.gz)"
EXTRACT_DIR="${RESTORE_ROOT}/${BACKUP_BASENAME}"
CHECKSUM_PATH="${ARCHIVE_PATH}.sha256"
DB_DUMP_PATH="${EXTRACT_DIR}/${BACKUP_BASENAME}/database.sql.gz"
APP_ARCHIVE_PATH="${EXTRACT_DIR}/${BACKUP_BASENAME}/application-files.tar.gz"

mkdir -p "${RESTORE_ROOT}"
rm -rf "${EXTRACT_DIR}"
mkdir -p "${EXTRACT_DIR}"

echo "=== Innovation Design Full Restore ==="
echo "Archive: ${ARCHIVE_PATH}"
echo "Extract directory: ${EXTRACT_DIR}"
echo "Database target: ${DB_CONTAINER_NAME}/${POSTGRES_DB}"
echo "Application target: ${RESTORE_TARGET_DIR}"
echo "Non-interactive mode: ${ASSUME_YES}"
echo

if [ "${VERIFY_CHECKSUM}" = "1" ] && [ -f "${CHECKSUM_PATH}" ]; then
    echo "Verifying archive checksum..."
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$(dirname "${ARCHIVE_PATH}")" && sha256sum -c "$(basename "${CHECKSUM_PATH}")")
    else
        (cd "$(dirname "${ARCHIVE_PATH}")" && shasum -a 256 -c "$(basename "${CHECKSUM_PATH}")")
    fi
elif [ "${VERIFY_CHECKSUM}" = "1" ]; then
    echo "WARNING: checksum file not found, skipping checksum verification"
fi

echo "Extracting archive..."
tar -xzf "${ARCHIVE_PATH}" -C "${EXTRACT_DIR}"

[ -f "${DB_DUMP_PATH}" ] || { echo "ERROR: Missing database dump in archive"; exit 1; }
[ -f "${APP_ARCHIVE_PATH}" ] || { echo "ERROR: Missing application archive in backup"; exit 1; }

if [ "${SKIP_DB_RESTORE}" != "1" ]; then
    if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER_NAME}$"; then
        echo "ERROR: Database container '${DB_CONTAINER_NAME}' is not running"
        exit 1
    fi

    echo
    echo "A pre-restore database backup will be created before importing the archive dump."
    if [ "${ASSUME_YES}" != "1" ] && ! confirm "Continue with database restore"; then
        echo "Database restore cancelled. Extracted files remain at ${EXTRACT_DIR}"
        exit 0
    fi

    PRE_RESTORE_BACKUP="${RESTORE_ROOT}/pre_restore_$(date +"%Y%m%d_%H%M%S").sql.gz"
    echo "Creating pre-restore database backup: ${PRE_RESTORE_BACKUP}"
    docker exec -i "${DB_CONTAINER_NAME}" pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${PRE_RESTORE_BACKUP}"

    echo "Restoring database dump..."
    gunzip -c "${DB_DUMP_PATH}" | docker exec -i "${DB_CONTAINER_NAME}" psql -U "${POSTGRES_USER}" "${POSTGRES_DB}"
fi

if [ "${SKIP_APP_RESTORE}" != "1" ]; then
    echo
    if [ "${ASSUME_YES}" != "1" ] && ! confirm "Extract application files into ${RESTORE_TARGET_DIR}"; then
        echo "Application file restore skipped. Extracted files remain at ${EXTRACT_DIR}"
        exit 0
    fi

    tar -xzf "${APP_ARCHIVE_PATH}" -C "${RESTORE_TARGET_DIR}"
fi

echo
echo "Restore completed successfully."
echo "Extracted backup directory: ${EXTRACT_DIR}"