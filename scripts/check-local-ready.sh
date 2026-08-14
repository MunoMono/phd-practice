#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

COMPOSE_FILE="${LOCAL_COMPOSE_FILE:-docker-compose.dev.yml}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
SUMMARY_FILE=""
MANUAL_RERUN="./scripts/check-local-ready.sh"
HTTP_WAIT_SECONDS="${HTTP_WAIT_SECONDS:-60}"
HTTP_WAIT_INTERVAL="${HTTP_WAIT_INTERVAL:-2}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --compose-file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        --frontend-url)
            FRONTEND_URL="$2"
            shift 2
            ;;
        --backend-url)
            BACKEND_URL="$2"
            shift 2
            ;;
        --summary-file)
            SUMMARY_FILE="$2"
            shift 2
            ;;
        *)
            echo "ERROR: Unknown option '$1'" >&2
            exit 1
            ;;
    esac
done

cd "${REPO_ROOT}"

compose_cmd=(docker compose -f "${COMPOSE_FILE}")
LAST_FAILED_CHECK=""
LAST_FAILED_URL=""
LAST_FAILED_HTTP_STATUS=""
LAST_FAILED_REASON=""
declare -a CHECK_LINES=()

append_summary() {
    local line="$1"
    CHECK_LINES+=("${line}")
    if [[ -n "${SUMMARY_FILE}" ]]; then
        printf '%s\n' "${line}" >> "${SUMMARY_FILE}"
    fi
}

fail_with_diagnostics() {
    local suspected_cause

    case "${LAST_FAILED_CHECK}" in
        containers)
            suspected_cause="One or more expected services failed to start or exited early."
            ;;
        backend_health|granite_model_info)
            suspected_cause="Backend startup likely failed because of database connectivity, dependency import, or schema drift."
            ;;
        frontend_root)
            suspected_cause="Frontend dev server may not be listening on the expected port, or the build failed before serving."
            ;;
        dashboard_stats|documents_list|graphql_metrics)
            suspected_cause="The local database restore may have targeted the wrong database volume, restored empty data, or the API contract is broken."
            ;;
        *)
            suspected_cause="Check the backend and frontend logs for the first upstream error."
            ;;
    esac

    echo "READINESS CHECK FAILED: ${LAST_FAILED_CHECK}" >&2
    if [[ -n "${LAST_FAILED_HTTP_STATUS}" ]]; then
        echo "HTTP status: ${LAST_FAILED_HTTP_STATUS}" >&2
    fi
    if [[ -n "${LAST_FAILED_URL}" ]]; then
        echo "Local URL: ${LAST_FAILED_URL}" >&2
    fi
    if [[ -n "${LAST_FAILED_REASON}" ]]; then
        echo "Reason: ${LAST_FAILED_REASON}" >&2
    fi
    echo "Manual rerun: ${MANUAL_RERUN}" >&2
    echo "Suspected cause: ${suspected_cause}" >&2
    echo >&2
    echo "Last 80 backend log lines:" >&2
    "${compose_cmd[@]}" logs --tail 80 backend >&2 || true
    echo >&2
    echo "Last 80 frontend log lines:" >&2
    "${compose_cmd[@]}" logs --tail 80 frontend >&2 || true

    append_summary "final_readiness_result=FAILED"
    append_summary "failed_check=${LAST_FAILED_CHECK}"
    if [[ -n "${LAST_FAILED_URL}" ]]; then
        append_summary "failed_url=${LAST_FAILED_URL}"
    fi
    if [[ -n "${LAST_FAILED_HTTP_STATUS}" ]]; then
        append_summary "failed_http_status=${LAST_FAILED_HTTP_STATUS}"
    fi

    exit 1
}

require_running_service() {
    local service="$1"
    local running_services

    running_services="$(${compose_cmd[@]} ps --status running --services 2>/dev/null || true)"
    if ! printf '%s\n' "${running_services}" | grep -qx "${service}"; then
        LAST_FAILED_CHECK="containers"
        LAST_FAILED_REASON="Expected service '${service}' is not running."
        fail_with_diagnostics
    fi

    append_summary "container_${service}=running"
}

