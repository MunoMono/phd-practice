#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${REPO_ROOT}/.runtime/qwen"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
MODEL="${TURIN_MODEL:-qwen3:8b-q4_K_M}"
WAIT_SECONDS="${QWEN_WAIT_SECONDS:-60}"

mkdir -p "${RUNTIME_DIR}"

ready() {
    curl --max-time 3 -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1
}

model_installed() {
    curl --max-time 5 -fsS "${OLLAMA_URL}/api/tags" | grep -Fq '"name":"'"${MODEL}"'"'
}

if ! ready; then
    if ! command -v ollama >/dev/null 2>&1; then
        printf 'Ollama is not installed. Install it from https://ollama.com/download, then run this script again.\n' >&2
        exit 1
    fi
    if [[ "$(uname -s)" == "Darwin" && -d "/Applications/Ollama.app" ]]; then
        open -a Ollama
    else
        nohup ollama serve >"${RUNTIME_DIR}/ollama.log" 2>&1 &
        printf '%s\n' "$!" >"${RUNTIME_DIR}/ollama.pid"
    fi
fi

for ((elapsed = 0; elapsed < WAIT_SECONDS; elapsed += 1)); do
    ready && break
    sleep 1
done

if ! ready; then
    printf 'Ollama did not become ready at %s within %s seconds.\n' "${OLLAMA_URL}" "${WAIT_SECONDS}" >&2
    exit 1
fi

if ! model_installed; then
    printf 'Downloading %s. This only happens once.\n' "${MODEL}"
    ollama pull "${MODEL}"
fi

curl --max-time 120 -fsS "${OLLAMA_URL}/api/generate" \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"${MODEL}\",\"prompt\":\"\",\"stream\":false,\"keep_alive\":\"24h\"}" \
    >/dev/null

printf 'Qwen is ready.\nModel: %s\nOllama: %s\nTest: ollama run %q\n' "${MODEL}" "${OLLAMA_URL}" "${MODEL}"