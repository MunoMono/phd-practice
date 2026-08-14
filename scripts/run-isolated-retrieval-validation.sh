#!/bin/bash

set -euo pipefail

TARGET_DATABASE="testamentary_traces_retrieval_validation"
QUERY=""
TOP_K="5"
EXPANSION=""
CORPUS_VERSION=""

usage() {
    echo "Usage: scripts/run-isolated-retrieval-validation.sh --query <text> [--expansion <term>] [--corpus-version <version>] [--database <name>] [--top-k 1-50]"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --database)
            TARGET_DATABASE="${2:-}"
            shift 2
            ;;
        --query)
            QUERY="${2:-}"
            shift 2
            ;;
        --top-k)
            TOP_K="${2:-}"
            shift 2
            ;;
        --expansion)
            EXPANSION="${2:-}"
            shift 2
            ;;
        --corpus-version)
            CORPUS_VERSION="${2:-}"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown option: $1" >&2
            exit 2
            ;;
    esac
done

if [[ ! "$TARGET_DATABASE" =~ ^testamentary_traces_[a-z0-9_]*retrieval_validation$ ]]; then
    echo "ERROR: retrieval runner accepts only isolated retrieval-validation databases" >&2
    exit 2
fi
if [[ -z "$QUERY" ]]; then
    echo "ERROR: --query is required" >&2
    exit 2
fi
if [[ ! "$TOP_K" =~ ^([1-9]|[1-4][0-9]|50)$ ]]; then
    echo "ERROR: --top-k must be between 1 and 50" >&2
    exit 2
fi

docker compose run --rm --no-deps --entrypoint python \
    -e "POSTGRES_DB=$TARGET_DATABASE" \
    -e "RETRIEVAL_QUERY=$QUERY" \
    -e "RETRIEVAL_TOP_K=$TOP_K" \
    -e "RETRIEVAL_EXPANSION=$EXPANSION" \
    -e "RETRIEVAL_CORPUS_VERSION=$CORPUS_VERSION" \
    backend -c '
import json
import os
from app.core.database import LocalSessionLocal
from app.services.retrieval_validation_service import QueryExpansion, RetrievalValidationRequest, RetrievalValidationService

expansion = os.environ.get("RETRIEVAL_EXPANSION", "").strip()
request = RetrievalValidationRequest(
    query=os.environ["RETRIEVAL_QUERY"],
    top_k=int(os.environ["RETRIEVAL_TOP_K"]),
    corpus_version=os.environ.get("RETRIEVAL_CORPUS_VERSION") or None,
    expansions=[QueryExpansion(value=expansion, source="researcher_supplied")] if expansion else [],
)
database = LocalSessionLocal()
try:
    service = RetrievalValidationService()
    retrieval = service.retrieve(database, request)
    print(json.dumps(service.persist_validation_run(database, request, retrieval), indent=2))
finally:
    database.close()
'