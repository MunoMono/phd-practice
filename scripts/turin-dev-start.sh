#!/usr/bin/env bash

# Start the native Mac development servers and perform read-only Turin checks.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${REPO_ROOT}/.runtime/turin-dev"
LOG_DIR="${REPO_ROOT}/logs/turin-dev"
BACKEND_URL="${TURIN_BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${TURIN_FRONTEND_URL:-http://127.0.0.1:3000}"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
MODEL="${TURIN_MODEL:-qwen3:8b-q4_K_M}"
EXPECTED_CORPUS="corpus_turin_archive_first_cc11e8678168"
PRODUCTION_HOST="${TURIN_PRODUCTION_HOST:-104.248.170.26}"
PRODUCTION_URL="${TURIN_PRODUCTION_URL:-https://innovationdesign.io}"
WAIT_SECONDS="${TURIN_DEV_WAIT_SECONDS:-60}"

mkdir -p "${RUNTIME_DIR}" "${LOG_DIR}"
cd "${REPO_ROOT}"

declare -a FAILURES=()
PARITY_FAILED=false
OLLAMA_READY=false
MODEL_READY=false
DATABASE_READY=false

section() { printf '\n%s\n' "$1"; }
status() { printf '  %-22s %s\n' "$1" "$2"; }
fail() { FAILURES+=("$1"); }

wait_for_url() {
    local url="$1"
    local expected_status="${2:-200}"
    local elapsed=0 status
    while (( elapsed < WAIT_SECONDS )); do
        status="$(curl --max-time 3 -sS -o /dev/null -w '%{http_code}' "${url}" 2>/dev/null || true)"
        [[ "${status}" == "${expected_status}" ]] && return 0
        sleep 1
        ((elapsed += 1))
    done
    return 1
}

pid_is_running() {
    local pid_file="$1" pid
    [[ -f "${pid_file}" ]] || return 1
    pid="$(cat "${pid_file}")"
    kill -0 "${pid}" 2>/dev/null
}

clear_stale_pid() {
    local pid_file="$1"
    [[ -f "${pid_file}" ]] && ! pid_is_running "${pid_file}" && rm -f "${pid_file}"
}

listener_exists() {
    local port="$1"
    lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t >/dev/null 2>&1
}

find_python() {
    if [[ -x "${REPO_ROOT}/backend/venv/bin/python" ]]; then
        printf '%s\n' "${REPO_ROOT}/backend/venv/bin/python"
    elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
        printf '%s\n' "${REPO_ROOT}/.venv/bin/python"
    else
        command -v python3
    fi
}

start_ollama() {
    if curl --max-time 3 -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
        return 0
    fi
    if ! command -v ollama >/dev/null 2>&1; then
        return 1
    fi
    if [[ "$(uname -s)" == "Darwin" ]] && [[ -d "/Applications/Ollama.app" ]]; then
        open -a Ollama >/dev/null 2>&1 || true
    else
        nohup ollama serve >"${LOG_DIR}/ollama.log" 2>&1 &
        echo "$!" >"${RUNTIME_DIR}/ollama.pid"
    fi
    local elapsed=0
    while (( elapsed < WAIT_SECONDS )); do
        curl --max-time 3 -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1 && return 0
        sleep 1
        ((elapsed += 1))
    done
    return 1
}

model_is_installed() {
    curl --max-time 5 -fsS "${OLLAMA_URL}/api/tags" | grep -Fq '"name":"'"${MODEL}"'"'
}

