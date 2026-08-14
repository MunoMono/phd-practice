#!/bin/bash

git_detect_deploy_state() {
    local allow_dirty_used="${1:-false}"

    if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
        echo "ERROR: Deployment must be run from inside the git workspace." >&2
        return 1
    fi

    GIT_DEPLOY_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
    GIT_DEPLOY_COMMIT="$(git rev-parse HEAD)"
    GIT_DEPLOY_ALLOW_DIRTY_USED="${allow_dirty_used}"

    if [[ -n "$(git status --porcelain --untracked-files=normal)" ]]; then
        GIT_DEPLOY_TREE_DIRTY="true"
    else
        GIT_DEPLOY_TREE_DIRTY="false"
    fi
}

git_require_clean_worktree() {
    local allow_dirty="${1:-false}"

    git_detect_deploy_state "${allow_dirty}"

    if [[ "${GIT_DEPLOY_TREE_DIRTY}" == "true" && "${allow_dirty}" != "true" ]]; then
        echo "ERROR: Deployment blocked because the git worktree is dirty." >&2
        echo "Re-run with --allow-dirty only for an emergency deploy." >&2
        return 1
    fi
}

deployment_marker_contents() {
    local deploy_script="$1"
    local deployed_at_utc

    deployed_at_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

    cat <<EOF
branch=${GIT_DEPLOY_BRANCH}
git_commit=${GIT_DEPLOY_COMMIT}
tree_dirty=${GIT_DEPLOY_TREE_DIRTY}
allow_dirty_used=${GIT_DEPLOY_ALLOW_DIRTY_USED}
deployed_at_utc=${deployed_at_utc}
deploy_script=${deploy_script}
EOF
}