#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SCRIPT_DIR}"

PROD_SSH_HOST="${PROD_SSH_HOST:-104.248.170.26}"
PROD_SSH_USER="${PROD_SSH_USER:-root}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/root/phd-practice}"
PROD_COMPOSE_FILE="${PROD_COMPOSE_FILE:-docker-compose.prod.yml}"
LOCAL_COMPOSE_FILE="${LOCAL_COMPOSE_FILE:-docker-compose.dev.yml}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
ASSUME_YES=false
TIMESTAMP="$(date -u +"%Y%m%dT%H%M%SZ")"
SYNC_DIR="${REPO_ROOT}/backups/sync-from-production/${TIMESTAMP}"
SUMMARY_FILE="${SYNC_DIR}/refresh-summary.txt"
REMOTE_SYNC_DIR="${REMOTE_APP_DIR}/backups/sync-from-production/${TIMESTAMP}"
REMOTE_DUMP_PATH="${REMOTE_SYNC_DIR}/production-db.sql.gz"
LOCAL_DUMP_PATH="${SYNC_DIR}/production-db.sql.gz"
LOCAL_PRE_REFRESH_BACKUP="${SYNC_DIR}/local-pre-refresh.sql.gz"
DEPLOYMENT_MARKER_PATH="${SYNC_DIR}/production-current-deployment.txt"
MANUAL_RERUN="./pull-from-production.sh --yes"
CURRENT_STEP="initializing"

compose_cmd=(docker compose -f "${LOCAL_COMPOSE_FILE}")

usage() {
    cat <<EOF
Usage: ./pull-from-production.sh --yes

Options:
  --yes    Run non-interactively and replace the local development database.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes)
            ASSUME_YES=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$1'" >&2
            usage >&2
            exit 1
            ;;
    esac
done

if [[ "${ASSUME_YES}" != "true" ]]; then
    echo "This will replace your local development database with a fresh dump from production." >&2
    echo "Re-run with --yes to continue." >&2
    exit 1
fi

mkdir -p "${SYNC_DIR}"

summary() {
    printf '%s\n' "$1" | tee -a "${SUMMARY_FILE}"
}

print_compose_logs() {
    echo "Last 80 backend log lines:" >&2
    "${compose_cmd[@]}" logs --tail 80 backend >&2 || true
    echo >&2
    echo "Last 80 frontend log lines:" >&2
    "${compose_cmd[@]}" logs --tail 80 frontend >&2 || true
}

on_error() {
    local line="$1"
    local command="$2"

    echo "MORNING REFRESH FAILED: ${CURRENT_STEP}" >&2
    echo "Command: ${command}" >&2
    echo "Manual rerun: ${MANUAL_RERUN}" >&2
    summary "final_readiness_result=FAILED"
    summary "failed_step=${CURRENT_STEP}"
    summary "failed_command=${command}"
    summary "failed_line=${line}"
    print_compose_logs
    exit 1
}

trap 'on_error ${LINENO} "$BASH_COMMAND"' ERR

cd "${REPO_ROOT}"

summary "timestamp=${TIMESTAMP}"
summary "production_dump_path=${REMOTE_DUMP_PATH}"
summary "local_db_backup_path=${LOCAL_PRE_REFRESH_BACKUP}"
summary "local_compose_file=${LOCAL_COMPOSE_FILE}"
summary "media_sync=not_configured"

if git rev-parse --show-toplevel >/dev/null 2>&1; then
    summary "local_git_branch=$(git rev-parse --abbrev-ref HEAD)"
    summary "local_git_commit=$(git rev-parse HEAD)"
fi

CURRENT_STEP="checking production deployment marker"
if ssh "${PROD_SSH_USER}@${PROD_SSH_HOST}" "test -f '${REMOTE_APP_DIR}/current-deployment.txt'"; then
    scp "${PROD_SSH_USER}@${PROD_SSH_HOST}:${REMOTE_APP_DIR}/current-deployment.txt" "${DEPLOYMENT_MARKER_PATH}" >/dev/null
    echo "Production deployment marker:"
    cat "${DEPLOYMENT_MARKER_PATH}"
    summary "production_deployment_marker=present"
    while IFS= read -r line; do
        summary "production_marker_${line}"
    done < "${DEPLOYMENT_MARKER_PATH}"
else
    echo "WARNING: Production deployment marker not found at ${REMOTE_APP_DIR}/current-deployment.txt" >&2
    summary "production_deployment_marker=missing"
fi

CURRENT_STEP="creating timestamped production dump on droplet"
ssh "${PROD_SSH_USER}@${PROD_SSH_HOST}" \
    "set -euo pipefail; mkdir -p '${REMOTE_SYNC_DIR}'; cd '${REMOTE_APP_DIR}'; docker compose -f '${PROD_COMPOSE_FILE}' exec -T db sh -lc 'pg_dump -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"' | gzip -c > '${REMOTE_DUMP_PATH}'; test -s '${REMOTE_DUMP_PATH}'"
summary "remote_dump_status=created"

CURRENT_STEP="downloading production dump"
scp "${PROD_SSH_USER}@${PROD_SSH_HOST}:${REMOTE_DUMP_PATH}" "${LOCAL_DUMP_PATH}" >/dev/null
test -s "${LOCAL_DUMP_PATH}"
summary "download_status=completed"

CURRENT_STEP="stopping local compose stack before restore"
"${compose_cmd[@]}" down --remove-orphans || true

CURRENT_STEP="starting local database container"
"${compose_cmd[@]}" up -d db

CURRENT_STEP="waiting for local database readiness"
db_container_id="$(${compose_cmd[@]} ps -q db)"
if [[ -z "${db_container_id}" ]]; then
    echo "ERROR: Local database container ID could not be resolved." >&2
    exit 1
fi

for _ in {1..30}; do
    db_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${db_container_id}")"
    if [[ "${db_health}" == "healthy" || "${db_health}" == "running" ]]; then
        break
    fi
    sleep 2
done

db_health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${db_container_id}")"
if [[ "${db_health}" != "healthy" && "${db_health}" != "running" ]]; then
    echo "ERROR: Local database container did not become ready. Status=${db_health}" >&2
    exit 1
fi
summary "local_db_container_status=${db_health}"

CURRENT_STEP="backing up current local database"
"${compose_cmd[@]}" exec -T db sh -lc 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip -c > "${LOCAL_PRE_REFRESH_BACKUP}"
test -s "${LOCAL_PRE_REFRESH_BACKUP}"
summary "local_backup_status=completed"

CURRENT_STEP="restoring production dump into local database"
"${compose_cmd[@]}" exec -T db sh -lc 'dropdb --if-exists -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
gunzip -c "${LOCAL_DUMP_PATH}" | "${compose_cmd[@]}" exec -T db sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
summary "restore_status=completed"

CURRENT_STEP="starting code-driven local compose stack"
"${compose_cmd[@]}" up -d --build
summary "local_stack_status=started"

CURRENT_STEP="running strict readiness checks"
"${REPO_ROOT}/scripts/check-local-ready.sh" \
    --compose-file "${LOCAL_COMPOSE_FILE}" \
    --frontend-url "${FRONTEND_URL}" \
    --backend-url "${BACKEND_URL}" \
    --summary-file "${SUMMARY_FILE}"

summary "final_readiness_result=READY"

echo "READY FOR DEVELOPMENT"