#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "${SCRIPT_DIR}")"
DATE="$(date +"%Y-%m-%d")"

ENV_FILE="${ENV_FILE:-${PROJECT_DIR}/.env}"
SPACES_ENV_FILE="${SPACES_ENV_FILE:-${SCRIPT_DIR}/backup-full-spaces.env}"
PROJECT_NAME="${PROJECT_NAME:-innovationdesign}"
BACKUP_SLUG="${BACKUP_SLUG:-innovationdesign-full}"
BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-${PROJECT_DIR}/backups/full}"
DAILY_DIR="${DAILY_DIR:-${BACKUP_BASE_DIR}/daily}"
LOG_DIR="${LOG_DIR:-${PROJECT_DIR}/logs/full-backups}"
STATUS_LOG="${LOG_DIR}/full_backup_status_${DATE}.log"
SPACES_BUCKET="${SPACES_BUCKET:-${S3_BUCKET:-archive-media}}"
SPACES_PREFIX="${SPACES_PREFIX:-innovationdesign-backups/innovationdesign-full}"
SPACES_ENDPOINT="${SPACES_ENDPOINT:-${S3_ENDPOINT:-https://lon1.digitaloceanspaces.com}}"
CHECK_REMOTE="${CHECK_REMOTE:-auto}"
MAIL_TO="${MAIL_TO:-}"
STATUS="PASS"
LATEST_LOCAL_ARCHIVE=""
LATEST_REMOTE_PREFIX=""
REMOTE_ENABLED="1"

load_env_file() {
    local file_path="$1"

    if [ -f "${file_path}" ]; then
        set -a
        # shellcheck disable=SC1090
        source "${file_path}"
        set +a
    fi
}

log() {
    mkdir -p "${LOG_DIR}"
    echo "$1" | tee -a "${STATUS_LOG}"
}

mark_fail() {
    STATUS="FAIL"
    log "$1"
}

check_local_backup() {
    local checksum_path
    local verification_path

    LATEST_LOCAL_ARCHIVE="$(find "${DAILY_DIR}" -maxdepth 1 -type f -name "${BACKUP_SLUG}-*.tar.gz" | sort -r | head -n 1 || true)"
    if [ -z "${LATEST_LOCAL_ARCHIVE}" ]; then
        mark_fail "LOCAL FAIL: no local full backup archives found in ${DAILY_DIR}"
        return
    fi

    checksum_path="${LATEST_LOCAL_ARCHIVE}.sha256"
    verification_path="${LATEST_LOCAL_ARCHIVE%.tar.gz}.verification.txt"

    log "LOCAL INFO: latest archive ${LATEST_LOCAL_ARCHIVE}"

    if [ ! -f "${checksum_path}" ]; then
        mark_fail "LOCAL FAIL: missing checksum file ${checksum_path}"
    elif command -v sha256sum >/dev/null 2>&1; then
        (cd "$(dirname "${LATEST_LOCAL_ARCHIVE}")" && sha256sum -c "$(basename "${checksum_path}")") >> "${STATUS_LOG}" 2>&1 || mark_fail "LOCAL FAIL: checksum verification failed for $(basename "${LATEST_LOCAL_ARCHIVE}")"
    else
        (cd "$(dirname "${LATEST_LOCAL_ARCHIVE}")" && shasum -a 256 -c "$(basename "${checksum_path}")") >> "${STATUS_LOG}" 2>&1 || mark_fail "LOCAL FAIL: checksum verification failed for $(basename "${LATEST_LOCAL_ARCHIVE}")"
    fi

    if [ ! -f "${verification_path}" ]; then
        mark_fail "LOCAL FAIL: missing verification file ${verification_path}"
    elif ! grep -q "PASS\|Innovation Design backup verification" "${verification_path}"; then
        mark_fail "LOCAL FAIL: verification file ${verification_path} does not contain expected markers"
    else
        log "LOCAL PASS: verification file present ${verification_path}"
    fi
}