local_runtime_config() {
    local key="$1" default_value="$2" value=""
    if [[ -f "${REPO_ROOT}/backend/.env" ]]; then
        value="$(sed -nE "s/^${key}=([^#[:space:]]*).*/\\1/p" "${REPO_ROOT}/backend/.env" | tail -n 1)"
    fi
    printf '%s\n' "${value:-${default_value}}"
}

start_backend() {
    local pid_file="${RUNTIME_DIR}/backend.pid" python_bin
    clear_stale_pid "${pid_file}"
    if listener_exists 8000; then
        return 0
    fi
    python_bin="$(find_python)"
    if ! "${python_bin}" -c 'import uvicorn' >/dev/null 2>&1; then
        return 1
    fi
    (
        cd "${REPO_ROOT}/backend"
        export TURIN_INFERENCE_PROVIDER=remote_ollama
        export TURIN_MODEL="${MODEL}"
        export OLLAMA_BASE_URL="${OLLAMA_URL}"
        export GRANITE_AUTO_LOAD=false
        nohup "${python_bin}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload \
            >"${LOG_DIR}/backend.log" 2>&1 &
        echo "$!" >"${pid_file}"
    )
}

start_frontend() {
    local pid_file="${RUNTIME_DIR}/frontend.pid"
    clear_stale_pid "${pid_file}"
    if listener_exists 3000; then
        return 0
    fi
    [[ -d "${REPO_ROOT}/frontend/node_modules" ]] || return 1
    (
        cd "${REPO_ROOT}/frontend"
        nohup npm run dev -- --host 127.0.0.1 >"${LOG_DIR}/frontend.log" 2>&1 &
        echo "$!" >"${pid_file}"
    )
}

runtime_files() {
    printf '%s\n' \
        backend/app/api/routes/analysis.py \
        backend/app/api/routes/retrieval.py \
        backend/app/api/routes/runtime.py \
        backend/app/core/config.py \
        backend/app/main.py \
        backend/app/services/inference_service.py \
        backend/app/services/turin_archive_first_retrieval_service.py \
        backend/app/services/turin_retrieval_v316_project_identity_surface.py \
        backend/requirements.txt backend/Dockerfile backend/docker-entrypoint.sh \
        frontend/src/api/provenance.js \
        frontend/src/components/evidence/EvidenceSourceCard.jsx \
        frontend/src/components/visualizations/EvidenceGraph.jsx \
        frontend/src/pages/EvidenceTracer/EvidenceTracer.jsx \
        frontend/package.json frontend/package-lock.json frontend/vite.config.js \
        frontend/Dockerfile frontend/nginx.prod.conf docker-compose.prod.yml
}

write_local_hashes() {
    local output="$1" path
    : >"${output}"
    while IFS= read -r path; do
        [[ -f "${path}" ]] && shasum -a 256 "${path}" | awk '{print $1 "  " $2}' >>"${output}"
    done < <(runtime_files | sort -u)
    sort -o "${output}" "${output}"
}

write_production_hashes() {
    local output="$1"
    ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${PRODUCTION_HOST}" \
        "cd /root/phd-practice && printf '%s\\n' backend/app/api/routes/analysis.py backend/app/api/routes/retrieval.py backend/app/api/routes/runtime.py backend/app/core/config.py backend/app/main.py backend/app/services/inference_service.py backend/app/services/turin_archive_first_retrieval_service.py backend/app/services/turin_retrieval_v316_project_identity_surface.py backend/requirements.txt backend/Dockerfile backend/docker-entrypoint.sh frontend/src/api/provenance.js frontend/src/components/evidence/EvidenceSourceCard.jsx frontend/src/components/visualizations/EvidenceGraph.jsx frontend/src/pages/EvidenceTracer/EvidenceTracer.jsx frontend/package.json frontend/package-lock.json frontend/vite.config.js frontend/Dockerfile frontend/nginx.prod.conf docker-compose.prod.yml | while IFS= read -r path; do test -f \"\$path\" && shasum -a 256 \"\$path\"; done" \
        >"${output}"
    sed -E 's@  \./@  @' "${output}" | sort >"${output}.normalized"
    mv "${output}.normalized" "${output}"
}

compare_hashes() {
    local local_hashes="$1" production_hashes="$2" path local_hash production_hash
    local combined="${RUNTIME_DIR}/parity-paths.txt"
    { awk '{print $2}' "${local_hashes}"; awk '{print $2}' "${production_hashes}"; } | sort -u >"${combined}"
    while IFS= read -r path; do
        local_hash="$(awk -v path="${path}" '$2 == path { print $1 }' "${local_hashes}")"
        production_hash="$(awk -v path="${path}" '$2 == path { print $1 }' "${production_hashes}")"
        if [[ -z "${local_hash}" ]]; then
            printf '  %-58s %-16s production=%s\n' "${path}" "PRODUCTION_ONLY" "${production_hash}"
            PARITY_FAILED=true
        elif [[ -z "${production_hash}" ]]; then
            printf '  %-58s %-16s local=%s\n' "${path}" "LOCAL_ONLY" "${local_hash}"
            PARITY_FAILED=true
        elif [[ "${local_hash}" == "${production_hash}" ]]; then
            printf '  %-58s %-16s local=%s production=%s\n' "${path}" "MATCH" "${local_hash}" "${production_hash}"
        else
            printf '  %-58s %-16s local=%s production=%s\n' "${path}" "MISMATCH" "${local_hash}" "${production_hash}"
            PARITY_FAILED=true
        fi
    done <"${combined}"
}

echo '============================================================'
echo 'TURIN DEVELOPMENT PREFLIGHT'
echo '============================================================'

section 'Local services'
if start_ollama; then
    status 'Ollama' 'READY'
    OLLAMA_READY=true
else
    status 'Ollama' 'NOT READY'
    fail "Ollama is unavailable. Start Ollama, then rerun: open -a Ollama"
fi
if model_is_installed; then
    status 'Qwen3 8B Q4_K_M' 'READY'
    MODEL_READY=true
else
    status 'Qwen3 8B Q4_K_M' 'NOT READY'
    fail "Model ${MODEL} is missing. Remediation: ollama pull ${MODEL}"
fi
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h "${POSTGRES_HOST:-127.0.0.1}" -p "${POSTGRES_PORT:-5432}" >/dev/null 2>&1; then
    status 'Database' 'READY'
    DATABASE_READY=true
else
    status 'Database' 'NOT READY'
    fail 'Local PostgreSQL is not reachable. The native backend requires the existing host database; no database was created, reset, or migrated.'
fi

if listener_exists 8000 && wait_for_url "${BACKEND_URL}/health"; then
    status 'Backend' 'READY'
elif [[ "${OLLAMA_READY}" == true && "${MODEL_READY}" == true && "${DATABASE_READY}" == true ]] && start_backend && wait_for_url "${BACKEND_URL}/health"; then
    status 'Backend' 'READY'
else
    status 'Backend' 'NOT READY'
    if [[ "${OLLAMA_READY}" == true && "${MODEL_READY}" == true && "${DATABASE_READY}" == true ]]; then
        fail "Backend did not become healthy. See ${LOG_DIR}/backend.log"
    else
        fail 'Backend was not started because an Ollama, model, or database prerequisite is not ready.'
    fi
fi
if listener_exists 3000 && wait_for_url "${FRONTEND_URL}/"; then
    status 'Frontend' 'READY'
elif start_frontend && wait_for_url "${FRONTEND_URL}/"; then
    status 'Frontend' 'READY'
else
    status 'Frontend' 'NOT READY'
    fail "Frontend did not become reachable. See ${LOG_DIR}/frontend.log"
fi

section 'Local configuration'
local_corpus="$(local_runtime_config TURIN_ARCHIVE_FIRST_CORPUS_VERSION "${EXPECTED_CORPUS}")"
local_model="$(local_runtime_config TURIN_MODEL "${MODEL}")"
status 'Corpus' "${local_corpus}"
status 'Model' "${local_model}"
status 'Granite fallback' 'NONE (TURIN_INFERENCE_PROVIDER=remote_ollama)'
[[ "${local_corpus}" == "${EXPECTED_CORPUS}" ]] || fail "Local archive-first corpus is ${local_corpus}, expected ${EXPECTED_CORPUS}."
[[ "${local_model}" == "${MODEL}" ]] || fail "Local model is ${local_model}, expected ${MODEL}."
if wait_for_url "${BACKEND_URL}/health"; then
    runtime_json="$(curl --max-time 5 -fsS "${BACKEND_URL}/api/runtime/health" 2>/dev/null || true)"
    if printf '%s' "${runtime_json}" | grep -Fq '"runtime":"remote_ollama"' && printf '%s' "${runtime_json}" | grep -Fq '"model":"'"${MODEL}"'"'; then
        status 'Qwen route' 'READY (remote_ollama)'
    else
        status 'Qwen route' 'NOT READY'
        fail 'Backend runtime is not the expected remote_ollama Qwen route; no inference was attempted.'
    fi
fi

section 'Production'
if curl --max-time 10 -fsS -o /dev/null "${PRODUCTION_URL}/"; then
    status 'Frontend' 'READY'
else
    status 'Frontend' 'NOT READY'
    fail 'Production frontend is unreachable.'
fi
production_health="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${PRODUCTION_HOST}" "curl --max-time 10 -fsS http://127.0.0.1:8000/health" 2>/dev/null || true)"
if printf '%s' "${production_health}" | grep -Fq '"status":"healthy"'; then
    status 'Backend' 'READY'
else
    status 'Backend' 'NOT READY'
    fail 'Production backend health check failed.'
fi
production_runtime="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${PRODUCTION_HOST}" "curl --max-time 10 -fsS http://127.0.0.1:8000/api/runtime/health" 2>/dev/null || true)"
if printf '%s' "${production_runtime}" | grep -Fq '"runtime":"remote_ollama"' && printf '%s' "${production_runtime}" | grep -Fq '"model":"'"${MODEL}"'"'; then
    status 'Qwen runtime' 'READY (remote_ollama)'
