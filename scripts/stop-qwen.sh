#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${REPO_ROOT}/.runtime/qwen"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
MODEL="${TURIN_MODEL:-qwen3:8b-q4_K_M}"

if curl --max-time 3 -fsS "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
    if command -v ollama >/dev/null 2>&1; then
        ollama stop "${MODEL}" >/dev/null 2>&1 || true
    else
        curl --max-time 10 -fsS "${OLLAMA_URL}/api/generate" \
            -H 'Content-Type: application/json' \
            -d "{\"model\":\"${MODEL}\",\"keep_alive\":0}" \
            >/dev/null || true
    fi
    printf 'Unloaded %s from Ollama.\n' "${MODEL}"
else
    printf 'Ollama is not running at %s.\n' "${OLLAMA_URL}"
fi

if [[ "${QWEN_STOP_OLLAMA:-0}" == "1" && -f "${RUNTIME_DIR}/ollama.pid" ]]; then
    pid="$(cat "${RUNTIME_DIR}/ollama.pid")"
    if kill -0 "${pid}" 2>/dev/null; then
        kill "${pid}"
        printf 'Stopped the Ollama server started by this script.\n'
    fi
    rm -f "${RUNTIME_DIR}/ollama.pid"
fi