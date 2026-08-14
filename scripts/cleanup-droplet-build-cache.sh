#!/bin/bash

set -euo pipefail

DROPLET_HOST="${DROPLET_HOST:-104.248.170.26}"
DROPLET_USER="${DROPLET_USER:-root}"
REMOTE_NPM_CACHE_DIR="${REMOTE_NPM_CACHE_DIR:-/root/.npm/_cacache}"
DRY_RUN=false
SKIP_BUILDER_PRUNE=false
SKIP_IMAGE_PRUNE=false
SKIP_NPM_CACHE=false

usage() {
    cat <<'EOF'
Usage: ./scripts/cleanup-droplet-build-cache.sh [options]

Safely reclaims droplet disk space used by Docker build cache, unused images,
and the npm cache without touching running containers or volumes.

Options:
  --host <hostname>          Override the droplet host
  --user <username>          Override the SSH user
  --npm-cache-dir <path>     Override the remote npm cache path
  --skip-builder-prune       Leave Docker builder cache untouched
  --skip-image-prune         Leave unused Docker images untouched
  --skip-npm-cache           Leave the remote npm cache untouched
  --dry-run                  Print the remote commands without executing them
  --help                     Show this message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            DROPLET_HOST="$2"
            shift 2
            ;;
        --user)
            DROPLET_USER="$2"
            shift 2
            ;;
        --npm-cache-dir)
            REMOTE_NPM_CACHE_DIR="$2"
            shift 2
            ;;
        --skip-builder-prune)
            SKIP_BUILDER_PRUNE=true
            shift
            ;;
        --skip-image-prune)
            SKIP_IMAGE_PRUNE=true
            shift
            ;;
        --skip-npm-cache)
            SKIP_NPM_CACHE=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
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

REMOTE_TARGET="${DROPLET_USER}@${DROPLET_HOST}"

echo "Droplet cleanup target: ${REMOTE_TARGET}"
echo "Builder prune: $([[ "${SKIP_BUILDER_PRUNE}" == "true" ]] && echo skipped || echo enabled)"
echo "Image prune:   $([[ "${SKIP_IMAGE_PRUNE}" == "true" ]] && echo skipped || echo enabled)"
echo "npm cache:     $([[ "${SKIP_NPM_CACHE}" == "true" ]] && echo skipped || echo enabled)"

if [[ "${DRY_RUN}" == "true" ]]; then
    cat <<EOF
ssh ${REMOTE_TARGET} env \
  REMOTE_NPM_CACHE_DIR='${REMOTE_NPM_CACHE_DIR}' \
  SKIP_BUILDER_PRUNE='${SKIP_BUILDER_PRUNE}' \
  SKIP_IMAGE_PRUNE='${SKIP_IMAGE_PRUNE}' \
  SKIP_NPM_CACHE='${SKIP_NPM_CACHE}' \
  'bash -s' <<'ENDSSH'
...remote cleanup script omitted in dry-run output...
ENDSSH
EOF
    exit 0
fi

ssh "${REMOTE_TARGET}" \
    env \
    REMOTE_NPM_CACHE_DIR="${REMOTE_NPM_CACHE_DIR}" \
    SKIP_BUILDER_PRUNE="${SKIP_BUILDER_PRUNE}" \
    SKIP_IMAGE_PRUNE="${SKIP_IMAGE_PRUNE}" \
    SKIP_NPM_CACHE="${SKIP_NPM_CACHE}" \
    'bash -s' <<'ENDSSH'
set -euo pipefail

echo "== Disk usage before cleanup =="
df -h /
echo
docker system df || true
echo

if [[ "${SKIP_BUILDER_PRUNE}" != "true" ]]; then
    echo "== Pruning Docker builder cache =="
    docker builder prune -af
    echo
fi

if [[ "${SKIP_IMAGE_PRUNE}" != "true" ]]; then
    echo "== Pruning unused Docker images =="
    docker image prune -af
    echo
fi

if [[ "${SKIP_NPM_CACHE}" != "true" ]]; then
    echo "== Clearing npm cache at ${REMOTE_NPM_CACHE_DIR} =="
    rm -rf "${REMOTE_NPM_CACHE_DIR}"
    echo
fi

echo "== Disk usage after cleanup =="
df -h /
echo
docker system df || true
ENDSSH

echo "Cleanup complete. Running containers and volumes were not pruned."