http_request() {
    local method="$1"
    local url="$2"
    local body_file="$3"
    local payload="${4:-}"

    if [[ -n "${payload}" ]]; then
        curl -sS -o "${body_file}" -w "%{http_code}" -X "${method}" \
            -H 'Content-Type: application/json' \
            --data "${payload}" \
            "${url}"
    else
        curl -sS -o "${body_file}" -w "%{http_code}" -X "${method}" "${url}"
    fi
}

retry_http_request() {
    local method="$1"
    local url="$2"
    local body_file="$3"
    local payload="${4:-}"
    local attempts
    local attempt=1
    local status=""

    attempts=$((HTTP_WAIT_SECONDS / HTTP_WAIT_INTERVAL))
    if (( attempts < 1 )); then
        attempts=1
    fi

    while (( attempt <= attempts )); do
        if status="$(http_request "${method}" "${url}" "${body_file}" "${payload}" 2>/dev/null)"; then
            printf '%s' "${status}"
            return 0
        fi

        if (( attempt == attempts )); then
            return 1
        fi

        sleep "${HTTP_WAIT_INTERVAL}"
        attempt=$((attempt + 1))
    done

    return 1
}

check_json_contains() {
    local name="$1"
    local url="$2"
    local method="$3"
    local pattern="$4"
    local payload="${5:-}"
    local body_file
    local status
    local compact_body

    body_file="$(mktemp)"
    status="$(retry_http_request "${method}" "${url}" "${body_file}" "${payload}")" || {
        rm -f "${body_file}"
        LAST_FAILED_CHECK="${name}"
        LAST_FAILED_URL="${url}"
        LAST_FAILED_REASON="curl failed before receiving a stable response within ${HTTP_WAIT_SECONDS}s."
        fail_with_diagnostics
    }

    compact_body="$(tr -d '[:space:]' < "${body_file}")"

    if [[ "${status}" != "200" ]]; then
        LAST_FAILED_CHECK="${name}"
        LAST_FAILED_URL="${url}"
        LAST_FAILED_HTTP_STATUS="${status}"
        LAST_FAILED_REASON="Expected HTTP 200."
        rm -f "${body_file}"
        fail_with_diagnostics
    fi

    if ! printf '%s' "${compact_body}" | grep -Eq "${pattern}"; then
        LAST_FAILED_CHECK="${name}"
        LAST_FAILED_URL="${url}"
        LAST_FAILED_HTTP_STATUS="${status}"
        LAST_FAILED_REASON="Response did not contain expected production-derived data."
        rm -f "${body_file}"
        fail_with_diagnostics
    fi

    append_summary "${name}=HTTP_${status}"
    rm -f "${body_file}"
}

require_running_service db
require_running_service backend
require_running_service frontend

check_json_contains backend_health "${BACKEND_URL}/health" GET '"status":"healthy"'

frontend_body="$(mktemp)"
frontend_status="$(retry_http_request GET "${FRONTEND_URL}" "${frontend_body}")" || {
    rm -f "${frontend_body}"
    LAST_FAILED_CHECK="frontend_root"
    LAST_FAILED_URL="${FRONTEND_URL}"
    LAST_FAILED_REASON="curl failed before receiving a stable response within ${HTTP_WAIT_SECONDS}s."
    fail_with_diagnostics
}

if [[ "${frontend_status}" != "200" ]]; then
    LAST_FAILED_CHECK="frontend_root"
    LAST_FAILED_URL="${FRONTEND_URL}"
    LAST_FAILED_HTTP_STATUS="${frontend_status}"
    LAST_FAILED_REASON="Expected frontend HTTP 200."
    rm -f "${frontend_body}"
    fail_with_diagnostics
fi
append_summary "frontend_root=HTTP_${frontend_status}"
rm -f "${frontend_body}"

check_json_contains granite_model_info "${BACKEND_URL}/api/granite/model-info" GET '"model'
check_json_contains dashboard_stats "${BACKEND_URL}/api/viz/dashboard-stats" GET '"totalDocuments":[1-9]'
check_json_contains documents_list "${BACKEND_URL}/api/documents" GET '"count":[1-9]'
check_json_contains graphql_metrics "${BACKEND_URL}/api/graphql" POST '"pidCount":[1-9]|"total":[1-9]' '{"query":"query MorningReadiness { systemMetrics { pidCount localDb { total } } recentDocuments(days: 7) { pid title } }"}'

append_summary "final_readiness_result=READY"

echo "Local readiness checks passed."