else
    status 'Qwen runtime' 'NOT READY'
    fail 'Production Qwen runtime is not the expected remote_ollama model route.'
fi

section 'Configuration parity (non-secret)'
production_corpus_configured="$(ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${PRODUCTION_HOST}" "grep -Fq '${EXPECTED_CORPUS}' /root/phd-practice/backend/app/core/config.py" 2>/dev/null && echo yes || true)"
if printf '%s' "${production_runtime}" | grep -Fq '"runtime":"remote_ollama"' && printf '%s' "${production_runtime}" | grep -Fq '"model":"'"${MODEL}"'"' && [[ "${production_corpus_configured}" == yes ]]; then
    status 'Runtime configuration' 'PASS'
else
    status 'Runtime configuration' 'FAIL'
    fail 'Local and production non-secret Turin runtime configuration do not match the expected remote_ollama/Qwen/successor-corpus values.'
fi

section 'Parity (read-only SHA-256)'
local_hashes="${RUNTIME_DIR}/local-runtime-sha256.txt"
production_hashes="${RUNTIME_DIR}/production-runtime-sha256.txt"
if write_local_hashes "${local_hashes}" && write_production_hashes "${production_hashes}"; then
    compare_hashes "${local_hashes}" "${production_hashes}"
    if [[ "${PARITY_FAILED}" == false ]]; then
        status 'Runtime files' 'PASS'
    else
        status 'Runtime files' 'FAIL'
        fail 'Production parity failed; one or more governed runtime files differ.'
    fi
else
    status 'Runtime files' 'FAIL'
    fail 'Could not complete the read-only production SHA-256 parity check.'
fi

echo '============================================================'
if [[ ${#FAILURES[@]} -eq 0 ]]; then
    echo 'TURIN DEVELOPMENT ENVIRONMENT: READY'
    echo '============================================================'
    exit 0
fi
echo 'TURIN DEVELOPMENT ENVIRONMENT: NOT READY'
printf 'Reason:\n'
for reason in "${FAILURES[@]}"; do
    printf '  - %s\n' "${reason}"
done
echo '============================================================'
exit 1