check_remote_backup() {
    local remote_daily_root
    local remote_listing
    local remote_files

    if [ "${REMOTE_ENABLED}" != "1" ]; then
        log "REMOTE INFO: skipped because Spaces configuration is unavailable"
        return
    fi

    remote_daily_root="s3://${SPACES_BUCKET}/${SPACES_PREFIX}/daily/"
    remote_listing="$(aws --endpoint-url "${SPACES_ENDPOINT}" s3 ls "${remote_daily_root}" 2>> "${STATUS_LOG}" | awk '/PRE / {print $2}' | sed 's#/$##' | grep "^${BACKUP_SLUG}-" | sort -r || true)"

    LATEST_REMOTE_PREFIX="$(printf '%s\n' "${remote_listing}" | head -n 1)"
    if [ -z "${LATEST_REMOTE_PREFIX}" ]; then
        mark_fail "REMOTE FAIL: no remote backup prefixes found under ${remote_daily_root}"
        return
    fi

    log "REMOTE INFO: latest prefix ${remote_daily_root}${LATEST_REMOTE_PREFIX}/"
    remote_files="$(aws --endpoint-url "${SPACES_ENDPOINT}" s3 ls "${remote_daily_root}${LATEST_REMOTE_PREFIX}/" 2>> "${STATUS_LOG}" | awk '{print $4}' || true)"

    printf '%s\n' "${remote_files}" | grep -q "${LATEST_REMOTE_PREFIX}.tar.gz" || mark_fail "REMOTE FAIL: missing archive object for ${LATEST_REMOTE_PREFIX}"
    printf '%s\n' "${remote_files}" | grep -q "${LATEST_REMOTE_PREFIX}.tar.gz.sha256" || mark_fail "REMOTE FAIL: missing checksum object for ${LATEST_REMOTE_PREFIX}"
    printf '%s\n' "${remote_files}" | grep -q "${LATEST_REMOTE_PREFIX}.verification.txt" || mark_fail "REMOTE FAIL: missing verification object for ${LATEST_REMOTE_PREFIX}"

    if [ "${STATUS}" = "PASS" ]; then
        log "REMOTE PASS: latest remote prefix contains archive, checksum, and verification objects"
    fi
}

send_email_if_configured() {
    if [ -z "${MAIL_TO}" ]; then
        return
    fi

    if command -v mail >/dev/null 2>&1; then
        mail -s "[${PROJECT_NAME}] Full backup status ${STATUS}" "${MAIL_TO}" < "${STATUS_LOG}" || log "MAIL WARN: failed to send status email via mail"
    elif command -v mailx >/dev/null 2>&1; then
        mailx -s "[${PROJECT_NAME}] Full backup status ${STATUS}" "${MAIL_TO}" < "${STATUS_LOG}" || log "MAIL WARN: failed to send status email via mailx"
    else
        log "MAIL WARN: MAIL_TO is set but no mail or mailx command is installed"
    fi
}

load_env_file "${ENV_FILE}"
load_env_file "${SPACES_ENV_FILE}"

if [ "${CHECK_REMOTE}" = "0" ]; then
    REMOTE_ENABLED="0"
elif [ -z "${SPACES_BUCKET}" ] || [ -z "${SPACES_PREFIX}" ] || [ -z "${SPACES_ENDPOINT}" ] || ! command -v aws >/dev/null 2>&1; then
    REMOTE_ENABLED="0"
elif [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
    if [ ! -f "${AWS_SHARED_CREDENTIALS_FILE:-${HOME}/.aws/credentials}" ]; then
        REMOTE_ENABLED="0"
    fi
fi

mkdir -p "${LOG_DIR}"
: > "${STATUS_LOG}"

log "[$(date '+%Y-%m-%d %H:%M:%S')] Starting full backup status check"
check_local_backup
check_remote_backup
log "STATUS: ${STATUS}"
send_email_if_configured

if [ "${STATUS}" != "PASS" ]; then
    exit 1
fi