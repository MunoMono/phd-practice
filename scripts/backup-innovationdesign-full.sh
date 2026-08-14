#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
TIMESTAMP="$(date +"%Y%m%d_%H%M%S")"
DATE="$(date +"%Y-%m-%d")"

DB_DUMP_NAME="database.sql.gz"
APP_ARCHIVE_NAME="application-files.tar.gz"

ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
SPACES_ENV_FILE="${SPACES_ENV_FILE:-${SCRIPT_DIR}/backup-full-spaces.env}"
EXTERNAL_OVERRIDE_NAMES="PROJECT_NAME BACKUP_SLUG BACKUP_BASE_DIR DAILY_DIR LOG_DIR RETENTION_DAYS REMOTE_RETENTION_COUNT POSTGRES_USER POSTGRES_DB DB_CONTAINER_NAME SPACES_BUCKET SPACES_PREFIX SPACES_ENDPOINT AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY REQUIRE_UPLOAD"

save_external_overrides() {
    local name
    local value

    for name in ${EXTERNAL_OVERRIDE_NAMES}; do
        if printenv "${name}" >/dev/null 2>&1; then
            value="$(printenv "${name}")"
            printf -v "EXTERNAL_${name}" '%s' "${value}"
            printf -v "EXTERNAL_SET_${name}" '%s' "1"
        fi
    done
}

apply_external_overrides() {
    local name
    local set_var
    local value_var

    for name in ${EXTERNAL_OVERRIDE_NAMES}; do
        set_var="EXTERNAL_SET_${name}"
        value_var="EXTERNAL_${name}"

        if [ "${!set_var:-}" = "1" ]; then
            printf -v "${name}" '%s' "${!value_var}"
            export "${name}"
        fi
    done
}

initialize_config() {
    PROJECT_NAME="${PROJECT_NAME:-innovationdesign}"
    BACKUP_SLUG="${BACKUP_SLUG:-innovationdesign-full}"
    BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-${PROJECT_DIR}/backups/full}"
    DAILY_DIR="${DAILY_DIR:-${BACKUP_BASE_DIR}/daily}"
    LOG_DIR="${LOG_DIR:-${PROJECT_DIR}/logs/full-backups}"
    LOG_FILE="${LOG_DIR}/full_backup_${DATE}.log"
    RETENTION_DAYS="${RETENTION_DAYS:-14}"
    REMOTE_RETENTION_COUNT="${REMOTE_RETENTION_COUNT:-14}"

    POSTGRES_USER="${POSTGRES_USER:-postgres}"
    POSTGRES_DB="${POSTGRES_DB:-testamentary-traces}"
    DB_CONTAINER_NAME="${DB_CONTAINER_NAME:-phd-practice-db}"

    SPACES_BUCKET="${SPACES_BUCKET:-${S3_BUCKET:-archive-media}}"
    SPACES_PREFIX="${SPACES_PREFIX:-innovationdesign-backups/innovationdesign-full}"
    SPACES_ENDPOINT="${SPACES_ENDPOINT:-${S3_ENDPOINT:-https://lon1.digitaloceanspaces.com}}"
    REQUIRE_UPLOAD="${REQUIRE_UPLOAD:-1}"

    BACKUP_NAME="${BACKUP_SLUG}-${TIMESTAMP}"
    STAGING_DIR="${DAILY_DIR}/${BACKUP_NAME}"
    ARCHIVE_FILE="${DAILY_DIR}/${BACKUP_NAME}.tar.gz"
    ARCHIVE_SHA_FILE="${ARCHIVE_FILE}.sha256"
    VERIFICATION_FILE="${DAILY_DIR}/${BACKUP_NAME}.verification.txt"
}

cleanup() {
    rm -rf "${STAGING_DIR}"
}

log() {
    mkdir -p "${LOG_DIR}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

fail() {
    log "ERROR: $1"
    cleanup
    exit 1
}

checksum_value() {
    local file_path="$1"

    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "${file_path}" | awk '{print $1}'
    else
        shasum -a 256 "${file_path}" | awk '{print $1}'
    fi
}

write_checksum_file() {
    local file_path="$1"
    local output_path="$2"
    local file_name
    local checksum

    file_name="$(basename "${file_path}")"
    checksum="$(checksum_value "${file_path}")"
    printf '%s  %s\n' "${checksum}" "${file_name}" > "${output_path}"
}

load_env_file() {
    local file_path="$1"

    if [ -f "${file_path}" ]; then
        set -a
        # shellcheck disable=SC1090
        source "${file_path}"
        set +a
    fi
}

verify_requirements() {
    command -v docker >/dev/null 2>&1 || fail "docker is required"
    command -v tar >/dev/null 2>&1 || fail "tar is required"
    command -v gzip >/dev/null 2>&1 || fail "gzip is required"

    if ! command -v sha256sum >/dev/null 2>&1 && ! command -v shasum >/dev/null 2>&1; then
        fail "sha256sum or shasum is required"
    fi

    if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER_NAME}$"; then
        fail "database container '${DB_CONTAINER_NAME}' is not running"
    fi

    if [ "${REQUIRE_UPLOAD}" = "1" ]; then
        command -v aws >/dev/null 2>&1 || fail "aws CLI is required when REQUIRE_UPLOAD=1"
        [ -n "${SPACES_BUCKET}" ] || fail "SPACES_BUCKET is required when REQUIRE_UPLOAD=1"
        [ -n "${SPACES_PREFIX}" ] || fail "SPACES_PREFIX is required when REQUIRE_UPLOAD=1"
        [ -n "${SPACES_ENDPOINT}" ] || fail "SPACES_ENDPOINT is required when REQUIRE_UPLOAD=1"

        if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
            [ -f "${AWS_SHARED_CREDENTIALS_FILE:-${HOME}/.aws/credentials}" ] || fail "AWS credentials not found in environment or ${AWS_SHARED_CREDENTIALS_FILE:-${HOME}/.aws/credentials}"
        fi
    fi
}

create_database_dump() {
    local output_path="$1"

    log "Creating PostgreSQL dump from ${DB_CONTAINER_NAME}/${POSTGRES_DB}"
    if ! docker exec -i "${DB_CONTAINER_NAME}" pg_dump -U "${POSTGRES_USER}" "${POSTGRES_DB}" | gzip > "${output_path}"; then
        fail "database dump failed"
    fi

    [ -s "${output_path}" ] || fail "database dump is empty"
    log "Database dump ready: $(du -h "${output_path}" | awk '{print $1}')"
}

create_app_archive() {
    local output_path="$1"
    local relative_backup_dir=""
    local relative_output_path=""
    local -a tar_args

    if [[ "${BACKUP_BASE_DIR}" == "${PROJECT_DIR}/"* ]]; then
        relative_backup_dir="${BACKUP_BASE_DIR#${PROJECT_DIR}/}"
    fi

    if [[ "${output_path}" == "${PROJECT_DIR}/"* ]]; then
        relative_output_path="${output_path#${PROJECT_DIR}/}"
    fi

    tar_args=(
        --exclude='.git'
        --exclude='.github'
        --exclude='.prod-sync'
        --exclude='.venv'
        --exclude='.DS_Store'
        --exclude='backups'
        --exclude='logs'
        --exclude='frontend/node_modules'
        --exclude='frontend/dist'
        --exclude='frontend/playwright-report'
        --exclude='frontend/test-results'
        --exclude='backend/__pycache__'
        --exclude='backend/.pytest_cache'
        --exclude='backend/.mypy_cache'
        --exclude='backend/logs/*.log'
    )

    if [ -n "${relative_backup_dir}" ]; then
        tar_args+=("--exclude=${relative_backup_dir}")
    fi

    if [ -n "${relative_output_path}" ]; then
        tar_args+=("--exclude=${relative_output_path}")
    fi

    log "Creating application/config archive"
    (
        cd "${PROJECT_DIR}"
        tar "${tar_args[@]}" \
            -czf "${output_path}" \
            .
    ) || fail "application archive failed"

    [ -s "${output_path}" ] || fail "application archive is empty"
    log "Application archive ready: $(du -h "${output_path}" | awk '{print $1}')"
}

write_metadata() {
    local metadata_path="$1"

    cat > "${metadata_path}" <<EOF
backup_name=${BACKUP_NAME}
project_name=${PROJECT_NAME}
created_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
project_dir=${PROJECT_DIR}
db_container_name=${DB_CONTAINER_NAME}
postgres_db=${POSTGRES_DB}
spaces_bucket=${SPACES_BUCKET}
spaces_prefix=${SPACES_PREFIX}/daily/${BACKUP_NAME}/
archive_file=$(basename "${ARCHIVE_FILE}")
app_archive_file=${APP_ARCHIVE_NAME}
database_dump_file=${DB_DUMP_NAME}
EOF
}

write_verification_manifest() {
    local manifest_path="$1"
    local db_dump_path="$2"
    local app_archive_path="$3"
    local metadata_path="$4"

    {
        echo "Innovation Design backup verification"
        echo "Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        echo
        printf '%s  %s\n' "$(checksum_value "${db_dump_path}")" "${DB_DUMP_NAME}"
        printf '%s  %s\n' "$(checksum_value "${app_archive_path}")" "${APP_ARCHIVE_NAME}"
        printf '%s  %s\n' "$(checksum_value "${metadata_path}")" "metadata.txt"
    } > "${manifest_path}"
}

package_backup() {
    log "Packaging staged backup into ${ARCHIVE_FILE}"
    (
        cd "${DAILY_DIR}"
        tar -czf "${ARCHIVE_FILE}" "${BACKUP_NAME}"
    ) || fail "failed to create final archive"

    tar -tzf "${ARCHIVE_FILE}" >/dev/null || fail "archive validation failed"
    write_checksum_file "${ARCHIVE_FILE}" "${ARCHIVE_SHA_FILE}"
    log "Archive checksum: $(cut -d' ' -f1 "${ARCHIVE_SHA_FILE}")"
}

upload_backup() {
    local remote_prefix="s3://${SPACES_BUCKET}/${SPACES_PREFIX}/daily/${BACKUP_NAME}/"

    if [ "${REQUIRE_UPLOAD}" != "1" ]; then
        log "Upload skipped because REQUIRE_UPLOAD=${REQUIRE_UPLOAD}"
        return
    fi

    log "Uploading archive, checksum, and verification manifest to ${remote_prefix}"
    aws --endpoint-url "${SPACES_ENDPOINT}" s3 cp "${ARCHIVE_FILE}" "${remote_prefix}" --only-show-errors \
        || fail "archive upload failed"
    aws --endpoint-url "${SPACES_ENDPOINT}" s3 cp "${ARCHIVE_SHA_FILE}" "${remote_prefix}" --only-show-errors \
        || fail "checksum upload failed"
    aws --endpoint-url "${SPACES_ENDPOINT}" s3 cp "${VERIFICATION_FILE}" "${remote_prefix}" --only-show-errors \
        || fail "verification manifest upload failed"
    log "Upload completed successfully"
}

apply_remote_retention() {
    local remote_daily_root
    local prefixes
    local prefix_count
    local delete_list
    local backup_prefix

    if [ "${REQUIRE_UPLOAD}" != "1" ]; then
        return
    fi

    if ! [[ "${REMOTE_RETENTION_COUNT}" =~ ^[0-9]+$ ]]; then
        fail "REMOTE_RETENTION_COUNT must be a non-negative integer"
    fi

    if [ "${REMOTE_RETENTION_COUNT}" -eq 0 ]; then
        log "Remote retention disabled because REMOTE_RETENTION_COUNT=0"
        return
    fi

    remote_daily_root="s3://${SPACES_BUCKET}/${SPACES_PREFIX}/daily/"
    prefixes="$(aws --endpoint-url "${SPACES_ENDPOINT}" s3 ls "${remote_daily_root}" | awk '/PRE / {print $2}' | sed 's#/$##' | grep "^${BACKUP_SLUG}-" | sort -r || true)"

    if [ -z "${prefixes}" ]; then
        log "Remote retention found no existing backup prefixes"
        return
    fi

    prefix_count="$(printf '%s\n' "${prefixes}" | awk 'NF' | wc -l | tr -d ' ')"
    if [ "${prefix_count}" -le "${REMOTE_RETENTION_COUNT}" ]; then
        log "Remote retention: nothing to delete (${prefix_count} prefix(es), keeping ${REMOTE_RETENTION_COUNT})"
        return
    fi

    delete_list="$(printf '%s\n' "${prefixes}" | awk -v keep="${REMOTE_RETENTION_COUNT}" 'NR > keep')"
    while IFS= read -r backup_prefix; do
        [ -n "${backup_prefix}" ] || continue
        log "Remote retention deleting ${remote_daily_root}${backup_prefix}/"
        aws --endpoint-url "${SPACES_ENDPOINT}" s3 rm "${remote_daily_root}${backup_prefix}/" --recursive --only-show-errors \
            || fail "remote retention deletion failed for ${backup_prefix}"
    done <<EOF
${delete_list}
EOF
}

apply_retention() {
    log "Applying local retention policy: ${RETENTION_DAYS} day(s)"
    find "${DAILY_DIR}" -type f \( -name "${BACKUP_SLUG}-*.tar.gz" -o -name "${BACKUP_SLUG}-*.tar.gz.sha256" -o -name "${BACKUP_SLUG}-*.verification.txt" \) -mtime +"${RETENTION_DAYS}" -delete
    find "${DAILY_DIR}" -mindepth 1 -maxdepth 1 -type d -name "${BACKUP_SLUG}-*" -mtime +"${RETENTION_DAYS}" -exec rm -rf {} +
}

main() {
    save_external_overrides
    load_env_file "${ENV_FILE}"
    load_env_file "${SPACES_ENV_FILE}"
    apply_external_overrides
    initialize_config

    mkdir -p "${DAILY_DIR}" "${LOG_DIR}" "${STAGING_DIR}"

    log "=== Starting Innovation Design full backup ==="
    log "Backup name: ${BACKUP_NAME}"
    log "Backup directory: ${DAILY_DIR}"

    verify_requirements

    create_database_dump "${STAGING_DIR}/${DB_DUMP_NAME}"
    create_app_archive "${STAGING_DIR}/${APP_ARCHIVE_NAME}"
    write_metadata "${STAGING_DIR}/metadata.txt"
    write_verification_manifest "${STAGING_DIR}/verification.txt" "${STAGING_DIR}/${DB_DUMP_NAME}" "${STAGING_DIR}/${APP_ARCHIVE_NAME}" "${STAGING_DIR}/metadata.txt"

    cp "${STAGING_DIR}/verification.txt" "${VERIFICATION_FILE}"
    package_backup
    upload_backup
    apply_remote_retention
    apply_retention

    log "Backup archive created: ${ARCHIVE_FILE}"
    log "Checksum file created: ${ARCHIVE_SHA_FILE}"
    log "Verification manifest created: ${VERIFICATION_FILE}"
    log "=== Innovation Design full backup completed successfully ==="

    cleanup
}

main "$@"